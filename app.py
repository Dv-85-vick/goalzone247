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

# ============================================================
# VICTOR'S RULES - DO NOT CHANGE WITHOUT HIS PERMISSION
# 1. Odds ONLY for Today + Tomorrow. NEVER Yesterday / Next.
# 2. Fixtures ONLY for Today + Tomorrow. Yesterday / Next = empty, 0 calls.
# 3. Cache / Lock = 2 HOURS (7200s). One refresh blocks everyone else.
# 4. Live scores: separate small check, Today only, every 5 min, NO odds.
# 5. Daily cap: stop API calls after 80 calls, serve cached data.
# 6. NEW COMBO MARKETS: home_1x_over15 (1X + Over 1.5) and away_x2_over15 (X2 + Over 1.5).
#    Real combo odd if bookmaker offers it, else estimated fallback. Never multiply 1X x Over1.5.
# ============================================================
CACHE_SECONDS = 7200  # 2 hours
LIVE_CHECK_SECONDS = 300  # 5 minutes, live scores only
DAILY_CALL_CAP = 80
ESTIMATED_MARKETS = {"over15": 1.25, "over25": 1.50, "btts": 1.65, "home_over15": 1.60, "away_over15": 1.60, "home_1x_over15": 1.45, "away_x2_over15": 1.50}
# STRONG LEAGUES - accumulators pick these FIRST. They play regularly, score regularly, perform well.
STRONG_LEAGUES = {"Premier League", "Championship", "La Liga", "LaLiga", "Bundesliga", "2. Bundesliga", "Serie A", "Serie B", "Ligue 1", "Ligue 2", "Eredivisie", "Primeira Liga", "Pro League", "Super Lig", "Serie A", "Primera Division", "Liga MX", "MLS", "Major League Soccer", "Premiership", "Bundesliga", "Super League", "Superliga", "Allsvenskan", "Eliteserien", "Ekstraklasa", "First League", "HNL", "Super League", "Premier League", "Liga Portugal", "Scottish Premiership", "Austrian Bundesliga", "Swiss Super League", "Danish Superliga", "Norwegian Eliteserien", "Swedish Allsvenskan", "Polish Ekstraklasa", "Czech First League", "Croatian HNL", "Greek Super League", "Israeli Premier League", "Romanian Liga I", "Hungarian NB I", "Slovenian PrvaLiga", "Serbian SuperLiga", "Bulgarian First League", "Brazil Serie A", "Argentina Primera Division", "Chile Primera Division", "Colombia Primera A", "Uruguay Primera Division", "Peru Liga 1", "Ecuador Liga Pro", "Japan J1 League", "Korea K League 1", "Australia A-League", "South Africa Premier Division", "Egypt Premier League", "Morocco Botola Pro", "Nigeria NPFL", "Ghana Premier League", "Kenya Premier League"}
# SMART PICKING - do NOT pick anyhow. Each market has a MAX ODD = bookmaker confidence.
# Lower odd = bookmaker thinks it will happen = stronger pick.
# Away Over 1.5: away team must be strong, so odd must be low.
# 1X+Over 1.5: home team must be strong + not lose, so odd must be low.
# X2+Over 1.5: away team must be strong + not lose, so odd must be low.
# TIER SYSTEM - NO SHORTAGE. Tier 1 = STRONG (preferred). Tier 2 = GOOD. Tier 3 = FILL (best of rest).
# These are PREFERRED odds, not hard blocks. If Tier 1 is not enough, system uses Tier 2, then Tier 3 to fill card.
# Thresholds raised to REAL bookmaker levels so we never run out of matches.
SMART_MAX_ODD = {"over15": 1.45, "over25": 1.85, "btts": 1.95, "home_over15": 1.95, "away_over15": 1.95, "home_1x_over15": 1.75, "away_x2_over15": 1.85}
def tier_of(m, mk):
    odd = m["markets"].get(mk, 99)
    if odd <= SMART_MAX_ODD.get(mk, 99): return "STRONG"
    if odd <= SMART_MAX_ODD.get(mk, 99) + 0.35: return "GOOD"
    return "FILL"
def smart_score(m, mk):
    odd = m["markets"].get(mk, 99)
    if odd is None or odd <= 1: return -999
    confidence = (1.0 / odd) * 100  # higher = bookmaker more sure
    bonus = 15 if m.get("league") in STRONG_LEAGUES else 0
    # Away markets: extra bonus if away odd is much lower than home odd (away is stronger)
    return confidence + bonus
def why_pick(m, mk):
    odd = m["markets"].get(mk, 0)
    tier = tier_of(m, mk)
    league = m.get("league","")
    strong = league in STRONG_LEAGUES
    if mk == "away_over15":
        return f"Away team strong in attack - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Good away scoring form'}"
    if mk == "home_over15":
        return f"Home team strong in attack - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Good home scoring form'}"
    if mk == "home_1x_over15":
        return f"Home team strong, hard to beat at home + goals expected @ {odd} - {'Strong league: '+league if strong else 'Home form strong'}"
    if mk == "away_x2_over15":
        return f"Away team strong, hard to beat away + goals expected @ {odd} - {'Strong league: '+league if strong else 'Away form strong'}"
    if mk == "over15":
        return f"Both teams score goals - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Goals expected'}"
    if mk == "over25":
        return f"High-scoring game expected - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'Goals expected'}"
    if mk == "btts":
        return f"Both teams score regularly - bookmaker confident @ {odd} - {'Strong league: '+league if strong else 'BTTS form strong'}"
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
    """One API call. Returns []. Respects daily cap. Logs everything."""
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
        response = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=p, timeout=6)
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
                for value in bet.get("values", []):
                    try:
                        odd = float(value.get("odd", 0))
                    except (TypeError, ValueError):
                        continue
                    if odd <= 1:
                        continue
                    sel = value.get("value", "")
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
            # === NEW COMBO MARKETS ===
            # Real bookmaker combo: Double Chance + Over 1.5
            # Names vary: "Double Chance - Over/Under", "Double Chance & Over/Under",
            # "1X & Over 1.5", "Home Win or Draw + Over 1.5", etc.
            # We NEVER multiply 1X * Over1.5 - that would be wrong.
            # We only take the real combo odd if the bookmaker offers it.
            # If not offered, the match falls back to ESTIMATED_MARKETS below.
            low_name = name.lower()
            low_sel = sel.lower()
            # Normalise selection: "1x / over 1.5", "1x and over 1.5", "home / over 1.5"
            is_1x = ("1x" in low_sel) or ("home" in low_sel and "draw" in low_sel) or ("home win or draw" in low_name)
            is_x2 = ("x2" in low_sel) or ("2x" in low_sel) or ("away" in low_sel and "draw" in low_sel) or ("away win or draw" in low_name)
            is_over15 = ("over 1.5" in low_sel) or ("over 1.5" in low_name and "over" in low_sel) or ("1.5" in low_sel and "over" in low_sel)
            is_combo_bet = ("double chance" in low_name) or ("1x" in low_name) or ("x2" in low_name) or ("win or draw" in low_name)
            if is_combo_bet and is_over15:
                if is_1x:
                    markets.setdefault("home_1x_over15", odd)
                elif is_x2:
                    markets.setdefault("away_x2_over15", odd)
            if len(markets) == 7:
                break
        return markets
    except Exception:
        return markets

def _build_day(date_string, with_odds):
    """Build ONE day. with_odds=False means fixtures only, 0 odds calls."""
    fixtures = api_get("fixtures", {"date": date_string}, with_timezone=True)

    odds_map = {}
    if with_odds:
        # ODDS ONLY FOR TODAY + TOMORROW - never called for Yesterday / Next
        odds_list = api_get("odds", {"date": date_string}, with_timezone=True)
        for item in odds_list:
            try:
                odds_map[item["fixture"]["id"]] = item
            except (KeyError, TypeError):
                continue

    matches = []
    for fixture in fixtures[:150]:
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
            _st = sd.get("short", "NS"); _sh = goals.get("home") or 0; _sa = goals.get("away") or 0
            _is_postponed = False
            try:
                _ko = datetime.fromisoformat(fd.replace("Z", "+00:00")).astimezone(WAT)
                if _st == "NS" and (datetime.now(WAT) - _ko).total_seconds() > 2.5*3600:
                    _is_postponed = True
            except Exception:
                pass
            matches.append({
                "fixture_id": fid, "league": fixture["league"]["name"], "league_id": fixture["league"].get("id"),
                "country": fixture["league"].get("country", ""),
                "date": date_string,
                "home": fixture["teams"]["home"]["name"], "away": fixture["teams"]["away"]["name"],
                "time": fd[11:16] if len(fd) >= 16 else "", "status": _st,
                "score_home": _sh, "score_away": _sa,
                "elapsed": sd.get("elapsed") or 0, "is_postponed": _is_postponed, "display_status": ("POSTPONED" if _is_postponed else _st), "markets": markets,
                "market_results": {k: market_result(k, _st, _sh, _sa) for k in markets},
                "market_labels": MARKET_LABELS,
                "odds_estimated": is_estimated, "score_rank": score_rank
            })
        except (KeyError, TypeError, ValueError):
            continue
    matches.sort(key=lambda m: m["score_rank"], reverse=True)
    print(f"{date_string}: fixtures={len(fixtures)} matches={len(matches)} odds_called={with_odds}")
    return matches

def generate_accumulators(matches, date_string=""):
    def _leg(m, mk):
        return {"fixture_id": m["fixture_id"], "home": m["home"], "away": m["away"], "league": m["league"], "country": m.get("country", ""), "date": m.get("date", date_string), "time": m["time"], "score_home": m.get("score_home", 0), "score_away": m.get("score_away", 0), "status": m.get("status", "NS"), "is_postponed": m.get("is_postponed", False), "display_status": m.get("display_status", m.get("status", "NS")), "elapsed": m.get("elapsed", 0), "market": mk, "market_label": MARKET_LABELS.get(mk, mk), "odd": m["markets"].get(mk), "result": market_result(mk, m.get("status", "NS"), m.get("score_home", 0), m.get("score_away", 0)), "why": why_pick(m, mk) + f" - Tier: {tier_of(m, mk)}", "smart_score": round(smart_score(m, mk), 1)}
    def _wrap(legs, total, target):
        r = [l["result"] for l in legs]
        overall = "WIN" if r and all(x == "WIN" for x in r) else ("LOST" if any(x == "LOST" for x in r) else "PENDING")
        return {"legs": legs, "total_odds": round(total, 2), "count": len(legs), "target": target, "overall_status": overall, "wins": r.count("WIN"), "losses": r.count("LOST"), "pending": r.count("PENDING")}
    # GLOBAL used pool: one fixture may appear in at most ONE card if possible.
    # This stops Inca/Panama killing every card. Reuse only if unused pool is exhausted.
    USED = set()
    def _pick(pool, mk, want_unused=True):
        # TIER PICK: STRONG first, GOOD second, FILL last. NEVER empty - always fill from best available.
        def _tier_rank(x):
            return {"STRONG": 0, "GOOD": 1, "FILL": 2}.get(tier_of(x, mk), 2)
        cands = sorted(pool, key=lambda x: (_tier_rank(x), -smart_score(x, mk)))
        for m in cands:
            if m["fixture_id"] not in USED and m["markets"].get(mk):
                return m
        if want_unused:
            return None
        for m in cands:
            if m["markets"].get(mk):
                return m
        return None
    def build_single(mk, target, pool=None):
        pool = pool if pool is not None else matches
        legs, total = [], 1.0
        seen = set()
        while total < target:
            m = _pick([x for x in pool if x["fixture_id"] not in seen], mk, want_unused=True)
            if m is None:
                m = _pick([x for x in pool if x["fixture_id"] not in seen], mk, want_unused=False)
            if m is None:
                break
            seen.add(m["fixture_id"]); USED.add(m["fixture_id"])
            legs.append(_leg(m, mk)); total *= m["markets"].get(mk)
            if len(legs) >= 20:
                break
        return _wrap(legs, total, target)
    def _in_window(m, start_h, end_h):
        try:
            hh = int((m.get("time") or "00:00")[:2])
            return start_h <= hh < end_h
        except Exception:
            return False
    # TIME-FRAME: Midnight 00:00-03:00, Early Morning 02:00-05:59. Fallback to all matches if pool too small.
    # PURE MIXED - Midnight 00:00-03:00, Early 04:00-10:00. Rotate all 7 markets, Tier picking, never same fixture twice.
    def build_mix_pool(target, pool):
        order = ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]
        legs, total, seen = [], 1.0, set()
        idx = 0
        while total < target and len(legs) < 20:
            mk = order[idx % len(order)]; idx += 1
            m = _pick([x for x in pool if x["fixture_id"] not in seen], mk, want_unused=True)
            if m is None:
                m = _pick([x for x in pool if x["fixture_id"] not in seen], mk, want_unused=False)
            if m is None:
                continue
            seen.add(m["fixture_id"]); USED.add(m["fixture_id"])
            legs.append(_leg(m, mk)); total *= m["markets"].get(mk)
        return _wrap(legs, total, target)
    midnight_pool = [m for m in matches if _in_window(m, 0, 3)] or matches
    early_pool = [m for m in matches if _in_window(m, 4, 10)] or matches
    acc = {}
    acc["midnight"] = build_mix_pool(12.0, midnight_pool)
    acc["early"] = build_mix_pool(12.0, early_pool)
    for mk in ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]:
        acc[mk] = {"2.5": build_single(mk, 2.5), "8": build_single(mk, 8.0)}
    def build_mix(target):
        # TRULY MIXED: rotate markets round-robin so Over 1.5 cannot dominate.
        order = ["over15", "over25", "btts", "home_over15", "away_over15", "home_1x_over15", "away_x2_over15"]
        legs, total, seen = [], 1.0, set()
        idx = 0
        while total < target and len(legs) < 20:
            mk = order[idx % len(order)]; idx += 1
            m = _pick([x for x in matches if x["fixture_id"] not in seen], mk, want_unused=True)
            if m is None:
                m = _pick([x for x in matches if x["fixture_id"] not in seen], mk, want_unused=False)
            if m is None:
                continue
            seen.add(m["fixture_id"]); USED.add(m["fixture_id"])
            legs.append(_leg(m, mk)); total *= m["markets"].get(mk)
        return _wrap(legs, total, target)
    acc["mix"] = {"10": build_mix(10.0), "20": build_mix(20.0)}
    return acc

def build_all():
    """Full refresh: ONLY Today + Tomorrow. Max 4 API calls (2 fixtures + 2 odds)."""
    now = datetime.now(WAT)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    _reset_daily_counter_if_needed()
    before = CACHE.get("api_calls_today", 0)
    today_matches = _build_day(today, with_odds=True)
    tomorrow_matches = _build_day(tomorrow, with_odds=False)  # FAST v13: odds only Today, Tomorrow uses estimated - saves 1 heavy API call
    # Yesterday + Next: NO API CALLS AT ALL. Kept as empty so template does not break.
    dates = {
        "yesterday": {"date": yesterday, "matches": [], "accumulators": {}},
        "today": {"date": today, "matches": today_matches, "accumulators": generate_accumulators(today_matches, today)},
        "tomorrow": {"date": tomorrow, "matches": tomorrow_matches, "accumulators": generate_accumulators(tomorrow_matches, tomorrow)},
        "next_tomorrow": {"date": next_day, "matches": [], "accumulators": {}},
    }
    after = CACHE.get("api_calls_today", 0)
    print(f"FULL REFRESH DONE (v13: odds Today only): used {after-before} API calls this refresh, total today {after}/{DAILY_CALL_CAP}")
    return {"dates": dates, "current_date": today, "last_update": datetime.now(WAT).isoformat(), "api_calls_today": after, "last_error": CACHE.get("last_error"), "cache_until": (datetime.now(WAT) + timedelta(seconds=CACHE_SECONDS)).isoformat()}

def refresh_cache_locked():
    data = build_all()
    CACHE["data"] = data
    CACHE["last_fetch"] = time.monotonic()
    return data

def _empty_data():
    now = datetime.now(WAT)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = (now + timedelta(days=2)).strftime("%Y-%m-%d")
    return {"dates": {"yesterday": {"date": yesterday, "matches": [], "accumulators": {}}, "today": {"date": today, "matches": [], "accumulators": {}}, "tomorrow": {"date": tomorrow, "matches": [], "accumulators": {}}, "next_tomorrow": {"date": next_day, "matches": [], "accumulators": {}}}, "current_date": today, "last_update": datetime.now(WAT).isoformat(), "api_calls_today": CACHE.get("api_calls_today", 0), "last_error": CACHE.get("last_error"), "cache_until": (datetime.now(WAT) + timedelta(seconds=CACHE_SECONDS)).isoformat()}

def get_data():
    with DATA_LOCK:
        now = time.monotonic()
        if CACHE["data"] is not None and now - CACHE["last_fetch"] < CACHE_SECONDS:
            return CACHE["data"]
        try:
            return refresh_cache_locked()
        except Exception as e:
            print(f"FAST FALLBACK: build failed {e} - returning empty page, no 504")
            CACHE["last_error"] = str(e)
            return _empty_data()

def refresh_live_scores_only():
    """Live check: Today only, every 5 min, fixtures only, NO odds. Updates score/time/status only."""
    with DATA_LOCK:
        if CACHE["data"] is None:
            return get_data()
        now = time.monotonic()
        if now - CACHE.get("last_live_check", 0) < LIVE_CHECK_SECONDS:
            return CACHE["data"]
        # Only check if any Today match is actually live / starting soon
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
    # v13 INSTANT: NEVER call API on page load. Return empty shell instantly (<1s, no 504).
    # Browser JS then fetches /api/data in background and reloads with real data.
    # If this Vercel instance already loaded data (warmed by /api/data), serve it instantly. Else empty shell.
    if CACHE.get("data") is not None:
        data = CACHE["data"]
        selected_date = request.args.get("date", "today")
        selected_data = data["dates"].get(selected_date) or data["dates"].get("today")
        def _rank(m):
            s = m.get("status", "NS")
            if s in ("1H", "2H", "HT", "ET", "P", "LIVE"): return 0
            if m.get("is_postponed"): return 2
            if s == "NS": return 1
            if s in ("FT", "AET", "PEN"): return 3
            return 2
        ordered = sorted(selected_data["matches"], key=lambda m: (_rank(m), m.get("time", "")))
        return render_template("index.html", data=data, selected_date=selected_date, dates=data["dates"], matches=ordered, accas=selected_data["accumulators"], date=selected_data["date"], total=len(selected_data["matches"]), api_calls=data["api_calls_today"], last_update=data["last_update"], api_key_set=bool(API_KEY), cache_until=data.get("cache_until"))
    data = _empty_data()
    selected_date = request.args.get("date", "today")
    selected_data = data["dates"].get(selected_date) or data["dates"].get("today")
    return render_template("index.html", data=data, selected_date=selected_date, dates=data["dates"], matches=[], accas={}, date=selected_data["date"], total=0, api_calls=CACHE.get("api_calls_today", 0), last_update=data["last_update"], api_key_set=bool(API_KEY), cache_until=data.get("cache_until"))

@app.route("/api/data")
def api_data():
    # Background data load: called by JS after page opens. If this times out, page stays open and JS retries.
    try:
        data = get_data()
    except Exception as e:
        return jsonify({"status": "loading", "message": str(e)}), 202
    return jsonify({"status": "ok", "today": len(data["dates"]["today"]["matches"]), "tomorrow": len(data["dates"]["tomorrow"]["matches"]), "last_update": data["last_update"], "api_calls_today": data["api_calls_today"]})

@app.route("/api/refresh")
def refresh():
    """Manual refresh: BLOCKED for everyone if 2h lock is still active. One refresh blocks all others."""
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
    # Live = cached data + small live-score check only. Never triggers full refresh.
    data = refresh_live_scores_only()
    return jsonify(data)

@app.route("/api/debug")
def debug():
    data = CACHE.get("data") or _empty_data()  # v13: debug must never call API
    return jsonify({"api_key_set": bool(API_KEY), "last_error": CACHE.get("last_error"), "last_update": data.get("last_update"), "cache_until": data.get("cache_until"), "api_calls_today": CACHE.get("api_calls_today", 0), "daily_cap": DAILY_CALL_CAP, "counts": {k: len(v["matches"]) for k, v in data["dates"].items()}, "rules": "Odds: Today+Tomorrow only. Cache: 2h lock. Live: Today only, 5 min, no odds. Combos: 1X+Over1.5, X2+Over1.5."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
