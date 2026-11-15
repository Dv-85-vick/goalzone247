
import os
import json
import requests

from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv


# ==========================================
# CONFIGURATION
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

WAT = ZoneInfo("Africa/Lagos")

SITE_URL = "https://goalzone247.com"


# ==========================================
# SEND TELEGRAM MESSAGE
# ==========================================

def send_telegram(text):

    if not BOT_TOKEN or not CHANNEL_ID:

        print("Telegram not configured.")

        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:

        response = requests.post(
            url,
            data=payload,
            timeout=15
        )

        print(
            f"Telegram HTTP status: {response.status_code}"
        )

        try:
            result = response.json()
        except ValueError:
            result = {}

        if response.status_code == 200 and result.get("ok"):

            print("Telegram message sent successfully.")

            return True

        print(
            "Telegram rejected message:",
            result.get("description", response.text[:300])
        )

        return False

    except requests.RequestException as error:

        print(f"Telegram connection error: {error}")

        return False

    except Exception as error:

        print(f"Telegram error: {error}")

        return False


# ==========================================
# GET TODAY'S MATCHES
# ==========================================

def get_today_matches(data):

    # New nested format.
    dates = data.get("dates", {})

    if isinstance(dates, dict):

        today_data = dates.get("today", {})

        if isinstance(today_data, dict):

            matches = today_data.get("matches", [])

            if isinstance(matches, list):
                return matches

    # Legacy flat format.
    matches = data.get("matches", [])

    if isinstance(matches, list):
        return matches

    return []


# ==========================================
# FORMAT DAILY TELEGRAM POST
# ==========================================

def format_daily_post(data):

    matches = get_today_matches(data)

    date_str = datetime.now(WAT).strftime("%d %b %Y")

    count = len(matches)

    return f"""⚽ <b>GoalZone24/7 - {date_str}</b>

🔥 <b>{count} MATCHES ANALYZED</b>

🆓 <b>3 FREE ACCAS OPEN ON SITE</b>

🔗 {SITE_URL}

🔒 <b>Premium Membership</b>
Weekly: ₦8,000
Monthly: ₦28,000

📊 High Goal Leagues Only

⚽ Visit GoalZone24/7 for today's predictions.
"""


# ==========================================
# MAIN
# ==========================================

def main():

    try:

        if not os.path.exists("data.json"):

            print("data.json not found.")

            return

        with open(
            "data.json",
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        message = format_daily_post(data)

        send_telegram(message)

    except json.JSONDecodeError:

        print("data.json contains invalid JSON.")

    except Exception as error:

        print(f"Telegram posting error: {error}")


if __name__ == "__main__":

    main()
