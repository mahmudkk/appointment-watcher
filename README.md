# Appointment Watcher

A small Telegram bot that watches an appointment booking portal you already have an account on and notifies you the moment a slot opens up. It only checks availability. It never books anything for you.

The target portal is described in a JSON file, so nothing in the code is tied to a specific site.

## How it works

1. Playwright opens a Chromium window and logs into the portal with your own account.
2. If the login page has a CAPTCHA, the bot does not try to solve it. It screenshots the CAPTCHA and sends it to you on Telegram. You reply with the characters and the bot types them in.
3. After login, the bot runs the navigation steps from your target file (choosing a location, category and so on) until it reaches the calendar page.
4. The browser session is kept in a persistent profile, so reloading the page normally does not trigger another login or CAPTCHA.
5. The page is re-checked every `POLL_INTERVAL_SECONDS`. When a slot is open, you get a Telegram alert and book it yourself.
6. If the session expires or something breaks, the bot tells you and starts a fresh login on the next cycle.

## Requirements

- Python 3.10+
- An account on the portal you want to watch
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Installation

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
cp target.example.json target.json
```

Windows (PowerShell):

```powershell
py -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
Copy-Item target.example.json target.json
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Configuration

### `.env`

| Variable | Required | Description |
| --- | --- | --- |
| `PORTAL_USERNAME` | yes | Your account username or email |
| `PORTAL_PASSWORD` | yes | Your account password |
| `TELEGRAM_BOT_TOKEN` | yes | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | yes | Your numeric Telegram chat ID |
| `TARGET_FILE` | no | Path to the target description (default: `target.json`) |
| `POLL_INTERVAL_SECONDS` | no | Seconds between checks (default: `300`) |
| `BROWSER_PROFILE_DIR` | no | Where the browser session is stored (default: `./browser_profile`) |
| `HEADLESS` | no | `true` to hide the browser window (default: `false`) |

Getting your Telegram chat ID: bots cannot start a conversation, so first send any message (for example `/start`) to your bot. Then open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and copy the number from `"chat":{"id": ...}`.

### `target.json`

Describes the portal. Start from `target.example.json`.

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | Label used in Telegram messages |
| `login_url` | yes | Login page |
| `alert_url` | no | Link sent in the alert (defaults to `login_url`) |
| `login.username_selector` | yes | CSS selector of the username field |
| `login.password_selector` | yes | CSS selector of the password field |
| `login.submit_selector` | yes | CSS selector of the login button |
| `login.success_selector` | yes | Element that only appears once logged in |
| `login.captcha_image_selector` | no | CAPTCHA image. Omit if the login has no CAPTCHA |
| `login.captcha_input_selector` | if CAPTCHA | Field for the CAPTCHA text |
| `steps` | no | Ordered actions to reach the calendar page |
| `availability.open_slot_selector` | yes | Element that exists only when a slot can be booked |
| `availability.no_slots_selector` | no | Element shown when nothing is available |

Each step has an `action` and a `selector`:

- `select`: choose a dropdown option by its visible label (`value`)
- `fill`: type `value` into a field
- `click`: click the element

Any selector can be a comma-separated list of alternatives. Playwright also supports text selectors such as `text=Continue`.

## Finding the selectors

Run the first time with `HEADLESS=false` and watch where the bot disagrees with the real page. To find a selector, open the page in your browser, press F12, right-click the element and choose Inspect, then copy a stable `id`, `name` or class.

`availability.open_slot_selector` decides whether an alert is sent, so test it carefully before trusting notifications.

## Running

```bash
python main.py
```

Leave it running in a terminal. You get a message on startup, whenever a CAPTCHA needs solving, and when a slot opens.

## Project structure

```
.
├── main.py                # Browser automation and Telegram bot
├── config.py              # Settings and target file loading
├── target.example.json    # Template for describing a portal
├── requirements.txt
├── .env.example
└── .gitignore
```

## Security

- Credentials are read from `.env` and typed only into the login page of the portal you configure.
- `.env`, `target.json` and `browser_profile/` are in `.gitignore`. Never commit them.
- The password is stored in plaintext on disk. Restrict access to the file (`chmod 600 .env` on macOS/Linux) and use a machine you trust.
- Anyone with your bot token can act as your bot. Keep it private.

## Disclaimer

This is a personal tool for individual use with your own account. Automated access may be restricted by a website's terms of use, so review them before pointing this at any portal. Keep the polling interval reasonable, do not use it to book or resell appointments for others, and stop if your account is rate-limited or flagged. Site changes will break selectors, so expect to recalibrate occasionally. The authors accept no responsibility for how it is used.
