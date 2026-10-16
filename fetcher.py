import os
import json
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

def fetch_fixtures():
    headers = {'x-apisports-key': API_KEY} if API_KEY else {}
    
    if not API_KEY:
        print("❌ NO API KEY")
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"Fetching for {today}")
    
    try:
        url = f"{BASE_URL}/fixtures?date={today}"
        r = requests.get(url, headers=headers, timeout=20)
        print(f"Status: {r.status_code}")
        data = r.json()
        fixtures = data.get('response', [])
        print(f"Found {len(fixtures)} fixtures")
        
        if len(fixtures) == 0:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            url = f"{BASE_URL}/fixtures?date={tomorrow}"
            r = requests.get(url, headers=headers, timeout=20)
            data = r.json()
            fixtures = data.get('response', [])
            print(f"Tomorrow {tomorrow}: {len(fixtures)} fixtures")
        
        return fixtures
    except Exception as e:
        print(f"Error: {e}")
        return []

def build_data():
    """This is what app.py calls"""
    fixtures = fetch_fixtures()
    
    # Convert to your site format
    matches = []
    for fx in fixtures[:20]:
        try:
            matches.append({
                "league": fx['league']['name'],
                "home": fx['teams']['home']['name'],
                "away": fx['teams']['away']['name'],
                "time": fx['fixture']['date'][11:16],
                "status": fx['fixture']['status']['short']
            })
        except:
            continue
    
    # If no real fixtures, return demo so site doesn't look empty
    if not matches:
        matches = [
            {"league": "Premier League", "home": "Man City", "away": "Arsenal", "time": "15:00", "market": "Over 1.5 - 1.4x", "confidence": "95%", "status": "Not Started"},
            {"league": "La Liga", "home": "Barcelona", "away": "Sevilla", "time": "17:30", "market": "Barcelona Win - 1.65x", "confidence": "90%", "status": "Not Started"}
        ]
    
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "matches": matches,
        "api_calls": 1 if fixtures else 0
    }
    
    # Save
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"data.json created with {len(matches)} matches")
    return data