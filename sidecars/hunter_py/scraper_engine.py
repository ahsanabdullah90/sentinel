import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
import google.generativeai as genai
from .rate_limiter import TokenBucketRateLimiter

class ScraperEngine:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def classify_page(self, page: Page) -> str:
        """Classifies page into Catalog, Details, Captcha, or Other."""
        content = await page.content()
        # Basic heuristic for Captcha
        if "captcha" in content.lower() or "hcaptcha" in content.lower() or "recaptcha" in content.lower():
            return "Captcha"

        prompt = f"""
        Classify this page into one of: Catalog, Details, Captcha, Other.
        Catalog: A list of jobs or opportunities.
        Details: A single job or RFP detail page.
        Captcha: A security challenge page.
        Other: Login, landing, or irrelevant.

        HTML Snippet:
        {content[:10000]}
        """

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            text = response.text.strip()
            if "Catalog" in text: return "Catalog"
            if "Details" in text: return "Details"
            if "Captcha" in text: return "Captcha"
            return "Other"
        except Exception:
            return "Other"

    async def get_recipe(self, page: Page, goal: str) -> Dict[str, Any]:
        """Discovery Loop: Uses LLM to produce a scraping recipe."""
        # Extract meaningful DOM info
        dom_info = await page.evaluate("""() => {
            const items = Array.from(document.querySelectorAll('a, button, h1, h2, h3, input'));
            return items.map(el => ({
                tag: el.tagName,
                text: el.innerText.substring(0, 50),
                id: el.id,
                class: el.className,
                type: el.getAttribute('type')
            })).slice(0, 100);
        }""")

        prompt = f"""
        You are a scraping recipe expert. Based on this DOM structure, generate a JSON recipe to find {goal}.
        JSON format:
        {{
            "item_selector": "css_selector_for_each_card",
            "title_selector": "relative_selector_for_title",
            "link_selector": "relative_selector_for_link",
            "date_selector": "relative_selector_for_date"
        }}

        DOM:
        {json.dumps(dom_info)}
        """

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            # Find JSON in response
            text = response.text
            start = text.find('{')
            end = text.rfind('}')
            return json.loads(text[start:end+1])
        except Exception as e:
            print(f"Failed to get recipe: {e}")
            return {{}}

    async def production_scrape(self, page: Page, recipe: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Production Loop: Scrapes using recipe without LLM."""
        if not recipe or "item_selector" not in recipe:
            return []

        results = []
        items = await page.query_selector_all(recipe["item_selector"])
        for item in items:
            title_el = await item.query_selector(recipe.get("title_selector", "h1,h2,h3,a"))
            link_el = await item.query_selector(recipe.get("link_selector", "a"))
            date_el = await item.query_selector(recipe.get("date_selector", "span,time"))

            results.append({
                "title": await title_el.inner_text() if title_el else "Untitled",
                "url": await link_el.get_attribute("href") if link_el else "",
                "date": await date_el.inner_text() if date_el else ""
            })
        return results

    async def hunt(self, portal_id: str, config: Dict[str, Any], rate_limiter: TokenBucketRateLimiter):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await rate_limiter.acquire()
            await page.goto(config.get("baseUrl", "https://sam.gov"), wait_until="networkidle")

            classification = await self.classify_page(page)
            if classification == "Captcha":
                rate_limiter.on_captcha(portal_id)
                # In real scenario, wait for resume or HITL
                return

            recipe = await self.get_recipe(page, "RFP listings")
            opportunities = await self.production_scrape(page, recipe)

            for opp in opportunities:
                print(json.dumps({"event": "opportunity_found", "data": opp}))

            await browser.close()
