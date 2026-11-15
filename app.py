from flask import Flask, render_template, jsonify, request
import os
import requests
import time
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}
WAT = ZoneInfo("Africa/Lagos")

CACHE_SECONDS = 7200
LIVE_CHECK_SECONDS = 300
DAILY_CALL_CAP = 80
ESTIMATED_MARKETS = {"over15": 1.28, "over25": 1.75, "btts": 1.80, "home_over15": 1.90, "away_over15": 2.20, "home_1x_over15": 1.55, "away_x2_over15": 1.60}
MARKET_LABELS = {"over15": "Over 1.5", "over25": "Over 2.5", "btts": "BTTS", "home_over15": "Home Over 1.5", "away_over15": "Away Over 1.5", "home_1x_over15": "Home Win/Draw + Over 1.5", "away_x2_over15": "Away Win/Draw + Over 1.5"}
FINISHED = ("FT", "AET", "PEN")
def market_result(market_key, status, sh, sa):
    if status not in FINISHED:
        return "PENDING"
    total = (sh or 0) + (sa or 0)
    if market_key == "over15": return "WIN" if total >= 2 else "LOST"
    if market_key == "over25": return "WIN" if total >= 3 else "LOST"
    if market_key == "btts": return "WIN" if (sh or 0) > 0 and (sa or 0) > 0 else "LOST"
    if market_key == "home_over15": return "WIN" if (sh or 0) >= 2 else "LOST"
    if market_key == "away_over15": return "WIN" if (sa or 0) >= 2 else "LOST"
    if market_key == "home_1x_over15": return "WIN" if (sh or 0) >= (sa or 0) and total >= 2 else "LOST"
    if market_key == "away_x2_over15": return "WIN" if (sa or 0) >= (sh or 0) and total >= 2 else "LOST"
    return "PENDING"

DATA_LOCK = threading.Lock()
CACHE = {"data": None, "last_fetch": 0.0, "last_manual_refresh": 0.0, "last_live_check": 0.0, "last_error": None, "api_calls_today": 0, "api_calls_date": None}

def _today_str():
    return datetime.now(WAT).strftime("%Y-%m-%d")

def _reset_daily_counter_if_needed():
    today = _today_str()
    if CACHE.get("api_calls_date") != today:
        CACHE["api_calls_date"] = today
        CACHE["api_calls_today"] = 0

def _can_call_api():
    _reset_daily_counter_if_needed()
    return CACHE.get("api_calls_today", 0) < DAILY_CALL_CAP

def api_get(endpoint, params, with_timezone=True):
    if not API_KEY:
        print("API_FOOTBALL_KEY is missing.")
        return []
    if not _can_call_api():
        print(f"DAILY CAP REACHED: {CACHE['api_calls_today']}/{DAILY_CALL_CAP} - serving cached data, no API call.")
        return []
    try:
        p = dict(params)
        if with_timezone and "timezone" not in p:
            p["timezone"] = "Africa/Lagos"
        response = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=p, timeout=20)
        CACHE["api_calls_today"] = CACHE.get("api_calls_today", 0) + 1
        print(f"API {endpoint} params={p} -> status={response.status_code} | calls_today={CACHE['api_calls_today']}/{DAILY_CALL_CAP}")
        if response.status_code == 200:
            body = response.json()
            if body.get("errors"):
                print(f"API {endpoint} body errors: {body.get('errors')}")
                CACHE["last_error"] = str(body.get("errors"))
            results = body.get("response", [])
            print(f"API {endpoint} returned {len(results)} items")
            return results
        print(f"API {endpoint} failed {response.status_code}: {response.text[:500]}")
        CACHE["last_error"] = f"{endpoint} {response.status_code}: {response.text[:300]}"
        return []
    except requests.RequestException as e:
        print(f"API error {endpoint}: {e}")
        CACHE["last_error"] = str(e)
        return []
    except Exception as e:
        print(f"Unexpected API error {endpoint}: {e}")
        CACHE["last_error"] = str(e)
        return []

def parse_odds(odds_data):
    markets = {}
    if not odds_data:
        return markets
    try:
        for bookmaker in odds_data.get("bookmakers", []):
            for bet in bookmaker.get("bets", []):
                name = bet.get("name", "")
                low_name = name.lower()
                for value in bet.get("values", []):
                    try:
                        odd = float(value.get("odd", 0))
                    except (TypeError, ValueError):
                        continue
                    if odd <= 1:
                        continue
                    sel = value.get("value", "")
                    low_sel = str(sel).lower()
                    if "Over/Under" in name:
                        if sel == "Over 1.5":
                            markets.setdefault("over15", odd)
                        elif sel == "Over 2.5":
                            markets.setdefault("over25", odd)
                    if "Both Teams to Score" in name and sel == "Yes":
                        markets.setdefault("btts", odd)
                    if "Home Team" in name and "Over 1.5" in sel:
                        markets.setdefault("home_over15", odd)
                    if "Away Team" in name and "Over 1.5" in sel:
                        markets.setdefault("away_over15", odd)
                    is_combo_bet = ("double chance" in low_name) or ("1x" in low_name) or ("x2" in low_name) or ("win or draw" in low_name)
                    is_over15 = ("over 1.5" in low_sel) or ("1.5" in low_sel and "over" in low_sel)
                    if is_combo_bet and is_over15 and "under" not in low_sel:
                        is_1x = ("1x" in low_sel) or ("home" in low_sel and "draw" in low_sel) or ("home win or draw" in low_name and "away" not in low_sel)
                        is_x2 = ("x2" in low_sel) or ("2x" in low_sel) or ("away" in low_sel and "draw" in low_sel) or ("away win or draw" in low_name and "home" not in low_sel)
                        if is_1x:
                            markets.setdefault("home_1x_over15", odd)
                        elif is_x2:
                            markets.setdefault("away_x2_over15", odd)
            if len(markets) >= 7:
                break
        return markets
    except Exception:
        return markets

def _build_day(date_string, with_odds):
    fixtures = api_get("fixtures", {"date": date_string}, with_timezone=True)
    if len(fixtures) == 0:
        print(f"No fixtures for {date_string} with Lagos TZ, retrying UTC...")
        fixtures = api_get("fixtures", {"date": date_string, "timezone": "UTC"}, with_timezone=False)
    if len(fixtures) == 0:
        print(f"Still 0 for {date_string}, retrying no timezone...")
        fixtures = api_get("fixtures", {"date": date_string}, with_timezone=False)
    odds_map = {}
    if with_odds:
        odds_list = api_get("odds", {"date": date_string}, with_timezone=True)
        for item in odds_list:
            try:
                odds_map[item["fixture"]["id"]] = item
            except (KeyError, TypeError):
                continue
    matches = []
    for fixture in fixtures[:500]:
        try:
            fid = fixture["fixture"]["id"]
            markets = parse_odds(odds_map.get(fid)) if with_odds else {}
            is_estimated = False
            if not markets:
                markets = dict(ESTIMATED_MARKETS)
                is_estimated = True
            over15 = markets.get("over15")
            score_rank = (10 - (over15 - 1.0) * 2 if over15 else 0)
            fd = fixture["fixture"].get("date", "")
            sd = fixture["fixture"].get("status", {})
            goals = fixture.get("goals", {})
            _sh = goals.get("home") or 0; _sa = goals.get("away") or 0; _st = sd.get("short", "NS")
            _results = {k: market_result(k, _st, _sh, _sa) for k in markets}
            matches.append({
                "fixture_id": fid, "league": fixture["league"]["name"], "league_id": fixture["league"].get("id"),
                "country": fixture["league"].get("country", ""),
                "date": date_string,
                "home": fixture["teams"]["home"]["name"], "away": fixture["teams"]["away"]["name"],
                "time": fd[11:16] if len(fd) >= 16 else "", "status": _st,
                "score_home": _sh, "score_away": _sa,
                "elapsed": sd.get("elapsed") or 0, "markets": markets,
                "market_results": _results, "market_labels": MARKET_LABELS,
                "odds_estimated": is_estimated, "score_rank": score_rank
            })
        except (KeyError, TypeError, ValueError):
            continue
    matches.sort(key=lambda m: m["score_rank"], reverse=True)
    print(f"{date_string}: fixtures={len(fixtures)} matches={len(matches)} odds_called={with_odds}")
    return matches

def generate_accumulators(matches, date_string=""):
    def _leg(m, mk):
        odd = m["markets"].get(mk)
        return {"fixture_id": m["fixture_id"], "home": m["home"], "away": m["away"],
                "league": m["league"], "country": m.get("country", ""), "date": m.get("date", date_string), "time": m["time"],
                "score_home": m.get("score_home", 0), "score_away": m.get("score_away", 0), "status": m.get("status", "NS"),
                "market": mk, "market_label": MARKET_LABELS.get(mk, mk), "odd": odd,
                "result": market_result(mk, m.get("status", "NS"), m.get("score_home", 0), m.get("score_away", 0))}
    def _wrap(legs, total, target):
        results = [l["result"] for l in legs]
        if results and all(r == "WIN" for r in results):
            overall = "WIN"
        elif any(r == "LOST" for r in results):
            overall = "LOST"
        else:
            overall = "PENDING"
        return {"legs": legs, "total_odds": round(total, 2), "count": len(legs), "target": target,
                "overall_status": overall, "wins": results.count("WIN"), "losses": results.count("LOST"), "pending": results.count("PENDING")}
    def build_single(mk, target):
        legs, used, total = [], set(), 1.0
        for m in sorted(matches, key=lambda x: x["markets"].get(mk, 99)):
            fid = m["fixture_id"]
            if fid in used: continue
            if not m["markets"].get(mk): continue
            legs.append(_leg(m, mk)); used.add(fid); total *= m["markets"][mk]
            if total >= target: break
        return _wrap(legs, total, target)
    def build_mix(target):
        legs, used, total, pool = [], set(), 1.0, []
        for m in matches:
            for mk in ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]:
                odd = m["markets"].get(mk)
                if odd: pool.append((m, mk))
        pool.sort(key=lambda x: (x[0]["score_rank"], -x[0]["markets"][x[1]]), reverse=True)
        for m, mk in pool:
            if m["fixture_id"] in used: continue
            legs.append(_leg(m, mk)); used.add(m["fixture_id"]); total *= m["markets"][mk]
            if total >= target: break
        return _wrap(legs, total, target)
    acc = {}
    for mk in ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]:
        acc[mk] = {"3": build_single(mk, 3.0), "6": build_single(mk, 6.0)}
    acc["mix"] = {"10": build_mix(10.0), "20": build_mix(20.0)}
    return acc

def build_all():
    now = datetime.now(WAT)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    _reset_daily_counter_if_needed()
    before = CACHE.get("api_calls_today", 0)
    today_matches = _build_day(today, with_odds=True)
    tomorrow_matches = _build_day(tomorrow, with_odds=True)
    dates = {
        "yesterday": {"date": yesterday, "matches": [], "accumulators": {}},
        "today": {"date": today, "matches": today_matches, "accumulators": generate_accumulators(today_matches, today)},
        "tomorrow": {"date": tomorrow, "matches": tomorrow_matches, "accumulators": generate_accumulators(tomorrow_matches, tomorrow)},
        "next_tomorrow": {"date": next_day, "matches": [], "accumulators": {}},
    }
    after = CACHE.get("api_calls_today", 0)
    print(f"FULL REFRESH DONE: used {after-before} API calls this refresh, total today {after}/{DAILY_CALL_CAP}")
    return {"dates": dates, "current_date": today, "last_update": datetime.now(WAT).isoformat(), "api_calls_today": after, "last_error": CACHE.get("last_error"), "cache_until": (datetime.now(WAT) + timedelta(seconds=CACHE_SECONDS)).isoformat()}

def refresh_cache_locked():
    data = build_all()
    CACHE["data"] = data
    CACHE["last_fetch"] = time.monotonic()
    return data

def get_data():
    with DATA_LOCK:
        now = time.monotonic()
        if CACHE["data"] is not None and now - CACHE["last_fetch"] < CACHE_SECONDS:
            remaining = int(CACHE_SECONDS - (now - CACHE["last_fetch"]))
            print(f"CACHE HIT: serving cached data, {remaining}s left in 2h lock. No API call.")
            return CACHE["data"]
        print("CACHE EXPIRED (2h) or empty - doing full refresh...")
        return refresh_cache_locked()

def refresh_live_scores_only():
    with DATA_LOCK:
        if CACHE["data"] is None:
            return get_data()
        now = time.monotonic()
        if now - CACHE.get("last_live_check", 0) < LIVE_CHECK_SECONDS:
            return CACHE["data"]
        today_matches = CACHE["data"]["dates"]["today"]["matches"]
        has_live = any(m["status"] in ("1H", "2H", "HT", "ET", "P", "LIVE") for m in today_matches)
        if not has_live:
            print("LIVE CHECK: no live matches right now, skipping API call.")
            CACHE["last_live_check"] = now
            return CACHE["data"]
        print("LIVE CHECK: live matches found, fetching Today fixtures only (1 call, no odds)...")
        CACHE["last_live_check"] = now
        fixtures = api_get("fixtures", {"date": CACHE["data"]["current_date"], "live": "all"}, with_timezone=True)
        if not fixtures:
            return CACHE["data"]
        live_map = {}
        for f in fixtures:
            try:
                live_map[f["fixture"]["id"]] = f
            except (KeyError, TypeError):
                continue
        for m in today_matches:
            f = live_map.get(m["fixture_id"])
            if f:
                sd = f["fixture"].get("status", {})
                goals = f.get("goals", {})
                m["status"] = sd.get("short", m["status"])
                m["score_home"] = goals.get("home") or 0
                m["score_away"] = goals.get("away") or 0
                m["elapsed"] = sd.get("elapsed") or 0
                m["market_results"] = {k: market_result(k, m["status"], m["score_home"], m["score_away"]) for k in m.get("markets", {})}
        CACHE["data"]["dates"]["today"]["accumulators"] = generate_accumulators(today_matches, CACHE["data"]["current_date"])
        return CACHE["data"]

@app.route("/")
def index():
    data = get_data()
    selected_date = request.args.get("date", "today")
    selected_data = data["dates"].get(selected_date) or data["dates"].get("today")
    return render_template("index.html", data=data, selected_date=selected_date, dates=data["dates"], matches=selected_data["matches"], accas=selected_data["accumulators"], date=selected_data["date"], total=len(selected_data["matches"]), api_calls=data["api_calls_today"], last_update=data["last_update"], api_key_set=bool(API_KEY), cache_until=data.get("cache_until"))

@app.route("/api/refresh")
def refresh():
    with DATA_LOCK:
        now = time.monotonic()
        if CACHE["data"] is not None and now - CACHE["last_fetch"] < CACHE_SECONDS:
            remaining = int(CACHE_SECONDS - (now - CACHE["last_fetch"]))
            return jsonify({"status": "locked", "message": f"Already refreshed. Next refresh in {remaining//60} minutes. Everyone sees the same data.", "retry_after_seconds": remaining, "cache_until": CACHE["data"].get("cache_until")}), 429
        if not _can_call_api():
            return jsonify({"status": "cap_reached", "message": f"Daily cap {DAILY_CALL_CAP} reached. Showing last saved data.", "api_calls_today": CACHE.get("api_calls_today", 0)}), 429
        data = refresh_cache_locked()
        CACHE["last_manual_refresh"] = time.monotonic()
        return jsonify({"status": "ok", "message": "Data refreshed successfully.", "today": len(data["dates"]["today"]["matches"]), "tomorrow": len(data["dates"]["tomorrow"]["matches"]), "last_update": data["last_update"], "api_calls_today": data["api_calls_today"]})

@app.route("/api/live")
def live():
    data = refresh_live_scores_only()
    return jsonify(data)

@app.route("/api/debug")
def debug():
    data = CACHE.get("data") or get_data()
    return jsonify({"api_key_set": bool(API_KEY), "last_error": CACHE.get("last_error"), "last_update": data.get("last_update"), "cache_until": data.get("cache_until"), "api_calls_today": CACHE.get("api_calls_today", 0), "daily_cap": DAILY_CALL_CAP, "counts": {k: len(v["matches"]) for k, v in data["dates"].items()}, "rules": "Odds: Today+Tomorrow only. Cache: 2h lock. Live: Today only, 5 min, no odds. Combos: 1X+Over1.5, X2+Over1.5."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)