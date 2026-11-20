# MAIN.PY - TEST 3 - CORRECT ENDPOINTS
import os, time, hmac, hashlib, requests
KEY = os.environ.get("BYBIT_API_KEY","").strip()
SEC = os.environ.get("BYBIT_API_SECRET","").strip()
RW = "5000"
print(f"TEST3 KEY {KEY[:4]}**** LEN {len(KEY)}", flush=True)
def sign(payload, ts):
    return hmac.new(SEC.encode(), (ts+KEY+RW+payload).encode(), hashlib.sha256).hexdigest()

# 1 - WALLET BALANCE - header only, like real bot
print("\n--- 1. WALLET-BALANCE header only ---", flush=True)
ts = str(int(time.time()*1000))
qs = "accountType=UNIFIED"
h = {"X-BPI-APIKEY": KEY, "X-BPI-SIGN": sign(qs, ts), "X-BPI-SIGN-TYPE": "2", "X-BPI-TIMESTAMP": ts, "X-BPI-RECV-WINDOW": RW, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
r = requests.get(f"https://api.bybit.com/v5/account/wallet-balance?{qs}", headers=h, timeout=10)
print(f"Status: {r.status_code} Body: {r.text[:500]}", flush=True)

# 2 - QUERY-API - with apiKey in URL (correct way for this endpoint)
print("\n--- 2. QUERY-API with apiKey in URL ---", flush=True)
ts2 = str(int(time.time()*1000))
qs2 = f"apiKey={KEY}"
h2 = {"X-BPI-APIKEY": KEY, "X-BPI-SIGN": sign(qs2, ts2), "X-BPI-SIGN-TYPE": "2", "X-BPI-TIMESTAMP": ts2, "X-BPI-RECV-WINDOW": RW, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
r2 = requests.get(f"https://api.bybit.com/v5/user/query-api?{qs2}", headers=h2, timeout=10)
print(f"Status: {r2.status_code} Body: {r2.text[:500]}", flush=True)

print("\n=== TEST3 DONE ===", flush=True)
time.sleep(30)
