import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


async def scrape_hn_titles(page) -> list[dict]:
    await page.goto("https://news.ycombinator.com", timeout=15000)
    await page.wait_for_selector(".athing", timeout=10000)

    items = await page.query_selector_all(".athing")
    results = []
    for item in items[:5]:
        title_el = await item.query_selector(".titleline > a")
        if not title_el:
            continue
        title = await title_el.inner_text()
        results.append({"title": title})
    return results


async def main():
    output_path = Path(__file__).parent.parent / "data" / "articles.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            articles = await scrape_hn_titles(page)
        except PlaywrightTimeoutError as e:
            print(f"Timeout while loading page: {e}")
            await browser.close()
            return
        except PlaywrightError as e:
            print(f"Browser error while scraping: {e}")
            await browser.close()
            return

        if not articles:
            print("No articles found — page structure may have changed")
            await browser.close()
            return

        await browser.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(articles, f, indent=2)

    print(f"Saved {len(articles)} articles to {output_path}")
    for i, a in enumerate(articles, 1):
        print(f"  {i}. {a['title']}")


if __name__ == "__main__":
    asyncio.run(main())
