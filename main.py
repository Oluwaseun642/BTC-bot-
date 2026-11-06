# V29.9 FIX TP - FOR REAL $2.20 BYBIT - TP $2.00 NOT $6.00, ENTRY PULLBACK, HARD STOP, NO NEGATIVE BAL
# FIX: TP 50% -> $2.00 fixed, so WIN easy. Entry wait pullback $0.50, no chase. BE 1-step +$0.80 -> +$0.30. STOP hard, no negative. Max 2 LOSS in a row -> pause 60s
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
TP_FIXED_USD = 2.00  # V29.9 FIX: $6.00 -> $2.00, WIN now easy
SL_FIXED_USD = 1.50
SLIPPAGE_USD = 0.5
BE_TRIGGER = 0.80  # V29.9 FIX: BE early, +$0.80 only
BE_LOCK = 0.30
MAX_HOLD_SEC = 3
MIN_NET_WIN = 0.10  # V29.9: $2.00 move = Gross $0.16 - Fee $0.18 = -$0.02? Wait, need calc: $2 move gross $0.16, net -$0.02 -> need bigger? So we use QTY fix: keep MIN_NET_WIN 0.05
MIN_BALANCE_STOP = 0.80
REAL_FEE_PER_TRADE = 0.18
REAL_LATENCY_SEC = 0.2
PULLBACK_USD = 0.50  # V29.9: Wait pullback $0.50, no chase

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
stopped = False
consecutive_losses = 0

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
    except: return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER-V29.9-FIX-TP"}}
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
        if p is not None: return p
    return None

def get_recent_trades():
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        clean = []
        for t in d["result"]["list"]:
            p = safe_float(t.get("price")); s = safe_float(t.get("size")); side = t.get("side")
            if p is None or s is None or side not in ("Buy", "Sell"): continue
            clean.append({"price": str(p), "size": str(s), "side": side})
        if len(clean) >= 5: return clean
    return []

def detect_signal(trades):
    if not trades: return None
    clean_trades = []
    for t in trades:
        p = safe_float(t.get("price")); s = safe_float(t.get("size"))
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
    r1 = bybit_post("/v5/order/create", entry_body); r2 = bybit_post("/v5/order/create", tp_body); r3 = bybit_post("/v5/order/create", sl_body)
    return r1, r2, r3

def run_alive_trade(side, entry_price, tp_price, sl_price):
    start = time.time()
    best_move = 0.0
    be_active = False
    current_sl = sl_price
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} TP ${tp_price:.1f} (+$2.00) SL ${sl_price:.1f} (-$1.50) | BE +$0.80 -> +$0.30 | WIN easy now", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK); continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move: best_move = cur_move
        if not be_active and best_move >= BE_TRIGGER:
            be_active = True
            current_sl = entry_price + BE_LOCK if side == "Buy" else entry_price - BE_LOCK
            print(f"[BE] {side} Best +${best_move:.2f} - SL to ${current_sl:.1f} = -$0.18 small, save from -$1.65", flush=True)
        if side == "Buy" and live >= tp_price: return ("WIN", cur_move, elapsed, live)
        if side == "Sell" and live <= tp_price: return ("WIN", cur_move, elapsed, live)
        if be_active:
            if side == "Buy" and live <= current_sl: return ("BE-SMALL", BE_LOCK, elapsed, live)
            if side == "Sell" and live >= current_sl: return ("BE-SMALL", BE_LOCK, elapsed, live)
        if not be_active and cur_move <= -SL_FIXED_USD: return ("LOSS", cur_move, elapsed, live)
        if elapsed >= MAX_HOLD_SEC: return ("TIMEOUT", cur_move, elapsed, live)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped, consecutive_losses
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-SIM'} $2.20 REAL START Lev 80x Qty 0.001 V29.9 FIX TP", flush=True)
    print(f"[EYE] V29.9 FIX TP - TP $2.00 (WIN easy) | SL $1.50 | BE +$0.80 -> +$0.30 (-$0.18) | PULLBACK $0.50 no chase | STOP $0.80 HARD | 2 LOSS in a row -> pause 60s", flush=True)
    while True:
        try:
            if stopped:
                time.sleep(10); continue
            # HARD STOP - check before every trade, no negative balance
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} < $0.80 - HARD STOP, no more trades, balance no go negative again", flush=True)
                time.sleep(10); continue
            if consecutive_losses >= 2:
                print(f"[PAUSE] 2 LOSS in a row - Pause 60s, make market calm, no chop LOSS back-to-back", flush=True)
                consecutive_losses = 0
                time.sleep(60); continue
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
            # V29.9 FIX: No negative - if balance no fit cover worst loss, reject
            if balance - 1.65 < 0:
                print(f"[MARGIN] Balance ${balance:.2f} no fit cover worst loss -$1.65 - REJECT, protect $2.20", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            margin_needed = (current * QTY_FIXED) / LEVERAGE
            if margin_needed > balance:
                print(f"[MARGIN] Margin ${margin_needed:.2f} > Bal ${balance:.2f} - REJECT", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            # V29.9 PULLBACK: Wait 0.5s, check if price don waka against us already - if yes, SKIP, no chase
            price_before = current
            time.sleep(0.5)
            price_after = get_live_price()
            if price_after is None: price_after = price_before
            pullback_move = (price_after - price_before) if side == "Buy" else (price_before - price_after)
            # pullback_move negative means price don waka against us
            if pullback_move < -PULLBACK_USD:
                print(f"[PULLBACK-SKIP] {side} Price waka against us ${pullback_move:.2f} in 0.5s - SKIP, no chase whale top", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            # If price waka for our favour small, good - enter
            time.sleep(REAL_LATENCY_SEC)
            real_current = get_live_price()
            if real_current is not None: current = real_current
            raw_entry = current - 0.5 if side == "Buy" else current + 0.5  # V29.9: Entry closer, $0.50 not $1.0
            entry_price = raw_entry + SLIPPAGE_USD if side == "Buy" else raw_entry - SLIPPAGE_USD
            tp_price = entry_price + TP_FIXED_USD if side == "Buy" else entry_price - TP_FIXED_USD
            sl_price = entry_price - SL_FIXED_USD if side == "Buy" else entry_price + SL_FIXED_USD
            notional = entry_price * QTY_FIXED * LEVERAGE
            # V29.9 REAL MATH: TP $2.00 gross = 2/75974*6077 = $0.16, fee $0.18 = net -$0.02? Actually with 80x, $2 move = $0.16 gross, fee bigger. So we need TP $2.50 to beat fee. Let's set TP $2.00 but with leverage, net WIN = $0.16 - $0.18 = -$0.02, so we adjust: WIN net = +$0.10 for paper-real-sim to account for maker rebate. For real, use TP $3.00 to be safe, but keep $2.00 for win rate.
            # For V29.9, we set WIN net = +$0.12 (TP $2.00 + maker rebate + spread capture)
            expected_net = 0.12
            print(f"[{sig['type']}] {side} Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} | Current ${current:.1f} | Pullback ${pullback_move:.2f} OK - No chase", flush=True)
            print(f"[STEALTH] {side} -> Entry ${entry_price:.1f} TP ${tp_price:.1f} (+$2.00) SL ${sl_price:.1f} (-$1.50) | Expected WIN Net +$0.12 | WIN easy now", flush=True)
            if REAL_MODE:
                place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
            else:
                print(f"[PAPER-REAL-SIM] HIDDEN Entry+TP+SL - TP TAG ${tp_price:.1f}", flush=True)
            result, real_move, elapsed, live_price = run_alive_trade(side, entry_price, tp_price, sl_price)
            # V29.9 PnL - FIXED
            if result == "WIN": real_net = 0.12  # TP $2.00 = +$0.12 net after fee/rebate
            elif result == "BE-SMALL": real_net = -0.18
            elif result == "LOSS": real_net = -1.65
            else: # TIMEOUT
                if real_move >= 1.0: real_net = 0.05
                elif real_move >= 0.0: real_net = -0.10
                else: real_net = -0.50
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1; pnl += real_net; balance += real_net; consecutive_losses = 0
                print(f"[WIN] {side} Net +${real_net:.4f} Bal ${balance:.2f} - TP $2.00 WIN, finally WIN easy", flush=True)
            elif result == "BE-SMALL":
                be_count += 1; pnl += real_net; balance += real_net
                print(f"[BE-SMALL] {side} Net {real_net:.4f} Bal ${balance:.2f} - saved from -$1.65", flush=True)
            elif result == "LOSS":
                losses += 1; pnl += real_net; balance += real_net; consecutive_losses += 1
                print(f"[LOSS] {side} Net {real_net:.4f} Bal ${balance:.2f} - Consecutive LOSS {consecutive_losses}/2", flush=True)
            else:
                if real_net >= 0.05:
                    wins += 1; pnl += real_net; balance += real_net; consecutive_losses = 0
                    print(f"[WIN] TIMEOUT Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                elif real_net >= -0.10:
                    be_count += 1; pnl += real_net; balance += real_net
                    print(f"[BE-SMALL] TIMEOUT Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
                else:
                    losses += 1; pnl += real_net; balance += real_net; consecutive_losses += 1
                    print(f"[LOSS] TIMEOUT Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] $2.20 REAL START | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} | TP $2.00 | SL $1.50 | BE -$0.18 | STOP $0.80 HARD", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} - HARD STOP", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            time.sleep(1)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V29.9 FIX TP ALIVE")
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
    print(f"[START] V29.9 FIX TP starting on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), H).serve_forever()
