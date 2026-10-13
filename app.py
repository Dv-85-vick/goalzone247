import os
from flask import Flask

app = Flask(__name__)

# === YOUR KEYS - FINAL ===
PAYSTACK_PUBLIC_KEY = "pk_test_2f95c67fd6a7b83a16c09487aa4cb73c00f3fe4e"
TELEGRAM_VIP_LINK = "https://t.me/goalzone_daily_tips"

# Today's Predictions (You can edit these daily)
TODAY_PREDICTIONS = [
    {"time": "15:00", "match": "Man City vs Arsenal", "tip": "Over 1.5 Goals", "odd": "1.40", "conf": "95%"},
    {"time": "17:30", "match": "Barcelona vs Sevilla", "tip": "Barcelona Win", "odd": "1.65", "conf": "90%"},
    {"time": "18:00", "match": "Chelsea vs Liverpool", "tip": "BTTS - Yes", "odd": "1.75", "conf": "88%"},
    {"time": "19:45", "match": "Bayern Munich vs Dortmund", "tip": "Over 2.5", "odd": "1.60", "conf": "92%"},
    {"time": "20:00", "match": "PSG vs Lyon", "tip": "PSG Win & Over 1.5", "odd": "1.85", "conf": "89%"},
]

HTML_PAGE = f"""
<!DOCTYPE html>
<html>
<head>
    <title>GoalZone247 - #1 Football Predictions | VIP Tips</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
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
        .test-info {{ background:#fffbeb; border:1px solid #fcd34d; color:#92400e; padding:12px; border-radius:10px; font-size:11px; margin:15px 0; }}
        .yesterday {{ background:#1e293b; border-radius:12px; padding:15px; margin:15px 0; }}
        .won {{ color:#22c55e; }}
        .footer {{ text-align:center; padding:25px; color:#64748b; font-size:11px; }}
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
        <p style="margin-top:10px;"><span style="background:rgba(255,255,255,0.2); padding:5px 12px; border-radius:15px; font-size:12px;">🧪 Test Mode: {PAYSTACK_PUBLIC_KEY[:15]}... active</span></p>
    </div>

    <div class="container">
        
        <div class="card">
            <h3 style="display:flex; justify-content:space-between;">⚽ Today's Predictions <span style="font-size:11px; background:#0f172a; color:white; padding:3px 8px; border-radius:10px;">{TODAY_PREDICTIONS[0]['time']} - {TODAY_PREDICTIONS[-1]['time']}</span></h3>
            <table class="prediction-table">
                <tr><th>Time</th><th>Match & Tip</th><th>Odds</th></tr>
                {"".join([f"<tr><td>{p['time']}</td><td><b>{p['match']}</b><br><span style='color:#16a34a; font-weight:bold;'>{p['tip']}</span> <span style='color:#94a3b8; font-size:11px;'>({p['conf']})</span></td><td><span class='odd'>{p['odd']}</span></td></tr>" for p in TODAY_PREDICTIONS])}
            </table>
            <p style="font-size:11px; color:#64748b; margin-top:10px;">💡 VIP members get 10+ extra tips with 5-20 odds daily + live in-play tips</p>
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
            <p style="text-align:center; color:#64748b; font-size:13px; margin-bottom:15px;">Paystack Secured • Instant Telegram Access to {TELEGRAM_VIP_LINK}</p>
            
            <div class="price-box">
                <h3>Weekly VIP</h3>
                <h1>₦8,000 <span style="font-size:13px; color:#64748b; font-weight:normal;">/ 7 days</span></h1>
                <p style="font-size:13px; color:#475569;">✓ 7 days premium tips ✓ Telegram VIP access ✓ Daily 5-10 odds</p>
                <button class="btn btn-weekly" onclick="payWithPaystack(8000, 'weekly')">TEST Weekly - ₦8,000</button>
            </div>

            <div class="price-box popular">
                <div class="popular-tag">BEST VALUE - SAVE ₦4,000</div>
                <h3>Monthly VIP</h3>
                <h1>₦28,000 <span style="font-size:13px; color:#16a34a; font-weight:bold;">Save ₦4k</span></h1>
                <p style="font-size:13px; color:#475569;">✓ 30 days premium ✓ All accumulator tips ✓ VIP support + Live tips</p>
                <button class="btn btn-vip" onclick="payWithPaystack(28000, 'monthly')">TEST Monthly - ₦28,000 🔥</button>
            </div>

            <div class="test-info">
                <b>🧪 Paystack TEST MODE ACTIVE:</b><br>
                Your key {PAYSTACK_PUBLIC_KEY} is active<br>
                Test Card: 4084084084084081 | Exp: 12/30 | CVV: 123 | PIN: 0000 | OTP: 123456<br>
                No real money will be charged in test mode
            </div>

            <div style="text-align:center;">
                <a href="{TELEGRAM_VIP_LINK}" target="_blank" class="telegram-btn">📲 Go to VIP Telegram Channel</a>
                <p style="font-size:11px; color:#94a3b8; margin-top:10px;">Already paid? Click to join: {TELEGRAM_VIP_LINK}</p>
            </div>
        </div>

    </div>

    <div class="footer">
        <p>GoalZone247 © 2026 | Telegram: goalzone_daily_tips | Paystack Test Secured</p>
        <p>Predictions are analysis, gamble responsibly | 18+</p>
    </div>

<script>
function payWithPaystack(amountNaira, plan){{
    var email = prompt("Enter your email (for test receipt):", "victor@goalzone247.com");
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
            alert('✅ TEST PAYMENT SUCCESS!\\nPlan: ' + plan + '\\nAmount: ₦' + amountNaira + '\\nRef: ' + response.reference + '\\n\\nRedirecting you to VIP Telegram Channel...');
            window.location.href = '{TELEGRAM_VIP_LINK}';
        }},
        onClose: function(){{
            alert('Payment window closed - you can try again');
        }}
    }});
    handler.openIframe();
}}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return HTML_PAGE

@app.route('/health')
def health():
    return {"status": "ok", "paystack": "active", "telegram": TELEGRAM_VIP_LINK, "predictions": len(TODAY_PREDICTIONS)}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
