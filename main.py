# MAIN.PY - TEST ONLY - NO DATA ENGINE, NO GOLD BOSS, NO TRADING
# Copy this over your main.py, deploy, send me the retCode line
# After test, we go put back the real bot main.py
import os, time, hmac, hashlib, requests

BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "").strip()
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "").strip()
BASE_URL = "https://api.bybit.com"
RECV_WINDOW = "5000"

print("=== BYBIT AUTH TEST - NO DATA ENGINE ===", flush=True)
print(f"DEBUG KEY LEN {len(BYBIT_API_KEY)} START {BYBIT_API_KEY[:4]}**** | SECRET LEN {len(BYBIT_API_SECRET)}", flush=True)

def _sign_v5(payload_str, ts):
    msg = ts + BYBIT_API_KEY + RECV_WINDOW + payload_str
    return hmac.new(BYBIT_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

def test_get(path, params):
    ts = str(int(time.time() * 1000))
    qs = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    sign = _sign_v5(qs, ts)
    headers = {
        "X-BPI-APIKEY": BYBIT_API_KEY,
        "X-BPI-SIGN": sign,
        "X-BPI-SIGN-TYPE": "2",
        "X-BPI-TIMESTAMP": ts,
        "X-BPI-RECV-WINDOW": RECV_WINDOW,
        "Content-Type": "application/json"
    }
    url = BASE_URL + path + (f"?{qs}" if qs else "")
    print(f"\n--- TEST {path} ---", flush=True)
    print(f"Headers sent: {list(headers.keys())}", flush=True)
    print(f"APIKEY len: {len(headers['X-BPI-APIKEY'])} start: {headers['X-BPI-APIKEY'][:4]}****", flush=True)
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"HTTP Status: {r.status_code}", flush=True)
        print(f"Raw Body: {r.text[:500]}", flush=True)
        try:
            j = r.json()
            print(f"retCode: {j.get('retCode')} retMsg: {j.get('retMsg')}", flush=True)
            if j.get("retCode") == 0:
                print("✅ SUCCESS - KEY IS ALIVE!", flush=True)
            else:
                print("❌ BYBIT REJECTED KEY", flush=True)
        except:
            print("❌ Bybit returned empty / non-JSON - blocked", flush=True)
    except Exception as e:
        print(f"Request error: {e}", flush=True)

test_get("/v5/user/query-api", {})
test_get("/v5/account/wallet-balance", {"accountType": "UNIFIED"})

print("\n=== TEST DONE - NO DATA ENGINE WAS USED ===", flush=True)
# Keep alive so Render no restart am too fast, you fit read log
time.sleep(30)
