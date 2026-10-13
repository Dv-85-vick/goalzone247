import os
from flask import Flask

app = Flask(__name__)

PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'pk_test_xxxxxxxxxxxxxxxx')

@app.route('/')
def home():
    return f"""
<html>
<head>
    <title>GoalZone247 - VIP Test Mode</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://js.paystack.co/v1/inline.js"></script>
    <style>
        body {{ font-family: Arial; background: #0f172a; color: white; text-align: center; padding: 20px; }}
        .test-badge {{ background: #f59e0b; color: black; padding: 8px 15px; border-radius: 20px; font-weight: bold; font-size: 12px; }}
        .card {{ background: white; color: black; max-width: 500px; margin: 20px auto; padding: 25px; border-radius: 15px; }}
        .price-box {{ border: 2px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 15px 0; }}
        .price-box.popular {{ border-color: #22c55e; background: #f0fdf4; }}
        .btn {{ width: 100%; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 10px; }}
        .btn-weekly {{ background: #334155; color: white; }}
        .btn-monthly {{ background: #16a34a; color: white; }}
        .save {{ color: #16a34a; font-weight: bold; }}
    </style>
</head>
<body>
    <span class="test-badge">🧪 TEST MODE - No real money charged</span>
    <h1>⚽ GoalZone247</h1>
    <p>Premium VIP - Testing with Paystack</p>

    <div class="card">
        <h2>Choose Your Plan (TEST)</h2>
        
        <div class="price-box">
            <h3>Weekly Access</h3>
            <h1>₦8,000</h1>
            <p>7 days VIP tips</p>
            <button class="btn btn-weekly" onclick="payWithPaystack(8000, 'weekly')">TEST Pay Weekly - ₦8,000</button>
        </div>

        <div class="price-box popular">
            <h3>Monthly Access</h3>
            <h1>₦28,000 <span style="font-size:14px;">(Save ₦4k)</span></h1>
            <p>30 days VIP tips - BEST VALUE</p>
            <p class="save">Save ₦4,000 vs weekly!</p>
            <button class="btn btn-monthly" onclick="payWithPaystack(28000, 'monthly')">TEST Pay Monthly - ₦28,000</button>
        </div>

        <p style="font-size:11px; color:#64748b; margin-top:15px;">
            Test Mode: Use test card 4084084084084081 - Any future date - Any CVV<br>
            Secured by Paystack Test
        </p>
    </div>

<script>
function payWithPaystack(amountNaira, plan){{
    var email = prompt("Enter test email:", "test@goalzone247.com");
    if(!email) return;
    
    var handler = PaystackPop.setup({{
        key: '{PAYSTACK_PUBLIC_KEY}',
        email: email,
        amount: amountNaira * 100,
        currency: 'NGN',
        ref: plan + '_test_' + Math.floor(Math.random() * 1000000000),
        callback: function(response){{
            alert('TEST SUCCESS! Plan: ' + plan + ' Amount: ₦' + amountNaira + ' Ref: ' + response.reference);
            document.body.innerHTML = '<div style="padding:50px;text-align:center;background:#0f172a;color:white;"><h1 style="color:#22c55e;">✅ TEST Payment Successful!</h1><h2>Plan: ' + plan + ' - ₦' + amountNaira + '</h2><p>Ref: ' + response.reference + '</p><p>In LIVE mode, you would now add this user to VIP Telegram manually.</p><p>Test email: ' + email + '</p><a href="/" style="color:#22c55e;">Back to Test Again</a></div>';
        }},
        onClose: function(){{ alert('Test payment closed'); }}
    }});
    handler.openIframe();
}}
</script>
</body>
</html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',10000)))
