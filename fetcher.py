
import os
import json
import time
import requests
import tempfile

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==========================================
# CONFIGURATION
# ==========================================

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
} if API_KEY else {}

WAT = ZoneInfo("Africa/Lagos")

DATA_FILE = "data.json"
LOCK_FILE = "fetcher.lock"

API_COOLDOWN_SECONDS = 60
MANUAL_REFRESH_COOLDOWN_SECONDS = 120


# ==========================================
# FILE HELPERS
# ==========================================

def read_saved_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
    except Exception as error:
        print(f"Could not read saved data: {error}")

    return None


def save_data(data):
    """
    Save data safely using a temporary file,
    then replace data.json.
    """

    directory = os.path.dirname(os.path.abspath(DATA_FILE))

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            prefix="fetcher_",
            dir=directory,
            delete=False
        ) as file:

            json.dump(data, file, indent=2)
            temp_path = file.name

        os.replace(temp_path, DATA_FILE)

        return True

    except Exception as error:
        print(f"Could not save data.json: {error}")

        try:
            if "temp_path" in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

        return False


# ==========================================
# PROCESS LOCK
# ==========================================

def acquire_lock():

    try:
        descriptor = os.open(
            LOCK_FILE,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY
        )

        with os.fdopen(descriptor, "w") as file:
            file.write(str(time.time()))

        return True

    except FileExistsError:

        # Remove a lock left behind by a crashed process.
        try:
            lock_age = time.time() - os.path.getmtime(LOCK_FILE)

            if lock_age > 300:
                os.remove(LOCK_FILE)
                return acquire_lock()

        except Exception:
            pass

        return False

    except Exception as error:
        print(f"Lock error: {error}")
        return False


def release_lock():

    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as error:
        print(f"Could not release lock: {error}")


# ==========================================
# API REQUEST
# ==========================================

def api_get(endpoint, params):

    if not API_KEY:
        print("API_FOOTBALL_KEY is missing.")
        return []

    try:
        request_params = dict(params)

        if "timezone" not in request_params:
            request_params["timezone"] = "Africa/Lagos"

        response = requests.get(
            f"{BASE}/{endpoint}",
            headers=HEADERS,
            params=request_params,
            timeout=30
        )

        if response.status_code == 200:
            return response.json().get("response", [])

        print(
            f"API {endpoint} failed "
            f"{response.status_code}: "
            f"{response.text[:300]}"
        )

        return []

    except requests.RequestException as error:
        print(f"API error {endpoint}: {error}")
        return []

    except Exception as error:
        print(f"Unexpected API error {endpoint}: {error}")
        return []


# ==========================================
# ODDS PARSER
# ==========================================

def parse_odds(odds_data):

    markets = {}

    if not odds_data:
        return None

    try:
        bookmakers = odds_data.get("bookmakers", [])

        if not bookmakers:
            return None

        # Check all available bookmakers.
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

                    if name == "Match Winner":

                        if selection == "Home":
                            markets.setdefault("1", odd)

                        elif selection == "Away":
                            markets.setdefault("2", odd)

                    if "Over/Under" in name:

                        if selection == "Over 1.5":
                            markets.setdefault("ov1.5", odd)

                        elif selection == "Over 2.5":
                            markets.setdefault("ov2.5", odd)

                    if (
                        "Both Teams to Score" in name
                        and selection == "Yes"
                    ):
                        markets.setdefault("btts", odd)

                    if (
                        "Home Team Over/Under" in name
                        and "1.5" in selection
                        and "Over" in selection
                    ):
                        markets.setdefault("home_ov1.5", odd)

                    if (
                        "Away Team Over/Under" in name
                        and "1.5" in selection
                        and "Over" in selection
                    ):
                        markets.setdefault("away_ov1.5", odd)

        return markets if markets else None

    except Exception as error:
        print(f"Odds parsing error: {error}")
        return None


# ==========================================
# FETCH ONE DATE
# ==========================================

def build_for_date_light(date_str):

    # Keep the original two API calls per date.
    fixtures = api_get(
        "fixtures",
        {"date": date_str}
    )

    odds_list = api_get(
        "odds",
        {"date": date_str}
    )

    odds_map = {}

    for item in odds_list:

        try:
            fixture_id = item["fixture"]["id"]
            odds_map[fixture_id] = item

        except (KeyError, TypeError):
            continue

    pending = []

    for fixture in fixtures:

        try:
            fixture_id = fixture["fixture"]["id"]

            markets = (
                parse_odds(odds_map.get(fixture_id))
                if fixture_id in odds_map
                else None
            )

            # Preserve your estimated odds.
            # They are clearly marked as estimates.
            if not markets:

                markets = {
                    "ov1.5": 1.28,
                    "ov2.5": 1.75,
                    "btts": 1.80,
                    "home_ov1.5": 1.90,
                    "away_ov1.5": 2.20,
                    "_estimated": True
                }

            else:
                markets["_estimated"] = False

            results = {
                key: "PENDING"
                for key in markets
                if not key.startswith("_")
            }

            fixture_date = fixture["fixture"].get("date", "")

            status_data = fixture["fixture"].get("status", {})

            goals = fixture.get("goals", {})

            pending.append({

                "fixture_id": fixture_id,

                "league": fixture["league"]["name"],

                "league_id": fixture["league"]["id"],

                "home": fixture["teams"]["home"]["name"],

                "away": fixture["teams"]["away"]["name"],

                "time": fixture_date[11:16],

                "status": status_data.get("short", "NS"),

                "score_home": goals.get("home") or 0,

                "score_away": goals.get("away") or 0,

                "elapsed": status_data.get("elapsed") or 0,

                "markets": markets,

                "results": results,

                "score_rank": 10

            })

        except (KeyError, TypeError, ValueError) as error:

            print(f"Skipping invalid fixture: {error}")
            continue

    return {
        "matches": pending[:100],
        "accumulators": {},
        "api_calls": 2
    }


# ==========================================
# BUILD ALL FOUR DATES
# ==========================================

def build_data(light=False):

    today = datetime.now(WAT)

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
    total_calls = 0

    for key, date_string in dates.items():

        print(f"Fetching {key}: {date_string}")

        date_data = build_for_date_light(date_string)

        all_data[key] = {

            "date": date_string,

            "matches": date_data["matches"],

            "accumulators": date_data["accumulators"]

        }

        total_calls += date_data["api_calls"]

    final = {

        # New nested format
        "dates": all_data,

        "current_date": dates["today"],

        "last_update": datetime.now(WAT).isoformat(),

        "api_calls_today": total_calls,

        # Legacy format for older scripts
        "date": dates["today"],

        "matches": all_data["today"]["matches"],

        "accumulators": all_data["today"]["accumulators"]

    }

    return final


# ==========================================
# COOLDOWN CONTROL
# ==========================================

def fetch_with_cooldown(manual=False):

    saved = read_saved_data()

    now = time.time()

    last_fetch = 0
    last_manual = 0

    if saved:

        last_fetch = saved.get(
            "_cooldown_last_fetch",
            0
        )

        last_manual = saved.get(
            "_cooldown_last_manual",
            0
        )

    # Automatic 60-second cooldown.
    fetch_remaining = (
        API_COOLDOWN_SECONDS - (now - last_fetch)
    )

    if saved and last_fetch and fetch_remaining > 0:

        print(
            f"FETCHER COOLDOWN: "
            f"Wait {int(fetch_remaining + 0.99)} seconds."
        )

        return saved

    # Manual 120-second cooldown.
    if manual and last_manual:

        manual_remaining = (
            MANUAL_REFRESH_COOLDOWN_SECONDS
            - (now - last_manual)
        )

        if manual_remaining > 0:

            print(
                f"MANUAL COOLDOWN: "
                f"Wait {int(manual_remaining + 0.99)} seconds."
            )

            return saved

    # Prevent overlapping fetcher processes.
    if not acquire_lock():

        print("Another fetcher process is already running.")

        return saved

    try:

        # Check cooldown again after acquiring the lock.
        saved = read_saved_data()

        now = time.time()

        last_fetch = (
            saved.get("_cooldown_last_fetch", 0)
            if saved else 0
        )

        last_manual = (
            saved.get("_cooldown_last_manual", 0)
            if saved else 0
        )

        fetch_remaining = (
            API_COOLDOWN_SECONDS - (now - last_fetch)
        )

        if saved and last_fetch and fetch_remaining > 0:
            print("Another process has recently fetched the data.")
            return saved

        if manual and last_manual:

            manual_remaining = (
                MANUAL_REFRESH_COOLDOWN_SECONDS
                - (now - last_manual)
            )

            if manual_remaining > 0:
                print("Manual refresh cooldown is active.")
                return saved

        # Perform the actual fetch.
        print("Starting football data fetch...")

        fresh_data = build_data(light=True)

        completed_at = time.time()

        fresh_data["_cooldown_last_fetch"] = completed_at

        if manual:
            fresh_data["_cooldown_last_manual"] = completed_at
        else:
            fresh_data["_cooldown_last_manual"] = last_manual

        save_data(fresh_data)

        print(
            f"FETCH COMPLETE | "
            f"WAT Date: {fresh_data['current_date']} | "
            f"Calls: {fresh_data['api_calls_today']} | "
            f"Today's matches: "
            f"{len(fresh_data['dates']['today']['matches'])}"
        )

        return fresh_data

    finally:

        release_lock()


# ==========================================
# MAIN ENTRY POINT
# ==========================================

if __name__ == "__main__":

    # Default execution uses automatic cooldown.
    # Manual mode can be requested through:
    # FETCHER_MANUAL_REFRESH=1

    manual_mode = (
        os.getenv("FETCHER_MANUAL_REFRESH", "0") == "1"
    )

    fetch_with_cooldown(manual=manual_mode)
