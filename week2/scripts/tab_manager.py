import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


URLS = [
    "https://news.ycombinator.com",
    "https://github.com",
    "https://stackoverflow.com",
    "https://python.org",
    "https://playwright.dev",
]


async def open_tab(context, url: str) -> dict:
    page = await context.new_page()
    try:
        await page.goto(url, timeout=15000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        title = await page.title()
        return {"url": url, "title": title, "page": page, "error": None}
    except PlaywrightTimeoutError:
        return {"url": url, "title": None, "page": page, "error": "timeout"}
    except PlaywrightError as e:
        return {"url": url, "title": None, "page": page, "error": str(e)}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Open all 5 tabs in parallel
        print("Opening 5 tabs in parallel...")
        results = await asyncio.gather(*[open_tab(context, url) for url in URLS])

        print("\nTab titles captured:")
        for i, r in enumerate(results, 1):
            if r["error"]:
                print(f"  Tab {i}: {r['url']} — ERROR: {r['error']}")
            else:
                print(f"  Tab {i}: {r['title']}")

        # Close tabs 2–5, keep tab 1
        first_page = results[0]["page"]
        for r in results[1:]:
            await r["page"].close()
        print(f"\nClosed 4 tabs. Remaining: '{await first_page.title()}'")

        pages = context.pages
        print(f"Open pages in context: {len(pages)}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
