import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    username: str
    password: str
    telegram_bot_token: str
    telegram_chat_id: int
    target_file: str
    poll_interval_seconds: int
    browser_profile_dir: str
    headless: bool


def load_settings() -> Settings:
    return Settings(
        username=_require("PORTAL_USERNAME"),
        password=_require("PORTAL_PASSWORD"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=int(_require("TELEGRAM_CHAT_ID")),
        target_file=os.getenv("TARGET_FILE", "target.json"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        browser_profile_dir=os.getenv("BROWSER_PROFILE_DIR", "./browser_profile"),
        headless=os.getenv("HEADLESS", "false").lower() == "true",
    )


def _check_keys(section: dict, keys: list[str], label: str) -> None:
    missing = [k for k in keys if not section.get(k)]
    if missing:
        raise RuntimeError(f"Target file: '{label}' is missing {', '.join(missing)}")


def load_target(path: str) -> dict:
    file = Path(path)
    if not file.exists():
        raise RuntimeError(
            f"Target file not found: {path}. Copy target.example.json to {path} and edit it."
        )
    data = json.loads(file.read_text(encoding="utf-8"))

    _check_keys(data, ["name", "login_url", "login", "availability"], "root")
    _check_keys(
        data["login"],
        ["username_selector", "password_selector", "submit_selector", "success_selector"],
        "login",
    )
    if data["login"].get("captcha_image_selector"):
        _check_keys(data["login"], ["captcha_input_selector"], "login")
    _check_keys(data["availability"], ["open_slot_selector"], "availability")

    for i, step in enumerate(data.get("steps", [])):
        _check_keys(step, ["action", "selector"], f"steps[{i}]")
        if step["action"] not in {"select", "click", "fill"}:
            raise RuntimeError(f"Target file: steps[{i}] has unknown action '{step['action']}'")
        if step["action"] in {"select", "fill"} and "value" not in step:
            raise RuntimeError(f"Target file: steps[{i}] needs a 'value'")
    return data
