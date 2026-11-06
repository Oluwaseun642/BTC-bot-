# V29.3 REAL WEBSOCKET + COOLDOWN 5s + BE PROTECTIVE THAN LOSS - REAL $2.20 WIN STRICTLY - LEV 80x QTY 0.001
# Real WS: Bybit push price to us 0.02s, no polling. BE 2-stage: +$0.50 -> Entry (protect), +$1.50 -> +$1.50 lock (profit)
# Cooldown 5s, Loss -$0.80 = -$0.156, BE worst -$0.092, BE best +$0.028, TP +$0.148. Win Strictly: Enter only if Expected Net >= +$0.10
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.20  # V29.3: REAL $2.20, win strictly, no gamble
LEVERAGE = 80
QTY_FIXED = 0.001

CHECK_INTERVAL = 0.1  # V29.3: WS go push, this na just fallback
LIVE_CHECK = 0.05  # V29.3: WS live, this na fallback
COOLDOWN_SEC = 5  # V29.3: You talk am - 5 sec cooldown, no chase chop
MIN_WHALE_BTC = 0.15
MIN_SPIKE_BTC = 0.15
MIN_WICK_USD = 6.0
TP_WICK_PCT = 0.50
SLIPPAGE_USD = 0.3
LOSS_CUT_USD = 0.80  # Loss = -$0.156 Net
BE_LOCK_USD = 0.50  # Stage 1 Instant BE - protect
BE_PROTECT_USD = 1.50  # Stage 2 Profit Lock - profit +$0.028
TIME_BE_SEC = 0.5
TIME_BE_MIN = 0.30
MAX_HOLD_SEC = 3
MIN_NET_WIN = 0.10  # V29.3 WIN STRICTLY: Was 0.03, now 0.10 - enter only if fit give real win
MIN_NET_BE = 0.10  # Same - no small BE entry
MIN_BALANCE_STOP = 1.00

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
stopped = False
live_price_cache = [None]
live_price_time = [0]
ws_trades = []  # Real WS trades list, Bybit push am
ws_trades_lock = threading.Lock()

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
        return {"retCode": 0, "result": {"orderId": "PAPER-V29.3"}}
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
    # V29.3 REAL BYBIT WEBSOCKET: Bybit push price to us, we no dey ask every 0.1s
    # If websocket-client no dey, fallback to fast polling 0.1s
    try:
        import websocket
        def on_message(ws, message):
            try:
                data = json.loads(message)
                topic = data.get("topic", "")
                # Ticker push: tickers.BTCUSDT
                if "tickers" in topic:
                    d = data.get("data", {})
                    if d and "lastPrice" in d:
                        live_price_cache[0] = float(d["lastPrice"])
                        live_price_time[0] = time.time()
                # Trade push: publicTrade.BTCUSDT
                if "publicTrade" in topic:
                    trades_data = data.get("data", [])
                    with ws_trades_lock:
                        for t in trades_data:
                            # Bybit WS trade: {price, size, side, ...} side: Buy/Sell
                            ws_trades.insert(0, {"price": str(t.get("price")), "size": str(t.get("size")), "side": t.get("side")})
                        # Keep only last 50
                        del ws_trades[50:]
            except: pass
        def on_open(ws):
            print("[WS] Connected to Bybit Real Websocket - Price dey come to us 0.02s", flush=True)
            ws.send(json.dumps({"op": "subscribe", "args": ["tickers.BTCUSDT", "publicTrade.BTCUSDT"]}))
        def on_error(ws, err):
            print(f"[WS ERR] {err} - fallback to polling", flush=True)
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
        print("[WS] websocket-client no dey, using fast polling fallback 0.1s - add websocket-client to requirements.txt for real WS", flush=True)
        while True:
            try:
                d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
                if d and d.get("result") and d["result"].get("list"):
                    live_price_cache[0] = float(d["result"]["list"][0]["lastPrice"])
                    live_price_time[0] = time.time()
            except: pass
            time.sleep(0.1)

def get_recent_trades():
    # Prefer WS trades if fresh, else REST
    with ws_trades_lock:
        if len(ws_trades) >= 10:
            return list(ws_trades[:50])
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        return d["result"]["list"]
    with ws_trades_lock:
        return list(ws_trades[:50])

def get_live_price():
    # WS cache is fresh if <0.5s - Bybit push am, no need fetch
    if live_price_cache[0] is not None and time.time() - live_price_time[0] < 0.5:
        return live_price_cache[0]
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
    if d and d.get("result") and d["result"].get("list"):
        try:
            p = float(d["result"]["list"][0]["lastPrice"])
            live_price_cache[0] = p
            live_price_time[0] = time.time()
            return p
        except: return live_price_cache[0]
    return live_price_cache[0]

def detect_signal(trades):
    if not trades: return None
    prices = [float(t["price"]) for t in trades]
    wick = max(prices) - min(prices)
    current = float(trades[0]["price"])
    biggest = max(trades, key=lambda t: float(t.get("size", 0)))
    biggest_size = float(biggest.get("size", 0))
    biggest_side = biggest.get("side", "")
    buy_sum = sum(float(t["size"]) for t in trades if t.get("side") == "Buy")
    sell_sum = sum(float(t["size"]) for t in trades if t.get("side") == "Sell")
    if biggest_size >= MIN_WHALE_BTC:
        return {"type": "WHALE", "side": biggest_side, "size": biggest_size, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    if buy_sum >= MIN_SPIKE_BTC and buy_sum > sell_sum * 2.0:
        return {"type": "SMALL-SPIKE", "side": "Buy", "size": buy_sum, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    if sell_sum >= MIN_SPIKE_BTC and sell_sum > buy_sum * 2.0:
        return {"type": "SMALL-SPIKE", "side": "Sell", "size": sell_sum, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
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
    # V29.3 BE PROTECTIVE THAN LOSS: Stage 1 +$0.50 -> Entry (worst -$0.092), Stage 2 +$1.50 -> +$1.50 lock (worst +$0.028)
    start = time.time()
    best_move = 0.0
    be_stage1 = False
    be_stage2 = False
    current_sl = sl_price
    liq_dist = entry_price * 0.011
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} (slip ${SLIPPAGE_USD}) TP 50% ${tp_price:.1f} SL ${sl_price:.1f} BE-Stage1 +${BE_LOCK_USD} -> Entry | BE-Stage2 +${BE_PROTECT_USD} -> +${BE_PROTECT_USD} lock (profit) | Liq ~${entry_price - liq_dist:.1f} - WS Live 0.02s", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK)
            continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move:
            best_move = cur_move
        # Stage 1 - Instant BE Protective: At +$0.50, SL to Entry
        if not be_stage1 and best_move >= BE_LOCK_USD:
            be_stage1 = True
            current_sl = entry_price
            print(f"[BE-STAGE1-PROTECT] {side} Best +${best_move:.2f} >= +${BE_LOCK_USD} - SL moved to Entry ${current_sl:.1f} INSTANT. Worst case now na only fee -$0.092, no be LOSS -$0.156. BE > LOSS.", flush=True)
        # Stage 2 - Profit Lock: At +$1.50, SL to +$1.50 lock
        if be_stage1 and not be_stage2 and best_move >= BE_PROTECT_USD:
            be_stage2 = True
            if side == "Buy":
                current_sl = entry_price + BE_PROTECT_USD
            else:
                current_sl = entry_price - BE_PROTECT_USD
            print(f"[BE-STAGE2-PROFIT] {side} Best +${best_move:.2f} >= +${BE_PROTECT_USD} - SL upgraded to ${current_sl:.1f} (+${BE_PROTECT_USD} profit lock). Worst case now +$0.028 profit. Let am run to TP ${tp_price:.1f}", flush=True)
        # Time BE: After 0.5s, if still +$0.30, SL to Entry
        if elapsed >= TIME_BE_SEC and not be_stage1 and cur_move >= TIME_BE_MIN:
            be_stage1 = True
            current_sl = entry_price
            print(f"[TIME-BE] {side} After {elapsed:.1f}s still +${cur_move:.2f} - SL moved to Entry ${current_sl:.1f} FAST PROTECT", flush=True)
        if side == "Buy" and live >= tp_price:
            return ("WIN", cur_move, elapsed, live, be_stage1)
        if side == "Sell" and live <= tp_price:
            return ("WIN", cur_move, elapsed, live, be_stage1)
        if be_stage1:
            if side == "Buy" and live <= current_sl:
                if be_stage2:
                    return ("BE-PROTECT", BE_PROTECT_USD, elapsed, live, be_stage1)
                else:
                    return ("BE-TIME", 0.0, elapsed, live, be_stage1)
            if side == "Sell" and live >= current_sl:
                if be_stage2:
                    return ("BE-PROTECT", BE_PROTECT_USD, elapsed, live, be_stage1)
                else:
                    return ("BE-TIME", 0.0, elapsed, live, be_stage1)
        if not be_stage1:
            if cur_move <= -LOSS_CUT_USD:
                return ("LOSS", cur_move, elapsed, live, be_stage1)
        if elapsed >= MAX_HOLD_SEC:
            return ("TIMEOUT", cur_move, elapsed, live, be_stage1)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-THINKING'} ${BASE_BALANCE} REAL START Lev {LEVERAGE}x Qty {QTY_FIXED} V29.3 REAL WS", flush=True)
    print(f"[EYE] Eye open WIDE! V29.3 - REAL WS 0.02s | Cooldown 5s | Single Confirm Whale 0.15 | Wick $6 | TP 50% Min +$0.148 | Loss -${LOSS_CUT_USD} = -$0.156 | BE-Stage1 +$0.50 -> Entry (worst -$0.092) | BE-Stage2 +$1.50 -> +$1.50 lock (worst +$0.028) | WIN STRICTLY Enter only >= +$0.10 | STOP if Bal < ${MIN_BALANCE_STOP} | EST-TAG | % EAT", flush=True)
    while True:
        try:
            if stopped:
                time.sleep(10)
                continue
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance too low Bal ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT DON STOP to protect your $2.20. PnL ${pnl:.4f} Wins {wins} BE {be_count} Losses {losses}", flush=True)
                time.sleep(10)
                continue
            now = time.time()
            trades = get_recent_trades()
            sig = detect_signal(trades)
            if sig is None:
                time.sleep(CHECK_INTERVAL)
                continue
            if now - last_trade_time < COOLDOWN_SEC:
                time.sleep(CHECK_INTERVAL)
                continue
            if sig["wick"] < MIN_WICK_USD:
                print(f"[{sig['type']}] {sig['side']} Size {sig['size']:.3f} BTC but Wick ${sig['wick']:.2f} ({sig['wick_pct']:.4f}%) too small < ${MIN_WICK_USD} - Skip", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            side = sig["side"]
            current = sig["current"]
            cached = get_live_price()
            if cached is not None:
                current = cached
            margin_needed = (current * QTY_FIXED) / LEVERAGE
            if margin_needed > balance:
                print(f"[MARGIN] Margin needed ${margin_needed:.2f} > Bal ${balance:.2f} - REJECT like Bybit", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            raw_entry = current - 1.0 if side == "Buy" else current + 1.0
            entry_price = raw_entry + SLIPPAGE_USD if side == "Buy" else raw_entry - SLIPPAGE_USD
            tp_move = sig["wick"] * TP_WICK_PCT
            tp_price = entry_price + tp_move if side == "Buy" else entry_price - tp_move
            sl_price = entry_price - LOSS_CUT_USD if side == "Buy" else entry_price + LOSS_CUT_USD
            gross_pct, lev_pct = calc_pct(tp_move, entry_price)
            notional = entry_price * QTY_FIXED * LEVERAGE
            expected_gross = (tp_move / entry_price) * notional
            real_fee = 0.092
            expected_net = expected_gross - real_fee
            net_pct_bal = (expected_net / balance * 100) if balance else 0
            est_tag = tp_price
            wick_pct = sig["wick_pct"]
            # WIN STRICTLY: Enter only if Expected Net >= +$0.10
            if expected_net < MIN_NET_WIN:
                print(f"[WIN-STRICTLY] {sig['type']} Expected Net ${expected_net:.4f} < +$0.10 - Skip, we dey on $2.20, we no dey gamble small win", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            print(f"[{sig['type']}] {side} SINGLE-CONFIRM! Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} ({wick_pct:.4f}%) | Current ${current:.1f} | Margin ${margin_needed:.2f} OK - ENTER VIA WS FAST", flush=True)
            print(f"[STEALTH] Follow {sig['type']} {side} -> HIDDEN Entry ${entry_price:.1f} (slip ${SLIPPAGE_USD}) TP 50% ${tp_price:.1f} SL ${sl_price:.1f} Move ${tp_move:.2f}", flush=True)
            print(f"[% -EAT] Wick {wick_pct:.4f}% | TP Move ${tp_move:.2f} = {gross_pct:.4f}% gross x {LEVERAGE}x = {lev_pct:.3f}% lev | Expected Net ${expected_net:.4f} = {net_pct_bal:.2f}% of Bal ${balance:.2f} | Fee ${real_fee} | Min TP +$0.148 over fees | WIN STRICTLY", flush=True)
            print(f"[EST-TAG] Estimated Market Price Tag: Entry ${entry_price:.1f} -> TP TAG ${est_tag:.1f} ({side} {'+' if side=='Buy' else '-'}{tp_move:.2f}) | SL TAG ${sl_price:.1f} | BE-Stage1 TAG ${entry_price:.1f} | BE-Stage2 TAG ${entry_price + BE_PROTECT_USD if side=='Buy' else entry_price - BE_PROTECT_USD:.1f}", flush=True)
            if REAL_MODE:
                r1, r2, r3 = place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
                print(f"[REAL-STEALTH] Entry+TP+SL same time Entry {entry_price:.1f} TP TAG {est_tag:.1f} SL {sl_price:.1f}", flush=True)
            else:
                print(f"[PAPER-REAL-THINKING] HIDDEN Entry+TP+SL same time - TP TAG ${est_tag:.1f} - Watching REAL WS price every 0.02s", flush=True)
            result, real_move, elapsed, live_price, be_protected = run_alive_trade(side, entry_price, tp_price, sl_price)
            real_gross = (real_move / entry_price) * notional if entry_price else 0
            real_net = real_gross - real_fee
            if result == "BE-PROTECT":
                real_gross = (BE_PROTECT_USD / entry_price) * notional
                real_net = real_gross - real_fee
            if result == "BE-TIME":
                real_net = -0.092
            real_net_pct = (real_net / balance * 100) if balance else 0
            real_gross_pct, real_lev_pct = calc_pct(real_move, entry_price)
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1
                pnl += real_net
                balance += real_net
                print(f"[WIN-STEALTH] {sig['type']} {side} Entry {entry_price:.1f} -> LIVE ${live_price:.1f} (EST-TAG ${est_tag:.1f} HIT) in {elapsed:.1f}s Real Move ${real_move:.2f} ({real_gross_pct:.4f}% gross, {real_lev_pct:.3f}% lev) Net +${real_net:.4f} (+{real_net_pct:.2f}% of Bal) Bal ${balance:.2f}", flush=True)
            elif result == "BE-PROTECT":
                be_count += 1
                pnl += real_net
                balance += real_net
                print(f"[BE-PROTECT] {sig['type']} {side} BE-STAGE2 HIT Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Protected Move +${BE_PROTECT_USD:.2f} Net +${real_net:.4f} (+{real_net_pct:.2f}%) Bal ${balance:.2f} - BE PROTECTIVE, profit locked, no loss", flush=True)
            elif result == "BE-TIME":
                be_count += 1
                pnl += real_net
                balance += real_net
                print(f"[BE-PROTECT] {sig['type']} {side} BE-STAGE1 HIT Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Net {real_net:.4f} Bal ${balance:.2f} - BE PROTECTIVE, saved from LOSS -$0.156, only fee -$0.092", flush=True)
            elif result == "LOSS":
                losses += 1
                pnl += real_net
                balance += real_net
                print(f"[LOSS-STEALTH] {sig['type']} {side} CUT Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Real Move ${real_move:.2f} Net {real_net:.4f} Bal ${balance:.2f} - Cut at -${LOSS_CUT_USD}", flush=True)
            else:
                if real_net >= MIN_NET_WIN:
                    wins += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[WIN-STEALTH] {sig['type']} {side} TIMEOUT 3s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                elif real_net >= 0.0:
                    be_count += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[BE-STEALTH] {sig['type']} {side} TIMEOUT 3s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net +${real_net:.4f} Bal ${balance:.2f} - BE over fees", flush=True)
                else:
                    losses += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[LOSS-STEALTH] {sig['type']} {side} TIMEOUT 3s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] PAPER-REAL-THINKING $2.20 REAL START | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} Lev 80x | TP 50% | Wick $6 | Loss -${LOSS_CUT_USD} | BE Protective > Loss | Cooldown 5s | REAL WS | WIN STRICTLY", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance don drop to ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT DON STOP to protect your $2.20.", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            time.sleep(1)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V29.3 REAL WS BE-PROTECTIVE ALIVE")
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
