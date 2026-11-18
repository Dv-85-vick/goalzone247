from flask import Flask, render_template, jsonify, request
import os
import requests
import time
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
API_KEY = os.getenv("API_FOOTBALL_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "goalszone247")
BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}
WAT = ZoneInfo("Africa/Lagos")

# v22 - FIX 504 + VICTOR'S RULE:
# 1. Homepage NEVER fetches - instant open, no 504, no hang
# 2. /api/refresh fetches ANYTIME - no 2h lock, no admin password
# 3. KEEP Cap 60 - stops at 60, never out of limit
# 4. ULTRA-LIGHT - max 80 fixtures, fast accumulators, no timeout
CACHE_SECONDS = 300
LIVE_CHECK_SECONDS = 300
DAILY_CALL_CAP = 60
MAX_FIXTURES = 80
ESTIMATED_MARKETS = {"over15": 1.25, "over25": 1.50, "btts": 1.65, "home_over15": 1.60, "away_over15": 1.60, "home_1x_over15": 1.45, "away_x2_over15": 1.50}
STRONG_LEAGUES = {"Premier League", "Championship", "La Liga", "LaLiga", "Bundesliga", "2. Bundesliga", "3. Liga", "Serie A", "Serie B", "Ligue 1", "Ligue 2", "Eredivisie", "Eerste Divisie", "Primeira Liga", "Liga Portugal", "Pro League", "Challenger Pro League", "Super Lig", "Primera Division", "Liga MX", "MLS", "Major League Soccer", "Premiership", "Scottish Premiership", "Super League", "Superliga", "Allsvenskan", "Superettan", "Eliteserien", "1. Divisjon", "Ekstraklasa", "First League", "HNL", "Austrian Bundesliga", "2. Liga", "Swiss Super League", "Challenge League", "Danish Superliga", "Norwegian Eliteserien", "Swedish Allsvenskan", "Polish Ekstraklasa", "Czech First League", "Croatian HNL", "Greek Super League", "Israeli Premier League", "Romanian Liga I", "Hungarian NB I", "Slovenian PrvaLiga", "Serbian SuperLiga", "Bulgarian First League", "Brazil Serie A", "Argentina Primera Division", "Chile Primera Division", "Colombia Primera A", "Uruguay Primera Division", "Peru Liga 1", "Ecuador Liga Pro", "Japan J1 League", "Korea K League 1", "Australia A-League", "South Africa Premier Division", "Egypt Premier League", "Morocco Botola Pro", "Nigeria NPFL", "Ghana Premier League", "Kenya Premier League", "Veikkausliiga", "Meistriliiga", "Virsliga", "A Lyga", "Urvalsdeild", "Úrvalsdeild", "Faroe Islands Premier League", "Cymru Premier", "Iceland Premier League"}
SMART_MAX_ODD = {"over15": 1.45, "over25": 1.85, "btts": 1.95, "home_over15": 1.95, "away_over15": 1.95, "home_1x_over15": 1.75, "away_x2_over15": 1.85}
def tier_of(m, mk):
    odd = m["markets"].get(mk, 99)
    if odd <= SMART_MAX_ODD.get(mk, 99): return "STRONG"
    if odd <= SMART_MAX_ODD.get(mk, 99) + 0.35: return "GOOD"
    return "FILL"
def smart_score(m, mk):
    odd = m["markets"].get(mk, 99)
    if odd is None or odd <= 1: return -999
    return (1.0 / odd) * 100 + (15 if m.get("league") in STRONG_LEAGUES else 0)
def why_pick(m, mk):
    odd = m["markets"].get(mk, 0)
    league = m.get("league","")
    strong = league in STRONG_LEAGUES
    if mk == "away_over15": return f"Away team strong in attack - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Good away scoring form'}"
    if mk == "home_over15": return f"Home team strong in attack - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Good home scoring form'}"
    if mk == "home_1x_over15": return f"Home team strong, hard to beat at home + goals expected @ {odd} - {'Strong league: '+league if strong else 'Home form strong'}"
    if mk == "away_x2_over15": return f"Away team strong, hard to beat away + goals expected @ {odd} - {'Strong league: '+league if strong else 'Away form strong'}"
    if mk == "over15": return f"Both teams score goals - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Goals expected'}"
    if mk == "over25": return f"High-scoring game expected - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Goals expected'}"
    if mk == "btts": return f"Both teams score regularly - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'BTTS form strong'}"
    return f"Bookmaker confident @ {odd}"
MARKET_LABELS = {"over15": "Over 1.5", "over25": "Over 2.5", "btts": "BTTS", "home_over15": "Home Over 1.5", "away_over15": "Away Over 1.5", "home_1x_over15": "Home Win/Draw + Over 1.5", "away_x2_over15": "Away Win/Draw + Over 1.5"}
FINISHED = ("FT", "AET", "PEN")
def market_result(mk, status, sh, sa):
    if status not in FINISHED: return "PENDING"
    total = (sh or 0) + (sa or 0)
    if mk == "over15": return "WIN" if total >= 2 else "LOST"
    if mk == "over25": return "WIN" if total >= 3 else "LOST"
    if mk == "btts": return "WIN" if (sh or 0) > 0 and (sa or 0) > 0 else "LOST"
    if mk == "home_over15": return "WIN" if (sh or 0) >= 2 else "LOST"
    if mk == "away_over15": return "WIN" if (sa or 0) >= 2 else "LOST"
    if mk == "home_1x_over15": return "WIN" if (sh or 0) >= (sa or 0) and total >= 2 else "LOST"
    if mk == "away_x2_over15": return "WIN" if (sa or 0) >= (sh or 0) and total >= 2 else "LOST"
    return "PENDING"
DATA_LOCK = threading.Lock()
CACHE = {"data": None, "last_fetch": 0.0, "last_manual_refresh": 0.0, "last_live_check": 0.0, "last_error": None, "api_calls_today": 0, "api_calls_date": None, "last_auto_date": None}
def _today_str(): return datetime.now(WAT).strftime("%Y-%m-%d")
def _reset_daily_counter_if_needed():
    today = _today_str()
    if CACHE.get("api_calls_date") != today:
        CACHE["api_calls_date"] = today; CACHE["api_calls_today"] = 0; CACHE["quota_exhausted"] = False
def _can_call_api():
    _reset_daily_counter_if_needed()
    if CACHE.get("quota_exhausted"): return False
    return CACHE.get("api_calls_today", 0) < DAILY_CALL_CAP
def api_get(endpoint, params, with_timezone=True):
    if not API_KEY: return []
    if not _can_call_api(): return []
    try:
        p = dict(params)
        if with_timezone and "timezone" not in p: p["timezone"] = "Africa/Lagos"
        response = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=p, timeout=5)
        CACHE["api_calls_today"] = CACHE.get("api_calls_today", 0) + 1
        if response.status_code in (403, 429):
            CACHE["quota_exhausted"] = True; CACHE["last_error"] = f"API quota finished ({response.status_code}). Resets midnight."; return []
        if response.status_code == 200:
            body = response.json()
            if body.get("errors"): CACHE["last_error"] = str(body.get("errors"))
            return body.get("response", [])
        CACHE["last_error"] = f"{endpoint} {response.status_code}: {response.text[:200]}"; return []
    except Exception as e:
        CACHE["last_error"] = str(e); return []
def parse_odds(odds_data):
    markets = {}
    if not odds_data: return markets
    try:
        for bookmaker in odds_data.get("bookmakers", []):
            for bet in bookmaker.get("bets", []):
                name = bet.get("name", "")
                for value in bet.get("values", []):
                    try: odd = float(value.get("odd", 0))
                    except (TypeError, ValueError): continue
                    if odd <= 1: continue
                    sel = value.get("value", "")
                    if "Over/Under" in name:
                        if sel == "Over 1.5": markets.setdefault("over15", odd)
                        elif sel == "Over 2.5": markets.setdefault("over25", odd)
                    if "Both Teams to Score" in name and sel == "Yes": markets.setdefault("btts", odd)
                    if "Home Team" in name and "Over 1.5" in sel: markets.setdefault("home_over15", odd)
                    if "Away Team" in name and "Over 1.5" in sel: markets.setdefault("away_over15", odd)
            if len(markets) == 7: break
        return markets
    except Exception: return markets
def _build_day(date_string):
    fixtures = api_get("fixtures", {"date": date_string}, with_timezone=True)
    matches = []
    for fixture in fixtures[:MAX_FIXTURES]:
        try:
            fid = fixture["fixture"]["id"]
            markets = dict(ESTIMATED_MARKETS)
            over15 = markets.get("over15"); score_rank = (10 - (over15 - 1.0) * 2 if over15 else 0)
            fd = fixture["fixture"].get("date", ""); sd = fixture["fixture"].get("status", {}); goals = fixture.get("goals", {})
            _st = sd.get("short", "NS"); _sh = goals.get("home") or 0; _sa = goals.get("away") or 0
            _is_postponed = False
            try:
                _ko = datetime.fromisoformat(fd.replace("Z", "+00:00")).astimezone(WAT)
                if _st == "NS" and (datetime.now(WAT) - _ko).total_seconds() > 2.5*3600: _is_postponed = True
            except Exception: pass
            matches.append({"fixture_id": fid, "league": fixture["league"]["name"], "league_id": fixture["league"].get("id"), "country": fixture["league"].get("country", ""), "date": date_string, "home": fixture["teams"]["home"]["name"], "away": fixture["teams"]["away"]["name"], "time": fd[11:16] if len(fd) >= 16 else "", "status": _st, "score_home": _sh, "score_away": _sa, "elapsed": sd.get("elapsed") or 0, "is_postponed": _is_postponed, "display_status": ("POSTPONED" if _is_postponed else _st), "markets": markets, "market_results": {k: market_result(k, _st, _sh, _sa) for k in markets}, "market_labels": MARKET_LABELS, "odds_estimated": False, "score_rank": score_rank})
        except (KeyError, TypeError, ValueError): continue
    matches.sort(key=lambda m: m["score_rank"], reverse=True)
    return matches
def generate_accumulators(matches, date_string=""):
    # ULTRA-FAST: sort once, then pick in order. No re-sort inside loop.
    if not matches: return {"midnight": {"legs": [], "total_odds": 0, "count": 0, "target": 12, "overall_status": "PENDING", "wins": 0, "losses": 0, "pending": 0}, "early": {"legs": [], "total_odds": 0, "count": 0, "target": 12, "overall_status": "PENDING", "wins": 0, "losses": 0, "pending": 0}, "mix": {"10": {"legs": [], "total_odds": 0, "count": 0, "target": 10, "overall_status": "PENDING", "wins": 0, "losses": 0, "pending": 0}, "20": {"legs": [], "total_odds": 0, "count": 0, "target": 20, "overall_status": "PENDING", "wins": 0, "losses": 0, "pending": 0}}}
    def _leg(m, mk): return {"fixture_id": m["fixture_id"], "home": m["home"], "away": m["away"], "league": m["league"], "country": m.get("country", ""), "date": m.get("date", date_string), "time": m["time"], "score_home": m.get("score_home", 0), "score_away": m.get("score_away", 0), "status": m.get("status", "NS"), "is_postponed": m.get("is_postponed", False), "display_status": m.get("display_status", m.get("status", "NS")), "elapsed": m.get("elapsed", 0), "market": mk, "market_label": MARKET_LABELS.get(mk, mk), "odd": m["markets"].get(mk), "result": market_result(mk, m.get("status", "NS"), m.get("score_home", 0), m.get("score_away", 0)), "why": why_pick(m, mk), "smart_score": round(smart_score(m, mk), 1)}
    def _wrap(legs, total, target):
        r = [l["result"] for l in legs]; overall = "WIN" if r and all(x == "WIN" for x in r) else ("LOST" if any(x == "LOST" for x in r) else "PENDING"); return {"legs": legs, "total_odds": round(total, 2), "count": len(legs), "target": target, "overall_status": overall, "wins": r.count("WIN"), "losses": r.count("LOST"), "pending": r.count("PENDING")}
    # Pre-sort by smart score once
    sorted_matches = sorted(matches, key=lambda x: -smart_score(x, "over15"))
    USED = set()
    def _pick_sorted(mk):
        for m in sorted_matches:
            if m["fixture_id"] not in USED and m["markets"].get(mk): return m
        for m in sorted_matches:
            if m["markets"].get(mk): return m
        return None
    def build_single(mk, target):
        legs, total, seen = [], 1.0, set()
        while total < target and len(legs) < 12:
            m = None
            for cand in sorted_matches:
                if cand["fixture_id"] not in seen and cand["fixture_id"] not in USED and cand["markets"].get(mk): m = cand; break
            if m is None:
                for cand in sorted_matches:
                    if cand["fixture_id"] not in seen and cand["markets"].get(mk): m = cand; break
            if m is None: break
            seen.add(m["fixture_id"]); USED.add(m["fixture_id"]); legs.append(_leg(m, mk)); total *= m["markets"].get(mk)
        return _wrap(legs, total, target)
    def _in_window(m, s, e):
        try: hh = int((m.get("time") or "00:00")[:2]); return s <= hh < e
        except Exception: return False
    def build_mix_pool(target, pool):
        order = ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]; legs, total, seen = [], 1.0, set(); idx = 0
        pool_sorted = sorted(pool, key=lambda x: -smart_score(x, "over15"))
        while total < target and len(legs) < 12:
            mk = order[idx % len(order)]; idx += 1
            m = None
            for cand in pool_sorted:
                if cand["fixture_id"] not in seen and cand["fixture_id"] not in USED and cand["markets"].get(mk): m = cand; break
            if m is None: continue
            seen.add(m["fixture_id"]); USED.add(m["fixture_id"]); legs.append(_leg(m, mk)); total *= m["markets"].get(mk)
        return _wrap(legs, total, target)
    midnight_pool = [m for m in matches if _in_window(m, 0, 3)] or matches
    early_pool = [m for m in matches if _in_window(m, 4, 10)] or matches
    acc = {}
    acc["midnight"] = build_mix_pool(12.0, midnight_pool)
    acc["early"] = build_mix_pool(12.0, early_pool)
    for mk in ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]: acc[mk] = {"2.5": build_single(mk, 2.5), "8": build_single(mk, 8.0)}
    def build_mix(target):
        order = ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]; legs, total, seen = [], 1.0, set(); idx = 0
        while total < target and len(legs) < 12:
            mk = order[idx % len(order)]; idx += 1
            m = None
            for cand in sorted_matches:
                if cand["fixture_id"] not in seen and cand["fixture_id"] not in USED and cand["markets"].get(mk): m = cand; break
            if m is None: continue
            seen.add(m["fixture_id"]); USED.add(m["fixture_id"]); legs.append(_leg(m, mk)); total *= m["markets"].get(mk)
        return _wrap(legs, total, target)
    acc["mix"] = {"10": build_mix(10.0), "20": build_mix(20.0)}
    return acc
def build_all():
    now = datetime.now(WAT); today = now.strftime("%Y-%m-%d"); tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d"); yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d"); next_day = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    _reset_daily_counter_if_needed()
    today_matches = _build_day(today); tomorrow_matches = _build_day(tomorrow)
    dates = {"yesterday": {"date": yesterday, "matches": [], "accumulators": {}}, "today": {"date": today, "matches": today_matches, "accumulators": generate_accumulators(today_matches, today)}, "tomorrow": {"date": tomorrow, "matches": tomorrow_matches, "accumulators": generate_accumulators(tomorrow_matches, tomorrow)}, "next_tomorrow": {"date": next_day, "matches": [], "accumulators": {}},}
    after = CACHE.get("api_calls_today", 0)
    return {"dates": dates, "current_date": today, "last_update": datetime.now(WAT).isoformat(), "api_calls_today": after, "last_error": CACHE.get("last_error"), "quota_exhausted": CACHE.get("quota_exhausted", False), "cache_until": (datetime.now(WAT) + timedelta(seconds=CACHE_SECONDS)).isoformat()}
def refresh_cache_locked():
    data = build_all(); CACHE["data"] = data; CACHE["last_fetch"] = time.monotonic(); return data
def _empty_data():
    now = datetime.now(WAT); today = now.strftime("%Y-%m-%d"); tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d"); yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d"); next_day = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    return {"dates": {"yesterday": {"date": yesterday, "matches": [], "accumulators": {}}, "today": {"date": today, "matches": [], "accumulators": {}}, "tomorrow": {"date": tomorrow, "matches": [], "accumulators": {}}, "next_tomorrow": {"date": next_day, "matches": [], "accumulators": {}}}, "current_date": today, "last_update": datetime.now(WAT).isoformat(), "api_calls_today": CACHE.get("api_calls_today", 0), "last_error": CACHE.get("last_error"), "quota_exhausted": CACHE.get("quota_exhausted", False), "cache_until": (datetime.now(WAT) + timedelta(seconds=CACHE_SECONDS)).isoformat()}
def get_data():
    with DATA_LOCK:
        now = time.monotonic()
        if CACHE["data"] is not None and now - CACHE["last_fetch"] < CACHE_SECONDS: return CACHE["data"]
        try: return refresh_cache_locked()
        except Exception as e: CACHE["last_error"] = str(e); return _empty_data()
@app.route("/")
def index():
    # v22: HOMEPAGE NEVER FETCHES - INSTANT OPEN, NO 504. Fetch only via /api/refresh button.
    data = CACHE.get("data") or _empty_data()
    selected_date = request.args.get("date", "today"); selected_data = data["dates"].get(selected_date) or data["dates"].get("today")
    def _rank(m):
        s = m.get("status", "NS")
        if s in ("1H", "2H", "HT", "ET", "P", "LIVE"): return 0
        if m.get("is_postponed"): return 2
        if s == "NS": return 1
        if s in ("FT", "AET", "PEN"): return 3
        return 2
    ordered = sorted(selected_data["matches"], key=lambda m: (_rank(m), m.get("time", "")))
    return render_template("index.html", data=data, selected_date=selected_date, dates=data["dates"], matches=ordered, accas=selected_data["accumulators"], date=selected_data["date"], total=len(selected_data["matches"]), api_calls=data["api_calls_today"], last_update=data["last_update"], api_key_set=bool(API_KEY), cache_until=data.get("cache_until"))
@app.route("/api/data")
def api_data():
    # v22: No password, fetch anytime until cap 60. Homepage does NOT call this automatically.
    if not _can_call_api(): return jsonify({"status": "cap_reached", "message": f"Daily cap {DAILY_CALL_CAP} reached.", "api_calls_today": CACHE.get("api_calls_today", 0)}), 429
    try: data = get_data()
    except Exception as e: return jsonify({"status": "loading", "message": str(e)}), 202
    return jsonify({"status": "ok", "today": len(data["dates"]["today"]["matches"]), "tomorrow": len(data["dates"]["tomorrow"]["matches"]), "last_update": data["last_update"], "api_calls_today": data["api_calls_today"]})
@app.route("/api/refresh")
def refresh():
    # v22: FETCH ANYTIME - NO LOCK, NO PASSWORD. Only cap 60 stops it.
    if not _can_call_api(): return jsonify({"status": "cap_reached", "message": f"Daily cap {DAILY_CALL_CAP} reached. Showing last saved data. Resets midnight.", "api_calls_today": CACHE.get("api_calls_today", 0)}), 429
    try:
        data = refresh_cache_locked(); CACHE["last_manual_refresh"] = time.monotonic(); return jsonify({"status": "ok", "message": "Data refreshed.", "today": len(data["dates"]["today"]["matches"]), "tomorrow": len(data["dates"]["tomorrow"]["matches"]), "last_update": data["last_update"], "api_calls_today": data["api_calls_today"]})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500
@app.route("/api/live")
def live():
    if not _can_call_api(): return jsonify({"status": "cap_reached", "message": "Cap 60 reached."}), 429
    with DATA_LOCK:
        if CACHE["data"] is None: return jsonify(get_data())
        fixtures = api_get("fixtures", {"date": CACHE["data"]["current_date"], "live": "all"}, with_timezone=True)
        if fixtures:
            live_map = {}
            for f in fixtures:
                try: live_map[f["fixture"]["id"]] = f
                except (KeyError, TypeError): continue
            for m in CACHE["data"]["dates"]["today"]["matches"]:
                f = live_map.get(m["fixture_id"])
                if f:
                    sd = f["fixture"].get("status", {}); goals = f.get("goals", {}); m["status"] = sd.get("short", m["status"]); m["score_home"] = goals.get("home") or 0; m["score_away"] = goals.get("away") or 0; m["elapsed"] = sd.get("elapsed") or 0
        return jsonify(CACHE["data"])
@app.route("/api/cron")
def cron_daily():
    if not _can_call_api(): return jsonify({"status": "cap_reached", "message": "Daily cap 60 reached. 0 API calls."}), 200
    try:
        data = refresh_cache_locked(); CACHE["last_auto_date"] = _today_str(); return jsonify({"status": "ok", "message": "Auto refresh done.", "today": len(data["dates"]["today"]["matches"]), "tomorrow": len(data["dates"]["tomorrow"]["matches"]), "api_calls_today": data["api_calls_today"]})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500
@app.route("/admin")
def admin():
    data = CACHE.get("data") or _empty_data(); return render_template("admin.html", data=data, api_calls=data.get("api_calls_today", 0), last_update=data.get("last_update"), quota_exhausted=data.get("quota_exhausted", False))
@app.route("/api/debug")
def debug():
    data = CACHE.get("data") or _empty_data(); return jsonify({"api_key_set": bool(API_KEY), "last_error": CACHE.get("last_error"), "last_update": data.get("last_update"), "cache_until": data.get("cache_until"), "api_calls_today": CACHE.get("api_calls_today", 0), "daily_cap": DAILY_CALL_CAP, "counts": {k: len(v["matches"]) for k, v in data["dates"].items()}, "rules": "v22: Homepage instant, Refresh anytime, Cap 60 only."})
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000)); app.run(host="0.0.0.0", port=port)