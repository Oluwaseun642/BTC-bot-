# MAIN.PY - TEST 2 - NO DATA ENGINE
import os, time, hmac, hashlib, requests

KEY = os.environ.get("BYBIT_API_KEY", "").strip()
SEC = os.environ.get("BYBIT_API_SECRET", "").strip()
TS = str(int(time.time()*1000))
RW = "5000"

print(f"TEST2 KEY {KEY[:4]}**** LEN {len(KEY)}", flush=True)

def sign(payload, ts):
    msg = ts + KEY + RW + payload
    return hmac.new(SEC.encode(), msg.encode(), hashlib.sha256).hexdigest()

# 1 - PUBLIC, NO AUTH AT ALL
print("\n--- 1. PUBLIC tickers (no auth) api.bybit.com ---", flush=True)
try:
    r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=10)
    print(f"Status: {r.status_code} Body[:200]: {r.text[:200]}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)

# 2 - AUTH + BROWSER USER-AGENT
print("\n--- 2. AUTH query-api + Browser UA api.bybit.com ---", flush=True)
try:
    qs = ""
    h = {
        "X-BPI-APIKEY": KEY,
        "X-BPI-SIGN": sign(qs, TS),
        "X-BPI-SIGN-TYPE": "2",
        "X-BPI-TIMESTAMP": TS,
        "X-BPI-RECV-WINDOW": RW,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    }
    r = requests.get("https://api.bybit.com/v5/user/query-api", headers=h, timeout=10)
    print(f"Status: {r.status_code} Body[:500]: {r.text[:500]}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)

# 3 - AUTH via bytick domain
print("\n--- 3. AUTH query-api via api.bytick.com ---", flush=True)
try:
    ts2 = str(int(time.time()*1000))
    h2 = {
        "X-BPI-APIKEY": KEY,
        "X-BPI-SIGN": sign("", ts2),
        "X-BPI-SIGN-TYPE": "2",
        "X-BPI-TIMESTAMP": ts2,
        "X-BPI-RECV-WINDOW": RW,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    }
    r = requests.get("https://api.bytick.com/v5/user/query-api", headers=h2, timeout=10)
    print(f"Status: {r.status_code} Body[:500]: {r.text[:500]}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)

print("\n=== TEST2 DONE ===", flush=True)
time.sleep(30)
