import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


PROFILE_PATH = Path(__file__).parent.parent.parent / "week1" / "data" / "user_profile.json"
SCREENSHOT_PATH = Path(__file__).parent.parent / "screenshots" / "form_filled.png"

GENDER_SELECTORS = {"Male": "gender-radio-1", "Female": "gender-radio-2", "Other": "gender-radio-3"}
HOBBY_SELECTORS = {"Sports": "hobbies-checkbox-1", "Reading": "hobbies-checkbox-2", "Music": "hobbies-checkbox-3"}


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Profile not found: {PROFILE_PATH}")
    with open(PROFILE_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid profile JSON: {e.msg}", e.doc, e.pos)


async def dismiss_modal(page) -> None:
    """Close any Bootstrap ad/overlay modal that blocks clicks on demoqa."""
    try:
        close_btn = page.locator(".modal.show .close, .modal.show button[aria-label='Close']")
        if await close_btn.count() > 0:
            await close_btn.first.click(timeout=3000)
            await page.wait_for_selector(".modal.show", state="hidden", timeout=5000)
    except PlaywrightTimeoutError:
        pass  # no modal visible — continue normally


async def fill_form(page, profile: dict) -> None:
    await page.goto("https://demoqa.com/automation-practice-form", timeout=20000)
    await page.wait_for_selector("#firstName", timeout=10000)

    # Name
    name_parts = profile.get("name", "").split(" ", 1)
    await page.fill("#firstName", name_parts[0] if name_parts else "")
    await page.fill("#lastName", name_parts[1] if len(name_parts) > 1 else "")

    # Contact
    await page.fill("#userEmail", profile.get("email", ""))
    phone_digits = profile.get("phone", "").replace("+91-", "").replace("-", "")[:10]
    await page.fill("#userNumber", phone_digits)

    # Gender — read from profile, fall back to Male
    gender = profile.get("gender", "Male")
    gender_id = GENDER_SELECTORS.get(gender, "gender-radio-1")
    await page.click(f"label[for='{gender_id}']")

    # Date of birth — Escape closes the picker without risking form submission
    await page.click("#dateOfBirthInput")
    await page.fill("#dateOfBirthInput", profile.get("date_of_birth", ""))
    await page.keyboard.press("Escape")

    # Subjects — click the autocomplete option instead of pressing Enter
    for subject in profile.get("subjects", []):
        await page.fill("#subjectsInput", subject)
        await page.wait_for_selector(".subjects-auto-complete__option", timeout=5000)
        await page.click(".subjects-auto-complete__option")

    # Hobbies — read list from profile
    for hobby in profile.get("hobbies", []):
        checkbox_id = HOBBY_SELECTORS.get(hobby)
        if checkbox_id:
            await page.click(f"label[for='{checkbox_id}']")

    # Current address
    addr = profile.get("address", {})
    address_str = f"{addr.get('street', '')}, {addr.get('city', '')}"
    await page.fill("#currentAddress", address_str)

    # State and city — use form_address from profile (demoqa-compatible values)
    form_addr = profile.get("form_address", {})
    state = form_addr.get("state", "")
    city = form_addr.get("city", "")

    await page.click("#state")
    await page.type("#state input", state, delay=100)
    await page.wait_for_selector("[id^='react-select'][id*='option']", timeout=8000)
    await page.keyboard.press("Enter")

    await page.click("#city")
    await page.type("#city input", city, delay=100)
    await page.wait_for_selector("[id^='react-select'][id*='option']", timeout=8000)
    await page.keyboard.press("Enter")


async def main():
    profile = load_profile()

    async with async_playwright() as p:
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        try:
            await fill_form(page, profile)
        except PlaywrightTimeoutError as e:
            print(f"Timeout — element took too long to appear: {e}")
            await browser.close()
            return
        except PlaywrightError as e:
            print(f"Browser error during form fill: {e}")
            await browser.close()
            return

        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        print(f"Screenshot saved to {SCREENSHOT_PATH}")

        print("Form filled — review before submitting. Waiting 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
