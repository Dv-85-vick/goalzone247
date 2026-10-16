from flask import Flask, render_template, jsonify, request
import json, os

app = Flask(__name__)

def get_data():
    # NEVER call API at startup - just return empty if no file
    if not os.path.exists('data.json'):
        return {"dates": {}, "current_date": "", "api_calls_today": 0, "last_update": "Building at 02:00 AM WAT..."}
    try:
        with open('data.json') as f:
            return json.load(f)
    except:
        return {"dates": {}, "current_date": "", "api_calls_today": 0, "last_update": ""}

@app.route('/')
def index():
    d = get_data()
    selected = request.args.get('date', 'today') 
    date_data = d.get('dates', {}).get(selected)
    if not date_data:
        date_data = d.get('dates', {}).get('today', {})

    return render_template('index.html',
        data=d,
        selected_date=selected,
        dates=d.get('dates', {}),
        matches=date_data.get('matches', []),
        accas=date_data.get('accumulators', {}),
        date=date_data.get('date', ''),
        total=len(date_data.get('matches', [])),
        api_calls=d.get('api_calls_today', 0),
        last_update=d.get('last_update', '')
    )

@app.route('/api/refresh')
def refresh():
    from fetcher import build_data
    d = build_data()
    return jsonify({"status": "ok", "dates": list(d.get('dates', {}).keys()), "api_calls": d.get('api_calls_today', 0)})

@app.route('/api/live')
def live():
    from live_updater import update_live
    update_live()
    d = get_data()
    return jsonify(d)

# CRITICAL FIX FOR RENDER PORT
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)