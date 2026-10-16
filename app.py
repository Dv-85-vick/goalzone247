from flask import Flask, render_template, jsonify, request
import os, requests
from datetime import datetime, timedelta

app = Flask(__name__)
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE = "https://v3.football.api-sports.io"
HEADERS = {'x-apisports-key': API_KEY} if API_KEY else {}

def api_get(endpoint, params):
    try:
        r = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=15)
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
                if "Over/Under" in name:
                    if val=="Over 1.5": m['over15']=odd
                    if val=="Over 2.5": m['over25']=odd
                if "Both Teams to Score" in name and val=="Yes": m['btts']=odd
                if "Home Team" in name and "Over 1.5" in val: m['home_over15']=odd
                if "Away Team" in name and "Over 1.5" in val: m['away_over15']=odd
        if 'over15' not in m: m['over15']=1.30
        if 'over25' not in m: m['over25']=1.85
        if 'btts' not in m: m['btts']=1.90
        if 'home_over15' not in m: m['home_over15']=2.10
        if 'away_over15' not in m: m['away_over15']=2.40
        return m
    except:
        return {'over15':1.30,'over25':1.85,'btts':1.90,'home_over15':2.10,'away_over15':2.40}

CACHE={"data":None}

def build_all():
    today=datetime.now()
    dates={
        "yesterday":(today-timedelta(days=1)).strftime("%Y-%m-%d"),
        "today":today.strftime("%Y-%m-%d"),
        "tomorrow":(today+timedelta(days=1)).strftime("%Y-%m-%d"),
        "next_tomorrow":(today+timedelta(days=2)).strftime("%Y-%m-%d")
    }
    all_data={}
    for key, ds in dates.items():
        fixtures=api_get("fixtures", {"date": ds})
        odds_list=api_get("odds", {"date": ds})
        odds_map={o['fixture']['id']: o for o in odds_list}
        matches=[]
        for fx in fixtures[:50]:
            fid=fx['fixture']['id']
            markets=parse_odds(odds_map.get(fid))
            rank = 10 - (markets.get('over15',1.3)-1.0)*2
            matches.append({
                "fixture_id":fid,"league":fx['league']['name'],"home":fx['teams']['home']['name'],"away":fx['teams']['away']['name'],
                "time":fx['fixture']['date'][11:16],"status":fx['fixture']['status']['short'],
                "score_home":fx['goals']['home'] or 0,"score_away":fx['goals']['away'] or 0,
                "elapsed":fx['fixture']['status']['elapsed'] or 0,"markets":markets,
                "score_rank":rank
            })
        matches.sort(key=lambda x: x['score_rank'], reverse=True)
        if len(matches)==0:
            matches=[
                {"fixture_id":1,"league":"Premier League","home":"【entity-Arsenal¦canonical_name=Arsenal】","away":"【entity-Chelsea¦canonical_name=Chelsea】","time":"18:00","status":"NS","score_home":0,"score_away":0,"elapsed":0,"markets":{"over15":1.28,"over25":1.75,"btts":1.80,"home_over15":1.90,"away_over15":2.20},"score_rank":9},
                {"fixture_id":2,"league":"La Liga","home":"【entity-Real Madrid¦canonical_name=Real Madrid】","away":"【entity-Barcelona¦canonical_name=Barcelona】","time":"20:00","status":"NS","score_home":0,"score_away":0,"elapsed":0,"markets":{"over15":1.30,"over25":1.85,"btts":1.75,"home_over15":2.00,"away_over15":2.10},"score_rank":8.5},
            ]
        accas = generate_accumulators(matches)
        all_data[key]={"date":ds,"matches":matches,"accumulators":accas}
    return {"dates":all_data,"current_date":dates["today"],"last_update":datetime.now().isoformat(),"api_calls_today":8}

def generate_accumulators(matches):
    def build_single_market(market_key, target_odds):
        legs=[]; used=set(); total=1.0
        sorted_m = sorted(matches, key=lambda x: x['markets'].get(market_key, 9.9))
        for m in sorted_m:
            fid=m['fixture_id']
            if fid in used: continue # NO DUPLICATE - 【entity-Chelsea¦canonical_name=Chelsea】 can't appear twice
            odd=m['markets'].get(market_key)
            if not odd: continue
            legs.append({"fixture_id":fid,"home":m['home'],"away":m['away'],"league":m['league'],"market":market_key,"odd":odd,"time":m['time']})
            used.add(fid)
            total*=odd
            if total>=target_odds:
                break
        return {"legs":legs,"total_odds":round(total,2),"count":len(legs),"target":target_odds}

    def build_mix(target_odds):
        legs=[]; used=set(); total=1.0
        pool=[]
        for m in matches:
            for mk in ['over15','over25','btts','home_over15','away_over15']:
                odd=m['markets'].get(mk)
                if odd:
                    pool.append({"fid":m['fixture_id'],"home":m['home'],"away":m['away'],"league":m['league'],"market":mk,"odd":odd,"rank":m['score_rank'],"time":m['time']})
        pool.sort(key=lambda x: (x['rank'], -1/x['odd']), reverse=True)
        for p in pool:
            if p['fid'] in used: continue # NO DUPLICATE IN MIX
            legs.append({"fixture_id":p['fid'],"home":p['home'],"away":p['away'],"league":p['league'],"market":p['market'],"odd":p['odd'],"time":p['time']})
            used.add(p['fid'])
            total*=p['odd']
            if total>=target_odds:
                break
        return {"legs":legs,"total_odds":round(total,2),"count":len(legs),"target":target_odds}

    accas={}
    for mk in ['over15','over25','btts','home_over15','away_over15']:
        accas[mk] = {"3": build_single_market(mk, 3.0), "6": build_single_market(mk, 6.0)}
    accas['mix'] = {"10": build_mix(10.0), "20": build_mix(20.0)}
    return accas

def get_data():
    global CACHE
    if CACHE["data"]:
        return CACHE["data"]
    data=build_all()
    CACHE["data"]=data
    return data

@app.route('/')
def index():
    d=get_data()
    sel=request.args.get('date','today')
    dd=d['dates'].get(sel) or d['dates'].get('today')
    return render_template('index.html', data=d, selected_date=sel, dates=d['dates'], matches=dd['matches'], accas=dd['accumulators'], date=dd['date'], total=len(dd['matches']), api_calls=d['api_calls_today'], last_update=d['last_update'], api_key_set=bool(API_KEY))

@app.route('/api/refresh')
def refresh():
    global CACHE
    CACHE["data"]=None
    d=get_data()
    return jsonify({"status":"ok","today":len(d['dates']['today']['matches'])})

@app.route('/api/live')
def live():
    return jsonify(get_data())

if __name__=='__main__':
    port=int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0',port=port)