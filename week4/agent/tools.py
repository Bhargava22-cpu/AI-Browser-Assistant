import os
import queue
import re
import threading
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from langchain.tools import tool

_MAX_PAGE_TEXT_CHARS = 4000


class BrowserWorker:
    """Runs all Playwright calls in a single dedicated thread to avoid greenlet issues."""

    def __init__(self):
        self._task_queue = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        with sync_playwright() as p:
            headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            while True:
                fn, result_queue = self._task_queue.get()
                if fn is None:
                    browser.close()
                    break
                try:
                    result_queue.put(("ok", fn(page)))
                except PlaywrightError as e:
                    result_queue.put(("err", e))

    def run(self, fn):
        result_queue = queue.Queue()
        self._task_queue.put((fn, result_queue))
        status, value = result_queue.get()
        if status == "err":
            raise value
        return value

    def close(self):
        self._task_queue.put((None, None))
        self._thread.join(timeout=5)


_worker = BrowserWorker()


def get_worker() -> BrowserWorker:
    """Accessor for the shared browser worker, for callers outside the LangChain
    tool-call interface (e.g. modules/form_filling) that need direct Playwright access."""
    return _worker


@tool
def navigate_to(url: str) -> str:
    """Navigate the browser to a given URL. Input should be a full URL including https://"""
    def _fn(page):
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            return f"Navigated to {url} — page title: '{page.title()}'"
        except PlaywrightTimeoutError:
            return f"Timeout while navigating to {url}"
    return _worker.run(_fn)


@tool
def click_element(selector: str) -> str:
    """Click an element on the current page using a CSS selector."""
    def _fn(page):
        try:
            page.wait_for_selector(selector, timeout=8000)
            page.click(selector)
            return f"Clicked element: {selector}"
        except PlaywrightTimeoutError:
            return f"Timeout: element '{selector}' not found on page"
        except PlaywrightError as e:
            return f"Failed to click '{selector}': {e}"
    return _worker.run(_fn)


@tool
def type_text(input: str) -> str:
    """Type text into an element and press Enter to submit. Input format: 'selector|||text to type'. NOTE: this automatically presses Enter after typing — do NOT call click_element for a submit button after this."""
    parts = input.split("|||", 1)
    if len(parts) != 2:
        return "Invalid input. Use format: 'selector|||text to type'"
    selector, text = parts[0].strip(), parts[1].strip()

    def _fn(page):
        try:
            page.wait_for_selector(selector, timeout=8000)
            page.fill(selector, text)
            page.keyboard.press("Enter")
            return f"Typed '{text}' into '{selector}' and pressed Enter"
        except PlaywrightTimeoutError:
            return f"Timeout: element '{selector}' not found on page"
        except PlaywrightError as e:
            return f"Failed to type into '{selector}': {e}"
    return _worker.run(_fn)


@tool
def get_page_text(selector: str) -> str:
    """Read the visible text content of the current page, so you can actually see
    what's on it instead of guessing from the page title alone — use this to
    summarize an article, list search results, or answer questions about page
    content. Pass an empty string to read the whole page (body), or a CSS
    selector to read just one element/section. Long pages are truncated."""
    target = selector.strip() or "body"

    def _fn(page):
        try:
            page.wait_for_selector(target, timeout=8000)
            text = page.inner_text(target)
        except PlaywrightTimeoutError:
            return f"Timeout: element '{target}' not found on page"
        except PlaywrightError as e:
            return f"Failed to read '{target}': {e}"

        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            return "No visible text found."
        if len(text) > _MAX_PAGE_TEXT_CHARS:
            remaining = len(text) - _MAX_PAGE_TEXT_CHARS
            text = text[:_MAX_PAGE_TEXT_CHARS] + f"\n...(truncated, {remaining} more characters)"
        return text

    return _worker.run(_fn)


def close_browser():
    _worker.close()
