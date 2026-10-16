import os, json, requests
from datetime import datetime

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY}

# Your leagues - J, K, Australia, Austria, China + high scoring
HIGH_LEAGUES = [
    "J1 League","J2 League","J League","Japan",
    "K League 1","K League 2","K League",
    "A-League","Australia",
    "Chinese Super League","China Super League","China",
    "Austrian Bundesliga","Austria",
    "Eredivisie","Bundesliga","Jupiler Pro League","Super League",
    "Premiership","Eliteserien","Allsvenskan","Premier League"
]

def api_get(endpoint, params):
    r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=20)
    if r.status_code==200:
        return r.json().get('response',[])
    print(f"API Error {endpoint}: {r.status_code}")
    return []

def parse_real_odds(odds_obj):
    """READ REAL ODDS from bookmaker - no calculation"""
    markets={}
    try:
        bookmaker = odds_obj['bookmakers'][0] # Bet365
        for bet in bookmaker['bets']:
            name = bet['name']
            for val in bet['values']:
                v = val['value']
                odd = float(val['odd'])
                # Your 6 markets
                if name=="Match Winner":
                    if v=="Home": markets['1']=odd
                    if v=="Away": markets['2']=odd
                if "Over/Under" in name:
                    if v=="Over 1.5": markets['ov1.5']=odd
                    if v=="Over 2.5": markets['ov2.5']=odd
                if "Both Teams to Score" in name and v=="Yes":
                    markets['btts']=odd
                if "Home Team Total" in name and "Over 1.5" in v:
                    markets['home_ov1.5']=odd
                if "Away Team Total" in name and "Over 1.5" in v:
                    markets['away_ov1.5']=odd
        return markets if 'ov1.5' in markets else None
    except:
        return None

def build_data():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"FINAL BUILD {today}")

    # 2 CALLS ONLY FOR THE DAY
    fixtures = api_get("fixtures", {"date": today}) # CALL 1
    odds_list = api_get("odds", {"date": today}) # CALL 2
    odds_map = {o['fixture']['id']: o for o in odds_list}

    pending = []
    for fx in fixtures:
        # ONLY PENDING MATCHES
        if fx['fixture']['status']['short']!= 'NS':
            continue
        fid = fx['fixture']['id']
        if fid not in odds_map: continue

        league = fx['league']['name']
        is_high = any(h.lower() in league.lower() for h in HIGH_LEAGUES)
        markets = parse_real_odds(odds_map[fid])
        if not markets: continue

        # Score for best of best
        score = 20 if is_high else 0
        if markets.get('ov1.5', 10) <= 1.35: score+=30

        pending.append({
            "fixture_id": fid,
            "league": league,
            "home": fx['teams']['home']['name'],
            "away": fx['teams']['away']['name'],
            "time": fx['fixture']['date'][11:16],
            "status": "PENDING",
            "score_home": 0,
            "score_away": 0,
            "elapsed": 0,
            "markets": markets, # REAL ODDS
            "results": {k: "PENDING" for k in markets}, # WIN/LOSE stickers
            "score_rank": score
        })

    pending.sort(key=lambda x: x['score_rank'], reverse=True)
    best_50 = pending[:50] # Your 50 best
    best_70 = pending[:70] # For accas

    # Build Accumulators with REAL ODDS
    accas = build_accas(best_70)

    data={
        "date": today,
        "matches": best_50,
        "accumulators": accas,
        "last_update": datetime.now().isoformat(),
        "api_calls_today": 2
    }
    with open('data.json','w') as f:
        json.dump(data,f,indent=2)
    print(f"FINAL: {len(best_50)} matches with REAL ODDS")
    return data

def build_accas(best_70):
    def make_combo(market, target, count):
        pool=[x for x in best_70 if market in x['markets']]
        pool.sort(key=lambda x: x['score_rank'], reverse=True)
        legs=[]; total=1
        for item in pool:
            if len(legs)>=count and total>=target: break
            odd=item['markets'][market]
            total*=odd
            legs.append({"fixture_id": item['fixture_id'], "game": f"{item['home']} vs {item['away']}", "market": market, "odd": odd, "status": "PENDING", "live": "0-0"})
        return {"total_odd": round(total,2), "legs": legs, "status": "PENDING", "win_count": f"0/{len(legs)}"}

    def make_mix(target):
        legs=[]; total=1; used=set()
        # Mix all your markets
        all_picks=[]
        for item in best_70:
            for mk in ['ov1.5','ov2.5','btts','home_ov1.5','away_ov1.5','1','2']:
                if mk in item['markets']:
                    all_picks.append((item,mk))
        all_picks.sort(key=lambda x: x[0]['score_rank'], reverse=True)
        for item,mk in all_picks:
            if item['fixture_id'] in used: continue
            if total>=target and len(legs)>=5: break
            odd=item['markets'][mk]
            total*=odd
            legs.append({"fixture_id": item['fixture_id'], "game": f"{item['home']} vs {item['away']}", "market": mk, "odd": odd, "status": "PENDING", "live": "0-0"})
            used.add(item['fixture_id'])
        return {"total_odd": round(total,2), "legs": legs, "status": "PENDING", "win_count": f"0/{len(legs)}"}

    return {
        "ov1.5_3odds": make_combo('ov1.5', 3, 3),
        "ov1.5_5odds": make_combo('ov1.5', 5, 5),
        "ov2.5_3odds": make_combo('ov2.5', 3, 3),
        "ov2.5_5odds": make_combo('ov2.5', 5, 5),
        "btts_3odds": make_combo('btts', 3, 3),
        "btts_5odds": make_combo('btts', 5, 5),
        "mix_10odds": make_mix(10),
        "mix_20odds": make_mix(20),
    }

if __name__=="__main__":
    build_data()