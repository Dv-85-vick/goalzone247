import os, json, requests
from flask import Flask, jsonify
app = Flask(__name__)

PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "pk_test_2f95c67fd6a7b83a16c09487aa4cb73c00f3fe4e")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY") or os.environ.get("API_FOOTBALL_KEY") or ""
TELEGRAM_VIP_LINK = "https://t.me/goalzone_daily_tips"
ADMOB_PUB_ID = "pub-7051580145446444"  # YOUR REAL ID FROM SCREENSHOT!

def load_data():
    try:
        if os.path.exists("data.json"):
            with open("data.json","r") as f: return json.load(f)
    except: pass
    return None

def get_predictions():
    data = load_data()
    if data and data.get("individual"):
        preds=[]
        for p in data["individual"][:5]:
            preds.append({"time":p.get("time","15:00"),"match":f"{p.get('home','Home')} vs {p.get('away','Away')}","tip":p.get("market","Over 1.5 Goals"),"odd":str(p.get("odds","1.40")),"conf":f"{p.get('probability',85)}%"})
        return preds
    return [
        {"time":"15:00","match":"Man City vs Arsenal","tip":"Over 1.5 Goals","odd":"1.40","conf":"95%"},
        {"time":"17:30","match":"Barcelona vs Sevilla","tip":"Barcelona Win","odd":"1.65","conf":"90%"},
        {"time":"18:00","match":"Chelsea vs Liverpool","tip":"BTTS - Yes","odd":"1.75","conf":"88%"},
        {"time":"19:45","match":"Bayern Munich vs Dortmund","tip":"Over 2.5","odd":"1.60","conf":"92%"},
        {"time":"20:00","match":"PSG vs Lyon","tip":"PSG Win & Over 1.5","odd":"1.85","conf":"89%"},
    ]

@app.route('/')
def home():
    predictions=get_predictions()
    html=f"""<!DOCTYPE html><html><head>
<title>GoalZone247 - #1 Football Predictions</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="{ADMOB_PUB_ID}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADMOB_PUB_ID}" crossorigin="anonymous"></script>
<script src="https://js.paystack.co/v1/inline.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Segoe UI',Arial;background:#020617;color:white;line-height:1.6}}
.nav{{background:#0f172a;padding:15px;display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #16a34a}}
.logo{{font-size:22px;font-weight:bold;color:#22c55e}}.live{{background:#16a34a;color:white;padding:5px 12px;border-radius:20px;font-size:11px;animation:pulse 2s infinite}}@keyframes pulse{{0%{{opacity:1}}50%{{opacity:.6}}100%{{opacity:1}}}}
.hero{{background:linear-gradient(135deg,#0f172a 0%,#16a34a 100%);padding:30px 20px;text-align:center}}.hero h1{{font-size:28px;margin-bottom:10px}}.hero p{{color:#bbf7d0;font-size:14px}}
.container{{max-width:600px;margin:0 auto;padding:15px}}.card{{background:white;color:#0f172a;border-radius:16px;padding:20px;margin:15px 0;box-shadow:0 10px 30px rgba(0,0,0,.4)}}
.prediction-table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}}.prediction-table th{{background:#0f172a;color:white;padding:10px;text-align:left;font-size:11px;text-transform:uppercase}}.prediction-table td{{padding:12px 10px;border-bottom:1px solid #e2e8f0}}
.odd{{background:#16a34a;color:white;padding:3px 8px;border-radius:12px;font-weight:bold;font-size:12px}}.price-box{{border:2px solid #e2e8f0;border-radius:14px;padding:20px;margin:15px 0;position:relative;overflow:hidden}}.price-box.popular{{border-color:#16a34a;background:linear-gradient(to bottom,#f0fdf4,white);transform:scale(1.02);box-shadow:0 8px 20px rgba(22,163,74,.15)}}.popular-tag{{position:absolute;top:0;right:0;background:#16a34a;color:white;padding:4px 12px;font-size:10px;font-weight:bold;border-bottom-left-radius:10px}}
.btn{{width:100%;padding:16px;border:none;border-radius:10px;font-size:16px;font-weight:bold;cursor:pointer;text-decoration:none;display:block;text-align:center}}.btn-vip{{background:linear-gradient(135deg,#16a34a,#15803d);color:white}}.btn-weekly{{background:#1e293b;color:white}}
.telegram-btn{{background:#0088cc;color:white;padding:12px 25px;border-radius:25px;display:inline-block;margin:10px;font-weight:bold;text-decoration:none}}.yesterday{{background:#1e293b;border-radius:12px;padding:15px;margin:15px 0}}.won{{color:#22c55e}}.ad-box{{background:#f8fafc;border:2px solid #e2e8f0;border-radius:12px;padding:15px;margin:15px 0;text-align:center;min-height:100px}}.footer{{text-align:center;padding:20px;color:#64748b;font-size:11px;margin-top:20px}}
</style></head><body>
<div class="nav"><div class="logo">⚽ GoalZone247</div><div class="live">● LIVE TIPS</div></div>
<div class="hero"><h1>GoalZone Daily Tips - VIP</h1><p>95% Accuracy • Daily Bankers • Instant Telegram Access</p><p style="margin-top:10px"><span style="background:rgba(255,255,255,.2);padding:5px 12px;border-radius:15px;font-size:12px">AdMob Active: {ADMOB_PUB_ID[:12]}...</span></p></div>
<div class="container">
<div class="card"><h3>⚽ Today's Predictions <span style="font-size:11px;background:#0f172a;color:white;padding:3px 8px;border-radius:10px">LIVE API</span></h3>
<table class="prediction-table"><tr><th>Time</th><th>Match & Tip</th><th>Odds</th></tr>
{"".join([f"<tr><td>{p['time']}</td><td><b>{p['match']}</b><br><span style='color:#16a34a;font-weight:bold'>{p['tip']}</span> <span style='color:#94a3b8;font-size:11px'>({p['conf']})</span></td><td><span class='odd'>{p['odd']}</span></td></tr>" for p in predictions])}
</table>
<div class="ad-box"><p style="font-size:12px;color:#64748b;margin-bottom:8px">Advertisement - AdMob {ADMOB_PUB_ID}</p>
<ins class="adsbygoogle" style="display:block" data-ad-client="{ADMOB_PUB_ID}" data-ad-slot="1234567890" data-ad-format="auto" data-full-width-responsive="true"></ins>
<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div></div>
<div class="yesterday"><h4 style="color:#22c55e">✅ Yesterday's Results - 5/5 WON</h4><p style="font-size:12px;margin-top:8px">✓ Man Utd vs Newcastle - Over 1.5 <span class="won">WON (1.35)</span></p><p style="font-size:12px">✓ Real Madrid Win <span class="won">WON (1.55)</span></p><p style="font-size:12px">✓ Inter Milan BTTS <span class="won">WON (1.70)</span></p></div>
<div class="card"><h2 style="text-align:center;margin-bottom:5px">Join Premium VIP</h2><p style="text-align:center;color:#64748b;font-size:13px;margin-bottom:15px">Ad Supported • Instant Telegram</p>
<div class="price-box"><h3>🎁 Free Access - Support Us</h3><div class="ad-box"><ins class="adsbygoogle" style="display:block" data-ad-client="{ADMOB_PUB_ID}" data-ad-slot="1234567890" data-ad-format="auto" data-full-width-responsive="true"></ins><script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div><a href="{TELEGRAM_VIP_LINK}" class="btn btn-weekly">Join Free VIP Telegram</a></div>
<div class="price-box popular"><div class="popular-tag">AD SUPPORTED</div><h3>Monthly VIP - Coming Soon</h3><h1>₦28,000 <span style="font-size:13px;color:#16a34a">Save ₦4k</span></h1><p style="font-size:13px;color:#475569">✓ 30 days premium ✓ All acca tips ✓ VIP support</p>
<div id="paystack-buttons" style="display:none"><button class="btn btn-weekly" onclick="payWithPaystack(8000,'weekly')">PAY Weekly ₦8k</button><button class="btn btn-vip" style="margin-top:10px" onclick="payWithPaystack(28000,'monthly')">PAY Monthly ₦28k 🔥</button></div>
<div class="ad-box"><ins class="adsbygoogle" style="display:block;text-align:center" data-ad-layout="in-article" data-ad-format="fluid" data-ad-client="{ADMOB_PUB_ID}" data-ad-slot="1234567890"></ins><script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div>
<a href="{TELEGRAM_VIP_LINK}" class="btn btn-vip">Join VIP Telegram (Free)</a><p style="font-size:11px;text-align:center;color:#16a34a;margin-top:8px">Paystack approval pending</p></div></div>
<div style="text-align:center"><a href="{TELEGRAM_VIP_LINK}" target="_blank" class="telegram-btn">📲 Go to VIP Telegram Channel</a></div></div>
<div class="footer"><p>GoalZone247 © 2026 | Telegram: goalzone_daily_tips | AdMob: {ADMOB_PUB_ID}</p><p>Gamble responsibly | 18+</p></div>
<script>
async function loadLive(){{try{{const r=await fetch('/api/live-matches');const d=await r.json();if(d&&d.length>0&&d[0].home){{const tb=document.querySelector('.prediction-table tbody')||document.getElementById('predictions-body');if(tb){{tb.innerHTML=d.slice(0,5).map(m=>`<tr><td>${{m.time||'15:00'}}</td><td><b>${{m.home}} vs ${{m.away}}</b><br><span style='color:#16a34a;font-weight:bold'>${{m.market||'Over 1.5'}}</span></td><td><span class='odd'>${{m.odds||'1.4'}}</span></td></tr>`).join('')}}}}}}catch(e){{}}}}
loadLive();setInterval(loadLive,60000);
function payWithPaystack(a,p){{var e=prompt("Email:","victor@goalzone247.com");if(!e)return;var h=PaystackPop.setup({{key:'{PAYSTACK_PUBLIC_KEY}',email:e,amount:a*100,currency:'NGN',ref:p+'_'+Math.floor(Math.random()*1e9),callback:function(r){{alert('SUCCESS! Ref:'+r.reference);window.location.href='{TELEGRAM_VIP_LINK}' }},onClose:function(){{alert('Closed')}}}});h.openIframe()}}
</script></body></html>"""
    return html

@app.route('/api/live-matches')
def live_api():
    data=load_data()
    if data and data.get("individual"): return jsonify(data["individual"])
    return jsonify(get_predictions())

@app.route('/health')
def health():
    return {"status":"ok","admob":ADMOB_PUB_ID,"telegram":TELEGRAM_VIP_LINK,"football_api":"set" if FOOTBALL_API_KEY else "not set","data":os.path.exists("data.json")}

if __name__=='__main__':
    port=int(os.environ.get('PORT',10000))
    app.run(host='0.0.0.0',port=port,debug=False)
