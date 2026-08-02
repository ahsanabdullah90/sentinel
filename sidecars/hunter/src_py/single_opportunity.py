"""Single Opportunity Extraction Module

Provides ``extract_single_opportunity`` which fetches a single opportunity URL
via Playwright, validates that it is a real page (not a 404 / custom error page),
and uses local Ollama to extract structured opportunity details.
"""

import asyncio
import json
import logging
import os

from playwright.async_api import async_playwright

from sidecars.hunter.src_py.ollama_utils import (
    fetch_ollama_generate_sync,
    fetch_ollama_tags_sync,
    extract_json,
)

logger = logging.getLogger("hunter.single_opportunity")

NOT_FOUND_INDICATORS = [
    "not found",
    "404",
    "page not found",
    "does not exist",
    "no such page",
    "the requested url",
    "sorry, we couldn",
    "could not find",
    "doesn't exist",
]

_PREFERRED_MODELS = [
    "qwen3",
    "qwen2.5-coder",
    "gemma3",
    "gemma4",
    "gemma",
    "llama3",
]


def _pick_model(ollama_url: str) -> str:
    try:
        avail = fetch_ollama_tags_sync(ollama_url)
        for pref in _PREFERRED_MODELS:
            match = next((m for m in avail if pref in m.lower()), None)
            if match:
                return match
        if avail:
            return avail[0]
    except Exception as e:
        logger.warning(f"Failed to fetch Ollama models: {e}")
    return "qwen3:8b"


async def extract_single_opportunity(url: str) -> dict:
    """Fetch *url* and extract structured opportunity fields via Ollama.

    Returns a dict with keys ``title``, ``description``, ``agency``,
    ``dueDate``, and ``url``. On failure, returns an ``error`` key.
    """
    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

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
        page = await browser.new_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                return {
                    "error": f"HTTP {response.status} returned for {url}",
                    "url": url,
                }

            body_text = await page.evaluate("() => document.body.innerText")
            if any(ind in body_text.lower() for ind in NOT_FOUND_INDICATORS):
                return {
                    "error": "Not Found page detected for the given URL",
                    "url": url,
                }

            page_title = await page.title()
            cleaned_html = await page.evaluate(
                r"""() => {
                if (!document.body) return "";
                const clone = document.body.cloneNode(true);
                const elementsToRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe, header, footer, nav, link, meta');
                elementsToRemove.forEach((el) => el.remove());
                let html = clone.innerHTML;
                return html.replace(/\s+/g, ' ').trim().substring(0, 50000);
            }"""
            )

            target_model = _pick_model(ollama_url)
            prompt = f"""
Task: Extract the opportunity/job listing details from the following HTML snippet.
The web page title is: {page_title}

Output ONLY a valid JSON object with these keys:
- "title": the full opportunity title
- "description": a concise summary of the opportunity (2-4 sentences)
- "agency": the hiring / issuing organization name
- "dueDate": the application closing date, or empty string if unknown

Content:
{cleaned_html[:50000]}
"""

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

            if not response_text:
                return {
                    "error": "Ollama returned an empty response",
                    "url": url,
                    "title": page_title,
                }

            parsed = extract_json(response_text)
            if not isinstance(parsed, dict):
                return {
                    "error": "Ollama response was not a JSON object",
                    "url": url,
                    "title": page_title,
                }

            result = {
                "title": parsed.get("title") or page_title or "",
                "description": parsed.get("description") or "",
                "agency": parsed.get("agency") or "",
                "dueDate": parsed.get("dueDate") or "",
                "url": url,
            }
            logger.info(f"Extracted opportunity: {result['title'][:80]}")
            return result
        except Exception as e:
            logger.error(f"extract_single_opportunity failed for {url}: {e}")
            return {"error": str(e), "url": url}
        finally:
            await page.close()
            await browser.close()
