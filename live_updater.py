import json, requests, os
from datetime import datetime

API_KEY=os.getenv("API_FOOTBALL_KEY")
BASE="https://v3.football.api-sports.io"
HEADERS={'x-apisports-key': API_KEY}

def get_result(market, gh, ga, status):
    if status=='NS': return "PENDING"
    total=gh+ga
    if market=='ov1.5': return "WIN" if total>=2 else "LOSE" if status=='FT' else "LIVE"
    if market=='ov2.5': return "WIN" if total>=3 else "LOSE" if status=='FT' else "LIVE"
    if market=='btts': return "WIN" if gh>0 and ga>0 else "LOSE" if status=='FT' else "LIVE"
    if market=='home_ov1.5': return "WIN" if gh>=2 else "LOSE" if status=='FT' else "LIVE"
    if market=='away_ov1.5': return "WIN" if ga>=2 else "LOSE" if status=='FT' else "LIVE"
    if market=='1': return "WIN" if status=='FT' and gh>ga else "LOSE" if status=='FT' else "LIVE"
    if market=='2': return "WIN" if status=='FT' and ga>gh else "LOSE" if status=='FT' else "LIVE"
    return "PENDING"

def update_live():
    if not os.path.exists('data.json'): return
    with open('data.json') as f:
        data=json.load(f)

    today=data.get('date')
    r=requests.get(f"{BASE}/fixtures", headers=HEADERS, params={"date": today}, timeout=15)
    if r.status_code!=200: return
    live_map={fx['fixture']['id']: fx for fx in r.json().get('response',[])}

    for m in data['matches']:
        fx=live_map.get(m['fixture_id'])
        if not fx: continue
        gh=fx['goals']['home'] or 0
        ga=fx['goals']['away'] or 0
        m['score_home']=gh; m['score_away']=ga
        m['elapsed']=fx['fixture']['status']['elapsed'] or 0
        m['status']=fx['fixture']['status']['short']
        for mk in m['markets']:
            m['results'][mk]=get_result(mk,gh,ga,m['status'])

    for acca in data['accumulators'].values():
        wins=sum(1 for leg in acca['legs'] if leg['status']=='WIN')
        loses=sum(1 for leg in acca['legs'] if leg['status']=='LOSE')
        for leg in acca['legs']:
            fx=live_map.get(leg['fixture_id'])
            if fx:
                gh=fx['goals']['home'] or 0; ga=fx['goals']['away'] or 0
                st=fx['fixture']['status']['short']
                leg['status']=get_result(leg['market'],gh,ga,st)
                leg['live']=f"{gh}-{ga} {st} {fx['fixture']['status']['elapsed'] or 0}'"
        acca['win_count']=f"{wins}/{len(acca['legs'])}"
        if loses>0: acca['status']="LOSE"
        elif wins==len(acca['legs']): acca['status']="WIN"
        elif wins>0: acca['status']="LIVE"
        else: acca['status']="PENDING"

    data['last_update']=datetime.now().isoformat()
    data['api_calls_today']=data.get('api_calls_today',0)+1
    with open('data.json','w') as f:
        json.dump(data,f,indent=2)
    print(f"Live updated - Total calls today: {data['api_calls_today']}")

if __name__=="__main__":
    update_live()