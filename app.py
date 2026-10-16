from flask import Flask, render_template, jsonify, request
import json, os
from fetcher import build_data
from live_updater import update_live

app = Flask(__name__)

def get_data():
    # Auto-build at 2AM WAT if data.json missing
    if not os.path.exists('data.json'):
        try:
            print("No data.json - Building at 02:00 WAT...")
            return build_data()  # 58 calls - 42 leftover
        except Exception as e:
            print(f"Build failed: {e}")
            return {"dates": {}, "current_date": "", "api_calls_today": 0, "last_update": ""}
    try:
        with open('data.json') as f:
            return json.load(f)
    except:
        return {"dates": {}, "current_date": "", "api_calls_today": 0, "last_update": ""}

@app.route('/')
def index():
    d = get_data()
    
    # 4-Day Toggle: yesterday, today, tomorrow, next_tomorrow
    selected = request.args.get('date', 'today') 
    # Fallback to today if selected date has no data
    date_data = d.get('dates', {}).get(selected)
    if not date_data:
        date_data = d.get('dates', {}).get('today', {})

    return render_template('index.html',
        data=d,
        selected_date=selected,  # For highlighting active toggle
        dates=d.get('dates', {}),  # All 4 days: yesterday, today, tomorrow, next_tomorrow
        matches=date_data.get('matches', []),  # 50 matches for selected date
        accas=date_data.get('accumulators', {}),  # Free accas for selected date
        date=date_data.get('date', ''),
        total=len(date_data.get('matches', [])),
        api_calls=d.get('api_calls_today', 0),  # 73 total (58 build + 15 live) - 27 leftover
        last_update=d.get('last_update', '')
    )

@app.route('/api/refresh')
def refresh():
    # Manual refresh - builds all 4 days + Top 25 stats
    # 2AM WAT = 01:00 UTC cron: 0 1 * * * python fetcher.py
    d = build_data()
    return jsonify({
        "status": "ok", 
        "build_time": "02:00 AM WAT / 01:00 UTC - Fresh 100 quota",
        "dates": list(d.get('dates', {}).keys()),
        "api_calls": d.get('api_calls_today', 0),
        "stats_top": "25 (50 calls for stats) - Best of best filtered by real stats"
    })

@app.route('/api/live')
def live():
    # LiveScore - 1 call per update - Every 45 mins cron: */45 * * * * python live_updater.py
    update_live()
    d = get_data()
    return jsonify({
        "status": "live updated", 
        "api_calls": d.get('api_calls_today', 0),
        "selected": "Today's live scores with WIN/LOSE stickers"
    })

if __name__ == '__main__':
    app.run()