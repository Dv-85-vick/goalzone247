
import os
import json
import time
import math
import sqlite3
import hashlib
import threading
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify, request

# ============================================================
# GOALZONE247 - FLY.IO BACKEND
# ============================================================

app = Flask(__name__)

API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()

WAT = ZoneInfo("Africa/Lagos")
DB_PATH = os.getenv("DB_PATH", "/data/goalzone247.sqlite3")

DAILY_API_LIMIT = int(os.getenv("DAILY_API_LIMIT", "60"))
MIN_API_INTERVAL = int(os.getenv("MIN_API_INTERVAL", "60"))
DAILY_CACHE_SECONDS = int(os.getenv("DAILY_CACHE_SECONDS", "10800"))
LIVE_CACHE_SECONDS = int(os.getenv("LIVE_CACHE_SECONDS", "1800"))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "20"))
API_BACKOFF_SECONDS = int(os.getenv("API_BACKOFF_SECONDS", "900"))

MEGA_MIXED_TARGET = float(os.getenv("MEGA_MIXED_TARGET", "55"))
HIGH_ROLLER_TARGET = float(os.getenv("HIGH_ROLLER_TARGET", "20"))

api_lock = threading.Lock()
db_lock = threading.RLock()

LIVE_CODES = {"1H", "HT", "2H", "ET", "BT", "P"}
FINISHED_CODES = {"FT", "AET", "PEN"}
UPCOMING_CODES = {"NS", "TBD"}

# Estimated prices are not bookmaker odds.
# The first seven values preserve the earlier backend estimates.
# Additional values are provisional estimates and must not be
# presented as confirmed market prices.
MARKETS = {
    "over15": {
        "name": "Over 1.5 Goals",
        "odd": 1.25,
        "group": "individual",
        "target": 12.0,
    },
    "over25": {
        "name": "Over 2.5 Goals",
        "odd": 1.50,
        "group": "individual",
        "target": 12.0,
    },
    "btts": {
        "name": "BTTS Yes",
        "odd": 1.65,
        "group": "individual",
        "target": 12.0,
    },
    "home_over15": {
        "name": "Home Over 1.5",
        "odd": 1.60,
        "group": "individual",
        "target": 12.0,
    },
    "away_over15": {
        "name": "Away Over 1.5",
        "odd": 1.60,
        "group": "individual",
        "target": 12.0,
    },
    "one_x_btts": {
        "name": "1X + BTTS",
        "odd": 1.85,
        "group": "individual",
        "target": 12.0,
    },
    "x_two_btts": {
        "name": "X2 + BTTS",
        "odd": 1.85,
        "group": "individual",
        "target": 12.0,
    },
    "home_win_over15": {
        "name": "Home Win + Over 1.5",
        "odd": 1.65,
        "group": "individual",
        "target": 12.0,
    },
    "away_win_over15": {
        "name": "Away Win + Over 1.5",
        "odd": 1.65,
        "group": "individual",
        "target": 12.0,
    },
    "first_half_over05": {
        "name": "First-Half Over 0.5",
        "odd": 1.30,
        "group": "individual",
        "target": 12.0,
    },
    "home_over05": {
        "name": "Home Team Over 0.5",
        "odd": 1.22,
        "group": "mixed_only",
        "target": None,
    },
    "away_over05": {
        "name": "Away Team Over 0.5",
        "odd": 1.22,
        "group": "mixed_only",
        "target": None,
    },
}

MIXED_MARKETS = [
    "over15",
    "over25",
    "btts",
    "home_over15",
    "away_over15",
    "one_x_btts",
    "x_two_btts",
    "home_win_over15",
    "away_win_over15",
    "first_half_over05",
    "home_over05",
    "away_over05",
]

# ============================================================
# DATABASE
# ============================================================

def ensure_database_directory():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)


@contextmanager
def db_connection():
    ensure_database_directory()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_lock:
        with db_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_usage (
                    usage_date TEXT PRIMARY KEY,
                    calls INTEGER NOT NULL DEFAULT 0,
                    last_call REAL NOT NULL DEFAULT 0,
                    blocked_until REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    saved_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS accumulator_cards (
                    card_id TEXT PRIMARY KEY,
                    card_date TEXT NOT NULL,
                    card_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rollover (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    stage INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    current_card TEXT,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS result_history (
                    fixture_id INTEGER NOT NULL,
                    market TEXT NOT NULL,
                    result TEXT NOT NULL,
                    home_goals INTEGER,
                    away_goals INTEGER,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (fixture_id, market)
                );
            """)

            conn.execute("""
                INSERT OR IGNORE INTO rollover
                (id, stage, status, current_card, updated_at)
                VALUES (1, 1, 'PENDING', NULL, ?)
            """, (time.time(),))


init_db()


def cache_get(key, max_age):
    with db_connection() as conn:
        row = conn.execute(
            "SELECT payload, saved_at FROM cache WHERE cache_key=?",
            (key,)
        ).fetchone()

    if not row:
        return None

    if time.time() - row["saved_at"] > max_age:
        return None

    try:
        return json.loads(row["payload"])
    except Exception:
        return None


def cache_set(key, payload):
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO cache(cache_key, payload, saved_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload=excluded.payload,
                saved_at=excluded.saved_at
        """, (key, json.dumps(payload), time.time()))


# ============================================================
# API-F​​OOTBALL CALL CONTROL
# ============================================================

class APIUnavailable(Exception):
    pass


def api_get(endpoint, params=None):
    if not API_KEY:
        raise APIUnavailable("API_FOOTBALL_KEY is not configured.")

    today_key = datetime.now(WAT).date().isoformat()
    now = time.time()

    with api_lock:
        with db_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO api_usage
                (usage_date, calls, last_call, blocked_until)
                VALUES (?, 0, 0, 0)
            """, (today_key,))

            row = conn.execute("""
                SELECT calls, last_call, blocked_until
                FROM api_usage WHERE usage_date=?
            """, (today_key,)).fetchone()

            if row["calls"] >= DAILY_API_LIMIT:
                raise APIUnavailable("Daily API call limit reached.")

            if now < row["blocked_until"]:
                raise APIUnavailable("API temporarily paused after an error.")

            wait_for = MIN_API_INTERVAL - (now - row["last_call"])
            if wait_for > 0:
                raise APIUnavailable(
                    f"API protection interval active. Retry in "
                    f"{int(math.ceil(wait_for))} seconds."
                )

            conn.execute("""
                UPDATE api_usage
                SET calls=calls+1, last_call=?
                WHERE usage_date=?
            """, (now, today_key))

        try:
            response = requests.get(
                f"{API_BASE}/{endpoint.lstrip('/')}",
                headers={"x-apisports-key": API_KEY},
                params=params or {},
                timeout=API_TIMEOUT
            )

            if response.status_code == 429:
                raise APIUnavailable("Football API rate limit returned 429.")

            response.raise_for_status()
            body = response.json()

            if body.get("errors"):
                raise APIUnavailable(
                    "Football API error: " + json.dumps(body["errors"])
                )

            return body.get("response", [])

        except APIUnavailable:
            with db_connection() as conn:
                conn.execute("""
                    UPDATE api_usage SET blocked_until=?
                    WHERE usage_date=?
                """, (time.time() + API_BACKOFF_SECONDS, today_key))
            raise

        except Exception as exc:
            with db_connection() as conn:
                conn.execute("""
                    UPDATE api_usage SET blocked_until=?
                    WHERE usage_date=?
                """, (time.time() + API_BACKOFF_SECONDS, today_key))
            raise APIUnavailable(str(exc))


def api_usage_today():
    today_key = datetime.now(WAT).date().isoformat()
    with db_connection() as conn:
        row = conn.execute(
            "SELECT calls FROM api_usage WHERE usage_date=?",
            (today_key,)
        ).fetchone()
    return row["calls"] if row else 0


# ============================================================
# FIXTURE NORMALIZATION
# ============================================================

def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_fixture(raw):
    fixture = raw.get("fixture", {})
    league = raw.get("league", {})
    teams = raw.get("teams", {})
    goals = raw.get("goals", {})
    score = raw.get("score", {})

    fixture_id = fixture.get("id")
    kickoff_raw = fixture.get("date")

    try:
        kickoff = datetime.fromisoformat(
            kickoff_raw.replace("Z", "+00:00")
        ).astimezone(WAT)
    except Exception:
        kickoff = None

    status_info = fixture.get("status", {})
    status_code = status_info.get("short", "NS")

    if status_code in LIVE_CODES:
        status = "LIVE"
    elif status_code in FINISHED_CODES:
        status = "FINISHED"
    elif status_code in {"PST", "CANC", "ABD", "AWD", "WO"}:
        status = status_code
    else:
        status = "UPCOMING"

    home = teams.get("home", {})
    away = teams.get("away", {})

    return {
        "id": fixture_id,
        "date": kickoff.strftime("%Y-%m-%d") if kickoff else None,
        "time": kickoff.strftime("%H:%M") if kickoff else None,
        "kickoff_wat": kickoff.isoformat() if kickoff else None,
        "timestamp": int(kickoff.timestamp()) if kickoff else 0,
        "country": league.get("country") or "Unknown",
        "league": league.get("name") or "Unknown League",
        "league_id": league.get("id"),
        "season": league.get("season"),
        "round": league.get("round"),
        "home": home.get("name") or "Home",
        "away": away.get("name") or "Away",
        "home_id": home.get("id"),
        "away_id": away.get("id"),
        "home_logo": home.get("logo"),
        "away_logo": away.get("logo"),
        "status": status,
        "status_code": status_code,
        "elapsed": status_info.get("elapsed"),
        "home_goals": safe_int(goals.get("home")),
        "away_goals": safe_int(goals.get("away")),
        "halftime_home": safe_int(
            (score.get("halftime") or {}).get("home")
        ),
        "halftime_away": safe_int(
            (score.get("halftime") or {}).get("away")
        ),
        "venue": (fixture.get("venue") or {}).get("name"),
        "referee": fixture.get("referee"),
    }


def sort_fixtures(fixtures):
    def key(f):
        order = {
            "LIVE": 0,
            "UPCOMING": 1,
            "FINISHED": 2,
        }
        if f["status"] in {"PST", "CANC", "ABD", "AWD", "WO"}:
            group = 3
        else:
            group = order.get(f["status"], 3)

        return (group, f.get("timestamp") or 0)

    return sorted(fixtures, key=key)


# ============================================================
# FETCH AND CACHE FIXTURES
# ============================================================

def fetch_daily_fixtures():
    cached = cache_get("daily_fixtures", DAILY_CACHE_SECONDS)
    if cached is not None:
        return cached

    today = datetime.now(WAT).date()
    tomorrow = today + timedelta(days=1)

    rows = api_get("fixtures", {
        "from": today.isoformat(),
        "to": tomorrow.isoformat(),
        "timezone": "Africa/Lagos",
    })

    fixtures = [normalize_fixture(row) for row in rows]
    fixtures = [f for f in fixtures if f.get("id")]

    payload = sort_fixtures(fixtures)
    cache_set("daily_fixtures", payload)
    return payload


def fetch_live_fixtures():
    cached = cache_get("live_fixtures", LIVE_CACHE_SECONDS)
    if cached is not None:
        return cached

    rows = api_get("fixtures", {
        "live": "all",
        "timezone": "Africa/Lagos",
    })

    fixtures = [normalize_fixture(row) for row in rows]
    fixtures = [f for f in fixtures if f.get("id")]

    payload = sort_fixtures(fixtures)
    cache_set("live_fixtures", payload)
    return payload


def combine_fixtures():
    daily = fetch_daily_fixtures()

    try:
        live = fetch_live_fixtures()
    except APIUnavailable:
        live = cache_get("live_fixtures", 86400) or []

    by_id = {f["id"]: f for f in daily}

    for fixture in live:
        by_id[fixture["id"]] = fixture

    return sort_fixtures(list(by_id.values()))


# ============================================================
# SELECTION AND ACCUMULATOR LOGIC
# ============================================================

def fixture_is_selectable(fixture):
    if fixture.get("status") != "UPCOMING":
        return False

    if not fixture.get("id"):
        return False

    if not fixture.get("home") or not fixture.get("away"):
        return False

    if fixture.get("home") == fixture.get("away"):
        return False

    league_name = (fixture.get("league") or "").lower()

    blocked_words = (
        "friendly",
        "friendlies",
        "club friendly",
        "youth friendly",
    )

    if any(word in league_name for word in blocked_words):
        return False

    if not fixture.get("timestamp"):
        return False

    return True


def fixture_diversity_key(fixture):
    # A deterministic key makes card creation repeatable.
    value = (
        str(fixture.get("id")) +
        str(fixture.get("league_id")) +
        str(fixture.get("home")) +
        str(fixture.get("away"))
    )
    return hashlib.sha256(value.encode()).hexdigest()


def diversified_pool(fixtures):
    pool = [f for f in fixtures if fixture_is_selectable(f)]
    pool.sort(key=lambda f: (
        f.get("timestamp", 0),
        fixture_diversity_key(f)
    ))

    # Avoid selecting many fixtures from the same league in a row.
    result = []
    league_counts = {}

    for fixture in pool:
        league_id = fixture.get("league_id") or fixture.get("league")
        count = league_counts.get(league_id, 0)

        if count >= 3:
            continue

        result.append(fixture)
        league_counts[league_id] = count + 1

    return result


def make_leg(fixture, market_key):
    market = MARKETS[market_key]

    return {
        "fixture_id": fixture["id"],
        "country": fixture.get("country"),
        "league": fixture.get("league"),
        "date": fixture.get("date"),
        "time": fixture.get("time"),
        "kickoff_wat": fixture.get("kickoff_wat"),
        "home": fixture.get("home"),
        "away": fixture.get("away"),
        "home_logo": fixture.get("home_logo"),
        "away_logo": fixture.get("away_logo"),
        "market": market_key,
        "market_name": market["name"],
        "odds": market["odd"],
        "odds_type": "ESTIMATED",
        "status": "PENDING",
    }


def multiply_odds(legs):
    total = 1.0
    for leg in legs:
        total *= float(leg["odds"])
    return round(total, 2)


def build_market_card(fixtures, market_key):
    market = MARKETS[market_key]
    target = float(market["target"])
    candidates = diversified_pool(fixtures)

    legs = []
    used_fixtures = set()
    product = 1.0

    for fixture in candidates:
        if fixture["id"] in used_fixtures:
            continue

        leg = make_leg(fixture, market_key)
        legs.append(leg)
        used_fixtures.add(fixture["id"])
        product *= leg["odds"]

        if product >= target:
            break

        if len(legs) >= 12:
            break

    if not legs or product < target:
        return {
            "id": f"{market_key}-{datetime.now(WAT).date()}",
            "name": market["name"],
            "market": market_key,
            "target_odds": target,
            "total_odds": round(product, 2),
            "status": "NO_QUALIFYING_CARD",
            "message": "Not enough eligible fixtures to reach the target.",
            "legs": [],
            "odds_type": "ESTIMATED",
        }

    return {
        "id": f"{market_key}-{datetime.now(WAT).date()}",
        "name": market["name"],
        "market": market_key,
        "target_odds": target,
        "total_odds": round(product, 2),
        "status": "PENDING",
        "message": "Estimated accumulator. Confirm prices independently.",
        "legs": legs,
        "odds_type": "ESTIMATED",
    }


def select_mixed_legs(fixtures, max_legs=12, time_filter=None):
    candidates = diversified_pool(fixtures)

    if time_filter == "midnight":
        candidates = [
            f for f in candidates
            if f.get("time") and "00:00" <= f["time"] < "04:00"
        ]

    elif time_filter == "early":
        candidates = [
            f for f in candidates
            if f.get("time") and "04:00" <= f["time"] < "09:00"
        ]

    legs = []
    used = set()
    market_index = 0

    for fixture in candidates:
        if fixture["id"] in used:
            continue

        market_key = MIXED_MARKETS[market_index % len(MIXED_MARKETS)]
        legs.append(make_leg(fixture, market_key))
        used.add(fixture["id"])
        market_index += 1

        if len(legs) >= max_legs:
            break

    return legs


def build_mixed_card(fixtures, card_id, name, target, max_legs=12,
                     time_filter=None):
    legs = select_mixed_legs(
        fixtures,
        max_legs=max_legs,
        time_filter=time_filter
    )

    total = multiply_odds(legs) if legs else 0

    if not legs or total < target:
        return {
            "id": card_id,
            "name": name,
            "target_odds": target,
            "total_odds": total,
            "status": "NO_QUALIFYING_CARD",
            "message": "Not enough eligible fixtures to reach the target.",
            "legs": [],
            "odds_type": "ESTIMATED",
        }

    return {
        "id": card_id,
        "name": name,
        "target_odds": target,
        "total_odds": total,
        "status": "PENDING",
        "message": "Mixed accumulator using estimated odds.",
        "legs": legs,
        "odds_type": "ESTIMATED",
    }


def build_rollover_card(fixtures):
    candidates = diversified_pool(fixtures)
    legs = []
    product = 1.0

    for fixture in candidates:
        # Use the earlier lower-price markets for a smaller target.
        market_key = "over15"
        leg = make_leg(fixture, market_key)

        legs.append(leg)
        product *= leg["odds"]

        if product >= 2.50:
            break

        if len(legs) >= 5:
            break

    if not legs or product < 2.50:
        return {
            "id": "rollover-250",
            "name": "2.50 Odds Rollover Challenge",
            "target_odds": 2.50,
            "total_odds": round(product, 2),
            "status": "NO_QUALIFYING_CARD",
            "message": "No qualifying 2.50 estimated-odds selection is available.",
            "legs": [],
            "odds_type": "ESTIMATED",
        }

    with db_connection() as conn:
        row = conn.execute(
            "SELECT stage, status FROM rollover WHERE id=1"
        ).fetchone()

    return {
        "id": "rollover-250",
        "name": "2.50 Odds Rollover Challenge",
        "stage": row["stage"] if row else 1,
        "target_odds": 2.50,
        "total_odds": round(product, 2),
        "status": row["status"] if row else "PENDING",
        "message": "Each stage targets combined estimated odds of 2.50.",
        "legs": legs,
        "odds_type": "ESTIMATED",
    }


def build_all_cards(fixtures):
    cards = []

    for market_key, market in MARKETS.items():
        if market["group"] != "individual":
            continue
        cards.append(build_market_card(fixtures, market_key))

    cards.extend([
        build_mixed_card(
            fixtures, "midnight", "Midnight Accumulator",
            2.50, max_legs=8, time_filter="midnight"
        ),
        build_mixed_card(
            fixtures, "early-morning", "Early Morning Accumulator",
            2.50, max_legs=8, time_filter="early"
        ),
        build_mixed_card(
            fixtures, "high-roller", "High Roller",
            HIGH_ROLLER_TARGET, max_legs=14
        ),
        build_mixed_card(
            fixtures, "mega-mixed", "Mega Mixed",
            MEGA_MIXED_TARGET, max_legs=20
        ),
        build_rollover_card(fixtures),
    ])

    return cards


# ============================================================
# SETTLEMENT LOGIC
# ============================================================

def evaluate_market(fixture, market_key):
    home = fixture.get("home_goals")
    away = fixture.get("away_goals")

    if home is None or away is None:
        return "PENDING"

    total = home + away

    if market_key == "over15":
        return "WIN" if total >= 2 else "LOST"

    if market_key == "over25":
        return "WIN" if total >= 3 else "LOST"

    if market_key == "btts":
        return "WIN" if home >= 1 and away >= 1 else "LOST"

    if market_key == "home_over15":
        return "WIN" if home >= 2 else "LOST"

    if market_key == "away_over15":
        return "WIN" if away >= 2 else "LOST"

    if market_key == "home_over05":
        return "WIN" if home >= 1 else "LOST"

    if market_key == "away_over05":
        return "WIN" if away >= 1 else "LOST"

    if market_key == "one_x_btts":
        condition = home >= away and home >= 1 and away >= 1
        return "WIN" if condition else "LOST"

    if market_key == "x_two_btts":
        condition = away >= home and home >= 1 and away >= 1
        return "WIN" if condition else "LOST"

    if market_key == "home_win_over15":
        condition = home > away and total >= 2
        return "WIN" if condition else "LOST"

    if market_key == "away_win_over15":
        condition = away > home and total >= 2
        return "WIN" if condition else "LOST"

    if market_key == "first_half_over05":
        ht_home = fixture.get("halftime_home")
        ht_away = fixture.get("halftime_away")

        if ht_home is None or ht_away is None:
            return "PENDING"

        return "WIN" if ht_home + ht_away >= 1 else "LOST"

    return "PENDING"


def settle_card(card, fixture_map):
    if not card.get("legs"):
        return card

    leg_results = []
    any_lost = False
    all_won = True

    for leg in card["legs"]:
        fixture = fixture_map.get(leg["fixture_id"])

        if not fixture:
            leg["status"] = "PENDING"
            all_won = False
            leg_results.append("PENDING")
            continue

        # Do not settle a losing selection until the match is finished.
        if fixture.get("status") != "FINISHED":
            leg["status"] = "PENDING"
            all_won = False
            leg_results.append("PENDING")
            continue

        result = evaluate_market(fixture, leg["market"])
        leg["status"] = result
        leg["home_goals"] = fixture.get("home_goals")
        leg["away_goals"] = fixture.get("away_goals")

        if result == "LOST":
            any_lost = True
            all_won = False
        elif result != "WIN":
            all_won = False

        leg_results.append(result)

    if any_lost:
        card["status"] = "LOST"
    elif all_won and leg_results:
        card["status"] = "WON"
    else:
        card["status"] = "PENDING"

    return card


def save_cards(cards):
    today = datetime.now(WAT).date().isoformat()

    with db_connection() as conn:
        for card in cards:
            conn.execute("""
                INSERT INTO accumulator_cards
                (card_id, card_date, card_type, payload, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
            """, (
                card["id"],
                today,
                card.get("market") or card["id"],
                json.dumps(card),
                time.time()
            ))


def load_saved_cards():
    today = datetime.now(WAT).date().isoformat()

    with db_connection() as conn:
        rows = conn.execute("""
            SELECT payload FROM accumulator_cards
            WHERE card_date=?
        """, (today,)).fetchall()

    cards = []
    for row in rows:
        try:
            cards.append(json.loads(row["payload"]))
        except Exception:
            continue

    return cards


def update_rollover(cards):
    rollover_card = next(
        (c for c in cards if c.get("id") == "rollover-250"),
        None
    )

    if not rollover_card:
        return

    with db_connection() as conn:
        row = conn.execute(
            "SELECT stage, status FROM rollover WHERE id=1"
        ).fetchone()

        if not row:
            return

        # A completed stage is recorded. A lost stage ends the current
        # challenge; a won stage advances to the next stage.
        if rollover_card["status"] == "LOST":
            conn.execute("""
                UPDATE rollover
                SET status='LOST', current_card=?, updated_at=?
                WHERE id=1
            """, (json.dumps(rollover_card), time.time()))

        elif rollover_card["status"] == "WON":
            conn.execute("""
                UPDATE rollover
                SET stage=stage+1, status='PENDING',
                    current_card=NULL, updated_at=?
                WHERE id=1
            """, (time.time(),))

        else:
            conn.execute("""
                UPDATE rollover
                SET current_card=?, updated_at=?
                WHERE id=1
            """, (json.dumps(rollover_card), time.time()))


# ============================================================
# RESPONSE BUILDING
# ============================================================

def build_response(fixtures):
    fixture_map = {f["id"]: f for f in fixtures}

    cards = load_saved_cards()

    if not cards:
        cards = build_all_cards(fixtures)

    cards = [settle_card(card, fixture_map) for card in cards]
    save_cards(cards)
    update_rollover(cards)

    return {
        "ok": True,
        "updated_at": datetime.now(WAT).isoformat(),
        "timezone": "Africa/Lagos",
        "fixtures": sort_fixtures(fixtures),
        "cards": cards,
        "accumulators": cards,
        "markets": MARKETS,
        "api_usage": {
            "calls_today": api_usage_today(),
            "daily_limit": DAILY_API_LIMIT,
        },
        "odds_notice": (
            "All odds marked ESTIMATED are estimates, not confirmed "
            "bookmaker prices. No historical scoring statistics or "
            "confidence percentages are fabricated."
        ),
    }


# ============================================================
# API ROUTES
# ============================================================

@app.get("/")
def home():
    return jsonify({
        "name": "Goalzone247 API",
        "status": "running",
        "timezone": "Africa/Lagos",
        "endpoints": [
            "/api/daily",
            "/api/live",
            "/api/health",
        ],
    })


@app.get("/api/health")
def health():
    with db_connection() as conn:
        rollover = conn.execute(
            "SELECT stage, status FROM rollover WHERE id=1"
        ).fetchone()

    return jsonify({
        "ok": True,
        "service": "Goalzone247",
        "database": "connected",
        "api_key_configured": bool(API_KEY),
        "api_calls_today": api_usage_today(),
        "api_daily_limit": DAILY_API_LIMIT,
        "rollover": dict(rollover) if rollover else None,
        "time": datetime.now(WAT).isoformat(),
    })


@app.get("/api/daily")
def daily():
    try:
        fixtures = combine_fixtures()
        return jsonify(build_response(fixtures))

    except APIUnavailable as exc:
        # Serve the last saved fixtures when the API is temporarily
        # unavailable, rather than returning invented new fixtures.
        cached_daily = cache_get("daily_fixtures", 86400) or []
        cached_live = cache_get("live_fixtures", 86400) or []

        by_id = {f["id"]: f for f in cached_daily}
        for fixture in cached_live:
            by_id[fixture["id"]] = fixture

        if by_id:
            payload = build_response(sort_fixtures(list(by_id.values())))
            payload["stale_data"] = True
            payload["warning"] = str(exc)
            return jsonify(payload)

        return jsonify({
            "ok": False,
            "error": str(exc),
            "fixtures": [],
            "cards": [],
            "accumulators": [],
        }), 503

    except Exception as exc:
        app.logger.exception("Daily endpoint failed")
        return jsonify({
            "ok": False,
            "error": str(exc),
            "fixtures": [],
            "cards": [],
            "accumulators": [],
        }), 500


@app.get("/api/live")
def live():
    try:
        fixtures = fetch_live_fixtures()
        return jsonify({
            "ok": True,
            "fixtures": fixtures,
            "updated_at": datetime.now(WAT).isoformat(),
            "api_usage": {
                "calls_today": api_usage_today(),
                "daily_limit": DAILY_API_LIMIT,
            },
        })

    except APIUnavailable as exc:
        cached = cache_get("live_fixtures", 86400) or []
        return jsonify({
            "ok": bool(cached),
            "fixtures": cached,
            "stale_data": True,
            "warning": str(exc),
        })


# Public refresh endpoint intentionally disabled.
@app.route("/api/refresh", methods=["GET", "POST"])
def refresh_disabled():
    return jsonify({
        "ok": False,
        "error": "Manual refresh is disabled to protect the API quota.",
    }), 403


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
