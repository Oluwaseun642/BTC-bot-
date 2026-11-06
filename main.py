# V29.8 FIXED DEPLOY - FOR REAL $2.20 BYBIT - NO WEBSOCKET, POLLING ONLY, DEPLOY FAST
# SL $1.50 | BE1 +$1.20 -> +$0.30 (-$0.18) | BE2 +$4.00 -> +$3.50 (+$0.03) | STOP $0.80 | Whale 0.30 | Wick $12
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse, traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.20
LEVERAGE = 80
QTY_FIXED = 0.001
CHECK_INTERVAL = 0.1
LIVE_CHECK = 0.05
COOLDOWN_SEC = 15
MIN_WHALE_BTC = 0.30
MIN_WICK_USD = 12.0
TP_WICK_PCT = 0.50
SLIPPAGE_USD = 0.5
LOSS_CUT_USD = 1.50
BE1_TRIGGER = 1.20
BE1_LOCK = 0.30
BE2_TRIGGER = 4.00
BE2_LOCK = 3.50
MAX_HOLD_SEC = 3
MIN_NET_WIN = 0.15
MIN_BALANCE_STOP = 0.80
REAL_FEE_PER_TRADE = 0.18
REAL_LATENCY_SEC = 0.3

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
stopped = False

def safe_float(x, default=None):
    try:
        if x is None: return default
        if isinstance(x, str):
            s = x.strip().lower()
            if s in ("none", "", "null", "nan"): return default
        v = float(x)
        if v != v: return default
        return v
    except: return default

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
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[GET ERR] {e}", flush=True)
        return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER-V29.8-FIXED"}}
    try:
        ts = str(int(time.time()*1000))
        payload = json.dumps(body)
        sig = hmac.new(API_SECRET.encode(), (ts + API_KEY + "5000" + payload).encode(), hashlib.sha256).hexdigest()
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "X-BAPI-SIGN": sig, "Content-Type": "application/json"}
        req = urllib.request.Request(f"https://api.bybit.com{path}", data=payload.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERR] POST {e}", flush=True)
        return None

def get_live_price():
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
    if d and d.get("result") and d["result"].get("list"):
        p = safe_float(d["result"]["list"][0].get("lastPrice"))
        if p is not None:
            return p
    return None

def get_recent_trades():
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        clean = []
        for t in d["result"]["list"]:
            p = safe_float(t.get("price"))
            s = safe_float(t.get("size"))
            side = t.get("side")
            if p is None or s is None or side not in ("Buy", "Sell"):
                continue
            clean.append({"price": str(p), "size": str(s), "side": side})
        if len(clean) >= 5:
            return clean
    return []

def detect_signal(trades):
    if not trades: return None
    clean_trades = []
    for t in trades:
        p = safe_float(t.get("price"))
        s = safe_float(t.get("size"))
        if p is None or s is None: continue
        clean_trades.append({"price": str(p), "size": str(s), "side": t.get("side")})
    if len(clean_trades) < 5: return None
    prices = [safe_float(t["price"]) for t in clean_trades]
    prices = [p for p in prices if p is not None]
    if not prices: return None
    wick = max(prices) - min(prices)
    current = safe_float(clean_trades[0].get("price"))
    if current is None: return None
    biggest = max(clean_trades, key=lambda t: safe_float(t.get("size"), 0) or 0)
    biggest_size = safe_float(biggest.get("size"), 0) or 0
    biggest_side = biggest.get("side", "")
    if biggest_size >= MIN_WHALE_BTC:
        return {"type": "WHALE", "side": biggest_side, "size": biggest_size, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0}
    return None

def place_stealth_trio(side, entry_price, tp_price, sl_price, qty):
    close_side = "Sell" if side == "Buy" else "Buy"
    entry_dir = 2 if side == "Buy" else 1
    tp_dir = 1 if side == "Buy" else 2
    sl_dir = 1 if side == "Buy" else 2
    entry_body = {"category": "linear", "symbol": SYMBOL, "side": side, "orderType": "Limit", "qty": str(qty), "price": f"{entry_price:.1f}", "triggerPrice": f"{entry_price:.1f}", "triggerDirection": entry_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": False}
    tp_body = {"category": "linear", "symbol": SYMBOL, "side": close_side, "orderType": "Limit", "qty": str(qty), "price": f"{tp_price:.1f}", "triggerPrice": f"{tp_price:.1f}", "triggerDirection": tp_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": True}
    sl_body = {"category": "linear", "symbol": SYMBOL, "side": close_side, "orderType": "Market", "qty": str(qty), "triggerPrice": f"{sl_price:.1f}", "triggerDirection": sl_dir, "triggerBy": "LastPrice", "timeInForce": "GoodTillCancel", "positionIdx": 0, "reduceOnly": True, "stopLoss": f"{sl_price:.1f}"}
    r1 = bybit_post("/v5/order/create", entry_body)
    r2 = bybit_post("/v5/order/create", tp_body)
    r3 = bybit_post("/v5/order/create", sl_body)
    return r1, r2, r3

def run_alive_trade(side, entry_price, tp_price, sl_price):
    start = time.time()
    best_move = 0.0
    be1 = False
    be2 = False
    current_sl = sl_price
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} TP ${tp_price:.1f} SL ${sl_price:.1f} | BE1 +$1.20 -> +$0.30 (-$0.18) | BE2 +$4.00 -> +$3.50 (+$0.03) | SL $1.50", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK)
            continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move: best_move = cur_move
        if not be1 and best_move >= BE1_TRIGGER:
            be1 = True
            current_sl = entry_price + BE1_LOCK if side == "Buy" else entry_price - BE1_LOCK
            print(f"[BE1-SMALL] {side} Best +${best_move:.2f} - SL to ${current_sl:.1f} = -$0.18 small, save from -$1.65", flush=True)
        if be1 and not be2 and best_move >= BE2_TRIGGER:
            be2 = True
            current_sl = entry_price + BE2_LOCK if side == "Buy" else entry_price - BE2_LOCK
            print(f"[BE2-PROFIT] {side} Best +${best_move:.2f} - SL to ${current_sl:.1f} = +$0.03 profit", flush=True)
        if side == "Buy" and live >= tp_price: return ("WIN", cur_move, elapsed, live)
        if side == "Sell" and live <= tp_price: return ("WIN", cur_move, elapsed, live)
        if be1:
            if side == "Buy" and live <= current_sl:
                return ("BE-PROFIT", BE2_LOCK, elapsed, live) if be2 else ("BE-SMALL", BE1_LOCK, elapsed, live)
            if side == "Sell" and live >= current_sl:
                return ("BE-PROFIT", BE2_LOCK, elapsed, live) if be2 else ("BE-SMALL", BE1_LOCK, elapsed, live)
        if not be1 and cur_move <= -LOSS_CUT_USD:
            return ("LOSS", cur_move, elapsed, live)
        if elapsed >= MAX_HOLD_SEC:
            return ("TIMEOUT", cur_move, elapsed, live)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-SIM'} $2.20 REAL START Lev 80x Qty 0.001 V29.8 FIXED DEPLOY", flush=True)
    print(f"[EYE] V29.8 FIXED - SL $1.50 | BE1 +$1.20 -> +$0.30 (-$0.18) | BE2 +$4.00 -> +$3.50 (+$0.03) | STOP $0.80 | Whale 0.30 | Wick $12 | Cooldown 15s | NO WEBSOCKET", flush=True)
    while True:
        try:
            if stopped:
                time.sleep(10); continue
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT STOP", flush=True)
                time.sleep(10); continue
            now = time.time()
            trades = get_recent_trades()
            sig = detect_signal(trades)
            if sig is None:
                time.sleep(CHECK_INTERVAL); continue
            if now - last_trade_time < COOLDOWN_SEC:
                time.sleep(CHECK_INTERVAL); continue
            if sig["wick"] < MIN_WICK_USD:
                time.sleep(CHECK_INTERVAL); continue
            side = sig["side"]
            current = sig["current"]
            cached = get_live_price()
            if cached is not None: current = cached
            margin_needed = (current * QTY_FIXED) / LEVERAGE
            if margin_needed > balance:
                print(f"[MARGIN] Margin ${margin_needed:.2f} > Bal ${balance:.2f} - REJECT", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            time.sleep(REAL_LATENCY_SEC)
            real_current = get_live_price()
            if real_current is not None: current = real_current
            raw_entry = current - 1.0 if side == "Buy" else current + 1.0
            entry_price = raw_entry + SLIPPAGE_USD if side == "Buy" else raw_entry - SLIPPAGE_USD
            tp_move = sig["wick"] * TP_WICK_PCT
            tp_price = entry_price + tp_move if side == "Buy" else entry_price - tp_move
            sl_price = entry_price - LOSS_CUT_USD if side == "Buy" else entry_price + LOSS_CUT_USD
            notional = entry_price * QTY_FIXED * LEVERAGE
            expected_gross = (tp_move / entry_price) * notional
            expected_net = expected_gross - REAL_FEE_PER_TRADE
            if expected_net < MIN_NET_WIN:
                print(f"[WIN-STRICTLY] Expected Net ${expected_net:.4f} < +$0.15 - Skip", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            print(f"[{sig['type']}] {side} Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} | Current ${current:.1f} | Margin ${margin_needed:.2f} OK", flush=True)
            print(f"[STEALTH] {side} -> Entry ${entry_price:.1f} TP ${tp_price:.1f} SL ${sl_price:.1f} Move ${tp_move:.2f} | Expected Net ${expected_net:.4f}", flush=True)
            if REAL_MODE:
                place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
            else:
                print(f"[PAPER-REAL-SIM] HIDDEN Entry+TP+SL - TP TAG ${tp_price:.1f}", flush=True)
            result, real_move, elapsed, live_price = run_alive_trade(side, entry_price, tp_price, sl_price)
            real_gross = (real_move / entry_price) * notional if entry_price else 0
            real_net = real_gross - REAL_FEE_PER_TRADE
            if result == "BE-PROFIT":
                real_gross = (BE2_LOCK / entry_price) * notional
                real_net = real_gross - REAL_FEE_PER_TRADE - 0.07
            if result == "BE-SMALL":
                real_gross = (BE1_LOCK / entry_price) * notional
                real_net = real_gross - REAL_FEE_PER_TRADE - 0.07
            if result == "LOSS": real_net = -1.65
            if result == "TIMEOUT" and real_net < 0:
                real_net = real_net - 0.02
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1; pnl += real_net; balance += real_net
                print(f"[WIN] {side} Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
            elif result == "BE-PROFIT":
                be_count += 1; pnl += real_net; balance += real_net
                print(f"[BE-PROFIT] {side} Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
            elif result == "BE-SMALL":
                be_count += 1; pnl += real_net; balance += real_net
                print(f"[BE-SMALL] {side} Net {real_net:.4f} Bal ${balance:.2f} - saved from -$1.65", flush=True)
            elif result == "LOSS":
                losses += 1; pnl += real_net; balance += real_net
                print(f"[LOSS] {side} Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            else:
                if real_net >= MIN_NET_WIN:
                    wins += 1; pnl += real_net; balance += real_net
                    print(f"[WIN] TIMEOUT Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                elif real_net >= 0.0:
                    be_count += 1; pnl += real_net; balance += real_net
                    print(f"[BE-PROFIT] TIMEOUT Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                else:
                    losses += 1; pnl += real_net; balance += real_net
                    print(f"[LOSS] TIMEOUT Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] $2.20 REAL START | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} | SL $1.50 | BE1 -$0.18 | BE2 +$0.03 | STOP $0.80", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} - BOT STOP", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            time.sleep(1)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V29.8 FIXED DEPLOY ALIVE")
    def log_message(self, *a): pass

def keep_alive():
    while True:
        time.sleep(240)
        if RENDER_URL:
            try: urllib.request.urlopen(RENDER_URL, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    print(f"[START] V29.8 FIXED DEPLOY starting on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), H).serve_forever()
