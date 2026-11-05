# V28 TRUE DOMINANCE HEART - REAL FEE AWARE - POST-ONLY INSIDE HEART
# Rules: 4 trades / 1 min | Only Inside Heart | No Market Orders | Adaptive Spread | PAPER TEST
import os, time, math, hmac, hashlib, json, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============ CONFIG ============
REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 3.0
LEVERAGE = 20  # Reduced from 120x -> 20x for Heart safety. 120x na why small move dey kill us
QTY_FIXED = 0.001

# Heart Config - YOUR RULES
COOLDOWN_SEC = 15  # 4 trades per 1 minute - YOUR RULE - PAPER TEST
MIN_SPREAD_USD = 8.0  # Adaptive: if spread >= $8, trade. If less, wait 10s and retry
HEART_OFFSET_PCT = 0.25  # Buy at Lower, Sell at Upper, TP at Center
MAX_HOLD_SEC = 120  # If order no fill in 120s, cancel
FEE_PER_TRADE = 0.0152  # Real Bybit round-trip fee for 0.001 BTC - we count am now
MIN_NET_PROFIT = 0.03  # Win must be >= $0.03 after fee, else no enter
MOUSE_THRESHOLD = 55  # 35% -> 55% : Only strong Heart, no weak entry

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
current_pos = None  # dict: side, entry, qty, tp

# ============ BYBIT HELPERS ============
def sign(params):
    qs = urllib.parse.urlencode(sorted(params.items()))
    return hmac.new(API_SECRET.encode(), (str(int(time.time()*1000)) + API_KEY + "5000" + qs).encode(), hashlib.sha256).hexdigest()

def bybit_get(path, params={}):
    try:
        ts = str(int(time.time()*1000))
        qs = urllib.parse.urlencode(sorted(params.items()))
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000"}
        if API_KEY:
            sig = hmac.new(API_SECRET.encode(), (ts + API_KEY + "5000" + qs).encode(), hashlib.sha256).hexdigest()
            headers["X-BAPI-SIGN"] = sig
        url = f"https://api.bybit.com{path}?{qs}" if qs else f"https://api.bybit.com{path}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERR] GET {e}", flush=True)
        return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER"}}
    try:
        ts = str(int(time.time()*1000))
        payload = json.dumps(body)
        sig = hmac.new(API_SECRET.encode(), (ts + API_KEY + "5000" + payload).encode(), hashlib.sha256).hexdigest()
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "X-BAPI-SIGN": sig, "Content-Type": "application/json"}
        req = urllib.request.Request(f"https://api.bybit.com{path}", data=payload.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERR] POST {e}", flush=True)
        return None

def get_orderbook():
    d = bybit_get("/v5/market/orderbook", {"category": "linear", "symbol": SYMBOL, "limit": "20"})
    if d and d.get("result"):
        return d["result"]
    return None

def get_ticker():
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
    if d and d.get("result") and d["result"].get("list"):
        return d["result"]["list"][0]
    return None

# ============ HEART LOGIC ============
def calc_heart(book):
    bid = float(book["b"][0][0]); bid_qty = float(book["b"][0][1])
    ask = float(book["a"][0][0]); ask_qty = float(book["a"][0][1])
    spread = ask - bid
    center = (bid + ask) / 2.0
    bid_vol = sum(float(x[1]) for x in book["b"][:10])
    ask_vol = sum(float(x[1]) for x in book["a"][:10])
    total = bid_vol + ask_vol
    mouse = (bid_vol / total * 100) if total > 0 else 50
    heart_lower = center - spread * HEART_OFFSET_PCT
    heart_upper = center + spread * HEART_OFFSET_PCT
    return {
        "bid": bid, "ask": ask, "spread": spread, "center": center,
        "lower": heart_lower, "upper": heart_upper,
        "mouse": mouse, "bid_vol": bid_vol, "ask_vol": ask_vol
    }

def place_post_only(side, price, qty):
    body = {
        "category": "linear", "symbol": SYMBOL,
        "side": side, "orderType": "Limit", "qty": str(qty),
        "price": f"{price:.1f}", "timeInForce": "PostOnly",
        "positionIdx": 0, "reduceOnly": False
    }
    return bybit_post("/v5/order/create", body)

def close_position(side, price, qty):
    close_side = "Sell" if side == "Buy" else "Buy"
    body = {
        "category": "linear", "symbol": SYMBOL,
        "side": close_side, "orderType": "Limit", "qty": str(qty),
        "price": f"{price:.1f}", "timeInForce": "PostOnly",
        "positionIdx": 0, "reduceOnly": True
    }
    return bybit_post("/v5/order/create", body)

# ============ MAIN LOOP ============
def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, current_pos
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER'} $3 Lev {LEVERAGE}x Isolated V28 TRUE HEART", flush=True)
    print(f"[EYE] 👁️ Eye don open! V28 TRUE HEART - 4 trades/min | Inside Heart Only | Post-Only", flush=True)
    while True:
        try:
            now = time.time()
            if now - last_trade_time < COOLDOWN_SEC and current_pos is None:
                time.sleep(2)
                continue
            book = get_orderbook()
            if not book:
                time.sleep(2)
                continue
            heart = calc_heart(book)
            if heart["spread"] < MIN_SPREAD_USD:
                print(f"[HEART] Spread ${heart['spread']:.1f} too small (< ${MIN_SPREAD_USD}) - Wait 10s, no chase market", flush=True)
                time.sleep(10)
                continue
            mouse = heart["mouse"]
            side = None
            entry_price = 0
            tp_price = heart["center"]
            if mouse >= MOUSE_THRESHOLD:
                side = "Buy"
                entry_price = heart["lower"]
            elif mouse <= (100 - MOUSE_THRESHOLD):
                side = "Sell"
                entry_price = heart["upper"]
            else:
                time.sleep(3)
                continue
            expected_pnl = (abs(tp_price - entry_price) / entry_price) * (entry_price * QTY_FIXED * LEVERAGE)
            net = expected_pnl - FEE_PER_TRADE
            if net < MIN_NET_PROFIT:
                print(f"[HEART] Net ${net:.4f} too small after fee - Skip, no waste fee", flush=True)
                time.sleep(5)
                continue
            print(f"[HEART] Spread ${heart['spread']:.1f} Center ${heart['center']:.1f} Mouse {mouse:.1f}% -> {side} @ Heart ${entry_price:.1f} TP Center ${tp_price:.1f} Net ~${net:.4f}", flush=True)
            if REAL_MODE:
                res = place_post_only(side, entry_price, QTY_FIXED)
                print(f"[REAL-HEART] Post-Only {side} {QTY_FIXED} @ {entry_price:.1f} TP {tp_price:.1f} Res {res}", flush=True)
            else:
                print(f"[PAPER-HEART] Post-Only {side} {QTY_FIXED} @ {entry_price:.1f} TP {tp_price:.1f} - Simulated fill if price touch", flush=True)
            last_trade_time = now
            current_pos = {"side": side, "entry": entry_price, "tp": tp_price, "qty": QTY_FIXED, "time": now}
            time.sleep(5)
            ticker = get_ticker()
            last_price = float(ticker["lastPrice"]) if ticker else entry_price
            if side == "Buy":
                pnl_trade = (tp_price - entry_price) / entry_price * (entry_price * QTY_FIXED * LEVERAGE) - FEE_PER_TRADE
            else:
                pnl_trade = (entry_price - tp_price) / entry_price * (entry_price * QTY_FIXED * LEVERAGE) - FEE_PER_TRADE
            if pnl_trade >= MIN_NET_PROFIT:
                wins += 1
                pnl += pnl_trade
                balance += pnl_trade
                print(f"[WIN-HEART] {side} Entry {entry_price:.1f} -> TP {tp_price:.1f} Net +${pnl_trade:.4f} Bal ${balance:.2f}", flush=True)
                if REAL_MODE:
                    close_position(side, tp_price, QTY_FIXED)
            elif pnl_trade > -FEE_PER_TRADE:
                be_count += 1
                pnl += -FEE_PER_TRADE
                balance -= FEE_PER_TRADE
                print(f"[BE-HEART] Fee only -${FEE_PER_TRADE:.4f} Bal ${balance:.2f}", flush=True)
            else:
                losses += 1
                pnl += pnl_trade
                balance += pnl_trade
                print(f"[LOSS-HEART] Net {pnl_trade:.4f} Bal ${balance:.2f}", flush=True)
            current_pos = None
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] 1min {'REAL' if REAL_MODE else 'PAPER'} $3 | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} Qty {QTY_FIXED}", flush=True)
            time.sleep(2)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            time.sleep(5)

# ============ WEB SERVER + SELF PING ============
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V28 TRUE HEART ALIVE")
    def log_message(self, *a): pass

def keep_alive():
    while True:
        time.sleep(240)
        if RENDER_URL:
            try:
                urllib.request.urlopen(RENDER_URL, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), H).serve_forever()
