"""Portal Analyzer Module

Provides the `analyze_portal` asynchronous function using Playwright and local Ollama
to inspect a portal URL and detect search capability.
"""

import os
import json
import logging
import urllib.request
from playwright.async_api import async_playwright

from sidecars.hunter.src_py.scraper_engine import extract_json
from sidecars.hunter.src_py.utils.search_detector import detect_search_input

logger = logging.getLogger("hunter.portal_analyzer")

async def analyze_portal(url: str) -> dict:
    """Analyze a target portal URL to detect capabilities and search fields.

    Uses a local Ollama model if available, falling back to clean heuristics.
    """
    print(json.dumps({
        "event": "progress",
        "portalId": "detector",
        "message": f"Analyzing {url} with local Ollama model..."
    }), flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        search_selector = ""

        try:
            await page.goto(url, wait_until="load", timeout=15000)

            # Clean HTML to save tokens
            cleaned_html = await page.evaluate("""() => {
                const clone = document.body.cloneNode(true);
                const toRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe');
                toRemove.forEach(el => el.remove());
                return clone.innerHTML.substring(0, 50000);
            }""")

            ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

            # 1. Fetch available models from local Ollama
            available_models = []
            try:
                req = urllib.request.Request(f"{ollama_url}/api/tags")
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        available_models = [m["name"] for m in data.get("models", [])]
            except Exception as e:
                logger.error(f"Failed to query Ollama models at {ollama_url}: {str(e)}")

            # If Ollama has models, attempt smart selector extraction
            if available_models:
                target_model = os.environ.get("OLLAMA_MODEL")
                if not target_model or target_model not in available_models:
                    target_model = available_models[0]

                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": f"Calling local Ollama ({target_model}) for intelligent search selector detection..."
                }), flush=True)

                prompt = f"""
                You are an expert web scraper. Analyze the following HTML snippet and find the CSS selector for the main job/opportunity search input field.
                Respond ONLY with a valid JSON object in this exact format:
                {{ "searchSelector": "your_css_selector_here" }}
                If you cannot find a search bar, return:
                {{ "searchSelector": "" }}

                HTML:
                {cleaned_html}
                """

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
                    with urllib.request.urlopen(req, timeout=30.0) as response:
                        if response.status == 200:
                            resp_data = json.loads(response.read().decode("utf-8"))
                            response_text = resp_data.get("response", "").strip()
                            parsed = extract_json(response_text)
                            if parsed and isinstance(parsed, dict) and parsed.get("searchSelector"):
                                search_selector = parsed["searchSelector"]
                except Exception as model_err:
                    logger.error(f"Local Ollama analysis error: {str(model_err)}")
            else:
                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": "Local Ollama has no models or is offline, falling back to heuristics..."
                }), flush=True)

            # Heuristics fallback
            if not search_selector:
                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": "Running heuristic search selector detection..."
                }), flush=True)

                search_selector = await detect_search_input(page)

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
                        "label": "Generic Search Scraper (Local Ollama Powered - Python)",
                        "feasibility": "recommended" if search_selector else "possible",
                        "requiresCredential": False,
                        "description": f"Detected search bar at selector: {search_selector}" if search_selector else "No obvious search bar detected. Manual configuration may be needed."
                    }
                ],
                "warnings": [] if search_selector else ["No obvious search bar detected."],
                "tosRiskLevel": "unknown"
            }
        except Exception as error:
            logger.error(f"Failed to analyze portal: {str(error)}")
            raise RuntimeError(f"Failed to analyze portal: {str(error)}")
        finally:
            await page.close()
            await browser.close()
