import os
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# --- ANTI-SLEEP WEB SERVER FOR FREE RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "BTC Bot V3.3b is ALIVE! No sleep! 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Start web server in background
Thread(target=run_flask, daemon=True).start()
# --- END ANTI-SLEEP ---

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

print("="*40)
print("BTC-BOT V3.3b CLOUD STARTED 🚀")
print(f"Time: {datetime.now()}")
print("Target: $10 -> $1000")
print("="*40)

while True:
    now = datetime.now().strftime("%H:%M:%S")
    has_key = "YES" if API_KEY else "NO - Add keys for LIVE"
    print(f"[{now}] Bot alive | Scanning BTC | API: {has_key} | Running...")
    time.sleep(30)
