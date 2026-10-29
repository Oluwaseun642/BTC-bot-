import os
import time
from datetime import datetime

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
