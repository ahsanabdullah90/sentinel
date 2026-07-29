"""Scraping Strategy Module

Implements the Strategy pattern for scraping external portals.
Utilizes pluggable adapters and local-only Ollama extraction.
"""

import asyncio
import json
import logging
import os
import re
import secrets
import tempfile
import uuid
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from sidecars.hunter.src_py.rate_limiter import TokenBucketRateLimiter
from sidecars.hunter.src_py.utils.search_detector import detect_search_input
from sidecars.hunter.src_py.adapters import resolve_adapter
from sidecars.hunter.src_py.models import PortalConfig, RFPOpportunity, OllamaExtraction
from sidecars.hunter.src_py.progress_reporter import ProgressReporter
from sidecars.hunter.src_py.ollama_utils import (
    extract_json,
    fetch_ollama_tags_sync,
    fetch_ollama_generate_sync,
)

logger = logging.getLogger("hunter.strategies")


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


class ScrapingStrategy:
    """Base class for all scraping strategies."""

    async def execute(
        self,
        config: PortalConfig,
        rate_limiter: TokenBucketRateLimiter,
        reporter: ProgressReporter,
    ) -> List[RFPOpportunity]:
        raise NotImplementedError()


class PublicApiStrategy(ScrapingStrategy):
    """Fetch opportunities from a publicly accessible REST API."""

    async def execute(
        self,
        config: PortalConfig,
        rate_limiter: TokenBucketRateLimiter,
        reporter: ProgressReporter,
    ) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Initializing API strategy sequence...")

        generic_fallback = GenericSearchStrategy()
        return await generic_fallback.execute(config, rate_limiter, reporter)


class StaticHtmlStrategy(ScrapingStrategy):
    """Download and parse a static HTML page."""

    async def execute(
        self,
        config: PortalConfig,
        rate_limiter: TokenBucketRateLimiter,
        reporter: ProgressReporter,
    ) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Initiating static HTML analysis sequence...")

        try:
            from bs4 import BeautifulSoup
            import urllib.request

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            req = urllib.request.Request(config.base_url, headers=headers)

            def run_get():
                try:
                    with urllib.request.urlopen(req, timeout=15.0) as response:
                        return response.read()
                except Exception as ex:
                    logger.debug(f"urllib static GET failed: {ex}")
                    return b""

            html_bytes = await asyncio.get_running_loop().run_in_executor(None, run_get)
            if not html_bytes:
                await reporter.report_progress(
                    "Static HTML fetch returned empty. Falling back to dynamic Playwright strategy."
                )
                generic_fallback = GenericSearchStrategy()
                return await generic_fallback.execute(config, rate_limiter, reporter)

            soup = BeautifulSoup(html_bytes, "html.parser")

            opportunities = []
            keywords = (
                [k.strip().lower() for k in config.keywords.split(",") if k.strip()]
                if config.keywords
                else ["rfp", "proposal", "bid", "tender", "opportunity"]
            )

            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)

                matches = any(kw in text.lower() or kw in href.lower() for kw in keywords)

                if matches and len(text) > 5:
                    full_url = urljoin(config.base_url, href)
                    opp = RFPOpportunity(
                        id=f"static-{secrets.token_hex(4)}",
                        portal_id=config.id,
                        title=text[:150],
                        url=full_url,
                        status="discovered",
                        description=f"Found via static HTML parsing of {config.base_url}",
                    )
                    opportunities.append(opp)
                    await reporter.report_opportunity(opp)

            if opportunities:
                await reporter.report_progress(
                    f"Discovered {len(opportunities)} opportunities via fast static HTML scraper."
                )
                return opportunities

        except Exception as e:
            logger.error(f"StaticHtmlStrategy execution failed: {e}")

        await reporter.report_progress(
            "No opportunities found via static HTML. Triggering dynamic Playwright fallback..."
        )
        generic_fallback = GenericSearchStrategy()
        return await generic_fallback.execute(config, rate_limiter, reporter)


class PlaywrightStrategy(ScrapingStrategy):
    """Render a JS-heavy page with headless Chromium."""

    async def execute(
        self,
        config: PortalConfig,
        rate_limiter: TokenBucketRateLimiter,
        reporter: ProgressReporter,
    ) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Initiating Playwright scraping sequence...")

        generic_fallback = GenericSearchStrategy()
        return await generic_fallback.execute(config, rate_limiter, reporter)


class GenericSearchStrategy(ScrapingStrategy):
    """AI-powered generic search: detect the search bar using heuristics, enter
    keywords, and extract opportunities from the results page using local Ollama.
    """

    async def execute(
        self,
        config: PortalConfig,
        rate_limiter: TokenBucketRateLimiter,
        reporter: ProgressReporter,
    ) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        portal_id = config.id
        base_url = config.base_url
        keywords = config.keywords or "RFP"

        await reporter.report_progress(
            f"Starting generic search strategy for {config.name}..."
        )

        search_selector = ""
        if config.selector_config:
            try:
                selectors = json.loads(config.selector_config)
                search_selector = selectors.get("searchSelector", "")
            except Exception:
                logger.warning("Failed to parse selector config, using heuristics")

        opportunities: List[RFPOpportunity] = []

        keyword_list = [k.strip() for k in re.split(r"[,;\n]+", keywords) if k.strip()]
        if not keyword_list:
            keyword_list.append("RFP")

        await reporter.report_progress(
            f"Identified {len(keyword_list)} search keyword(s) to process: {', '.join(keyword_list)}"
        )

        adapter = resolve_adapter(base_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            try:
                for keyword in keyword_list:
                    await reporter.report_progress(
                        f'Starting hunt for keyword: "{keyword}"'
                    )

                    page = await browser.new_page()
                    try:
                        target_url = base_url
                        is_direct_query = adapter.supports_direct_query()

                        if is_direct_query:
                            target_url = adapter.build_search_url(base_url, keyword)
                            await reporter.report_progress(
                                f"[{keyword}] Routing directly to: {target_url}"
                            )

                        await page.goto(
                            target_url, wait_until="domcontentloaded", timeout=30000
                        )
                        await asyncio.sleep(2)

                        if not is_direct_query:
                            if not search_selector:
                                try:
                                    search_selector = await detect_search_input(page)
                                except Exception as e:
                                    logger.warning(
                                        f"[{keyword}] Failed to auto-detect search input: {e}"
                                    )
                                    search_selector = None

                            if search_selector:
                                await reporter.report_progress(
                                    f"[{keyword}] Entering query into: {search_selector}..."
                                )
                                try:
                                    await page.fill(search_selector, keyword)
                                    clicked = await page.evaluate(
                                        """(sel) => {
                                        const input = document.querySelector(sel);
                                        if (!input) return false;
                                        const form = input.closest('form');
                                        if (form) { form.submit(); return true; }
                                        const parent = input.parentElement;
                                        if (parent) {
                                            const buttons = Array.from(parent.querySelectorAll('button, input[type="button"], input[type="submit"], #searchButton, .search, #search'));
                                            for (const btn of buttons) {
                                                if (btn !== input) { btn.click(); return true; }
                                            }
                                        }
                                        const globalBtn = document.querySelector('#searchButton, .btn-search, button[type="submit"], .search-btn');
                                        if (globalBtn) { globalBtn.click(); return true; }
                                        return false;
                                    }""",
                                        search_selector,
                                    )

                                    if not clicked:
                                        await page.press(search_selector, "Enter")
                                    await page.wait_for_load_state(
                                        "networkidle", timeout=10000
                                    )
                                except Exception as fill_err:
                                    logger.warning(
                                        f"[{keyword}] Failed to interact with search bar: {str(fill_err)}"
                                    )
                            else:
                                await reporter.report_progress(
                                    f"[{keyword}] No search bar detected, scraping current page..."
                                )

                        if not search_selector:
                            try:
                                search_selector = await detect_search_input(page)
                            except Exception as e:
                                logger.warning(
                                    f"[{keyword}] Failed to auto-detect search input on results page: {e}"
                                )
                                search_selector = None

                        if search_selector:
                            await reporter.report_portal_detected(
                                search_selector, base_url
                            )
                        else:
                            logger.info(
                                f"[{keyword}] No search selector found; skipping portal detection event."
                            )

                        cleaned_html = await page.evaluate(
                            r"""() => {
                            if (!document.body) return "";
                            const clone = document.body.cloneNode(true);
                            const elementsToRemove = clone.querySelectorAll(
                               'script, style, noscript, svg, img, iframe, header, footer, nav, link, meta'
                            );
                            elementsToRemove.forEach((el) => el.remove());
                            const elements = clone.querySelectorAll('*');
                            for (const el of elements) {
                              const attrs = Array.from(el.attributes);
                              for (const attr of attrs) {
                                if (attr.name !== 'href') {
                                  el.removeAttribute(attr.name);
                                }
                              }
                            }
                            let html = clone.innerHTML;
                            html = html.replace(/\s+/g, ' ');
                            return html.trim().substring(0, 50000);
                        }"""
                        )

                        plain_text = await page.evaluate(
                            "() => document.body.innerText"
                        )

                        await reporter.report_progress(
                            f"[{keyword}] Cleaned HTML size: {len(cleaned_html)} chars, "
                            f"plain text size: {len(plain_text)} chars. "
                            f"Contained keyword: {keyword.lower() in cleaned_html.lower()}."
                        )

                        max_retries = 3
                        new_opps = []
                        for attempt in range(1, max_retries + 1):
                            try:
                                new_opps = await self._extract_with_ollama(
                                    cleaned_html,
                                    keyword,
                                    portal_id,
                                    base_url,
                                    page.url,
                                    config,
                                    reporter,
                                    plain_text=plain_text,
                                )
                                break
                            except Exception as e:
                                logger.error(
                                    f"Ollama extraction failed (attempt {attempt}) for keyword {keyword}: {e}"
                                )
                                if attempt == max_retries:
                                    await reporter.report_error(
                                        f"Ollama extraction failed after {max_retries} attempts for keyword {keyword}."
                                    )
                                else:
                                    await asyncio.sleep(2**attempt)
                        opportunities.extend(new_opps)

                        for opp in new_opps:
                            if opp.url and opp.url.startswith("http"):
                                deep_page = await browser.new_page()
                                try:
                                    await reporter.report_progress(
                                        f"Deep crawling opportunity: {opp.title}"
                                    )
                                    await deep_page.goto(
                                        opp.url,
                                        wait_until="domcontentloaded",
                                        timeout=30000,
                                    )

                                    full_desc = await deep_page.evaluate(
                                        r"""() => {
                                        const container = document.querySelector('.job-detail, .description, .content, main, article, #content');
                                        if (container) {
                                            return container.innerText;
                                        }
                                        return document.body.innerText;
                                    }"""
                                    )

                                    if not full_desc or len(full_desc.strip()) < 100:
                                        await reporter.report_progress(
                                            f"Heuristics failed for {opp.title}. Falling back to Ollama extraction."
                                        )
                                        cleaned_deep_html = await deep_page.evaluate(
                                            r"""() => {
                                            if (!document.body) return "";
                                            const clone = document.body.cloneNode(true);
                                            const elementsToRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe, header, footer, nav, link, meta');
                                            elementsToRemove.forEach((el) => el.remove());
                                            let html = clone.innerHTML;
                                            return html.replace(/\s+/g, ' ').trim().substring(0, 50000);
                                        }"""
                                        )

                                        ollama_url = (
                                            config.ollama_url
                                            or os.environ.get(
                                                "OLLAMA_URL",
                                                "http://127.0.0.1:11434",
                                            )
                                        )

                                        target_model = config.ollama_model
                                        if not target_model:
                                            try:
                                                avail = await asyncio.to_thread(
                                                    fetch_ollama_tags_sync,
                                                    ollama_url,
                                                )
                                                preferred = [
                                                    "gemma3",
                                                    "gemma4",
                                                    "gemma",
                                                    "qwen3",
                                                    "qwen2.5-coder",
                                                    "llama3",
                                                ]
                                                for pref in preferred:
                                                    match = next(
                                                        (
                                                            m
                                                            for m in avail
                                                            if pref in m.lower()
                                                        ),
                                                        None,
                                                    )
                                                    if match:
                                                        target_model = match
                                                        break
                                                if not target_model and avail:
                                                    target_model = avail[0]
                                            except Exception:
                                                target_model = "gemma:2b"

                                        prompt = f"Extract ONLY the full job description text from the following HTML. Output nothing but the pure description text.\n\n{cleaned_deep_html[:50000]}"
                                        payload = {
                                            "model": target_model,
                                            "prompt": prompt,
                                            "stream": False,
                                            "options": {"temperature": 0.1},
                                        }
                                        try:
                                            response_text = await asyncio.to_thread(
                                                fetch_ollama_generate_sync,
                                                ollama_url,
                                                payload,
                                            )
                                            if response_text:
                                                full_desc = response_text
                                        except Exception as e:
                                            logger.warning(
                                                f"Ollama deep crawl fallback failed: {e}"
                                            )

                                    opp.description = full_desc.strip()[:50000]
                                    await reporter.report_opportunity_updated(opp)

                                    attachments = await deep_page.evaluate(
                                        r"""() => {
                                        const links = Array.from(document.querySelectorAll('a'));
                                        return links.filter(a => {
                                            const href = a.href.toLowerCase();
                                            return href.endsWith('.pdf') || href.endsWith('.doc') || href.endsWith('.docx');
                                        }).map(a => {
                                            let name = a.innerText.trim();
                                            if (!name) {
                                                const parts = a.href.split('/');
                                                name = parts[parts.length - 1];
                                            }
                                            return { name: name, href: a.href };
                                        });
                                    }"""
                                    )

                                    for att in attachments:
                                        try:
                                            temp_dir = os.path.join(
                                                tempfile.gettempdir(),
                                                "sentinel_attachments",
                                            )
                                            os.makedirs(temp_dir, exist_ok=True)

                                            safe_name = "".join(
                                                [
                                                    c
                                                    for c in att["name"]
                                                    if c.isalpha()
                                                    or c.isdigit()
                                                    or c in (" ", ".", "-", "_")
                                                ]
                                            ).rstrip()
                                            if not safe_name:
                                                safe_name = "attachment"
                                            if not any(
                                                safe_name.lower().endswith(ext)
                                                for ext in [".pdf", ".doc", ".docx"]
                                            ):
                                                safe_name += (
                                                    ".pdf"
                                                    if ".pdf" in att["href"].lower()
                                                    else ".doc"
                                                )

                                            temp_path = os.path.join(
                                                temp_dir,
                                                str(uuid.uuid4()) + "_" + safe_name,
                                            )

                                            resp = await deep_page.context.request.get(
                                                att["href"]
                                            )
                                            body = await resp.body()
                                            with open(temp_path, "wb") as f:
                                                f.write(body)

                                            await reporter.report_attachment_downloaded(
                                                opp.id, safe_name, temp_path
                                            )
                                            await reporter.report_progress(
                                                f"Downloaded attachment: {safe_name}"
                                            )
                                        except Exception as e:
                                            logger.warning(
                                                f"Failed to download attachment {att['href']}: {e}"
                                            )

                                except Exception as e:
                                    logger.warning(
                                        f"Deep crawl failed for {opp.url}: {e}"
                                    )
                                finally:
                                    await deep_page.close()

                    except Exception as kw_err:
                        logger.error(
                            f'Error processing keyword "{keyword}": {str(kw_err)}'
                        )
                        await reporter.report_error(
                            f"Error processing keyword '{keyword}': {str(kw_err)}"
                        )
                        continue
                    finally:
                        await page.close()
            finally:
                await browser.close()

        seen_urls = set()
        unique_opps: List[RFPOpportunity] = []
        for opp in opportunities:
            if opp.url and opp.url not in seen_urls:
                seen_urls.add(opp.url)
                unique_opps.append(opp)

        return unique_opps

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _extract_with_ollama(
        cleaned_html: str,
        keyword: str,
        portal_id: str,
        base_url: str,
        current_url: str,
        config: PortalConfig,
        reporter: ProgressReporter,
        plain_text: str = "",
    ) -> List[RFPOpportunity]:
        """Call local Ollama to extract opportunities from page content."""

        async def _run_extraction(
            content: str, source_label: str
        ) -> List[RFPOpportunity]:
            """Run one extraction pass on *content* (HTML or plain text)."""
            prompt = f"""
Task: Extract job/opportunity listings from the following {source_label}.
Filter opportunities based on the keyword "{keyword}".
Output ONLY a valid JSON array of objects, containing "title", "description", "url", "publishDate", "dueDate", and "agency".
Format matches:
[
  {{
    "title": "Title of the job posting",
    "description": "Description of the job",
    "url": "Link to the job page",
    "publishDate": "Date published, or empty if unknown",
    "dueDate": "Closing date, or empty if unknown",
    "agency": "Hiring company name"
  }}
]
If no matches are found, output an empty array: []

Content:
{content[:50000]}
"""

            opportunities: List[RFPOpportunity] = []
            parsed = None
            success = False

            try:
                payload = {
                    "model": target_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                }

                response_text = await asyncio.to_thread(
                    fetch_ollama_generate_sync, ollama_url, payload
                )

                if response_text:
                    await reporter.report_progress(
                        f"[{keyword}] Ollama responded ({len(response_text)} chars) from {source_label}"
                    )

                    is_refusal = (
                        "sorry" in response_text.lower()
                        or "can't assist" in response_text.lower()
                        or "cannot assist" in response_text.lower()
                        or "don't have the ability" in response_text.lower()
                        or "unable to assist" in response_text.lower()
                    )

                    if not is_refusal:
                        try:
                            parsed_data = json.loads(response_text)
                            parsed = parsed_data
                            success = True
                        except json.JSONDecodeError as decode_err:
                            logger.warning(
                                f"[{keyword}] Ollama response was not valid JSON: {response_text[:200]}, error: {str(decode_err)}"
                            )
                            await reporter.report_progress(
                                f"[{keyword}] Ollama response was not valid JSON: {str(decode_err)}"
                            )
                    else:
                        await reporter.report_progress(
                            f"[{keyword}] Ollama refused to extract from {source_label}"
                        )
                else:
                    logger.warning(f"[{keyword}] Ollama returned empty response")
                    await reporter.report_progress(
                        f"[{keyword}] Ollama returned empty response"
                    )
            except Exception as model_err:
                logger.error(
                    f"[{keyword}] Model extraction error: {str(model_err)}"
                )
                await reporter.report_progress(
                    f"[{keyword}] Ollama model extraction failed: {str(model_err)}"
                )

            if success and parsed:
                items = []
                if isinstance(parsed, list):
                    items = parsed
                elif isinstance(parsed, dict):
                    items = parsed.get("opportunities") or parsed.get("jobs") or []

                if isinstance(items, list):
                    for item in items:
                        try:
                            raw_ext = OllamaExtraction.model_validate(item)

                            full_url = raw_ext.url or current_url
                            if full_url.startswith("/"):
                                parsed_base = urlparse(base_url)
                                full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{full_url}"
                            elif not full_url.startswith("http"):
                                parsed_base = urlparse(base_url)
                                full_url = f"{parsed_base.scheme}://{parsed_base.netloc}/{full_url}"

                            opp = RFPOpportunity(
                                id=secrets.token_hex(8),
                                portalId=portal_id,
                                title=raw_ext.title or "Untitled Opportunity",
                                description=raw_ext.description or "",
                                url=full_url,
                                publishDate=raw_ext.publishDate or "",
                                dueDate=raw_ext.dueDate or "",
                                agency=raw_ext.agency or "Unknown",
                                status="open",
                            )
                            opportunities.append(opp)
                            await reporter.report_opportunity(opp)
                        except Exception as val_err:
                            logger.warning(
                                f"Skipping malformed extraction item: {item}, error: {str(val_err)}"
                            )

            return opportunities

        await reporter.report_progress(
            f"[{keyword}] Initiating local Ollama extraction..."
        )

        ollama_url = config.ollama_url or os.environ.get(
            "OLLAMA_URL", "http://localhost:11434"
        )

        if os.environ.get("RUNNING_IN_DOCKER") == "true":
            parsed_ollama = urlparse(ollama_url)
            if parsed_ollama.hostname in ("localhost", "127.0.0.1", "host.docker.internal"):
                use_resolved = False
                if parsed_ollama.hostname == "host.docker.internal":
                    try:
                        import socket

                        socket.gethostbyname("host.docker.internal")
                        use_resolved = True
                    except Exception:
                        pass

                if not use_resolved:
                    gateway_ip = "172.19.0.1"
                    try:
                        with open("/proc/net/route") as f:
                            for line in f:
                                fields = line.strip().split()
                                if len(fields) >= 3 and fields[1] == "00000000":
                                    val = fields[2]
                                    ip_parts = [
                                        str(int(val[i : i + 2], 16))
                                        for i in range(6, -1, -2)
                                    ]
                                    gateway_ip = ".".join(ip_parts)
                                    break
                    except Exception:
                        pass

                    netloc = (
                        f"{gateway_ip}:{parsed_ollama.port}"
                        if parsed_ollama.port
                        else gateway_ip
                    )
                    ollama_url = parsed_ollama._replace(netloc=netloc).geturl()

        available_models = await asyncio.to_thread(fetch_ollama_tags_sync, ollama_url)

        if not available_models:
            await reporter.report_progress(
                f"[{keyword}] Warning: Ollama server at {ollama_url} has no models installed "
                "or is unreachable. Please pull an LLM model (e.g. gemma or qwen2.5-coder) inside Settings."
            )
            return []

        target_model = config.ollama_model

        if not target_model and config.selector_config:
            try:
                sel_data = json.loads(config.selector_config)
                if sel_data.get("modelName"):
                    target_model = sel_data["modelName"]
            except Exception:
                pass

        if not target_model:
            target_model = os.environ.get("OLLAMA_MODEL")

        if not target_model or target_model not in available_models:
            preferred = ["gemma3", "gemma4", "gemma", "qwen3", "qwen2.5-coder", "llama3"]
            for pref in preferred:
                match = next(
                    (m for m in available_models if pref in m.lower()), None
                )
                if match:
                    target_model = match
                    break

            if not target_model or target_model not in available_models:
                target_model = available_models[0]

        await reporter.report_progress(
            f"[{keyword}] Selected dynamic Ollama model: {target_model}"
        )

        # Try HTML extraction first, then fall back to plain text
        opportunities = await _run_extraction(cleaned_html, "HTML snippet")
        if opportunities:
            return opportunities

        if plain_text:
            await reporter.report_progress(
                f"[{keyword}] HTML extraction returned no results, trying plain text..."
            )
            opportunities = await _run_extraction(plain_text, "plain text")

        return opportunities


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_strategy(option_id: str) -> ScrapingStrategy:
    """Return the ``ScrapingStrategy`` matching *option_id*.

    Args:
        option_id: One of ``public_api``, ``static_html``,
            ``playwright_public``, or ``generic_search``.

    Raises:
        ValueError: If *option_id* is unknown.
    """
    strategies = {
        "public_api": PublicApiStrategy,
        "static_html": StaticHtmlStrategy,
        "playwright_public": PlaywrightStrategy,
        "generic_search": GenericSearchStrategy,
    }
    cls = strategies.get(option_id)
    if cls is None:
        raise ValueError(f"Unknown scraping strategy: {option_id}")
    return cls()
