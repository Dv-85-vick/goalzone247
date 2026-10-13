import os
from flask import Flask, render_template_string

app = Flask(__name__)

# === ALL YOUR KEYS INCLUDED - NO ENV NEEDED FOR TEST ===
PAYSTACK_PUBLIC_KEY = "pk_test_2f95c67fd6a7b83a16c09487aa4cb73c00f3fe4e"
PAYSTACK_SECRET_KEY = "sk_test_placeholder_for_live_later"
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
TELEGRAM_CHANNEL_LINK = "https://t.me/goalzone247vip"
TELEGRAM_FREE_CHANNEL = "https://t.me/goalzone247"

HTML_PAGE = f"""
<!DOCTYPE html>
<html>
<head>
    <title>GoalZone247 - Best Football Predictions in Nigeria</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://js.paystack.co/v1/inline.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background: #0f172a; color: white; margin:0; padding:0; text-align:center; }}
        .header {{ background: linear-gradient(135deg, #16a34a, #15803d); padding: 25px; }}
        .badge {{ background: #f59e0b; color: black; padding: 6px 14px; border-radius: 20px; font-size:11px; font-weight:bold; letter-spacing:0.5px; }}
        .card {{ background: white; color: black; max-width: 520px; margin: 25px auto; padding: 25px; border-radius: 16px; box-shadow: 0 15px 30px rgba(0,0,0,0.4); }}
        .price {{ border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 15px 0; transition: 0.3s; }}
        .price.popular {{ border-color: #16a34a; background: #f0fdf4; transform: scale(1.03); box-shadow: 0 5px 15px rgba(22,163,74,0.2); }}
        .btn {{ width: 100%; padding: 16px; border: none; border-radius: 10px; font-size: 17px; font-weight: bold; cursor: pointer; margin-top: 10px; }}
        .btn-weekly {{ background: #334155; color: white; }}
        .btn-monthly {{ background: #16a34a; color: white; }}
        .btn:hover {{ opacity: 0.9; }}
        .free-tips {{ text-align: left; background: #1e293b; margin: 20px auto; max-width: 520px; padding: 18px; border-radius: 12px; border-left: 4px solid #16a34a; }}
        .live-dot {{ height:8px; width:8px; background:#22c55e; border-radius:50%; display:inline-block; margin-right:5px; animation: blink 1.5s infinite; }}
        @keyframes blink {{ 0% {{opacity:1}} 50% {{opacity:0.3}} 100% {{opacity:1}} }}
        a {{ text-decoration: none; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin:0;">⚽ GoalZone247</h1>
        <p style="margin:5px 0;"><span class="live-dot"></span>Live Predictions | Paystack Test Active</p>
        <span class="badge">PAYSTACK KEY INCLUDED - pk_test_2f95c... READY</span>
        <p style="font-size:13px; margin-top:10px;">Nigeria's Most Accurate Football Tips</p>
    </div>

    <div class="free-tips">
        <h3 style="margin-top:0;">🔥 Today's Free Tips</h3>
        <p>✅ Man City vs Arsenal - Over 1.5 Goals (1.40)</p>
        <p>✅ Barcelona - Win (1.65)</p>
        <p>✅ Chelsea vs Liverpool - BTTS Yes (1.75)</p>
        <hr style="border:0; border-top:1px solid #334155; margin:10px 0;">
        <p style="color:#22c55e; font-weight:bold;">💎 VIP Members Get 10+ Odds Daily - 95% Accuracy!</p>
    </div>

    <div class="card">
        <h2 style="margin-top:0;">Join VIP Club - Secured by Paystack</h2>
        <p style="color:#64748b; font-size:14px;">Your Paystack Test Key is active - No real money charged</p>
        
        <div class="price">
            <h3>Weekly VIP Access</h3>
            <h1 style="margin:5px 0;">₦8,000</h1>
            <p style="color:#64748b;">7 Days Premium Tips + Telegram VIP</p>
            <button class="btn btn-weekly" onclick="payWithPaystack(8000, 'weekly')">🧪 TEST Pay Weekly - ₦8,000</button>
        </div>

        <div class="price popular">
            <div style="background:#16a34a; color:white; padding:4px 10px; border-radius:15px; font-size:11px; display:inline-block; margin-bottom:8px;">🔥 MOST POPULAR - SAVE ₦4,000</div>
            <h3>Monthly VIP Access</h3>
            <h1 style="margin:5px 0;">₦28,000</h1>
            <p style="color:#16a34a; font-weight:bold;">30 Days Premium + Full VIP Telegram Access</p>
            <button class="btn btn-monthly" onclick="payWithPaystack(28000, 'monthly')">🧪 TEST Pay Monthly - ₦28,000</button>
        </div>

        <div style="background:#fffbeb; border:1px solid #fde68a; padding:10px; border-radius:8px; margin-top:15px; font-size:12px; color:#92400e;">
            <b>Test Mode Instructions:</b><br>
            Card: 4084084084084081 | Exp: 12/30 | CVV: 123 | PIN: 0000 | OTP: 123456
        </div>

        <p style="margin-top:20px;">
            <a href="{TELEGRAM_FREE_CHANNEL}" target="_blank" style="background:#0ea5e9; color:white; padding:10px 20px; border-radius:20px; display:inline-block;">📲 Join Free Telegram</a>
        </p>
    </div>

    <div style="padding:20px; color:#94a3b8; font-size:12px;">
        <p>GoalZone247 © 2026 | Secured by Paystack | Paystack Key: pk_test_2f95c... (Test Mode)</p>
        <p>After test success, user will be redirected to VIP Telegram: {TELEGRAM_CHANNEL_LINK}</p>
    </div>

<script>
function payWithPaystack(amountNaira, plan){{
    var email = prompt("Enter your email for test receipt:", "victor@goalzone247.com");
    if(!email) return;
    
    var handler = PaystackPop.setup({{
        key: '{PAYSTACK_PUBLIC_KEY}',
        email: email,
        amount: amountNaira * 100,
        currency: 'NGN',
        ref: plan + '_test_' + Math.floor(Math.random() * 1000000000),
        metadata: {{
            custom_fields: [
                {{ display_name: "Plan", variable_name: "plan", value: plan }},
                {{ display_name: "Platform", variable_name: "platform", value: "GoalZone247 Test" }}
            ]
        }},
        callback: function(response){{
            alert('✅ TEST PAYMENT SUCCESS!\\nPlan: ' + plan + '\\nAmount: ₦' + amountNaira + '\\nRef: ' + response.reference + '\\n\\nIn LIVE mode, we will now add you to VIP Telegram automatically.');
            document.body.innerHTML = '<div style="padding:60px 20px; text-align:center; background:#0f172a; color:white; min-height:100vh;"><h1 style="color:#22c55e; font-size:40px;">✅ TEST SUCCESS!</h1><h2>Plan: ' + plan + ' | ₦' + amountNaira + '</h2><p>Reference: ' + response.reference + '</p><p>Email: ' + email + '</p><p style="background:#1e293b; padding:15px; border-radius:10px; max-width:500px; margin:20px auto;">In LIVE mode:<br>1. We verify payment with Paystack Secret Key<br>2. We auto-add you to VIP Telegram Channel<br>3. You start receiving VIP tips immediately</p><a href="{TELEGRAM_CHANNEL_LINK}" target="_blank" style="background:#16a34a; color:white; padding:15px 30px; border-radius:25px; display:inline-block; margin:10px; text-decoration:none; font-weight:bold;">Go to VIP Telegram (Test)</a><br><a href="/" style="color:#94a3b8; display:inline-block; margin-top:20px;">← Back to Home (Test Again)</a></div>';
        }},
        onClose: function(){{
            alert('Test payment window closed - You can try again');
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
    return {"status": "ok", "service": "GoalZone247", "paystack": "test_mode_active", "key": PAYSTACK_PUBLIC_KEY[:15] + "..."}

@app.route('/api/test-paystack')
def test_paystack():
    return {"paystack_public_key": PAYSTACK_PUBLIC_KEY, "status": "Test key loaded correctly", "telegram": TELEGRAM_CHANNEL_LINK}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"GoalZone247 Starting on port {port} with Paystack Key {PAYSTACK_PUBLIC_KEY[:10]}...")
    app.run(host='0.0.0.0', port=port, debug=False)
