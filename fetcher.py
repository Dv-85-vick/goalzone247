import os, json, requests
from datetime import datetime, timedelta

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY}
HIGH_LEAGUES = ["J1 League","J2 League","J League","【entity-K League¦canonical_name=K League】","A-League","Chinese Super League","CSL","China","Austrian","【entity-Eredivisie¦canonical_name=Eredivisie】","【entity-Bundesliga¦canonical_name=Bundesliga】","Jupiler"]

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
                if "Home Team Total" in name and "Over 1.5" in val: m['home_ov1.5']=odd
                if "Away Team Total" in name and "Over 1.5" in val: m['away_ov1.5']=odd
        return m if m else None
    except:
        return None

def get_team_stats(team_id, league_id):
    season=datetime.now().year
    for s in [season, season-1]:
        data=api_get("teams/statistics", {"team": team_id, "league": league_id, "season": s})
        if data:
            try:
                gf=data.get('goals',{}).get('for',{}).get('average',{}).get('total')
                ga=data.get('goals',{}).get('against',{}).get('average',{}).get('total')
                gf=float(gf) if gf else 0; ga=float(ga) if ga else 0
                return {"avg_for":gf,"avg_against":ga,"total_avg":gf+ga}
            except:
                continue
    return None

def build_for_date(date_str, is_today=False):
    fixtures=api_get("fixtures", {"date": date_str})
    odds_list=api_get("odds", {"date": date_str})
    odds_map={o['fixture']['id']: o for o in odds_list}
    pending=[]
    for fx in fixtures:
        short=fx['fixture']['status']['short']
        if date_str==(datetime.now()-timedelta(days=1)).strftime("%Y-%m-%d"):
            if short not in ['FT','AET','PEN']: continue
        else:
            if short not in ['NS','TBD']: continue
        fid=fx['fixture']['id']
        markets=parse_odds(odds_map[fid]) if fid in odds_map else None
        if not markets:
            markets={"ov1.5":1.35,"ov2.5":1.85,"btts":1.80,"1":2.1,"2":2.5,"_estimated":True}
        else:
            markets["_estimated"]=False
        league=fx['league']['name']
        is_high=any(h.lower() in league.lower() for h in HIGH_LEAGUES)
        score=20 if is_high else 0
        if markets.get('ov1.5',10)<=1.35: score+=25
        pending.append({
            "fixture_id":fid,"league_id":fx['league']['id'],"team_home_id":fx['teams']['home']['id'],"team_away_id":fx['teams']['away']['id'],
            "league":league,"home":fx['teams']['home']['name'],"away":fx['teams']['away']['name'],
            "time":fx['fixture']['date'][11:16],"status":short,"score_home":fx['goals']['home'] or 0,"score_away":fx['goals']['away'] or 0,
            "elapsed":fx['fixture']['status']['elapsed'] or 0,"markets":markets,"results":{k:"PENDING" for k in markets if not k.startswith('_')},
            "stats":None,"score_rank":score
        })
    pending.sort(key=lambda x: x['score_rank'], reverse=True)
    best_50=pending[:50]
    api_calls=2
    if is_today and best_50:
        print(f"Fetching stats for TOP 25...")
        for match in best_50[:25]: # TOP 25 = 50 calls
            hs=get_team_stats(match['team_home_id'], match['league_id']); api_calls+=1
            aw=get_team_stats(match['team_away_id'], match['league_id']); api_calls+=1
            if hs and aw:
                comb=hs['total_avg']+aw['total_avg']
                match['stats']={"home":hs,"away":aw,"combined_avg":comb}
                if comb>=3.0: match['score_rank']+=30
                elif comb>=2.5: match['score_rank']+=20
                if hs['avg_for']>=1.5 or aw['avg_for']>=1.5: match['score_rank']+=10
        best_50.sort(key=lambda x: x['score_rank'], reverse=True)

    def combo(market,target,count):
        pool=[x for x in best_50 if market in x['markets']]; pool.sort(key=lambda x: x['score_rank'], reverse=True)
        legs=[]; total=1
        for item in pool:
            if len(legs)>=count and total>=target: break
            odd=item['markets'][market]; total*=odd
            legs.append({"fixture_id":item['fixture_id'],"game":f"{item['home']} vs {item['away']}","market":market,"odd":odd,"status":"PENDING","live":f"{item['score_home']}-{item['score_away']}"})
        return {"total_odd":round(total,2),"legs":legs,"status":"PENDING","win_count":f"0/{len(legs)}"}
    def mix(target):
        legs=[]; total=1; used=set(); picks=[]
        for item in best_50:
            for mk in ['ov1.5','ov2.5','btts']:
                if mk in item['markets']: picks.append((item,mk))
        picks.sort(key=lambda x: x[0]['score_rank'], reverse=True)
        for item,mk in picks:
            if item['fixture_id'] in used: continue
            if total>=target and len(legs)>=5: break
            odd=item['markets'][mk]; total*=odd
            legs.append({"fixture_id":item['fixture_id'],"game":f"{item['home']} vs {item['away']}","market":mk,"odd":odd,"status":"PENDING","live":f"{item['score_home']}-{item['score_away']}"})
            used.add(item['fixture_id'])
        return {"total_odd":round(total,2),"legs":legs,"status":"PENDING","win_count":f"0/{len(legs)}"}

    accas={"ov1.5_3odds":combo('ov1.5',3,3),"ov1.5_5odds":combo('ov1.5',5,5),"ov2.5_3odds":combo('ov2.5',3,3),"ov2.5_5odds":combo('ov2.5',5,5),"btts_3odds":combo('btts',3,3),"btts_5odds":combo('btts',5,5),"mix_10odds":mix(10),"mix_20odds":mix(20)}
    return {"matches":best_50,"accumulators":accas,"api_calls":api_calls}

def build_data():
    today=datetime.now()
    dates={"yesterday":(today-timedelta(days=1)).strftime("%Y-%m-%d"),"today":today.strftime("%Y-%m-%d"),"tomorrow":(today+timedelta(days=1)).strftime("%Y-%m-%d"),"next_tomorrow":(today+timedelta(days=2)).strftime("%Y-%m-%d")}
    all_data={}; total=0
    for key,ds in dates.items():
        is_today=(key=="today")
        data=build_for_date(ds,is_today=is_today)
        all_data[key]={"date":ds,"matches":data["matches"],"accumulators":data["accumulators"]}
        total+=data["api_calls"]
    final={"dates":all_data,"current_date":dates["today"],"last_update":datetime.now().isoformat(),"api_calls_today":total,"stats_top":25}
    if total<5 and os.path.exists('data.json'):
        with open('data.json') as f:
            old=json.load(f)
            if len(old.get('dates',{}).get('today',{}).get('matches',[]))>10:
                return old
    with open('data.json','w') as f:
        json.dump(final,f,indent=2)
    print(f"BUILD DONE 00H - Calls: {total}")
    return final

if __name__=="__main__":
    build_data()