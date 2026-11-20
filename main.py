# MAIN.PY - TEST 5 - MAINNET vs TESTNET
import os, time, hmac, hashlib, requests
KEY = os.environ.get("BYBIT_API_KEY","").strip()
SEC = os.environ.get("BYBIT_API_SECRET","").strip()
RW = "5000"
print(f"TEST5 KEY {KEY[:4]}**** LEN {len(KEY)}", flush=True)
def test(base, label):
    ts = str(int(time.time()*1000))
    qs = "accountType=UNIFIED"
    msg = ts + KEY + RW + qs
    sign = hmac.new(SEC.encode(), msg.encode(), hashlib.sha256).hexdigest()
    h = {"X-BPI-APIKEY": KEY, "X-BPI-SIGN": sign, "X-BPI-SIGN-TYPE": "2", "X-BPI-TIMESTAMP": ts, "X-BPI-RECV-WINDOW": RW, "User-Agent": "Mozilla/5.0"}
    r = requests.get(f"{base}/v5/account/wallet-balance?{qs}", headers=h, timeout=10)
    print(f"{label} -> Status: {r.status_code} Body: {r.text[:300]}", flush=True)

test("https://api.bybit.com", "1. MAINNET")
test("https://api-testnet.bybit.com", "2. TESTNET")
print("=== TEST5 DONE ===", flush=True)
import time; time.sleep(30)
