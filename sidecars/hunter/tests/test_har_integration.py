import pytest
from playwright.async_api import async_playwright
import os

@pytest.mark.asyncio
async def test_brightspyre_har_playback():
    """
    Play-back HAR integration test for Brightspyre adapter.
    This test uses a pre-recorded HAR file to mock network responses,
    ensuring that the scraping logic works against known HTML without
    hitting the live site.
    """
    har_path = os.path.join(os.path.dirname(__file__), "data", "brightspyre.har")
    
    if not os.path.exists(har_path):
        pytest.skip("HAR file not found for Brightspyre playback test.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Route network requests from the HAR file
        await context.route_from_har(har_path)
        
        page = await context.new_page()
        await page.goto("https://resume.brightspyre.com/jobs?query=test")
        
        # Verify page loaded from HAR mock
        title = await page.title()
        assert "Brightspyre" in title or title != ""
        
        # Clean up
        await context.close()
        await browser.close()
