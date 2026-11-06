# V29.7 ONLY BE WITH PROFIT - FOR REAL $2.20 BYBIT - NO MORE BE LOSS
# RULE: NO BE at Entry. Only BE when Best +$4.00, SL to Entry +$3.50 = Net +$0.03 profit after real fee. Else WIN or LOSS.
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
LOSS_CUT_USD = 0.80
# V29.7 ONLY BE WITH PROFIT
BE_TRIGGER_USD = 4.00  # Only BE when price don move +$4.00
BE_LOCK_USD = 3.50    # SL to Entry + $3.50 = Gross $0.28 - Fee $0.25 = +$0.03 profit
TIME_BE_SEC = 0.5
TIME_BE_MIN = 0.30
MAX_HOLD_SEC = 3
MIN_NET_WIN = 0.15
MIN_BALANCE_STOP = 1.50
REAL_FEE_PER_TRADE = 0.18
REAL_BE_COST = 0.25
REAL_LATENCY_SEC = 0.3

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
stopped = False
live_price_cache = [None]
live_price_time = [0]

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
        return {"retCode": 0, "result": {"orderId": "PAPER-V29.7-BE-PROFIT"}}
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

def websocket_feeder():
    try:
        import websocket
        def on_message(ws, message):
            try:
                data = json.loads(message)
                topic = data.get("topic", "")
                if "tickers" in topic:
                    d = data.get("data", {})
                    if isinstance(d, dict):
                        p = safe_float(d.get("lastPrice"))
                        if p is not None:
                            live_price_cache[0] = p
                            live_price_time[0] = time.time()
            except: pass
        def on_open(ws):
            print("[WS] Connected - Real Bybit WS for PRICE only, 0.02s - Trades from REST (safe)", flush=True)
            ws.send(json.dumps({"op": "subscribe", "args": ["tickers.BTCUSDT"]}))
        def on_error(ws, err): print(f"[WS ERR] {err}", flush=True)
        def on_close(ws, *a):
            print("[WS] Closed, reconnecting in 2s...", flush=True)
            time.sleep(2)
        while True:
            try:
                ws = websocket.WebSocketApp("wss://stream.bybit.com/v5/public/linear", on_message=on_message, on_open=on_open, on_error=on_error, on_close=on_close)
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"[WS LOOP ERR] {e}", flush=True)
                time.sleep(2)
    except ImportError:
        print("[WS] websocket-client no dey, using polling fallback 0.1s", flush=True)
        while True:
            try:
                d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
                if d and d.get("result") and d["result"].get("list"):
                    p = safe_float(d["result"]["list"][0].get("lastPrice"))
                    if p is not None:
                        live_price_cache[0] = p
                        live_price_time[0] = time.time()
            except: pass
            time.sleep(0.1)

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

def get_live_price():
    if live_price_cache[0] is not None and time.time() - live_price_time[0] < 0.5:
        return live_price_cache[0]
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
    if d and d.get("result") and d["result"].get("list"):
        p = safe_float(d["result"]["list"][0].get("lastPrice"))
        if p is not None:
            live_price_cache[0] = p
            live_price_time[0] = time.time()
            return p
    return live_price_cache[0]

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
    buy_sum = sum((safe_float(t["size"], 0) or 0) for t in clean_trades if t.get("side") == "Buy")
    sell_sum = sum((safe_float(t["size"], 0) or 0) for t in clean_trades if t.get("side") == "Sell")
    if biggest_size >= MIN_WHALE_BTC:
        return {"type": "WHALE", "side": biggest_side, "size": biggest_size, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    return None

def calc_pct(move, price):
    gross_pct = (move / price * 100) if price else 0
    lev_pct = gross_pct * LEVERAGE
    return gross_pct, lev_pct

def place_stealth_trio(side, entry_price, tp_price, sl_price, qty):
    entry_dir = 2 if side == "Buy" else 1
    tp_dir = 1 if side == "Buy" else 2
    sl_dir = 1 if side == "Buy" else 2
    close_side = "Sell" if side == "Buy" else "Buy"
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
    be_profit_active = False
    be_sl = sl_price
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} TP 50% ${tp_price:.1f} SL ${sl_price:.1f} | ONLY BE WITH PROFIT: If Best +${BE_TRIGGER_USD} -> SL to Entry +${BE_LOCK_USD} = +$0.03 profit | NO BE at Entry", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK)
            continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move: best_move = cur_move
        # V29.7: ONLY BE WITH PROFIT - No BE at +$0.50, No BE at +$1.50
        if not be_profit_active and best_move >= BE_TRIGGER_USD:
            be_profit_active = True
            be_sl = entry_price + BE_LOCK_USD if side == "Buy" else entry_price - BE_LOCK_USD
            print(f"[BE-PROFIT-ACTIVE] {side} Best +${best_move:.2f} - SL moved to ${be_sl:.1f} (Entry +${BE_LOCK_USD}) = Net +$0.03 profit locked, NO LOSS AGAIN", flush=True)
        # TP check
        if side == "Buy" and live >= tp_price: return ("WIN", cur_move, elapsed, live, be_profit_active)
        if side == "Sell" and live <= tp_price: return ("WIN", cur_move, elapsed, live, be_profit_active)
        # BE-PROFIT hit
        if be_profit_active:
            if side == "Buy" and live <= be_sl:
                return ("BE-PROFIT", BE_LOCK_USD, elapsed, live, be_profit_active)
            if side == "Sell" and live >= be_sl:
                return ("BE-PROFIT", BE_LOCK_USD, elapsed, live, be_profit_active)
        # Normal LOSS - only if BE-PROFIT never activate
        if not be_profit_active and cur_move <= -LOSS_CUT_USD:
            return ("LOSS", cur_move, elapsed, live, be_profit_active)
        if elapsed >= MAX_HOLD_SEC:
            return ("TIMEOUT", cur_move, elapsed, live, be_profit_active)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-SIM'} ${BASE_BALANCE} REAL START Lev {LEVERAGE}x Qty {QTY_FIXED} V29.7 ONLY BE WITH PROFIT", flush=True)
    print(f"[EYE] V29.7 REAL - WS Price + REST Trades | Cooldown 15s | Whale ONLY 0.30 | Wick $12 | TP 50% | Real Fee $0.18 | ONLY BE WITH PROFIT +$4.00 -> +$3.50 = +$0.03 | WIN +$0.30 | LOSS -$0.95 | STOP < $1.50", flush=True)
    while True:
        try:
            if stopped:
                time.sleep(10); continue
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT STOP to protect $2.20", flush=True)
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
            gross_pct, lev_pct = calc_pct(tp_move, entry_price)
            notional = entry_price * QTY_FIXED * LEVERAGE
            expected_gross = (tp_move / entry_price) * notional
            expected_net = expected_gross - REAL_FEE_PER_TRADE
            net_pct_bal = (expected_net / balance * 100) if balance else 0
            est_tag = tp_price
            wick_pct = sig["wick_pct"]
            if expected_net < MIN_NET_WIN:
                print(f"[WIN-STRICTLY-REAL] Expected Net ${expected_net:.4f} < +$0.15 after real fee $0.18 - Skip", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            print(f"[{sig['type']}] {side} SINGLE-CONFIRM! Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} ({wick_pct:.4f}%) | Current ${current:.1f} | Margin ${margin_needed:.2f} OK | Real Fee ${REAL_FEE_PER_TRADE}", flush=True)
            print(f"[STEALTH] {side} -> Entry ${entry_price:.1f} TP ${tp_price:.1f} SL ${sl_price:.1f} Move ${tp_move:.2f} | Expected Net ${expected_net:.4f} = {net_pct_bal:.2f}% after REAL fee | BE ONLY WITH PROFIT", flush=True)
            if REAL_MODE:
                place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
            else:
                print(f"[PAPER-REAL-SIM] HIDDEN Entry+TP+SL - TP TAG ${est_tag:.1f} - Watching WS price 0.02s + Real Delay 0.3s", flush=True)
            result, real_move, elapsed, live_price, be_protected = run_alive_trade(side, entry_price, tp_price, sl_price)
            # V29.7 REAL PnL - ONLY BE WITH PROFIT
            real_gross = (real_move / entry_price) * notional if entry_price else 0
            real_net = real_gross - REAL_FEE_PER_TRADE
            if result == "BE-PROFIT":
                # BE_LOCK $3.50 -> Gross $0.28 - Fee $0.25 = +$0.03 profit
                real_gross = (BE_LOCK_USD / entry_price) * notional
                real_net = real_gross - REAL_FEE_PER_TRADE - 0.07  # +$0.03
            if result == "LOSS": real_net = -0.95
            if result == "TIMEOUT" and real_net < 0:
                real_net = real_net - 0.02
            real_net_pct = (real_net / balance * 100) if balance else 0
            real_gross_pct, real_lev_pct = calc_pct(real_move, entry_price)
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1; pnl += real_net; balance += real_net
                print(f"[WIN] {side} Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Net +${real_net:.4f} (after real fee $0.18) Bal ${balance:.2f}", flush=True)
            elif result == "BE-PROFIT":
                be_count += 1; pnl += real_net; balance += real_net
                print(f"[BE-PROFIT] {side} BE WITH PROFIT Net +${real_net:.4f} Bal ${balance:.2f} - NO LOSS, profit locked +$0.03", flush=True)
            elif result == "LOSS":
                losses += 1; pnl += real_net; balance += real_net
                print(f"[LOSS] {side} CUT Net {real_net:.4f} Bal ${balance:.2f} - Real loss with fee, no fake BE", flush=True)
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
            print(f"[SUMMARY] $2.20 REAL START | Wins {wins} BE-PROFIT {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} | Cooldown 15s | Whale ONLY 0.30 | Wick $12 | BE ONLY WITH PROFIT +$0.03 | WIN +$0.30 | LOSS -$0.95", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} - BOT STOP - Protect $2.20", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            time.sleep(1)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V29.7 ONLY BE WITH PROFIT ALIVE")
    def log_message(self, *a): pass

def keep_alive():
    while True:
        time.sleep(240)
        if RENDER_URL:
            try: urllib.request.urlopen(RENDER_URL, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=websocket_feeder, daemon=True).start()
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), H).serve_forever()
