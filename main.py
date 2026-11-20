# TEST 7 - V13 EXACT HEADERS
import os, time, hmac, hashlib, json, requests
KEY = os.environ.get("BYBIT_API_KEY","").strip()
SEC = os.environ.get("BYBIT_API_SECRET","").strip()
print(f"TEST7 KEY {KEY[:4]}**** LEN {len(KEY)}", flush=True)

def bybit_get(path, params):
    ts = str(int(time.time()*1000)); rw = "5000"
    qs = "&".join([f"{k}={v}" for k,v in sorted(params.items())])
    payload = f"{ts}{KEY}{rw}{qs}"
    sign = hmac.new(SEC.encode(), payload.encode(), hashlib.sha256).hexdigest()
    h = {"X-BAPI-API-KEY": KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": rw, "X-BAPI-SIGN": sign}
    r = requests.get("https://api.bybit.com"+path, params=params, headers=h, timeout=10)
    print(f"Status: {r.status_code} Body: {r.text[:500]}", flush=True)
    return r.text

print("--- 1. WALLET with X-BAPI (V13 style) ---", flush=True)
bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
print("=== TEST7 DONE ===", flush=True)
import time; time.sleep(30)
