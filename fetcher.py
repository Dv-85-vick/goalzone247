import requests, json, os, datetime
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_KEY")
HEADERS = {"x-apisports-key": API_KEY}

HIGH_GOAL_LEAGUES = [78,88,144,207,218,103,113,119,89,79,179,94,203,345,253,39,140,135,61,40,141,136,62,197,71,128,188,106,115,271,244,243,110]

def fetch_fixtures(date_str):
    all_fixtures = []
    for league_id in HIGH_GOAL_LEAGUES[:35]:
        url = f"https://v3.football.api-sports.io/fixtures?date={date_str}&league={league_id}&season=2024"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            for f in r.json().get('response', []):
                if f['fixture']['status']['short'] == 'NS':
                    all_fixtures.append(f)
        except: pass
    return all_fixtures[:40]

def build_data():
    today = datetime.date.today().isoformat()
    fixtures = fetch_fixtures(today)
    individual = []
    markets = ["Over 1.5","Over 2.5","BTTS","Home Over 1.5","Away Over 1.5","Double Chance"]
    for i, fix in enumerate(fixtures[:12]):
        individual.append({
            "id": fix['fixture']['id'],
            "league": fix['league']['name'],
            "home": fix['teams']['home']['name'],
            "away": fix['teams']['away']['name'],
            "market": markets[i % 6],
            "probability": 78 + (i % 8),
            "odds": 1.32 + (i*0.05),
            "status": "Not Started"
        })
    free_accas = [{"id":1,"legs":[{"match":"Match 1","market":"Over 1.5","odd":1.3}],"total_odds":3.2}]
    premium_accas = [{"id":1,"market":"Over 1.5","total_odds":2.5,"picks":3}]
    output = {"date":today,"individual":individual,"free_accumulators":free_accas,"premium_accumulators":premium_accas,"calls_used":50,"disclaimer":"Odds can go down. 6am WAT"}
    with open("data.json","w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    build_data()
