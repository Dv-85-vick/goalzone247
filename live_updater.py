
import os
import json
import time
import requests
import tempfile

from datetime import datetime
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

# Use the SAME lock file as fetcher.py.
LOCK_FILE = "fetcher.lock"

# Minimum time between live API requests.
LIVE_COOLDOWN_SECONDS = 60


# ==========================================
# FILE LOCK
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

        # Remove stale lock left by a crashed process.
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
# DATA FILE HELPERS
# ==========================================

def load_data():

    if not os.path.exists(DATA_FILE):
        print("No data.json found.")
        return None

    try:

        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as error:

        print(f"Could not read data.json: {error}")

        return None


def save_data(data):

    directory = os.path.dirname(
        os.path.abspath(DATA_FILE)
    )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            prefix="update_",
            dir=directory,
            delete=False
        ) as file:

            json.dump(data, file, indent=2)

            temp_path = file.name

        os.replace(temp_path, DATA_FILE)

        return True

    except Exception as error:

        print(f"Could not save data.json: {error}")

        if temp_path and os.path.exists(temp_path):

            try:
                os.remove(temp_path)
            except Exception:
                pass

        return False


# ==========================================
# FOOTBALL API
# ==========================================

def get_live_fixtures(date_string):

    if not API_KEY:

        print("API_FOOTBALL_KEY is missing.")

        return None

    try:

        response = requests.get(

            f"{BASE}/fixtures",

            headers=HEADERS,

            params={
                "date": date_string,
                "timezone": "Africa/Lagos"
            },

            timeout=20

        )

        if response.status_code != 200:

            print(
                f"API failed {response.status_code}: "
                f"{response.text[:200]}"
            )

            return None

        return response.json().get("response", [])

    except requests.RequestException as error:

        print(f"Live API request error: {error}")

        return None

    except Exception as error:

        print(f"Unexpected API error: {error}")

        return None


# ==========================================
# MARKET RESULT CALCULATOR
# ==========================================

def get_result(market, gh, ga, status):

    finished_statuses = {
        "FT",
        "AET",
        "PEN"
    }

    if status == "NS":
        return "PENDING"

    total = gh + ga

    finished = status in finished_statuses

    if market == "ov1.5":

        if total >= 2:
            return "WIN"

        return "LOSE" if finished else "LIVE"

    if market == "ov2.5":

        if total >= 3:
            return "WIN"

        return "LOSE" if finished else "LIVE"

    if market == "btts":

        if gh > 0 and ga > 0:
            return "WIN"

        return "LOSE" if finished else "LIVE"

    if market == "home_ov1.5":

        if gh >= 2:
            return "WIN"

        return "LOSE" if finished else "LIVE"

    if market == "away_ov1.5":

        if ga >= 2:
            return "WIN"

        return "LOSE" if finished else "LIVE"

    if market == "1":

        if not finished:
            return "LIVE"

        return "WIN" if gh > ga else "LOSE"

    if market == "2":

        if not finished:
            return "LIVE"

        return "WIN" if ga > gh else "LOSE"

    return "PENDING"


# ==========================================
# FIXTURE UPDATE
# ==========================================

def update_match(match, live_map):

    fixture_id = match.get("fixture_id")

    if not fixture_id:
        return False

    fixture = live_map.get(fixture_id)

    if not fixture:
        return False

    try:

        goals = fixture.get("goals", {})

        fixture_data = fixture.get("fixture", {})

        status_data = fixture_data.get("status", {})

        gh = goals.get("home")

        ga = goals.get("away")

        # Keep zero as zero.
        gh = gh if gh is not None else 0

        ga = ga if ga is not None else 0

        status = status_data.get("short", "NS")

        elapsed = status_data.get("elapsed") or 0

        match["score_home"] = gh

        match["score_away"] = ga

        match["elapsed"] = elapsed

        match["status"] = status

        markets = match.get("markets", {})

        results = match.setdefault("results", {})

        for market in markets:

            if market.startswith("_"):
                continue

            results[market] = get_result(
                market,
                gh,
                ga,
                status
            )

        return True

    except Exception as error:

        print(
            f"Could not update fixture {fixture_id}: {error}"
        )

        return False


# ==========================================
# UPDATE ACCUMULATORS
# ==========================================

def update_accumulators(accumulator_data, live_map):

    if not isinstance(accumulator_data, dict):
        return

    for accumulator in accumulator_data.values():

        if not isinstance(accumulator, dict):
            continue

        legs = accumulator.get("legs", [])

        wins = 0
        losses = 0
        pending = 0
        live_count = 0

        for leg in legs:

            fixture_id = leg.get("fixture_id")

            fixture = live_map.get(fixture_id)

            if not fixture:
                pending += 1
                continue

            try:

                goals = fixture.get("goals", {})

                fixture_data = fixture.get("fixture", {})

                status_data = fixture_data.get("status", {})

                gh = goals.get("home")
                ga = goals.get("away")

                gh = gh if gh is not None else 0

                ga = ga if ga is not None else 0

                status = status_data.get("short", "NS")

                elapsed = status_data.get("elapsed") or 0

                result = get_result(
                    leg.get("market"),
                    gh,
                    ga,
                    status
                )

                leg["status"] = result

                leg["live"] = (
                    f"{gh}-{ga} {status} {elapsed}'"
                )

                if result == "WIN":
                    wins += 1

                elif result == "LOSE":
                    losses += 1

                elif result == "LIVE":
                    live_count += 1

                else:
                    pending += 1

            except Exception as error:

                print(
                    f"Accumulator leg update error: {error}"
                )

                pending += 1

        total_legs = len(legs)

        if total_legs == 0:
            continue

        accumulator["win_count"] = (
            f"{wins}/{total_legs}"
        )

        accumulator["lose_count"] = (
            f"{losses}/{total_legs}"
        )

        # A single losing selection makes the accumulator lose.
        if losses > 0:

            accumulator["status"] = "LOSE"

        elif wins == total_legs:

            accumulator["status"] = "WIN"

        elif live_count > 0:

            accumulator["status"] = "LIVE"

        else:

            accumulator["status"] = "PENDING"


# ==========================================
# MAIN LIVE UPDATE
# ==========================================

def update_live():

    # Acquire the shared file lock before reading or writing.
    if not acquire_lock():

        print(
            "Another fetcher or updater is running. "
            "Live update skipped."
        )

        return

    try:

        data = load_data()

        if not data:
            return

        # ==================================
        # DATE
        # ==================================

        today = (
            data.get("current_date")
            or data.get("date")
        )

        if (
            not today
            and "dates" in data
            and "today" in data["dates"]
        ):

            today = data["dates"]["today"].get("date")

        if not today:

            print("ERROR: No date found in data.json")

            return

        # ==================================
        # LIVE REQUEST COOLDOWN
        # ==================================

        now = time.time()

        last_live_update = data.get(
            "_cooldown_last_live_update",
            0
        )

        remaining = (
            LIVE_COOLDOWN_SECONDS
            - (now - last_live_update)
        )

        if last_live_update and remaining > 0:

            print(
                f"LIVE COOLDOWN: Wait "
                f"{int(remaining + 0.99)} seconds."
            )

            return

        print(f"Fetching LIVE for {today} WAT...")

        # ==================================
        # FETCH LIVE FIXTURES
        # ==================================

        live_fixtures = get_live_fixtures(today)

        # Even a failed attempt gets a cooldown,
        # preventing repeated API requests.
        data["_cooldown_last_live_update"] = time.time()

        if live_fixtures is None:

            save_data(data)

            print("Live API request failed. Existing data preserved.")

            return

        live_map = {}

        for fixture in live_fixtures:

            try:

                fixture_id = fixture["fixture"]["id"]

                live_map[fixture_id] = fixture

            except (KeyError, TypeError):
                continue

        print(
            f"API returned {len(live_map)} fixtures for {today}"
        )

        # ==================================
        # UPDATE ALL MATCH LISTS
        # ==================================

        updated = 0

        seen_lists = []

        # Nested date format.
        if isinstance(data.get("dates"), dict):

            for day_key, day_data in data["dates"].items():

                if not isinstance(day_data, dict):
                    continue

                matches = day_data.get("matches", [])

                if isinstance(matches, list):
                    seen_lists.append(matches)

        # Legacy flat format.
        if isinstance(data.get("matches"), list):

            seen_lists.append(data["matches"])

        # Update each list independently because
        # nested and flat JSON entries may be separate copies.
        for match_list in seen_lists:

            for match in match_list:

                if update_match(match, live_map):
                    updated += 1

        # ==================================
        # UPDATE ACCUMULATORS
        # ==================================

        update_accumulators(
            data.get("accumulators", {}),
            live_map
        )

        # Update accumulators for all nested dates too.
        if isinstance(data.get("dates"), dict):

            for day_data in data["dates"].values():

                if not isinstance(day_data, dict):
                    continue

                update_accumulators(
                    day_data.get("accumulators", {}),
                    live_map
                )

        # ==================================
        # KEEP DATA FORMATS IN SYNC
        # ==================================

        if (
            isinstance(data.get("dates"), dict)
            and isinstance(data["dates"].get("today"), dict)
        ):

            today_data = data["dates"]["today"]

            # Keep today's nested matches and legacy matches
            # synchronized using the updated legacy list.
            if isinstance(data.get("matches"), list):

                today_data["matches"] = data["matches"]

            today_data["last_update"] = datetime.now(
                WAT
            ).isoformat()

        # ==================================
        # UPDATE TIMESTAMPS AND API COUNT
        # ==================================

        data["last_update"] = datetime.now(
            WAT
        ).isoformat()

        data["api_calls_today"] = (
            data.get("api_calls_today", 0) + 1
        )

        # ==================================
        # SAVE
        # ==================================

        if save_data(data):

            print(
                f"Live update completed. "
                f"Updated match entries: {updated}. "
                f"API calls recorded: {data['api_calls_today']}"
            )

        else:

            print("Live update could not be saved.")

    finally:

        release_lock()


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":

    update_live()
