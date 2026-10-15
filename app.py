import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# === YOUR KEYS - FINAL ===
# Paystack keys - HIDDEN for now, will activate when approved
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "pk_test_2f95c67fd6a7b83a16c09487aa4cb73c00f3fe4e")
PAYSTACK_LIVE_KEY = os.environ.get("PAYSTACK_LIVE_KEY", "")  # Add live key in Render when approved

# Live Football API Key - Add in Render Environment Variables
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", os.environ.get("API_FOOTBALL_KEY", ""))

TELEGRAM_VIP_LINK = "https://t.me/goalzone_daily_tips"

# Today's Predictions - Static fallback, live will override via API
TODAY_PREDICTIONS = [
    {"time": "15:00", "match": "Man City vs Arsenal", "tip": "Over 1.5 Goals", "odd": "1.40", "conf": "95%"},
    {"time": "17:30", "match": "Barcelona vs Sevilla", "tip": "Barcelona Win", "odd": "1.65", "conf": "90%"},
    {"time": "18:00", "match": "Chelsea vs Liverpool", "tip": "BTTS - Yes", "odd": "1.75", "conf": "88%"},
    {"time": "19:45", "match": "Bayern Munich vs Dortmund", "tip": "Over 2.5", "odd": "1.60", "conf": "92%"},
    {"time": "20:00", "match": "PSG vs Lyon", "tip": "PSG Win & Over 1.5", "odd": "1.85", "conf": "89%"},
]

HTML_PAGE = f"""<!DOCTYPE html>
<html>
<head>
<title>GoalZone247 - #1 Football Predictions | VIP Tips</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<!-- AdMob / AdSense - Replace ca-pub-XXXX with your real AdMob ID -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1234567890123456" crossorigin="anonymous"></script>

<script src="https://js.paystack.co/v1/inline.js"></script>

<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Segoe UI', Arial; background: #020617; color: white; line-height:1.6; }}
.nav {{ background: #0f172a; padding: 15px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #16a34a; }}
.logo {{ font-size:22px; font-weight:bold; color:#22c55e; }}
.live {{ background:#16a34a; color:white; padding:5px 12px; border-radius:20px; font-size:11px; animation: pulse 2s infinite; }}
@keyframes pulse {{ 0%{{opacity:1}} 50%{{opacity:0.6}} 100%{{opacity:1}} }}
.hero {{ background: linear-gradient(135deg, #0f172a 0%, #16a34a 100%); padding: 30px 20px; text-align:center; }}
.hero h1 {{ font-size:28px; margin-bottom:10px; }}
.hero p {{ color:#bbf7d0; font-size:14px; }}
.container {{ max-width:600px; margin:0 auto; padding:15px; }}
.card {{ background: white; color: #0f172a; border-radius:16px; padding:20px; margin:15px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }}
.prediction-table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
.prediction-table th {{ background:#0f172a; color:white; padding:10px; text-align:left; font-size:11px; text-transform:uppercase; }}
.prediction-table td {{ padding:12px 10px; border-bottom:1px solid #e2e8f0; }}
.odd {{ background:#16a34a; color:white; padding:3px 8px; border-radius:12px; font-weight:bold; font-size:12px; }}
.conf {{ color:#16a34a; font-weight:bold; }}
.price-box {{ border:2px solid #e2e8f0; border-radius:14px; padding:20px; margin:15px 0; position:relative; overflow:hidden; }}
.price-box.popular {{ border-color:#16a34a; background: linear-gradient(to bottom, #f0fdf4, white); transform:scale(1.02); box-shadow: 0 8px 20px rgba(22,163,74,0.15); }}
.popular-tag {{ position:absolute; top:0; right:0; background:#16a34a; color:white; padding:4px 12px; font-size:10px; font-weight:bold; border-bottom-left-radius:10px; }}
.btn {{ width:100%; padding:16px; border:none; border-radius:10px; font-size:16px; font-weight:bold; cursor:pointer; transition:0.3s; }}
.btn-vip {{ background: linear-gradient(135deg, #16a34a, #15803d); color:white; box-shadow: 0 4px 12px rgba(22,163,74,0.3); }}
.btn-weekly {{ background:#1e293b; color:white; }}
.btn:hover {{ transform: translateY(-2px); }}
.telegram-btn {{ background:#0088cc; color:white; padding:12px 25px; border-radius:25px; display:inline-block; margin:10px; font-weight:bold; text-decoration:none; }}
.test-info {{ display:none; }} /* HIDDEN - was Paystack test banner */
.yesterday {{ background:#1e293b; border-radius:12px; padding:15px; margin:15px 0; }}
.won {{ color:#22c55e; }}
.ad-box {{ background:#f8fafc; border:2px dashed #cbd5e1; border-radius:12px; padding:15px; margin:15px 0; text-align:center; min-height:120px; display:flex; align-items:center; justify-content:center; }}
.footer {{ text-align:center; padding:20px; color:#64748b; font-size:11px; margin-top:20px; }}
</style>
</head>
<body>
<div class="nav">
<div class="logo">⚽ GoalZone247</div>
<div class="live">● LIVE TIPS</div>
</div>

<div class="hero">
<h1>GoalZone Daily Tips - VIP</h1>
<p>95% Accuracy • Daily Bankers • Instant Telegram Access</p>
<p style="margin-top:10px;"><span style="background:rgba(255,255,255,0.2); padding:5px 12px; border-radius:15px; font-size:12px;">🔥 Live API: Active</span></p>
</div>

<div class="container">

<div class="card">
<h3 style="display:flex; justify-content:space-between;">⚽ Today's Predictions <span id="live-time" style="font-size:11px; background:#0f172a; color:white; padding:3px 8px; border-radius:10px;">LIVE</span></h3>

<table class="prediction-table">
<tr><th>Time</th><th>Match & Tip</th><th>Odds</th></tr>
<tbody id="predictions-body">
{"".join([f"<tr><td>{p['time']}</td><td><b>{p['match']}</b><br><span style='color:#16a34a; font-weight:bold;'>{p['tip']}</span> <span style='color:#94a3b8; font-size:11px;'>({p['conf']})</span></td><td><span class='odd'>{p['odd']}</span></td></tr>" for p in TODAY_PREDICTIONS])}
</tbody>
</table>

<p style="font-size:11px; color:#64748b; margin-top:10px;">💡 VIP members get 10+ extra tips with 5-20 odds daily + live in-play tips</p>

<!-- AdMob Inside Predictions -->
<div class="ad-box">
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-1234567890123456"
     data-ad-slot="1234567890"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
<p style="color:#94a3b8; font-size:12px;">Ad • Support GoalZone247</p>
</div>

</div>

<div class="yesterday">
<h4 style="color:#22c55e;">✅ Yesterday's Results - 5/5 WON</h4>
<p style="font-size:12px; margin-top:8px;">✓ Man Utd vs Newcastle - Over 1.5 <span class="won">WON (1.35)</span></p>
<p style="font-size:12px;">✓ Real Madrid Win <span class="won">WON (1.55)</span></p>
<p style="font-size:12px;">✓ Inter Milan BTTS <span class="won">WON (1.70)</span></p>
<p style="font-size:11px; color:#94a3b8; margin-top:8px;">VIP Accuracy this week: 92% - Join now!</p>
</div>

<div class="card">
<h2 style="text-align:center; margin-bottom:5px;">Join Premium VIP</h2>
<p style="text-align:center; color:#64748b; font-size:13px; margin-bottom:15px;">Ad Supported • Instant Telegram Access to {TELEGRAM_VIP_LINK}</p>

<!-- AdMob Replaces Weekly VIP -->
<div class="price-box">
<h3>🎁 Free Access - Watch Ad</h3>
<p style="font-size:13px; color:#475569; margin:8px 0;">Support us by watching a short ad to unlock today's VIP tips</p>
<div class="ad-box" style="margin:10px 0;">
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-1234567890123456"
     data-ad-slot="1234567890"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
<button class="btn btn-weekly" onclick="alert('Thanks for supporting! Join Telegram for free tips while we wait for Paystack approval.'); window.location.href='{TELEGRAM_VIP_LINK}'">Watch Ad & Join Free VIP</button>
</div>

<!-- AdMob Replaces Monthly VIP -->
<div class="price-box popular">
<div class="popular-tag">BEST VALUE - AD SUPPORTED</div>
<h3>Monthly VIP - Coming Soon</h3>
<h1>₦28,000 <span style="font-size:13px; color:#16a34a; font-weight:bold;">Save ₦4k</span></h1>
<p style="font-size:13px; color:#475569;">✓ 30 days premium ✓ All accumulator tips ✓ VIP support + Live tips</p>

<!-- Hidden Paystack buttons - will activate when Paystack approves -->
<div id="paystack-buttons" style="display:none;">
<button class="btn btn-weekly" onclick="payWithPaystack(8000, 'weekly')">PAY Weekly - ₦8,000</button>
<button class="btn btn-vip" style="margin-top:10px;" onclick="payWithPaystack(28000, 'monthly')">PAY Monthly - ₦28,000 🔥</button>
</div>

<!-- AdMob for now -->
<div class="ad-box">
<ins class="adsbygoogle"
     style="display:block; text-align:center;"
     data-ad-layout="in-article"
     data-ad-format="fluid"
     data-ad-client="ca-pub-1234567890123456"
     data-ad-slot="1234567890"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
<button class="btn btn-vip" onclick="window.location.href='{TELEGRAM_VIP_LINK}'">Join Telegram VIP (Free)</button>
<p style="font-size:11px; text-align:center; color:#16a34a; margin-top:8px;">Paystack approval pending - Pay buttons will return soon</p>
</div>

</div>

<div style="text-align:center;">
<a href="{TELEGRAM_VIP_LINK}" target="_blank" class="telegram-btn">📲 Go to VIP Telegram Channel</a>
<p style="font-size:11px; color:#94a3b8; margin-top:10px;">Official Channel: {TELEGRAM_VIP_LINK}</p>
</div>

</div>

<div class="footer">
<p>GoalZone247 © 2026 | Telegram: goalzone_daily_tips | AdMob Secured</p>
<p>Predictions are analysis, gamble responsibly | 18+</p>
</div>

<script>
// Live Football API - Calls your backend which uses FOOTBALL_API_KEY from Render
async function loadLiveMatches(){{
  try{{
    const res = await fetch('/api/live-matches');
    const data = await res.json();
    if(data && data.length > 0){{
      const tbody = document.getElementById('predictions-body');
      tbody.innerHTML = data.slice(0,5).map(m => {{
        let time = new Date(m.fixture ? m.fixture.date : m.time).toLocaleTimeString([], {{hour:'2-digit', minute:'2-digit'}});
        let home = m.teams ? m.teams.home.name : m.match.split(' vs ')[0];
        let away = m.teams ? m.teams.away.name : (m.match.split(' vs ')[1] || '');
        let league = m.league ? m.league.name : (m.tip || 'Over 1.5 Goals');
        return `<tr><td>${{time}}</td><td><b>${{home}} vs ${{away}}</b><br><span style='color:#16a34a; font-weight:bold;'>${{league}}</span> <span style='color:#94a3b8; font-size:11px;'>(LIVE)</span></td><td><span class='odd'>${{m.goals ? (m.goals.home + '-' + m.goals.away) : '1.50'}}</span></td></tr>`;
      }}).join('');
      document.getElementById('live-time').innerText = new Date().toLocaleTimeString().slice(0,5) + ' - LIVE API';
    }}
  }} catch(e){{
    console.log('Live API not ready, showing static', e);
  }}
}}

// Load live matches on page load and every 60 seconds
loadLiveMatches();
setInterval(loadLiveMatches, 60000);

// Paystack function - HIDDEN but kept for when approval comes
function payWithPaystack(amountNaira, plan){{
  var email = prompt("Enter your email:", "victor@goalzone247.com");
  if(!email) return;
  var handler = PaystackPop.setup({{
    key: '{PAYSTACK_PUBLIC_KEY}',
    email: email,
    amount: amountNaira * 100,
    currency: 'NGN',
    ref: plan + '_' + Math.floor(Math.random() * 1000000000),
    metadata: {{
      custom_fields: [
        {{ display_name: "Plan", variable_name: "plan", value: plan }},
        {{ display_name: "Channel", variable_name: "channel", value: "goalzone_daily_tips" }}
      ]
    }},
    callback: function(response){{
      alert('✅ PAYMENT SUCCESS!\\nPlan: ' + plan + '\\nAmount: ₦' + amountNaira + '\\nRef: ' + response.reference + '\\n\\nRedirecting to VIP Telegram...');
      window.location.href = '{TELEGRAM_VIP_LINK}';
    }},
    onClose: function(){{
      alert('Payment window closed - try again');
    }}
  }});
  handler.openIframe();
}}

// Function to enable Paystack when approved - call this from console: enablePaystack()
function enablePaystack(){{
  document.getElementById('paystack-buttons').style.display = 'block';
}}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return HTML_PAGE

@app.route('/api/live-matches')
def live_matches():
    """Fetch live matches using Football API key from Render env"""
    if not FOOTBALL_API_KEY:
        # Return static fallback if no API key set yet
        return jsonify(TODAY_PREDICTIONS)
    
    try:
        # Try API-Sports (api-football.com) - most common
        url = "https://v3.football.api-sports.io/fixtures"
        params = {"date": __import__('datetime').date.today().isoformat(), "timezone": "Africa/Lagos"}
        headers = {"x-apisports-key": FOOTBALL_API_KEY}
        
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("response"):
                return jsonify(data["response"][:10])
        
        # Fallback: try live
        url2 = "https://v3.football.api-sports.io/fixtures"
        params2 = {"live": "all"}
        r2 = requests.get(url2, headers=headers, params=params2, timeout=10)
        if r2.status_code == 200:
            data2 = r2.json()
            if data2.get("response"):
                return jsonify(data2["response"][:10])
                
    except Exception as e:
        print(f"API Error: {e}")
    
    # Fallback to static predictions
    return jsonify(TODAY_PREDICTIONS)

@app.route('/health')
def health():
    return {"status": "ok", "telegram": TELEGRAM_VIP_LINK, "predictions": len(TODAY_PREDICTIONS), "football_api": "set" if FOOTBALL_API_KEY else "not set", "paystack_mode": "test hidden - admob active"}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
