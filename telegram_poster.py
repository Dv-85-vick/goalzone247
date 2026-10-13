import os, requests
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

def send_telegram(text):
    if not BOT_TOKEN or not CHANNEL_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except:
        return False

def format_daily_post(data):
    return f"⚽ <b>GoalZone24/7 - {datetime.now().strftime('%d %b')}</b>\n🔗 goalzone247.com\n🆓 3 FREE ACCAS OPEN\n🔒 Premium: Weekly ₦8k / Monthly ₦28k"
