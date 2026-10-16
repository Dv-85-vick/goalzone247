import json, requests, os
from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY=os.getenv("API_FOOTBALL_KEY")
BASE="https://v3.football.api-sports.io"
HEADERS={'x-apisports-key': API_KEY}
WAT = ZoneInfo("Africa/Lagos")

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
    if not os.path.exists('data.json'): 
        print("no data.json found")
        return
    with open('data.json') as f:
        data=json.load(f)

    # FIX: Handle BOTH old flat format and new nested format
    today = data.get('current_date') or data.get('date')
    if not today and 'dates' in data and 'today' in data['dates']:
        today = data['dates']['today'].get('date')
    
    if not today:
        print("ERROR: No date found in data.json")
        return

    print(f"Fetching LIVE for {today} WAT...")
    r=requests.get(f"{BASE}/fixtures", headers=HEADERS, params={"date": today, "timezone": "Africa/Lagos"}, timeout=20)
    if r.status_code!=200: 
        print(f"API failed {r.status_code}: {r.text[:200]}")
        return
    
    live_map={fx['fixture']['id']: fx for fx in r.json().get('response',[])}
    print(f"API returned {len(live_map)} fixtures for {today}")

    updated = 0
    # FIX: Update in both places - dates.today and top-level matches
    targets = []
    if 'dates' in data:
        for day_key in data['dates']:
            targets.extend(data['dates'][day_key].get('matches', []))
    if 'matches' in data:
        # Add top-level too but avoid double counting if same list
        if not targets or data['matches'] is not targets[0:len(data['matches'])]:
            targets.extend(data['matches'])

    # Use a set to avoid updating same fixture twice
    seen_ids = set()
    for m in targets:
        fid = m.get('fixture_id')
        if fid in seen_ids:
            continue
        fx=live_map.get(fid)
        if not fx: continue
        gh=fx['goals']['home'] or 0
        ga=fx['goals']['away'] or 0
        m['score_home']=gh; m['score_away']=ga
        m['elapsed']=fx['fixture']['status']['elapsed'] or 0
        m['status']=fx['fixture']['status']['short']
        for mk in m['markets']:
            if mk.startswith('_'): continue
            m['results'][mk]=get_result(mk,gh,ga,m['status'])
        seen_ids.add(fid)
        updated += 1

    # Handle accumulators if they exist in either format
    acca_dict = data.get('accumulators', {})
    if not acca_dict and 'dates' in data and 'today' in data['dates']:
        acca_dict = data['dates']['today'].get('accumulators', {})
    
    for acca in acca_dict.values():
        for leg in acca.get('legs', []):
            fx=live_map.get(leg.get('fixture_id'))
            if fx:
                gh=fx['goals']['home'] or 0; ga=fx['goals']['away'] or 0
                st=fx['fixture']['status']['short']
                leg['status']=get_result(leg.get('market'),gh,ga,st)
                leg['live']=f"{gh}-{ga} {st} {fx['fixture']['status']['elapsed'] or 0}'"
        wins=sum(1 for leg in acca.get('legs',[]) if leg.get('status')=='WIN')
        loses=sum(1 for leg in acca.get('legs',[]) if leg.get('status')=='LOSE')
        total_legs = len(acca.get('legs',[]))
        if total_legs:
            acca['win_count']=f"{wins}/{total_legs}"
            if loses>0: acca['status']="LOSE"
            elif wins==total_legs: acca['status']="WIN"
            elif wins>0: acca['status']="LIVE"
            else: acca['status']="PENDING"

    data['last_update']=datetime.now(WAT).isoformat()
    data['api_calls_today']=data.get('api_calls_today',0)+1
    
    # Keep both formats in sync
    if 'dates' in data and 'today' in data['dates']:
        data['dates']['today']['last_update'] = data['last_update']
        data['dates']['today']['matches'] = data.get('matches', data['dates']['today'].get('matches',[]))
    
    with open('data.json','w') as f:
        json.dump(data,f,indent=2)
    print(f"Live updated {updated} fixtures - Status now: {[m['status'] for m in list(live_map.values())[:3]]} - Total calls today: {data['api_calls_today']}")

if __name__=="__main__":
    update_live()
