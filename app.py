
from flask import Flask, render_template, jsonify, request
import os
import requests
import time
import threading

from datetime import datetime, timedelta

app = Flask(__name__)

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
} if API_KEY else {}


# ==========================================
# REQUEST COOLDOWN SETTINGS
# ==========================================

API_COOLDOWN_SECONDS = 60
MANUAL_REFRESH_COOLDOWN_SECONDS = 120

# One lock prevents overlapping API batches
# inside the same running Python instance.
DATA_LOCK = threading.Lock()

CACHE = {
    "data": None,
    "last_fetch": 0.0,
    "last_manual_refresh": 0.0
}


# ==========================================
# FOOTBALL API REQUEST
# ==========================================

def api_get(endpoint, params):
    if not API_KEY:
        return []

    try:
        response = requests.get(
            f"{BASE}/{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=15
        )

        if response.status_code == 200:
            return response.json().get("response", [])

        return []

    except requests.RequestException:
        return []

    except Exception:
        return []


# ==========================================
# REAL BOOKMAKER ODDS ONLY
# ==========================================

def parse_odds(odds_data):
    markets = {}

    if not odds_data:
        return markets

    try:
        bookmakers = odds_data.get("bookmakers", [])

        for bookmaker in bookmakers:
            for bet in bookmaker.get("bets", []):
                name = bet.get("name", "")

                for value in bet.get("values", []):
                    try:
                        odd = float(value.get("odd", 0))
                    except (TypeError, ValueError):
                        continue

                    if odd <= 1:
                        continue

                    selection = value.get("value", "")

                    if "Over/Under" in name:
                        if selection == "Over 1.5":
                            markets.setdefault("over15", odd)

                        elif selection == "Over 2.5":
                            markets.setdefault("over25", odd)

                    if (
                        "Both Teams to Score" in name
                        and selection == "Yes"
                    ):
                        markets.setdefault("btts", odd)

                    if (
                        "Home Team" in name
                        and "Over 1.5" in selection
                    ):
                        markets.setdefault("home_over15", odd)

                    if (
                        "Away Team" in name
                        and "Over 1.5" in selection
                    ):
                        markets.setdefault("away_over15", odd)

            # Stop once the required markets have been found.
            if len(markets) == 5:
                break

        return markets

    except Exception:
        return markets


# ==========================================
# BUILD FIXTURES AND ACCUMULATORS
# ==========================================

def build_all():

    now = datetime.now()

    dates = {
        "yesterday": (
            now - timedelta(days=1)
        ).strftime("%Y-%m-%d"),

        "today": now.strftime("%Y-%m-%d"),

        "tomorrow": (
            now + timedelta(days=1)
        ).strftime("%Y-%m-%d"),

        "next_tomorrow": (
            now + timedelta(days=2)
        ).strftime("%Y-%m-%d")
    }

    all_data = {}
    api_calls = 0

    for key, date_string in dates.items():

        fixtures = api_get(
            "fixtures",
            {"date": date_string}
        )

        if API_KEY:
            api_calls += 1

        odds_list = api_get(
            "odds",
            {"date": date_string}
        )

        if API_KEY:
            api_calls += 1

        odds_map = {}

        for item in odds_list:
            try:
                fixture_id = item["fixture"]["id"]
                odds_map[fixture_id] = item
            except (KeyError, TypeError):
                continue

        matches = []

        for fixture in fixtures[:50]:

            try:
                fixture_id = fixture["fixture"]["id"]

                markets = parse_odds(
                    odds_map.get(fixture_id)
                )

                # Do not display fixtures without any
                # actual supported bookmaker markets.
                if not markets:
                    continue

                over15 = markets.get("over15")

                score_rank = (
                    10 - (over15 - 1.0) * 2
                    if over15 else 0
                )

                fixture_date = fixture["fixture"].get(
                    "date", ""
                )

                status_data = fixture["fixture"].get(
                    "status", {}
                )

                goals = fixture.get("goals", {})

                matches.append({
                    "fixture_id": fixture_id,

                    "league": fixture["league"]["name"],

                    "home": fixture["teams"]["home"]["name"],

                    "away": fixture["teams"]["away"]["name"],

                    "time": fixture_date[11:16],

                    "status": status_data.get("short", "NS"),

                    "score_home": goals.get("home") or 0,

                    "score_away": goals.get("away") or 0,

                    "elapsed": status_data.get("elapsed") or 0,

                    "markets": markets,

                    "score_rank": score_rank
                })

            except (KeyError, TypeError, ValueError):
                continue

        matches.sort(
            key=lambda match: match["score_rank"],
            reverse=True
        )

        # No demo fixtures are inserted.
        # An empty list means no qualifying real fixtures.

        accumulators = generate_accumulators(matches)

        all_data[key] = {
            "date": date_string,
            "matches": matches,
            "accumulators": accumulators
        }

    return {
        "dates": all_data,
        "current_date": dates["today"],
        "last_update": datetime.now().isoformat(),
        "api_calls_today": api_calls
    }


# ==========================================
# ACCUMULATOR GENERATOR
# ==========================================

def generate_accumulators(matches):

    def build_single_market(market_key, target_odds):

        legs = []
        used = set()
        total = 1.0

        sorted_matches = sorted(
            matches,
            key=lambda match: match["markets"].get(
                market_key, 99
            )
        )

        for match in sorted_matches:

            fixture_id = match["fixture_id"]

            if fixture_id in used:
                continue

            odd = match["markets"].get(market_key)

            if not odd:
                continue

            legs.append({
                "fixture_id": fixture_id,
                "home": match["home"],
                "away": match["away"],
                "league": match["league"],
                "market": market_key,
                "odd": odd,
                "time": match["time"]
            })

            used.add(fixture_id)
            total *= odd

            if total >= target_odds:
                break

        return {
            "legs": legs,
            "total_odds": round(total, 2),
            "count": len(legs),
            "target": target_odds
        }

    def build_mix(target_odds):

        legs = []
        used = set()
        total = 1.0
        pool = []

        market_keys = [
            "over15",
            "over25",
            "btts",
            "home_over15",
            "away_over15"
        ]

        for match in matches:

            for market_key in market_keys:

                odd = match["markets"].get(market_key)

                if not odd:
                    continue

                pool.append({
                    "fid": match["fixture_id"],
                    "home": match["home"],
                    "away": match["away"],
                    "league": match["league"],
                    "market": market_key,
                    "odd": odd,
                    "rank": match["score_rank"],
                    "time": match["time"]
                })

        pool.sort(
            key=lambda item: (
                item["rank"],
                -item["odd"]
            ),
            reverse=True
        )

        for selection in pool:

            fixture_id = selection["fid"]

            # A fixture can appear only once in a mixed accumulator.
            if fixture_id in used:
                continue

            legs.append({
                "fixture_id": fixture_id,
                "home": selection["home"],
                "away": selection["away"],
                "league": selection["league"],
                "market": selection["market"],
                "odd": selection["odd"],
                "time": selection["time"]
            })

            used.add(fixture_id)
            total *= selection["odd"]

            if total >= target_odds:
                break

        return {
            "legs": legs,
            "total_odds": round(total, 2),
            "count": len(legs),
            "target": target_odds
        }

    accumulators = {}

    for market_key in [
        "over15",
        "over25",
        "btts",
        "home_over15",
        "away_over15"
    ]:

        accumulators[market_key] = {
            "3": build_single_market(market_key, 3.0),
            "6": build_single_market(market_key, 6.0)
        }

    accumulators["mix"] = {
        "10": build_mix(10.0),
        "20": build_mix(20.0)
    }

    return accumulators


# ==========================================
# CACHE REFRESH
# This function must be called while DATA_LOCK
# is already held.
# ==========================================

def refresh_cache_locked():

    data = build_all()

    CACHE["data"] = data

    # Start the cooldown after the API batch finishes.
    CACHE["last_fetch"] = time.monotonic()

    return data


# ==========================================
# GET CACHED DATA
# ==========================================

def get_data():

    with DATA_LOCK:

        now = time.monotonic()

        cache_exists = CACHE["data"] is not None

        cooldown_active = (
            cache_exists
            and now - CACHE["last_fetch"] < API_COOLDOWN_SECONDS
        )

        if cooldown_active:
            return CACHE["data"]

        return refresh_cache_locked()


# ==========================================
# MAIN WEBSITE
# ==========================================

@app.route("/")
def index():

    data = get_data()

    selected_date = request.args.get(
        "date", "today"
    )

    selected_data = (
        data["dates"].get(selected_date)
        or data["dates"].get("today")
    )

    return render_template(
        "index.html",
        data=data,
        selected_date=selected_date,
        dates=data["dates"],
        matches=selected_data["matches"],
        accas=selected_data["accumulators"],
        date=selected_data["date"],
        total=len(selected_data["matches"]),
        api_calls=data["api_calls_today"],
        last_update=data["last_update"],
        api_key_set=bool(API_KEY)
    )


# ==========================================
# MANUAL REFRESH
# Maximum one successful manual refresh
# every 120 seconds in this Python instance.
# ==========================================

@app.route("/api/refresh")
def refresh():

    with DATA_LOCK:

        now = time.monotonic()

        last_manual = CACHE["last_manual_refresh"]

        manual_remaining = (
            MANUAL_REFRESH_COOLDOWN_SECONDS
            - (now - last_manual)
        )

        if last_manual and manual_remaining > 0:

            return jsonify({
                "status": "cooldown",
                "message": "Please wait before refreshing again.",
                "retry_after_seconds": int(
                    manual_remaining + 0.99
                )
            }), 429

        last_fetch = CACHE["last_fetch"]

        api_remaining = (
            API_COOLDOWN_SECONDS
            - (now - last_fetch)
        )

        if CACHE["data"] is not None and api_remaining > 0:

            return jsonify({
                "status": "cooldown",
                "message": "The data was refreshed recently. Please wait.",
                "retry_after_seconds": int(
                    api_remaining + 0.99
                )
            }), 429

        data = refresh_cache_locked()

        CACHE["last_manual_refresh"] = time.monotonic()

        return jsonify({
            "status": "ok",
            "message": "Data refreshed successfully.",
            "today": len(data["dates"]["today"]["matches"]),
            "last_update": data["last_update"]
        })


# ==========================================
# LIVE DATA
# Returns cached data; does not force an API call.
# ==========================================

@app.route("/api/live")
def live():

    return jsonify(get_data())


# ==========================================
# START APPLICATION
# ==========================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
