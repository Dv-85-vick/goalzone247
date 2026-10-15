import os, requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

def send_telegram(text):
    if not BOT_TOKEN or not CHANNEL_ID:
        print("Telegram not configured")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=10)
        print(f"Telegram status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def format_daily_post(data):
    count = len(data.get('individual', []))
    date_str = datetime.now().strftime('%d %b %Y')
    return f"""⚽ <b>GoalZone24/7 - {date_str}</b>
🔥 {count} LIVE MATCHES ANALYZED

🆓 3 FREE ACCAS OPEN ON SITE
🔗 goalzone247.com

🔒 Premium: Weekly ₦8k / Monthly ₦28k
📊 High Goal Leagues Only
"""

if __name__ == "__main__":
    import json
    try:
        with open("data.json") as f:
            data = json.load(f)
        text = format_daily_post(data)
        send_telegram(text)
    except Exception as e:
        print(f"Error: {e}")
