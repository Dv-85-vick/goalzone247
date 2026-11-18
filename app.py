from flask import Flask, render_template, jsonify, request
import os, requests, time, threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}
WAT = ZoneInfo("Africa/Lagos")

# ===== VICTOR'S FINAL RULES =====
# Today + Tomorrow ONLY. Never Yesterday / Next.
# Fetch anytime, NO lock. Cap 60/day. Full refresh = 2 calls. Live = 1 call. No odds endpoint.
DAILY_CAP = 60
EST = {"over15": 1.25, "over25": 1.50, "btts": 1.65, "home_over15": 1.60, "away_over15": 1.60, "home_1x_over15": 1.45, "away_x2_over15": 1.50}
MARKETS = list(EST.keys())

# ===== MAJOR + HIGH-GOAL LEAGUES - FOCUS HERE =====
MAJOR_LEAGUES = {39,140,135,78,61,40,94,88,144,203,71,253,262}
HIGH_GOAL_LEAGUES = {88,78,144,218,207,179,119,113,103,203,253,71,128,262,135,140,39}
FOCUS_LEAGUES = MAJOR_LEAGUES | HIGH_GOAL_LEAGUES

LOCK = threading.Lock()
CACHE = {"data": None, "api_calls_today": 0, "api_calls_date": None, "last_live": 0.0}

def today_str():
    return datetime.now(WAT).strftime("%Y-%m-%d")

def reset_counter():
    t = today_str()
    if CACHE.get("api_calls_date") != t:
        CACHE["api_calls_date"] = t
        CACHE["api_calls_today"] = 0

def can_call():
    reset_counter()
    return CACHE["api_calls_today"] < DAILY_CAP

def api_get(endpoint, params):
    if not API_KEY:
        return []
    if not can_call():
        return []
    try:
        p = dict(params); p["timezone"] = "Africa/Lagos"
        r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=p, timeout=20)
        CACHE["api_calls_today"] += 1
        print(f"API {endpoint} -> {r.status_code} | total {CACHE['api_calls_today']}")
        if r.status_code == 200:
            return r.json().get("response", [])
        return []
    except Exception as e:
        print(f"API error {e}")
        return []

def calc_results(gh, ga, status):
    total = gh + ga
    finished = status in ("FT", "AET", "PEN")
    def win(cond):
        if cond: return "WIN"
        return "LOST" if finished else "PENDING"
    return {"over15": win(total >= 2), "over25": win(total >= 3), "btts": win(gh > 0 and ga > 0), "home_over15": win(gh >= 2), "away_over15": win(ga >= 2), "home_1x_over15": win(gh >= ga and total >= 2), "away_x2_over15": win(ga >= gh and total >= 2)}

def league_rank(lid):
    return 0 if lid in FOCUS_LEAGUES else 1

def build_day(date_str):
    fixtures = api_get("fixtures", {"date": date_str})
    matches = []
    for f in fixtures:
        try:
            fx = f["fixture"]; lg = f["league"]; tm = f["teams"]; gl = f.get("goals", {}); st = fx.get("status", {})
            gh = gl.get("home") if gl.get("home") is not None else 0
            ga = gl.get("away") if gl.get("away") is not None else 0
            status = st.get("short", "NS")
            disp = status
            try:
                ko = datetime.fromisoformat(fx["date"].replace("Z", "+00:00"))
                if status == "NS" and (datetime.now(WAT) - ko.astimezone(WAT)).total_seconds() > 9000:
                    disp = "POSTPONED-CHECK"
            except Exception:
                pass
            lid = lg.get("id", 0)
            matches.append({"fixture_id": fx["id"], "league": lg["name"], "league_id": lid, "home": tm["home"]["name"], "away": tm["away"]["name"], "time": fx["date"][11:16], "status": disp, "real_status": status, "score_home": gh, "score_away": ga, "elapsed": st.get("elapsed") or 0, "markets": dict(EST), "results": calc_results(gh, ga, status), "league_rank": league_rank(lid)})
        except Exception:
            continue
    def rank(m):
        if m["status"] in ("1H", "2H", "HT", "ET", "P"): return 0
        if m["status"] in ("NS", "POSTPONED-CHECK"): return 1
        return 2
    matches.sort(key=lambda m: (rank(m), m["league_rank"], m["time"]))
    return matches

def pick_leg(m, market, tier):
    return {"fixture_id": m["fixture_id"], "home": m["home"], "away": m["away"], "time": m["time"], "league": m["league"], "market": market, "odd": EST[market], "tier": tier, "why": f"{m['home']} vs {m['away']} - {m['league']} - Strong pick for {market}."}

def build_accas(matches, date_str):
    pool_all = [m for m in matches if m["real_status"] == "NS"]
    pool_focus = [m for m in pool_all if m["league_rank"] == 0]
    pool = pool_focus if len(pool_focus) >= 6 else pool_all
    if len(pool) < 3:
        return {}
    def make_card(title, target, legs):
        if not legs: return None
        total = 1.0
        for l in legs: total *= l["odd"]
        return {"title": title, "target": target, "total_odd": round(total, 2), "legs": legs, "status": "PENDING", "date": date_str}
    accas = {}
    mid = [m for m in pool if "00:" <= m["time"] <= "03:59"]
    if len(mid) >= 3:
        accas["midnight"] = make_card("Midnight Pure Mixed - 12.00", 12.00, [pick_leg(mid[i], MARKETS[i % len(MARKETS)], "STRONG" if i < 2 else "GOOD") for i in range(min(6, len(mid)))])
    early = [m for m in pool if "04:00" <= m["time"] <= "10:00"]
    if len(early) >= 3:
        accas["early"] = make_card("Early Morning Pure Mixed - 12.00", 12.00, [pick_leg(early[i], MARKETS[i % len(MARKETS)], "STRONG" if i < 2 else "GOOD") for i in range(min(6, len(early)))])
    for idx, mk in enumerate(MARKETS):
        cands = pool[idx::7][:3]
        if len(cands) >= 2:
            accas[f"banker_{mk}"] = make_card(f"Banker - {mk} - 2.50+", 2.50, [pick_leg(m, mk, "STRONG") for m in cands])
    for idx, mk in enumerate(MARKETS):
        cands = pool[(idx+2)::7][:5]
        if len(cands) >= 4:
            accas[f"high_{mk}"] = make_card(f"High Roller - {mk} - 8.00-10.00", 9.00, [pick_leg(m, mk, "STRONG" if i < 2 else "GOOD") for i, m in enumerate(cands)])
    if len(pool) >= 8:
        accas["mega_10"] = make_card("Mega Mixed - 10+", 10.00, [pick_leg(pool[i], MARKETS[i % len(MARKETS)], "STRONG" if i < 3 else "GOOD") for i in range(8)])
        accas["mega_20"] = make_card("Mega Mixed - 20+", 20.00, [pick_leg(pool[i], MARKETS[(i+2) % len(MARKETS)], "STRONG" if i < 3 else "FILL") for i in range(min(10, len(pool)))])
    return accas

def build_all():
    now = datetime.now(WAT)
    today = now.strftime("%Y-%m-%d"); tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d"); nxt = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    reset_counter(); before = CACHE["api_calls_today"]
    tm = build_day(today); tom = build_day(tomorrow)
    return {"dates": {"yesterday": {"date": yesterday, "matches": [], "accumulators": {}}, "today": {"date": today, "matches": tm, "accumulators": build_accas(tm, today)}, "tomorrow": {"date": tomorrow, "matches": tom, "accumulators": build_accas(tom, tomorrow)}, "next_tomorrow": {"date": nxt, "matches": [], "accumulators": {}}}, "current_date": today, "last_update": datetime.now(WAT).isoformat(), "api_calls_today": CACHE["api_calls_today"]}

def empty_data():
    now = datetime.now(WAT)
    today = now.strftime("%Y-%m-%d"); tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d"); nxt = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    return {"dates": {"yesterday": {"date": yesterday, "matches": [], "accumulators": {}}, "today": {"date": today, "matches": [], "accumulators": {}}, "tomorrow": {"date": tomorrow, "matches": [], "accumulators": {}}, "next_tomorrow": {"date": nxt, "matches": [], "accumulators": {}}}, "current_date": today, "last_update": "Never - Press REFRESH in /admin", "api_calls_today": CACHE["api_calls_today"]}

@app.route("/")
def index():
    data = CACHE.get("data") or empty_data()
    sel = request.args.get("date", "today")
    sd = data["dates"].get(sel) or data["dates"]["today"]
    return render_template("index.html", data=data, selected_date=sel, dates=data["dates"], matches=sd["matches"], accas=sd["accumulators"], date=sd["date"], total=len(sd["matches"]), api_calls=CACHE["api_calls_today"], last_update=data["last_update"], api_key_set=bool(API_KEY))

# ===== ADMIN - THIS IS WHAT YOU ASKED FOR =====
@app.route("/admin")
def admin():
    data = CACHE.get("data") or empty_data()
    return render_template("admin.html", api_calls=CACHE["api_calls_today"], last_update=data["last_update"], quota_exhausted=(CACHE["api_calls_today"] >= DAILY_CAP))

@app.route("/api/refresh")
def refresh():
    key = request.args.get("key", "")
    if key != os.getenv("ADMIN_PASSWORD", "goalszone247"):
        return jsonify({"status": "error", "message": "Wrong password"}), 403
    if not can_call():
        return jsonify({"status": "cap_reached", "message": f"Daily cap {DAILY_CAP} reached.", "api_calls_today": CACHE["api_calls_today"]}), 429
    with LOCK:
        data = build_all(); CACHE["data"] = data
        return jsonify({"status": "ok", "message": f"Refreshed! Today {len(data['dates']['today']['matches'])} + Tomorrow {len(data['dates']['tomorrow']['matches'])} matches.", "today": len(data["dates"]["today"]["matches"]), "tomorrow": len(data["dates"]["tomorrow"]["matches"]), "api_calls_today": data["api_calls_today"], "last_update": data["last_update"]})

@app.route("/api/live")
def live():
    key = request.args.get("key", "")
    if key != os.getenv("ADMIN_PASSWORD", "goalszone247"):
        return jsonify({"status": "error", "message": "Wrong password"}), 403
    if CACHE.get("data") is None:
        return jsonify({"status": "error", "message": "No data yet. Press REFRESH first."})
    now = time.time()
    if now - CACHE.get("last_live", 0) < 300:
        return jsonify(CACHE["data"])
    if not can_call():
        return jsonify(CACHE["data"])
    with LOCK:
        CACHE["last_live"] = now
        fixtures = api_get("fixtures", {"date": CACHE["data"]["current_date"], "live": "all"})
        mp = {}
        for f in fixtures:
            try: mp[f["fixture"]["id"]] = f
            except Exception: continue
        for m in CACHE["data"]["dates"]["today"]["matches"]:
            f = mp.get(m["fixture_id"])
            if f:
                sd = f["fixture"].get("status", {}); gl = f.get("goals", {})
                m["status"] = sd.get("short", m["status"]); m["score_home"] = gl.get("home") or 0; m["score_away"] = gl.get("away") or 0; m["elapsed"] = sd.get("elapsed") or 0
                m["results"] = calc_results(m["score_home"], m["score_away"], m["status"])
        CACHE["data"]["last_update"] = datetime.now(WAT).isoformat()
        return jsonify(CACHE["data"])

@app.route("/api/debug")
def debug():
    data = CACHE.get("data") or empty_data()
    return jsonify({"api_key_set": bool(API_KEY), "api_calls_today": CACHE["api_calls_today"], "daily_cap": DAILY_CAP, "last_update": data["last_update"], "counts": {k: len(v["matches"]) for k, v in data["dates"].items()}})

@app.route("/api/cron")
def cron():
    if not can_call():
        return jsonify({"status": "cap_reached"})
    with LOCK:
        data = build_all(); CACHE["data"] = data
        return jsonify({"status": "ok", "api_calls_today": data["api_calls_today"]})