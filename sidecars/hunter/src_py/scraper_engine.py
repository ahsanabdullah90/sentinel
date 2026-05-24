import os
import json
import secrets
import logging
import re
from typing import List, Dict, Any
from playwright.async_api import async_playwright
import google.generativeai as genai
from .rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger("hunter.scraper_engine")

def extract_json(text: str) -> Any:
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
            except Exception as e:
                raise ValueError(f"Failed to parse JSON: {str(err)}")
        raise err

class ScrapingStrategy:
    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        raise NotImplementedError()

class PublicApiStrategy(ScrapingStrategy):
    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        print(json.dumps({
            "event": "progress",
            "portalId": config.get("id"),
            "message": "Fetching from public API (Python stub)..."
        }), flush=True)
        return []

class StaticHtmlStrategy(ScrapingStrategy):
    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        print(json.dumps({
            "event": "progress",
            "portalId": config.get("id"),
            "message": "Fetching static HTML (Python stub)..."
        }), flush=True)
        return []

class PlaywrightStrategy(ScrapingStrategy):
    async def execute(self, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter) -> List[Dict[str, Any]]:
        await rate_limiter.acquire()
        print(json.dumps({
            "event": "progress",
            "portalId": config.get("id"),
            "message": "Launching headless browser (Python Playwright stub)..."
        }), flush=True)
        return []

class GenericSearchStrategy(ScrapingStrategy):
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

        opportunities = []
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
                        "message": f"Starting hunt for keyword: \"{keyword}\""
                    }), flush=True)

                    page = await browser.new_page()
                    try:
                        target_url = base_url
                        is_direct_query = "resume.brightspyre.com" in target_url
                        
                        if is_direct_query:
                            from urllib.parse import quote
                            target_url = f"https://resume.brightspyre.com/jobs?query={quote(keyword)}"
                            print(json.dumps({
                                "event": "progress",
                                "portalId": portal_id,
                                "message": f"[{keyword}] Routing directly to: {target_url}"
                            }), flush=True)

                        await page.goto(target_url, wait_until="networkidle", timeout=30000)

                        if not is_direct_query:
                            if not search_selector:
                                # Run heuristic input detector
                                search_selector = await page.evaluate("""() => {
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

                        # Auto-detect searchSelector on loaded results page if not already done
                        if not search_selector:
                            search_selector = await page.evaluate("""() => {
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

                        if search_selector:
                            print(json.dumps({
                                "event": "portal_detected",
                                "data": {
                                    "url": base_url,
                                    "searchSelector": search_selector
                                }
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
                            try:
                                print(json.dumps({
                                    "event": "progress",
                                    "portalId": portal_id,
                                    "message": f"[{keyword}] Trying model: {active_model}"
                                }), flush=True)
                                model = genai.GenerativeModel(active_model)
                                response = await model.generate_content_async(prompt)
                                response_text = response.text
                            except Exception:
                                active_model = "gemini-2.5-flash"
                                print(json.dumps({
                                    "event": "progress",
                                    "portalId": portal_id,
                                    "message": f"[{keyword}] Model failed. Trying fallback: {active_model}"
                                }), flush=True)
                                try:
                                    model = genai.GenerativeModel(active_model)
                                    response = await model.generate_content_async(prompt)
                                    response_text = response.text
                                except Exception:
                                    active_model = "gemini-1.5-flash"
                                    print(json.dumps({
                                        "event": "progress",
                                        "portalId": portal_id,
                                        "message": f"[{keyword}] Model failed. Trying fallback: {active_model}"
                                    }), flush=True)
                                    model = genai.GenerativeModel(active_model)
                                    response = await model.generate_content_async(prompt)
                                    response_text = response.text

                            print(json.dumps({
                                "event": "progress",
                                "portalId": portal_id,
                                "message": f"[{keyword}] AI responded using {active_model}. Response length: {len(response_text)} chars."
                            }), flush=True)

                            try:
                                parsed = extract_json(response_text)
                                print(json.dumps({
                                    "event": "progress",
                                    "portalId": portal_id,
                                    "message": f"[{keyword}] Successfully parsed AI response. Found {len(parsed) if isinstance(parsed, list) else 0} items."
                                }), flush=True)

                                if isinstance(parsed, list):
                                    for item in parsed:
                                        full_url = item.get("url") or page.url
                                        if full_url.startswith("/"):
                                            from urllib.parse import urlparse
                                            parsed_base = urlparse(base_url)
                                            full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{full_url}"
                                        elif not full_url.startswith("http"):
                                            from urllib.parse import urlparse
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
                    except Exception as kw_err:
                        logger.error(f"Error processing keyword \"{keyword}\": {str(kw_err)}")
                    finally:
                        await page.close()
            finally:
                await browser.close()

        # Deduplicate
        seen_urls = set()
        unique_opps = []
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

def get_strategy(option_id: str) -> ScrapingStrategy:
    if option_id == "public_api":
        return PublicApiStrategy()
    elif option_id == "static_html":
        return StaticHtmlStrategy()
    elif option_id == "playwright_public":
        return PlaywrightStrategy()
    elif option_id == "generic_search":
        return GenericSearchStrategy()
    else:
        raise ValueError(f"Unknown scraping strategy: {option_id}")
