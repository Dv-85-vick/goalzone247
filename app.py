from flask import Flask, render_template, jsonify
import json, os
from fetcher import build_data
from live_updater import update_live

app = Flask(__name__)

def get_data():
    try:
        with open('data.json') as f:
            return json.load(f)
    except:
        return {"matches": [], "accumulators": {}, "date": "2026-10-16", "api_calls_today": 0, "last_update": ""}

@app.route('/')
def index():
    d = get_data()
    return render_template('index.html',
        data=d,
        matches=d.get('matches', []),
        accas=d.get('accumulators', {}),
        date=d.get('date'),
        total=len(d.get('matches', [])),
        api_calls=d.get('api_calls_today', 0),
        last_update=d.get('last_update', '')
    )

@app.route('/api/refresh')
def refresh():
    d = build_data()
    return jsonify({"status": "ok", "matches": len(d['matches']), "api_calls": d['api_calls_today']})

@app.route('/api/live')
def live():
    update_live()
    d = get_data()
    return jsonify({"status": "live updated", "api_calls": d['api_calls_today']})

if __name__ == '__main__':
    app.run()