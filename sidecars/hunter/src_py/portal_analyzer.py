"""Portal Analyzer Module

Provides the `analyze_portal` asynchronous function using Playwright and local Ollama
to inspect a portal URL and detect search capability.
"""

import os
import json
import logging
from playwright.async_api import async_playwright

from sidecars.shared.llm_client import generate, list_models
from sidecars.hunter.src_py.ollama_utils import extract_json
from sidecars.hunter.src_py.utils.search_detector import detect_search_input

logger = logging.getLogger("hunter.portal_analyzer")

async def analyze_portal(url: str, provider_config: dict = None) -> dict:
    """Analyze a target portal URL to detect capabilities and search fields.

    Uses the configured LLM provider (Google Gemini or Ollama) if available,
    falling back to clean heuristics.
    """
    cfg = provider_config or {}
    provider = (cfg.get("provider") or os.environ.get("LLM_PROVIDER", "google")).lower()
    google_api_key = cfg.get("google_api_key") or os.environ.get("GOOGLE_API_KEY", "")
    google_model = cfg.get("google_model") or os.environ.get("GOOGLE_LLM_MODEL", "gemini-flash-latest")
    ollama_url = (cfg.get("ollama_url") or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")

    print(json.dumps({
        "event": "progress",
        "portalId": "detector",
        "message": f"Analyzing {url} with {provider} model..."
    }), flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        search_selector = ""

        try:
            await page.goto(url, wait_until="load", timeout=15000)

            # Clean HTML to save tokens
            cleaned_html = await page.evaluate("""() => {
                if (!document.body) return "";
                const clone = document.body.cloneNode(true);
                const toRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe');
                toRemove.forEach(el => el.remove());
                return clone.innerHTML.substring(0, 50000);
            }""")

            # Determine availability + target model per provider
            available_models = []
            target_model = google_model if provider == "google" else cfg.get("ollama_model") or os.environ.get("OLLAMA_MODEL", "")
            can_query = True

            if provider == "google":
                if not google_api_key:
                    can_query = False
            else:
                try:
                    available_models = await list_models(provider="ollama", ollama_url=ollama_url)
                except Exception as e:
                    logger.error(f"Failed to query Ollama models at {ollama_url}: {str(e)}")
                if not available_models:
                    can_query = False

            if can_query:
                if not target_model and available_models:
                    target_model = available_models[0]

                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": f"Calling {provider} ({target_model}) for intelligent search selector detection..."
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
                    response_text = await generate(
                        prompt,
                        model=target_model,
                        provider=provider,
                        ollama_url=ollama_url,
                        google_api_key=google_api_key,
                        json_mode=True,
                    )
                    if response_text:
                        parsed = extract_json(response_text)
                        if parsed and isinstance(parsed, dict) and parsed.get("searchSelector"):
                            search_selector = parsed["searchSelector"]
                except Exception as model_err:
                    logger.error(f"{provider} analysis error: {str(model_err)}")
            else:
                print(json.dumps({
                    "event": "progress",
                    "portalId": "detector",
                    "message": f"{provider} provider has no models / is offline, falling back to heuristics..."
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
