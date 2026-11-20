# MAIN.PY - TEST 4 - MIRROR TEST, NO BYBIT
import os, requests, json
KEY = os.environ.get("BYBIT_API_KEY","").strip()
print(f"TEST4 KEY {KEY[:4]}**** LEN {len(KEY)}", flush=True)

# Send to httpbin - e go echo back wetin e receive
h = {
    "X-BPI-APIKEY": KEY,
    "X-BPI-SIGN": "test123",
    "User-Agent": "Mozilla/5.0"
}
print(f"We send headers: {list(h.keys())}", flush=True)
r = requests.get("https://httpbin.org/headers", headers=h, timeout=10)
print(f"Status: {r.status_code}", flush=True)
print(f"httpbin saw: {r.text[:1000]}", flush=True)
print("\n=== TEST4 DONE ===", flush=True)
import time; time.sleep(30)
