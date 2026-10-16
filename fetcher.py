import os, json, requests
from datetime import datetime, timedelta

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY}

def api_get(endpoint, params):
    try:
        r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=20)
        if r.status_code==200:
            return r.json().get('response',[])
        return []
    except:
        return []

def parse_odds(o):
    m={}
    try:
        for bet in o['bookmakers'][0]['bets']:
            name=bet['name']
            for v in bet['values']:
                odd=float(v['odd']); val=v['value']
                if name=="Match Winner":
                    if val=="Home": m['1']=odd
                    if val=="Away": m['2']=odd
                if "Over/Under" in name:
                    if val=="Over 1.5": m['ov1.5']=odd
                    if val=="Over 2.5": m['ov2.5']=odd
                if "Both Teams to Score" in name and val=="Yes": m['btts']=odd
        return m if m else None
    except:
        return None

def build_for_date_light(date_str):
    fixtures=api_get("fixtures", {"date": date_str})
    odds_list=api_get("odds", {"date": date_str})
    odds_map={o['fixture']['id']: o for o in odds_list}
    pending=[]
    for fx in fixtures:
        fid=fx['fixture']['id']
        markets=parse_odds(odds_map[fid]) if fid in odds_map else None
        if not markets:
            markets={"ov1.5":1.35,"ov2.5":1.85,"btts":1.80,"_estimated":True}
        else:
            markets["_estimated"]=False
        pending.append({
            "fixture_id":fid,"league":fx['league']['name'],"home":fx['teams']['home']['name'],"away":fx['teams']['away']['name'],
            "time":fx['fixture']['date'][11:16],"status":fx['fixture']['status']['short'],
            "score_home":fx['goals']['home'] or 0,"score_away":fx['goals']['away'] or 0,
            "elapsed":fx['fixture']['status']['elapsed'] or 0,"markets":markets,
            "results":{k:"PENDING" for k in markets if not k.startswith('_')},
            "score_rank":10
        })
    return {"matches":pending[:50],"accumulators":{},"api_calls":2}

def build_data(light=False):
    today=datetime.now()
    dates={"yesterday":(today-timedelta(days=1)).strftime("%Y-%m-%d"),"today":today.strftime("%Y-%m-%d"),"tomorrow":(today+timedelta(days=1)).strftime("%Y-%m-%d"),"next_tomorrow":(today+timedelta(days=2)).strftime("%Y-%m-%d")}
    all_data={}; total=0
    for key,ds in dates.items():
        data=build_for_date_light(ds)
        all_data[key]={"date":ds,"matches":data["matches"],"accumulators":data["accumulators"]}
        total+=data["api_calls"]
    final={"dates":all_data,"current_date":dates["today"],"last_update":datetime.now().isoformat(),"api_calls_today":total}
    with open('data.json','w') as f:
        json.dump(final,f,indent=2)
    print(f"LIGHT BUILD DONE - Calls: {total}")
    return final

if __name__=="__main__":
    build_data(light=True)