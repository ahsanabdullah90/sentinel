"""Scraper Engine Module

Implements the Strategy pattern for scraping external portals.

Available strategies:
    * ``PublicApiStrategy``  – fetch from a public REST API.
    * ``StaticHtmlStrategy`` – simple HTTP GET + parse.
    * ``PlaywrightStrategy`` – headless Chromium via Playwright.
    * ``GenericSearchStrategy`` – AI-powered search-bar detection and
      opportunity extraction using Google Gemini.

The helper ``extract_json`` robustly parses JSON from markdown-fenced
or bare responses returned by LLMs.
"""

import asyncio
import os
import json
import secrets
import logging
import re
from typing import List, Dict, Any
from urllib.parse import quote, urlparse
import urllib.request
from playwright.async_api import async_playwright
import google.generativeai as genai
from .rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger("hunter.scraper_engine")


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

    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        raise NotImplementedError()


class PublicApiStrategy(ScrapingStrategy):
    """Fetch opportunities from a publicly accessible REST API."""

    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        print(json.dumps({
            "event": "progress",
            "portalId": config.get("id"),
            "message": "Fetching from public API (Python stub)..."
        }), flush=True)
        return []


class StaticHtmlStrategy(ScrapingStrategy):
    """Download and parse a static HTML page."""

    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        print(json.dumps({
            "event": "progress",
            "portalId": config.get("id"),
            "message": "Fetching static HTML (Python stub)..."
        }), flush=True)
        return []


class PlaywrightStrategy(ScrapingStrategy):
    """Render a JS-heavy page with headless Chromium."""

    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        print(json.dumps({
            "event": "progress",
            "portalId": config.get("id"),
            "message": "Launching headless browser (Python Playwright stub)..."
        }), flush=True)
        return []


class GenericSearchStrategy(ScrapingStrategy):
    """AI-powered generic search: detect the search bar, enter keywords,
    and extract opportunities from the results page using Gemini."""

    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        portal_id = config.get("id", "unknown")
        base_url = config.get("baseUrl")
        keywords = config.get("keywords", "RFP")

        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": "Running generic search strategy (Python)..."
        }), flush=True)

        search_selector = ""
        selector_config = config.get("selectorConfig")
        if selector_config:
            try:
                selectors = json.loads(selector_config)
                search_selector = selectors.get("searchSelector", "")
            except Exception:
                logger.warning("Failed to parse selector config, using heuristics")

        opportunities: List[Dict[str, Any]] = []
        api_key = os.environ.get("GEMINI_API_KEY")

        keyword_list = [k.strip() for k in re.split(r"[,;\n]+", keywords) if k.strip()]
        if not keyword_list:
            keyword_list.append("RFP")

        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": f"Identified {len(keyword_list)} search keyword(s) to process: {', '.join(keyword_list)}"
        }), flush=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                for keyword in keyword_list:
                    print(json.dumps({
                        "event": "progress",
                        "portalId": portal_id,
                        "message": f'Starting hunt for keyword: "{keyword}"'
                    }), flush=True)

                    page = await browser.new_page()
                    try:
                        target_url = base_url
                        is_direct_query = "resume.brightspyre.com" in target_url

                        if is_direct_query:
                            target_url = f"https://resume.brightspyre.com/jobs?query={quote(keyword)}"
                            print(json.dumps({
                                "event": "progress",
                                "portalId": portal_id,
                                "message": f"[{keyword}] Routing directly to: {target_url}"
                            }), flush=True)

                        await page.goto(target_url, wait_until="networkidle", timeout=30000)

                        if not is_direct_query:
                            if not search_selector:
                                search_selector = await self._detect_search_input(page)

                            if search_selector:
                                print(json.dumps({
                                    "event": "progress",
                                    "portalId": portal_id,
                                    "message": f"[{keyword}] Entering query into: {search_selector}..."
                                }), flush=True)
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
                                print(json.dumps({
                                    "event": "progress",
                                    "portalId": portal_id,
                                    "message": f"[{keyword}] No search bar detected, scraping current page..."
                                }), flush=True)

                        # Auto-detect on results page if not already found
                        if not search_selector:
                            search_selector = await self._detect_search_input(page)

                        if search_selector:
                            print(json.dumps({
                                "event": "portal_detected",
                                "data": {"url": base_url, "searchSelector": search_selector}
                            }), flush=True)

                        cleaned_html = await page.evaluate("""() => {
                            const clone = document.body.cloneNode(true);
                            const toRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe, header, footer, nav');
                            toRemove.forEach(el => el.remove());
                            return clone.innerHTML.substring(0, 300000);
                        }""")

                        print(json.dumps({
                            "event": "progress",
                            "portalId": portal_id,
                            "message": f"[{keyword}] Cleaned HTML size: {len(cleaned_html)} chars. Contains keyword: {keyword.lower() in cleaned_html.lower()}."
                        }), flush=True)

                        if api_key:
                            new_opps = await self._extract_with_gemini(
                                api_key, cleaned_html, keyword, portal_id, base_url, page.url
                            )
                            opportunities.extend(new_opps)
                        else:
                            new_opps = await self._extract_with_ollama(
                                cleaned_html, keyword, portal_id, base_url, page.url
                            )
                            opportunities.extend(new_opps)

                    except Exception as kw_err:
                        logger.error(f'Error processing keyword "{keyword}": {str(kw_err)}')
                    finally:
                        await page.close()
            finally:
                await browser.close()

        # Deduplicate
        seen_urls: set = set()
        unique_opps: List[Dict[str, Any]] = []
        for opp in opportunities:
            if opp["url"] not in seen_urls:
                seen_urls.add(opp["url"])
                unique_opps.append(opp)

        if not unique_opps:
            unique_opps.append({
                "id": secrets.token_hex(4),
                "portalId": portal_id,
                "title": f"Found result for {keywords}",
                "description": "Generic search result fallback (Python)",
                "url": base_url,
                "publishDate": "",
                "dueDate": "",
                "agency": "Unknown",
                "status": "open"
            })

        return unique_opps

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _detect_search_input(page) -> str:
        """Run heuristic JS to locate a search <input> on the page."""
        return await page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])'));
            for (const input of inputs) {
                const id = input.id.toLowerCase();
                const name = (input.getAttribute('name') || '').toLowerCase();
                const placeholder = (input.getAttribute('placeholder') || '').toLowerCase();
                const className = input.className.toLowerCase();
                if (id.includes('search') || id.includes('query') || id.includes('q') ||
                    name.includes('search') || name.includes('query') || name.includes('q') ||
                    placeholder.includes('search') || placeholder.includes('find') || placeholder.includes('query') ||
                    className.includes('search')) {
                    if (input.id) return `#${input.id}`;
                    const nameAttr = input.getAttribute('name');
                    if (nameAttr) return `input[name="${nameAttr}"]`;
                    if (input.getAttribute('placeholder')) return `input[placeholder="${input.getAttribute('placeholder')}"]`;
                }
            }
            if (inputs.length > 0) {
                const first = inputs[0];
                if (first.id) return `#${first.id}`;
                const firstName = first.getAttribute('name');
                if (firstName) return `input[name="${firstName}"]`;
            }
            return '';
        }""")

    @staticmethod
    async def _extract_with_gemini(api_key, cleaned_html, keyword, portal_id, base_url, current_url) -> List[Dict[str, Any]]:
        """Call Gemini to extract opportunities from *cleaned_html*."""
        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": f"[{keyword}] AI is extracting opportunities from results..."
        }), flush=True)

        genai.configure(api_key=api_key)
        prompt = f"""
        You are an expert data scraper. Below is the HTML of a job search/opportunity results page for the keyword "{keyword}".
        Extract all listed opportunities or job posts from the HTML.
        Respond ONLY with a valid JSON array of objects in this exact format:
        [
          {{
            "title": "Job/Opportunity Title",
            "description": "Brief description of the role or RFP",
            "url": "URL of the job page if absolute, or relative path",
            "publishDate": "Publish date if available, otherwise empty",
            "dueDate": "Due/deadline date if available, otherwise empty",
            "agency": "Issuing company or agency"
          }}
        ]

        If no opportunities are listed, return an empty array: []

        HTML:
        {cleaned_html}
        """

        response_text = ""
        active_model = "gemini-2.5-flash-lite"
        for fallback in ["gemini-2.5-flash", "gemini-1.5-flash"]:
            try:
                print(json.dumps({
                    "event": "progress",
                    "portalId": portal_id,
                    "message": f"[{keyword}] Trying model: {active_model}"
                }), flush=True)
                model = genai.GenerativeModel(active_model)
                response = await model.generate_content_async(prompt)
                response_text = response.text
                break
            except Exception:
                active_model = fallback
        else:
            # Last fallback already set
            model = genai.GenerativeModel(active_model)
            response = await model.generate_content_async(prompt)
            response_text = response.text

        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": f"[{keyword}] AI responded using {active_model}. Response length: {len(response_text)} chars."
        }), flush=True)

        opportunities: List[Dict[str, Any]] = []
        try:
            parsed = extract_json(response_text)
            print(json.dumps({
                "event": "progress",
                "portalId": portal_id,
                "message": f"[{keyword}] Successfully parsed AI response. Found {len(parsed) if isinstance(parsed, list) else 0} items."
            }), flush=True)

            if isinstance(parsed, list):
                for item in parsed:
                    full_url = item.get("url") or current_url
                    if full_url.startswith("/"):
                        parsed_base = urlparse(base_url)
                        full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{full_url}"
                    elif not full_url.startswith("http"):
                        parsed_base = urlparse(base_url)
                        full_url = f"{parsed_base.scheme}://{parsed_base.netloc}/{full_url}"

                    opportunities.append({
                        "id": secrets.token_hex(4),
                        "portalId": portal_id,
                        "title": item.get("title") or "Untitled Opportunity",
                        "description": item.get("description") or "",
                        "url": full_url,
                        "publishDate": item.get("publishDate") or "",
                        "dueDate": item.get("dueDate") or "",
                        "agency": item.get("agency") or "Unknown",
                        "status": "open"
                    })
        except Exception as parse_err:
            print(json.dumps({
                "event": "progress",
                "portalId": portal_id,
                "message": f"[{keyword}] Failed to parse AI response: {str(parse_err)}"
            }), flush=True)

        return opportunities

    @staticmethod
    async def _extract_with_ollama(cleaned_html, keyword, portal_id, base_url, current_url) -> List[Dict[str, Any]]:
        """Call local Ollama to extract opportunities from *cleaned_html*."""
        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": f"[{keyword}] Gemini key not found. Trying local Ollama extraction..."
        }), flush=True)

        ollama_urls = [
            "http://host.docker.internal:11434",
            "http://ollama:11434"
        ]

        active_url = None
        available_models = []

        for url in ollama_urls:
            try:
                req = urllib.request.Request(f"{url}/api/tags")
                with urllib.request.urlopen(req, timeout=2.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        models = [m["name"] for m in data.get("models", [])]
                        if models:
                            active_url = url
                            available_models = models
                            break
            except Exception:
                continue

        if not active_url:
            print(json.dumps({
                "event": "progress",
                "portalId": portal_id,
                "message": f"[{keyword}] No active Ollama instances detected or no models installed."
            }), flush=True)
            return []

        preferred_models = ["qwen2.5-coder:7b", "gemma", "qwen", "deepseek"]
        selected_model = available_models[0]
        
        for pref in preferred_models:
            matched = [m for m in available_models if pref in m.lower()]
            if matched:
                selected_model = matched[0]
                break

        print(json.dumps({
            "event": "progress",
            "portalId": portal_id,
            "message": f"[{keyword}] Found Ollama at {active_url}. Using model: {selected_model}"
        }), flush=True)

        prompt = f"""
        Extract all listed opportunities or job posts from the HTML for the keyword "{keyword}".
        Respond ONLY with a valid JSON array of objects in this exact format:
        [
          {{
            "title": "Job/Opportunity Title",
            "description": "Brief description of the role or RFP",
            "url": "URL of the job page if absolute, or relative path",
            "publishDate": "Publish date if available, otherwise empty",
            "dueDate": "Due/deadline date if available, otherwise empty",
            "agency": "Issuing company or agency"
          }}
        ]

        If no opportunities are listed, return an empty array: []

        HTML:
        {cleaned_html[:50000]}
        """

        opportunities: List[Dict[str, Any]] = []
        try:
            payload = {
                "model": selected_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1
                }
            }
            
            req = urllib.request.Request(
                f"{active_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=90.0) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    response_text = resp_data.get("response", "")
                    
                    print(json.dumps({
                        "event": "progress",
                        "portalId": portal_id,
                        "message": f"[{keyword}] Ollama extraction completed. Parsing response..."
                    }), flush=True)
                    
                    parsed = json.loads(response_text)
                    if isinstance(parsed, list):
                        for item in parsed:
                            full_url = item.get("url") or current_url
                            if full_url.startswith("/"):
                                parsed_base = urlparse(base_url)
                                full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{full_url}"
                            elif not full_url.startswith("http"):
                                parsed_base = urlparse(base_url)
                                full_url = f"{parsed_base.scheme}://{parsed_base.netloc}/{full_url}"

                            opportunities.append({
                                "id": secrets.token_hex(4),
                                "portalId": portal_id,
                                "title": item.get("title") or "Untitled Opportunity",
                                "description": item.get("description") or "",
                                "url": full_url,
                                "publishDate": item.get("publishDate") or "",
                                "dueDate": item.get("dueDate") or "",
                                "agency": item.get("agency") or "Unknown",
                                "status": "open"
                            })
        except Exception as ollama_err:
            print(json.dumps({
                "event": "progress",
                "portalId": portal_id,
                "message": f"[{keyword}] Ollama extraction failed: {str(ollama_err)}"
            }), flush=True)

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
