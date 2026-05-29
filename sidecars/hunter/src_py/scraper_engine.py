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

from .rate_limiter import TokenBucketRateLimiter
from .utils.search_detector import detect_search_input
from .adapters import resolve_adapter
from .models import PortalConfig, RFPOpportunity, OllamaExtraction

logger = logging.getLogger("hunter.scraper_engine")


# ---------------------------------------------------------------------------
# Progress & Event Reporting
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Handles unified reporting of progress and findings to stdout and gRPC."""

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

    async def report_portal_detected(self, search_selector: str, base_url: str) -> None:
        """Report successful search input selector detection."""
        event_data = {
            "url": base_url,
            "searchSelector": search_selector
        }
        print(json.dumps({"event": "portal_detected", "data": event_data}), flush=True)
        if self.on_event:
            await self.on_event("portal_detected", event_data)


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
        start = text.find("{") if text.find("{") != -1 else text.find("[")
        end = text.rfind("}") if text.find("}") != -1 else text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                raise ValueError(f"Failed to parse JSON: {str(err)}")
        raise err


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
        await reporter.report_progress("Fetching from public API (Python stub)...")
        return []


class StaticHtmlStrategy(ScrapingStrategy):
    """Download and parse a static HTML page."""

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Fetching static HTML (Python stub)...")
        return []


class PlaywrightStrategy(ScrapingStrategy):
    """Render a JS-heavy page with headless Chromium."""

    async def execute(self, config: PortalConfig, rate_limiter: TokenBucketRateLimiter, reporter: ProgressReporter) -> List[RFPOpportunity]:
        await rate_limiter.acquire()
        await reporter.report_progress("Launching headless browser (Python Playwright stub)...")
        return []


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
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
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

                        await page.goto(target_url, wait_until="load", timeout=15000)
                        await asyncio.sleep(2)

                        if not is_direct_query:
                            if not search_selector:
                                search_selector = await detect_search_input(page)

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
                                    await asyncio.sleep(5)
                                except Exception as fill_err:
                                    logger.warning(f"[{keyword}] Failed to interact with search bar: {str(fill_err)}")
                            else:
                                await reporter.report_progress(f"[{keyword}] No search bar detected, scraping current page...")

                        # Auto-detect on results page if not already found
                        if not search_selector:
                            search_selector = await detect_search_input(page)

                        if search_selector:
                            await reporter.report_portal_detected(search_selector, base_url)

                        cleaned_html = await page.evaluate(r"""() => {
                            const clone = document.body.cloneNode(true);
                            
                            // Remove unwanted elements
                            const elementsToRemove = clone.querySelectorAll(
                               'script, style, noscript, svg, img, iframe, header, footer, nav, link, meta'
                            );
                            elementsToRemove.forEach((el) => el.remove());
                            
                            // Strip all attributes except href
                            const stripAttributes = (node) => {
                               if (node.nodeType === 1) { // Element
                                 const attrs = Array.from(node.attributes);
                                 for (const attr of attrs) {
                                   if (attr.name !== 'href') {
                                     node.removeAttribute(attr.name);
                                   }
                                 }
                               }
                               for (let i = 0; i < node.childNodes.length; i++) {
                                 stripAttributes(node.childNodes[i]);
                               }
                            };
                            
                            stripAttributes(clone);
                            
                            // Clean up whitespace
                            let html = clone.innerHTML;
                            html = html.replace(/\s+/g, ' ');
                            return html.trim().substring(0, 300000);
                        }""")

                        await reporter.report_progress(f"[{keyword}] Cleaned HTML size: {len(cleaned_html)} chars. Contained keyword: {keyword.lower() in cleaned_html.lower()}.")

                        # Always extract using local Ollama model (no Gemini)
                        new_opps = await self._extract_with_ollama(
                            cleaned_html, keyword, portal_id, base_url, page.url, config, reporter
                        )
                        opportunities.extend(new_opps)

                    except Exception as kw_err:
                        logger.error(f'Error processing keyword "{keyword}": {str(kw_err)}')
                    finally:
                        await page.close()
            finally:
                await browser.close()

        # Deduplicate by URL
        seen_urls = set()
        unique_opps: List[RFPOpportunity] = []
        for opp in opportunities:
            if opp.url not in seen_urls:
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

        # Get local Ollama host, fallback to default if not configured
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

        # 1. Fetch available models from Ollama
        available_models = []
        try:
            req = urllib.request.Request(f"{ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    available_models = [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to query Ollama models at {ollama_url}: {str(e)}")

        if not available_models:
            raise RuntimeError(f"Ollama server at {ollama_url} has no models installed, or is unreachable. Please pull an LLM (e.g. gemma or qwen2.5-coder) before starting the hunt.")

        # Determine target model: check settings/config or pick the first available local model
        target_model = None
        
        # Read from selector_config settings if present
        if config.selector_config:
            try:
                sel_data = json.loads(config.selector_config)
                if sel_data.get("modelName"):
                    target_model = sel_data["modelName"]
            except Exception:
                pass

        # Fallback to general OLLAMA_MODEL environment variable or first available model
        if not target_model:
            target_model = os.environ.get("OLLAMA_MODEL")
            
        if not target_model or target_model not in available_models:
            # Pick first available local model
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
            
            req = urllib.request.Request(
                f"{ollama_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            # Use a total timeout budget of 120 seconds
            with urllib.request.urlopen(req, timeout=120.0) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    response_text = resp_data.get("response", "").strip()
                    
                    # Check for common refusal patterns
                    is_refusal = (
                        "sorry" in response_text.lower() or
                        "can't assist" in response_text.lower() or
                        "cannot assist" in response_text.lower() or
                        "don't have the ability" in response_text.lower() or
                        "unable to assist" in response_text.lower()
                    )

                    if not is_refusal:
                        parsed_data = json.loads(response_text)
                        
                        # Verify we didn't receive a JSON-formatted refusal object
                        is_json_refusal = False
                        if isinstance(parsed_data, dict) and not isinstance(parsed_data, list):
                            resp_val = parsed_data.get("response", "")
                            if isinstance(resp_val, str) and ("sorry" in resp_val.lower() or "assist" in resp_val.lower()):
                                is_json_refusal = True

                        if not is_json_refusal:
                            parsed = parsed_data
                            success = True
                            await reporter.report_progress(f"[{keyword}] Ollama extraction completed successfully. Parsing response...")
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
