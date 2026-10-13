from flask import Flask, render_template, jsonify
import json, os

app = Flask(__name__)

@app.route("/")
def home():
    try:
        with open("data.json","r") as f:
            data = json.load(f)
    except:
        data = {"individual":[],"free_accumulators":[],"premium_accumulators":[],"disclaimer":"Odds can go down. Fetched at 6am WAT"}
    return render_template("index.html", data=data)

@app.route("/api/data")
def api_data():
    try:
        with open("data.json","r") as f:
            return jsonify(json.load(f))
    except:
        return jsonify({})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
