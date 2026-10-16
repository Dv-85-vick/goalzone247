from flask import Flask, render_template, jsonify
import json, os
from fetcher import build_data

app = Flask(__name__)

def load_data():
    try:
        if os.path.exists("data.json"):
            with open("data.json", "r") as f:
                return json.load(f)
    except:
        pass
    return build_data()

@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", data=data)

@app.route("/api/data")
def api_data():
    return jsonify(load_data())

@app.route("/api/refresh")
def refresh():
    data = build_data()
    # Optional: auto post to telegram
    try:
        from telegram_poster import send_telegram, format_daily_post
        send_telegram(format_daily_post(data))
    except:
        pass
    return jsonify({"status": "ok", "matches": len(data.get("individual", []))})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)