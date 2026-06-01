"""Scraper Engine Module

Implements the Strategy pattern for scraping external portals.
Utilizes pluggable adapters and local-only Ollama extraction.
"""

import asyncio
import os
import json
import secrets
import logging
import re
from typing import List, Dict, Any, Optional, Callable, Awaitable
from urllib.parse import urlparse
import urllib.request
from playwright.async_api import async_playwright

from sidecars.hunter.src_py.rate_limiter import TokenBucketRateLimiter
from sidecars.hunter.src_py.utils.search_detector import detect_search_input
from sidecars.hunter.src_py.adapters import resolve_adapter
from sidecars.hunter.src_py.models import PortalConfig, RFPOpportunity, OllamaExtraction

logger = logging.getLogger("hunter.scraper_engine")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Progress & Event Reporting
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Handles unified reporting of progress and findings to stdout."""

    def __init__(self, portal_id: str, on_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None):
        self.portal_id = portal_id
        self.on_event = on_event

    async def report_progress(self, message: str) -> None:
        """Report a standard progress string."""
        event_data = {
            "portalId": self.portal_id,
            "message": message
        }
        print(json.dumps({"event": "progress", **event_data}), flush=True)
        if self.on_event:
            await self.on_event("progress", event_data)

    async def report_opportunity(self, opp: RFPOpportunity) -> None:
        """Report a discovered opportunity."""
        event_data = opp.model_dump(by_alias=True)
        print(json.dumps({"event": "opportunity_found", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("opportunity_found", event_data)

    async def report_opportunity_updated(self, opp: RFPOpportunity) -> None:
        """Report an updated opportunity after deep crawling."""
        event_data = opp.model_dump(by_alias=True)
        print(json.dumps({"event": "opportunity_updated", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("opportunity_updated", event_data)

    async def report_attachment_downloaded(self, opp_id: str, file_name: str, file_path: str) -> None:
        """Report a downloaded attachment."""
        event_data = {
            "opportunityId": opp_id,
            "fileName": file_name,
            "filePath": file_path
        }
        print(json.dumps({"event": "attachment_downloaded", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("attachment_downloaded", event_data)

    async def report_portal_detected(self, search_selector: str, base_url: str) -> None:
        """Report successful search input selector detection."""
        event_data = {
            "url": base_url,
            "searchSelector": search_selector
        }
        print(json.dumps({"event": "portal_detected", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("portal_detected", event_data)

    async def report_error(self, message: str) -> None:
        """Report an execution error."""
        event_data = {
            "portalId": self.portal_id,
            "message": message
        }
        print(json.dumps({"event": "error", **event_data}), flush=True)
        if self.on_event:
            await self.on_event("error", event_data)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Any:
    """Parse JSON from *text*, tolerating markdown code-fences.

    Args:
        text: Raw text potentially containing fenced JSON.

    Returns:
        The parsed Python object (list or dict).

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    try:
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        raw = match.group(1) if match else text
        return json.loads(raw.strip())
    except Exception as err:
        # Find the earliest occurrence of either '{' or '['
        start_brace = text.find("{")
        start_bracket = text.find("[")
        
        if start_brace == -1:
            start = start_bracket
        elif start_bracket == -1:
            start = start_brace
        else:
            start = min(start_brace, start_bracket)
            
        # Find the latest occurrence of either '}' or ']'
        end_brace = text.rfind("}")
        end_bracket = text.rfind("]")
        
        if end_brace == -1:
            end = end_bracket
        elif end_bracket == -1:
            end = end_brace
        else:
            end = max(end_brace, end_bracket)
            
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                raise ValueError(f"Failed to parse JSON: {str(err)}")
        raise err


# ---------------------------------------------------------------------------
# Ollama Network Helpers (Async-safe thread execution)
# ---------------------------------------------------------------------------

def fetch_ollama_tags_sync(ollama_url: str) -> List[str]:
    """Runs a blocking HTTP request to get available Ollama models safely outside the main event loop."""
    clean_url = ollama_url.rstrip("/")
    try:
        req = urllib.request.Request(f"{clean_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error(f"Failed to query Ollama models at {ollama_url}: {str(e)}")
    return []


def fetch_ollama_generate_sync(ollama_url: str, payload: dict) -> str:
    """Runs a blocking HTTP request to generate structured JSON safely outside the main event loop."""
    clean_url = ollama_url.rstrip("/")
    try:
        req = urllib.request.Request(
            f"{clean_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120.0) as response:
            if response.status == 200:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data.get("response", "").strip()
    except Exception as e:
        logger.error(f"Failed to perform Ollama generation at {ollama_url}: {str(e)}")
    return ""


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

class ScrapingStrategy:
    """Base class for all scraping strategies."""

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        raise NotImplementedError()


class PublicApiStrategy(ScrapingStrategy):
    """Fetch opportunities from a publicly accessible REST API."""

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Initializing API strategy sequence...")
        
        # Route to generic search strategy as the primary AI engine
        generic_fallback = GenericSearchStrategy()
        return await generic_fallback.execute(config, rate_limiter, reporter)


class StaticHtmlStrategy(ScrapingStrategy):
    """Download and parse a static HTML page."""

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Initiating static HTML analysis sequence...")
        
        # Route to generic search strategy as the primary AI engine
        generic_fallback = GenericSearchStrategy()
        return await generic_fallback.execute(config, rate_limiter, reporter)


class PlaywrightStrategy(ScrapingStrategy):
    """Render a JS-heavy page with headless Chromium."""

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Initiating Playwright scraping sequence...")
        
        # Route to generic search strategy to avoid a silent no-op stub failure
        generic_fallback = GenericSearchStrategy()
        return await generic_fallback.execute(config, rate_limiter, reporter)


class GenericSearchStrategy(ScrapingStrategy):
    """AI-powered generic search: detect the search bar using heuristics, enter
    keywords, and extract opportunities from the results page using local Ollama.
    """

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        portal_id = config.id
        base_url = config.base_url
        keywords = config.keywords or "RFP"

        await reporter.report_progress(f"Starting generic search strategy for {config.name}...")

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

        await reporter.report_progress(f"Identified {len(keyword_list)} search keyword(s) to process: {', '.join(keyword_list)}")

        adapter = resolve_adapter(base_url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            try:
                for keyword in keyword_list:
                    await reporter.report_progress(f'Starting hunt for keyword: "{keyword}"')

                    page = await browser.new_page()
                    try:
                        target_url = base_url
                        is_direct_query = adapter.supports_direct_query()

                        if is_direct_query:
                            target_url = adapter.build_search_url(base_url, keyword)
                            await reporter.report_progress(f"[{keyword}] Routing directly to: {target_url}")

                        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2)

                        if not is_direct_query:
                            if not search_selector:
                                try:
                                    search_selector = await detect_search_input(page)
                                except Exception as e:
                                    logger.warning(f"[{keyword}] Failed to auto-detect search input: {e}")
                                    search_selector = None

                            if search_selector:
                                await reporter.report_progress(f"[{keyword}] Entering query into: {search_selector}...")
                                try:
                                    await page.fill(search_selector, keyword)
                                    clicked = await page.evaluate("""(sel) => {
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
                                    }""", search_selector)

                                    if not clicked:
                                        await page.press(search_selector, "Enter")
                                    await page.wait_for_load_state("networkidle", timeout=10000)
                                except Exception as fill_err:
                                    logger.warning(f"[{keyword}] Failed to interact with search bar: {str(fill_err)}")
                            else:
                                await reporter.report_progress(f"[{keyword}] No search bar detected, scraping current page...")

                        # Auto-detect on results page if not already found
                        if not search_selector:
                            try:
                                search_selector = await detect_search_input(page)
                            except Exception as e:
                                logger.warning(f"[{keyword}] Failed to auto-detect search input on results page: {e}")
                                search_selector = None

                        if search_selector:
                            await reporter.report_portal_detected(search_selector, base_url)
                        else:
                            logger.info(f"[{keyword}] No search selector found; skipping portal detection event.")

                        cleaned_html = await page.evaluate(r"""() => {
                            if (!document.body) return "";
                            const clone = document.body.cloneNode(true);
                            
                            // Remove unwanted elements
                            const elementsToRemove = clone.querySelectorAll(
                               'script, style, noscript, svg, img, iframe, header, footer, nav, link, meta'
                            );
                            elementsToRemove.forEach((el) => el.remove());
                            
                            // Strip all attributes except href using flat non-recursive pass
                            const elements = clone.querySelectorAll('*');
                            for (const el of elements) {
                              const attrs = Array.from(el.attributes);
                              for (const attr of attrs) {
                                if (attr.name !== 'href') {
                                  el.removeAttribute(attr.name);
                                }
                              }
                            }
                            
                            // Clean up whitespace
                            let html = clone.innerHTML;
                            html = html.replace(/\s+/g, ' ');
                            return html.trim().substring(0, 50000);
                        }""")

                        await reporter.report_progress(f"[{keyword}] Cleaned HTML size: {len(cleaned_html)} chars. Contained keyword: {keyword.lower() in cleaned_html.lower()}.")

                        # Always extract using local Ollama model (no Gemini)
                        max_retries = 3
                        new_opps = []
                        for attempt in range(1, max_retries + 1):
                            try:
                                new_opps = await self._extract_with_ollama(
                                    cleaned_html, keyword, portal_id, base_url, page.url, config, reporter
                                )
                                break
                            except Exception as e:
                                logger.error(f"Ollama extraction failed (attempt {attempt}) for keyword {keyword}: {e}")
                                if attempt == max_retries:
                                    await reporter.report_error(f"Ollama extraction failed after {max_retries} attempts for keyword {keyword}.")
                                else:
                                    await asyncio.sleep(2 ** attempt)
                        opportunities.extend(new_opps)

                        # Deep Crawling Phase
                        for opp in new_opps:
                            if opp.url and opp.url.startswith("http"):
                                deep_page = await browser.new_page()
                                try:
                                    await reporter.report_progress(f"Deep crawling opportunity: {opp.title}")
                                    await deep_page.goto(opp.url, wait_until="domcontentloaded", timeout=30000)
                                    
                                    # Heuristic extraction for description
                                    full_desc = await deep_page.evaluate(r"""() => {
                                        const container = document.querySelector('.job-detail, .description, .content, main, article, #content');
                                        if (container) {
                                            return container.innerText;
                                        }
                                        return document.body.innerText;
                                    }""")
                                    
                                    # Fallback to Ollama if heuristic fails
                                    if not full_desc or len(full_desc.strip()) < 100:
                                        await reporter.report_progress(f"Heuristics failed for {opp.title}. Falling back to Ollama extraction.")
                                        cleaned_deep_html = await deep_page.evaluate(r"""() => {
                                            if (!document.body) return "";
                                            const clone = document.body.cloneNode(true);
                                            const elementsToRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe, header, footer, nav, link, meta');
                                            elementsToRemove.forEach((el) => el.remove());
                                            let html = clone.innerHTML;
                                            return html.replace(/\s+/g, ' ').trim().substring(0, 50000);
                                        }""")
                                        
                                        ollama_url = config.ollama_url
                                        if not ollama_url:
                                            ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
                                            
                                        target_model = config.ollama_model
                                        if not target_model:
                                            try:
                                                # Need to fetch available models quickly or use a known good default
                                                avail = await asyncio.to_thread(fetch_ollama_tags_sync, ollama_url)
                                                preferred = ["gemma4", "gemma", "qwen2.5-coder", "llama3"]
                                                for pref in preferred:
                                                    match = next((m for m in avail if pref in m.lower()), None)
                                                    if match:
                                                        target_model = match
                                                        break
                                                if not target_model and avail:
                                                    target_model = avail[0]
                                            except Exception:
                                                target_model = "gemma:2b"
                                                
                                        prompt = f"Extract ONLY the full job description text from the following HTML. Output nothing but the pure description text.\n\n{cleaned_deep_html[:50000]}"
                                        payload = {"model": target_model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
                                        try:
                                            response_text = await asyncio.to_thread(fetch_ollama_generate_sync, ollama_url, payload)
                                            if response_text:
                                                full_desc = response_text
                                        except Exception as e:
                                            logger.warning(f"Ollama deep crawl fallback failed: {e}")
                                            
                                    opp.description = full_desc.strip()[:50000]
                                    await reporter.report_opportunity_updated(opp)
                                    
                                    # Extract and download attachments
                                    attachments = await deep_page.evaluate(r"""() => {
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
                                    }""")
                                    
                                    import os
                                    import tempfile
                                    import uuid
                                    
                                    for att in attachments:
                                        try:
                                            temp_dir = os.path.join(tempfile.gettempdir(), "sentinel_attachments")
                                            os.makedirs(temp_dir, exist_ok=True)
                                            
                                            # Clean filename
                                            safe_name = "".join([c for c in att["name"] if c.isalpha() or c.isdigit() or c in (' ', '.', '-', '_')]).rstrip()
                                            if not safe_name: safe_name = "attachment"
                                            if not any(safe_name.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx']):
                                                safe_name += ".pdf" if ".pdf" in att["href"].lower() else ".doc"
                                                
                                            temp_path = os.path.join(temp_dir, str(uuid.uuid4()) + "_" + safe_name)
                                            
                                            # Download using playwright's context
                                            resp = await deep_page.context.request.get(att["href"])
                                            body = await resp.body()
                                            with open(temp_path, "wb") as f:
                                                f.write(body)
                                                
                                            await reporter.report_attachment_downloaded(opp.id, safe_name, temp_path)
                                            await reporter.report_progress(f"Downloaded attachment: {safe_name}")
                                        except Exception as e:
                                            logger.warning(f"Failed to download attachment {att['href']}: {e}")
                                            
                                except Exception as e:
                                    logger.warning(f"Deep crawl failed for {opp.url}: {e}")
                                finally:
                                    await deep_page.close()

                    except Exception as kw_err:
                        logger.error(f'Error processing keyword "{keyword}": {str(kw_err)}')
                        await reporter.report_error(f"Error processing keyword '{keyword}': {str(kw_err)}")
                        continue
                    finally:
                        await page.close()
            finally:
                await browser.close()

        # Deduplicate by URL
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
    async def _extract_with_ollama(cleaned_html: str, keyword: str, portal_id: str, base_url: str, current_url: str, config: PortalConfig, reporter: ProgressReporter) -> List[RFPOpportunity]:
        """Call local Ollama to extract opportunities from *cleaned_html*."""
        await reporter.report_progress(f"[{keyword}] Initiating local Ollama extraction...")

        # Determine Ollama URL (prioritize config.ollama_url, fallback to env)
        ollama_url = config.ollama_url
        if not ollama_url:
            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

        # Smart Loopback translation if running in Docker
        if os.environ.get("RUNNING_IN_DOCKER") == "true":
            parsed_ollama = urlparse(ollama_url)
            if parsed_ollama.hostname in ("localhost", "127.0.0.1", "host.docker.internal"):
                # First try to resolve host.docker.internal natively
                use_resolved = False
                if parsed_ollama.hostname == "host.docker.internal":
                    try:
                        import socket
                        socket.gethostbyname("host.docker.internal")
                        use_resolved = True
                    except Exception:
                        pass

                if not use_resolved:
                    # Read /proc/net/route to dynamically resolve the container's gateway IP
                    gateway_ip = "172.19.0.1"  # Default fallback
                    try:
                        with open("/proc/net/route") as f:
                            for line in f:
                                fields = line.strip().split()
                                if len(fields) >= 3 and fields[1] == "00000000":
                                    val = fields[2]
                                    ip_parts = [str(int(val[i:i+2], 16)) for i in range(6, -1, -2)]
                                    gateway_ip = ".".join(ip_parts)
                                    break
                    except Exception:
                        pass
                    
                    netloc = gateway_ip
                    if parsed_ollama.port:
                        netloc = f"{gateway_ip}:{parsed_ollama.port}"
                    ollama_url = parsed_ollama._replace(netloc=netloc).geturl()

        # 1. Fetch available models from Ollama
        available_models = await asyncio.to_thread(fetch_ollama_tags_sync, ollama_url)

        if not available_models:
            await reporter.report_progress(f"[{keyword}] Warning: Ollama server at {ollama_url} has no models installed or is unreachable. Please pull an LLM model (e.g. gemma or qwen2.5-coder) inside Settings.")
            return []

        # Determine target model: check config settings, selector_config, env, or pick first available local model
        target_model = config.ollama_model
        
        # Read from selector_config settings if present
        if not target_model and config.selector_config:
            try:
                sel_data = json.loads(config.selector_config)
                if sel_data.get("modelName"):
                    target_model = sel_data["modelName"]
            except Exception:
                pass

        # Fallback to general OLLAMA_MODEL environment variable
        if not target_model:
            target_model = os.environ.get("OLLAMA_MODEL")
            
        if not target_model or target_model not in available_models:
            # Prioritize better models for data extraction (gemma4 first to avoid qwen refusal)
            preferred = ["gemma4", "gemma", "qwen2.5-coder", "llama3"]
            for pref in preferred:
                match = next((m for m in available_models if pref in m.lower()), None)
                if match:
                    target_model = match
                    break
            
            # Pick first available local model if no preferred found
            if not target_model or target_model not in available_models:
                target_model = available_models[0]

        await reporter.report_progress(f"[{keyword}] Selected dynamic Ollama model: {target_model}")

        prompt = f"""
        Task: Convert the listed job postings in the following HTML snippet into a structured JSON list of objects.
        Filter jobs based on the keyword "{keyword}".
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

        HTML context:
        {cleaned_html[:50000]}
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
                "options": {
                    "temperature": 0.1
                }
            }
            
            # Offload the blocking IO to a background worker thread
            response_text = await asyncio.to_thread(
                fetch_ollama_generate_sync,
                ollama_url,
                payload
            )
            
            if response_text:
                # Check for common refusal patterns
                is_refusal = (
                    "sorry" in response_text.lower() or
                    "can't assist" in response_text.lower() or
                    "cannot assist" in response_text.lower() or
                    "don't have the ability" in response_text.lower() or
                    "unable to assist" in response_text.lower()
                )

                if not is_refusal:
                    try:
                        parsed_data = json.loads(response_text)
                        parsed = parsed_data
                        success = True
                    except json.JSONDecodeError as decode_err:
                        logger.warning(f"[{keyword}] Ollama response was not valid JSON: {response_text}, error: {str(decode_err)}")
                        await reporter.report_progress(f"[{keyword}] Ollama response was not valid JSON: {str(decode_err)}")
            else:
                logger.warning(f"[{keyword}] Ollama returned empty response")
                await reporter.report_progress(f"[{keyword}] Ollama returned empty response")
        except Exception as model_err:
            logger.error(f"[{keyword}] Model extraction error: {str(model_err)}")
            await reporter.report_progress(f"[{keyword}] Ollama model extraction failed: {str(model_err)}")

        if success and parsed:
            items = []
            if isinstance(parsed, list):
                items = parsed
            elif isinstance(parsed, dict):
                items = parsed.get("opportunities") or parsed.get("jobs") or []

            if isinstance(items, list):
                for item in items:
                    try:
                        # Clean/parse via Pydantic model
                        raw_ext = OllamaExtraction.model_validate(item)
                        
                        full_url = raw_ext.url or current_url
                        if full_url.startswith("/"):
                            parsed_base = urlparse(base_url)
                            full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{full_url}"
                        elif not full_url.startswith("http"):
                            parsed_base = urlparse(base_url)
                            full_url = f"{parsed_base.scheme}://{parsed_base.netloc}/{full_url}"

                        opp = RFPOpportunity(
                            id=secrets.token_hex(8),  # 64-bit cryptographically secure ID
                            portalId=portal_id,
                            title=raw_ext.title or "Untitled Opportunity",
                            description=raw_ext.description or "",
                            url=full_url,
                            publishDate=raw_ext.publishDate or "",
                            dueDate=raw_ext.dueDate or "",
                            agency=raw_ext.agency or "Unknown",
                            status="open"
                        )
                        opportunities.append(opp)
                        await reporter.report_opportunity(opp)
                    except Exception as val_err:
                        logger.warning(f"Skipping malformed extraction item: {item}, error: {str(val_err)}")

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
