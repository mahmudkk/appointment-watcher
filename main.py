import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import BufferedInputFile, Message
from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PWTimeoutError

from config import load_settings, load_target

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("appointment_watcher")

settings = load_settings()
target = load_target(settings.target_file)

bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()

captcha_reply_queue: asyncio.Queue[str] = asyncio.Queue()
awaiting_captcha = asyncio.Event()


@dp.message(F.text)
async def handle_message(message: Message) -> None:
    if message.chat.id != settings.telegram_chat_id:
        return
    if awaiting_captcha.is_set():
        await captcha_reply_queue.put(message.text.strip())
        awaiting_captcha.clear()
        await message.reply("Got it, submitting...")
    else:
        await message.reply("No CAPTCHA is pending right now.")


async def notify(text: str) -> None:
    await bot.send_message(settings.telegram_chat_id, text)


async def ask_user_to_solve_captcha(page: Page, selector: str) -> str:
    captcha_el = page.locator(selector)
    await captcha_el.wait_for(state="visible", timeout=15_000)
    screenshot_bytes = await captcha_el.screenshot()

    awaiting_captcha.set()
    await bot.send_photo(
        settings.telegram_chat_id,
        BufferedInputFile(screenshot_bytes, filename="captcha.png"),
        caption=f"CAPTCHA needed to log in to {target['name']}. Reply with the characters you see.",
    )
    return await captcha_reply_queue.get()


async def log_in(page: Page) -> None:
    login = target["login"]
    log.info("Opening %s", target["login_url"])
    await page.goto(target["login_url"], wait_until="networkidle")

    await page.locator(login["username_selector"]).fill(settings.username)
    await page.locator(login["password_selector"]).fill(settings.password)

    if login.get("captcha_image_selector"):
        answer = await ask_user_to_solve_captcha(page, login["captcha_image_selector"])
        await page.locator(login["captcha_input_selector"]).fill(answer)

    await page.locator(login["submit_selector"]).click()

    try:
        await page.locator(login["success_selector"]).wait_for(timeout=20_000)
        log.info("Logged in.")
    except PWTimeoutError:
        raise RuntimeError(
            "Login did not reach the expected page. Check the selectors or the CAPTCHA answer."
        )


async def run_steps(page: Page) -> None:
    for step in target.get("steps", []):
        locator = page.locator(step["selector"])
        action = step["action"]
        if action == "select":
            await locator.select_option(label=step["value"])
        elif action == "fill":
            await locator.fill(step["value"])
        elif action == "click":
            await locator.click()
        await page.wait_for_load_state("networkidle")


async def slots_are_available(page: Page) -> bool:
    availability = target["availability"]
    no_slots = availability.get("no_slots_selector")
    if no_slots and await page.locator(no_slots).count() > 0:
        return False
    return await page.locator(availability["open_slot_selector"]).count() > 0


async def watch_loop() -> None:
    Path(settings.browser_profile_dir).mkdir(parents=True, exist_ok=True)
    alert_url = target.get("alert_url") or target["login_url"]

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            settings.browser_profile_dir,
            headless=settings.headless,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        ready = False
        await notify(f"Watcher started for {target['name']}.")

        while True:
            try:
                if not ready:
                    await log_in(page)
                    await run_steps(page)
                    ready = True
                else:
                    await page.reload(wait_until="networkidle")

                if await slots_are_available(page):
                    await notify(
                        f"A slot appears to be open on {target['name']}. Book it now:\n{alert_url}"
                    )
                    log.info("Slot found, alert sent.")
                else:
                    log.info("No slots yet.")

            except Exception as exc:
                log.exception("Error during check, will retry next cycle: %s", exc)
                ready = False
                await notify(f"Watcher hit an error and will retry: {exc}")

            await asyncio.sleep(settings.poll_interval_seconds)


async def main() -> None:
    await asyncio.gather(
        dp.start_polling(bot),
        watch_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
