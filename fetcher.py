import os
import json
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

headers = {
    'x-apisports-key': API_KEY
}

def fetch_fixtures():
    if not API_KEY:
        print("❌ NO API KEY FOUND! Check Render Environment Variables")
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"Fetching fixtures for {today}...")
    
    # Don't use season param, just date - works better for free plan
    url = f"{BASE_URL}/fixtures?date={today}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        
        if response.status_code != 200:
            print(f"API Error: {data}")
            return []
            
        fixtures = data.get('response', [])
        print(f"✅ Found {len(fixtures)} fixtures from API")
        
        # If no fixtures today, try tomorrow
        if len(fixtures) == 0:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"No fixtures today, trying {tomorrow}...")
            url = f"{BASE_URL}/fixtures?date={tomorrow}"
            response = requests.get(url, headers=headers, timeout=30)
            data = response.json()
            fixtures = data.get('response', [])
            print(f"✅ Found {len(fixtures)} fixtures for tomorrow")
        
        return fixtures[:20]  # limit to 20
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

if __name__ == "__main__":
    fixtures = fetch_fixtures()
    # Save to data.json
    with open('data.json', 'w') as f:
        json.dump(fixtures if fixtures else [{"demo": True, "note": "No fixtures"}], f, indent=2)
    print(f"data.json created with {len(fixtures)} matches")