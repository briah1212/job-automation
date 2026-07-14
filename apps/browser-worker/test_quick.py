import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://localhost:8080")
        title = await page.title()
        print(f"Page title: {title}")
        
        # Check for mock ATS elements
        apply_btn = await page.query_selector("text=Apply for Senior Data Engineer")
        print(f"Apply button found: {apply_btn is not None}")
        
        await browser.close()
        print("✓ Browser test passed")

asyncio.run(test())
