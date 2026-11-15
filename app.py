
from flask import Flask, render_template, jsonify, request
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"

HEADERS = (
    {"x-apisports-key": API_KEY}
    if API_KEY else {}
)

CACHE = {"data": None}

MARKET_LABELS = {
    "over15": "Over 1.5",
    "over25": "Over 2.5",
    "btts": "BTTS",
    "home_over15": "Home Over 1.5",
    "away_over15": "Away Over 1.5"
}


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

        if response.status_code != 200:
            return []

        return response.json().get("response", [])

    except (requests.RequestException, ValueError):
        return []


def parse_odds(data):

    markets = {}

    if not data:
        return markets

    try:
        for bookmaker in data.get("bookmakers", []):

            for bet in bookmaker.get("bets", []):

                name = bet.get("name", "").lower()

                for value in bet.get("values", []):

                    try:
                        odd = float(value.get("odd", 0))
                    except (TypeError, ValueError):
                        continue

                    val = str(value.get("value", "")).lower()

                    if odd <= 1:
                        continue

                    if "over/under" in name:

                        if val == "over 1.5":
                            markets.setdefault("over15", odd)

                        elif val == "over 2.5":
                            markets.setdefault("over25", odd)

                    if "both teams to score" in name:

                        if val == "yes":
                            markets.setdefault("btts", odd)

                    if "home team" in name and "over 1.5" in val:
                        markets.setdefault("home_over15", odd)

                    if "away team" in name and "over 1.5" in val:
                        markets.setdefault("away_over15", odd)

        return markets

    except (KeyError, TypeError, ValueError):
        return markets


def build_all():

    today = datetime.now()

    dates = {
        "yesterday": (
            today - timedelta(days=1)
        ).strftime("%Y-%m-%d"),

        "today": today.strftime("%Y-%m-%d"),

        "tomorrow": (
            today + timedelta(days=1)
        ).strftime("%Y-%m-%d"),

        "next_tomorrow": (
            today + timedelta(days=2)
        ).strftime("%Y-%m-%d")
    }

    all_data = {}

    api_calls = 0

    for key, date_string in dates.items():

        fixtures = api_get(
            "fixtures",
            {"date": date_string}
        )
        api_calls += 1

        odds_list = api_get(
            "odds",
            {"date": date_string}
        )
        api_calls += 1

        odds_map = {}

        for item in odds_list:

            fixture_id = (
                item.get("fixture", {}).get("id")
            )

            if fixture_id:
                odds_map[fixture_id] = item

        matches = []

        # ONLY FIXTURES RETURNED BY API-FOOTBALL.
        # NO HARDCODED TEAMS.
        # NO DEMONSTRATION MATCHES.
        # NO FAKE FIXTURES.

        for fx in fixtures[:50]:

            try:

                fixture_id = fx["fixture"]["id"]

                home = fx["teams"]["home"]["name"]
                away = fx["teams"]["away"]["name"]

                league = fx["league"]["name"]

                fixture_date = fx["fixture"]["date"]

                status_data = fx["fixture"]["status"]

                goals = fx.get("goals", {})

                markets = parse_odds(
                    odds_map.get(fixture_id)
                )

                over15 = markets.get("over15")

                rank = (
                    10 - (over15 - 1.0) * 2
                    if over15 is not None
                    else 0
                )

                matches.append({

                    "fixture_id": fixture_id,

                    "league": league,

                    "home": home,

                    "away": away,

                    "time": fixture_date[11:16],

                    "status": status_data.get("short", "NS"),

                    "score_home": goals.get("home") or 0,

                    "score_away": goals.get("away") or 0,

                    "elapsed": status_data.get("elapsed") or 0,

                    "markets": markets,

                    "score_rank": rank

                })

            except (KeyError, TypeError, ValueError):
                continue

        matches.sort(
            key=lambda x: x["score_rank"],
            reverse=True
        )

        accas = generate_accumulators(matches)

        all_data[key] = {

            "date": date_string,

            "matches": matches,

            "accumulators": accas

        }

    return {

        "dates": all_data,

        "current_date": dates["today"],

        "last_update": datetime.now().isoformat(),

        "api_calls_today": api_calls

    }


def generate_accumulators(matches):

    def build_single_market(market_key, target_odds):

        legs = []

        used = set()

        total = 1.0

        sorted_matches = sorted(
            matches,
            key=lambda x: x["markets"].get(
                market_key, 999
            )
        )

        for match in sorted_matches:

            fixture_id = match["fixture_id"]

            if fixture_id in used:
                continue

            odd = match["markets"].get(market_key)

            # Never use invented odds.
            if odd is None:
                continue

            legs.append({

                "fixture_id": fixture_id,

                "home": match["home"],

                "away": match["away"],

                "league": match["league"],

                "market": market_key,

                "market_label": MARKET_LABELS[market_key],

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

        for match in matches:

            for market_key in MARKET_LABELS:

                odd = match["markets"].get(market_key)

                if odd is None:
                    continue

                pool.append({

                    "fid": match["fixture_id"],

                    "home": match["home"],

                    "away": match["away"],

                    "league": match["league"],

                    "market": market_key,

                    "market_label": MARKET_LABELS[market_key],

                    "odd": odd,

                    "rank": match["score_rank"],

                    "time": match["time"]

                })

        pool.sort(
            key=lambda x: (
                x["rank"],
                -1 / x["odd"]
            ),
            reverse=True
        )

        for item in pool:

            fixture_id = item["fid"]

            # A match can appear only once in a mixed acca.
            if fixture_id in used:
                continue

            legs.append({

                "fixture_id": fixture_id,

                "home": item["home"],

                "away": item["away"],

                "league": item["league"],

                "market": item["market"],

                "market_label": item["market_label"],

                "odd": item["odd"],

                "time": item["time"]

            })

            used.add(fixture_id)

            total *= item["odd"]

            if total >= target_odds:
                break

        return {

            "legs": legs,

            "total_odds": round(total, 2),

            "count": len(legs),

            "target": target_odds

        }

    accas = {}

    for market_key in MARKET_LABELS:

        accas[market_key] = {

            "3": build_single_market(
                market_key, 3.0
            ),

            "6": build_single_market(
                market_key, 6.0
            )

        }

    accas["mix"] = {

        "10": build_mix(10.0),

        "20": build_mix(20.0)

    }

    return accas


def get_data():

    global CACHE

    if CACHE["data"] is not None:
        return CACHE["data"]

    data = build_all()

    CACHE["data"] = data

    return data


@app.route("/")
def index():

    data = get_data()

    selected_date = request.args.get(
        "date", "today"
    )

    if selected_date not in data["dates"]:
        selected_date = "today"

    selected_data = data["dates"][selected_date]

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


@app.route("/api/refresh")
def refresh():

    global CACHE

    CACHE["data"] = None

    data = get_data()

    return jsonify({

        "status": "ok",

        "today": len(
            data["dates"]["today"]["matches"]
        )

    })


@app.route("/api/live")
def live():

    return jsonify(get_data())


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
