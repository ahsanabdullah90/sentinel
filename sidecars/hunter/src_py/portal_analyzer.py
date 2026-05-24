import os
import json
import logging
from playwright.async_api import async_playwright
import google.generativeai as genai
from .scraper_engine import extract_json

logger = logging.getLogger("hunter.portal_analyzer")

async def analyze_portal(url: str) -> dict:
    print(json.dumps({
        "event": "progress",
        "portalId": "detector",
        "message": f"Analyzing {url} with Gemini (Python)..."
    }), flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        search_selector = ""

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Clean HTML to save tokens
            cleaned_html = await page.evaluate("""() => {
                const clone = document.body.cloneNode(true);
                const toRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe');
                toRemove.forEach(el => el.remove());
                return clone.innerHTML.substring(0, 300000);
            }""")

            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": "Calling Gemini API for intelligent detection..."
                }), flush=True)

                genai.configure(api_key=api_key)
                prompt = f"""
                You are an expert web scraper. Analyze the following HTML snippet and find the CSS selector for the main job/opportunity search input field.
                Respond ONLY with a valid JSON object in this exact format:
                {{ "searchSelector": "your_css_selector_here" }}
                If you cannot find a search bar, return:
                {{ "searchSelector": "" }}

                HTML:
                {cleaned_html}
                """

                response_text = ""
                active_model = "gemini-2.5-flash-lite"
                try:
                    print(json.dumps({
                        "event": "progress",
                        "portalId": "detector",
                        "message": f"Trying model: {active_model}"
                    }), flush=True)
                    model = genai.GenerativeModel(active_model)
                    response = await model.generate_content_async(prompt)
                    response_text = response.text
                except Exception:
                    active_model = "gemini-2.5-flash"
                    print(json.dumps({
                        "event": "progress",
                        "portalId": "detector",
                        "message": f"Failed with lite. Trying model: {active_model}"
                    }), flush=True)
                    try:
                        model = genai.GenerativeModel(active_model)
                        response = await model.generate_content_async(prompt)
                        response_text = response.text
                    except Exception:
                        active_model = "gemini-1.5-flash"
                        print(json.dumps({
                            "event": "progress",
                            "portalId": "detector",
                            "message": f"Failed with 2.5-flash. Falling back to: {active_model}"
                        }), flush=True)
                        model = genai.GenerativeModel(active_model)
                        response = await model.generate_content_async(prompt)
                        response_text = response.text

                try:
                    parsed = extract_json(response_text)
                    if parsed and isinstance(parsed, dict) and parsed.get("searchSelector"):
                        search_selector = parsed["searchSelector"]
                except Exception as parse_err:
                    logger.error(f"Failed to parse Gemini response: {response_text}, error: {str(parse_err)}")
            else:
                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": "No GEMINI_API_KEY found, falling back to basic heuristics..."
                }), flush=True)

            # Heuristics fallback
            if not search_selector:
                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": "Running heuristic selector detection..."
                }), flush=True)

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

            return {
                "url": url,
                "score": "good" if search_selector else "limited",
                "authMethod": "public",
                "renderingMode": "js_required",
                "antiBot": "none",
                "apiAvailable": False,
                "searchSelector": search_selector,
                "scrapingOptions": [
                    {
                        "id": "generic_search",
                        "label": "Generic Search Scraper (AI Powered - Python)",
                        "feasibility": "recommended" if search_selector else "possible",
                        "requiresCredential": False,
                        "description": f"AI detected search bar at selector: {search_selector}" if search_selector else "No obvious search bar detected. Manual configuration may be needed."
                    }
                ],
                "warnings": [] if search_selector else ["No obvious search bar detected."],
                "tosRiskLevel": "unknown"
            }
        except Exception as error:
            logger.error(f"Failed to analyze portal: {str(error)}")
            raise RuntimeError(f"Failed to analyze portal: {str(error)}")
