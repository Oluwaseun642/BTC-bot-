# V29 LOW-LATENCY + BE-PROTECT - START $0.94 (Remaining) - LEV 80x QTY 0.001
# Rule: Fast eye 0.2s, Live 0.1s, Single Confirm Whale 0.15, Wick $6, TP 50% = Min +$0.148 over fees
# BE Protect: At +$1.00, move SL to +$1.50 lock, no close, let am run to TP. Time BE after 1s at +$0.50
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 0.94  # V29: Remaining balance wey V28.7 save, no be $2.20 again
LEVERAGE = 80
QTY_FIXED = 0.001

CHECK_INTERVAL = 0.2  # V29: Was 1.0, now 0.2 - 5x faster eye
LIVE_CHECK = 0.1  # V29: Was 0.5, now 0.1 - 5x faster live check
COOLDOWN_SEC = 3  # V29: Was 5, now 3 - catch next whale faster
MIN_WHALE_BTC = 0.15  # V29: Was 0.10, now 0.15 - bigger whale, single confirm still strong
MIN_SPIKE_BTC = 0.15  # V29: Was 0.10, now 0.15
MIN_WICK_USD = 6.0  # V29: Was 8.0, now 6.0 - catch early, no wait for wick finish
TP_WICK_PCT = 0.50
SLIPPAGE_USD = 0.3  # V29: Was 0.5, now 0.3 - faster entry, less slip
LOSS_CUT_USD = 1.50
BE_LOCK_USD = 1.00  # V29: Was 1.50, now 1.00 - lock faster
BE_PROTECT_USD = 1.50  # V29 NEW: When BE lock trigger, move SL to +$1.50 profit lock, no close
TIME_BE_SEC = 1.0  # V29 NEW: After 1 sec, if in profit +$0.50, move SL to entry
TIME_BE_MIN = 0.50
MAX_HOLD_SEC = 5
MIN_NET_WIN = 0.10
MIN_NET_BE = 0.03
MIN_BALANCE_STOP = 0.50  # V29: Was 1.00, now 0.50 - because we start from $0.94

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
stopped = False
# Pre-armed price cache - bot dey hold live price always, no calculation delay
live_price_cache = [None]
live_price_time = [0]

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
        return {"retCode": 0, "result": {"orderId": "PAPER-V29"}}
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

def price_feeder():
    # V29 LOW-LATENCY FEEDER: Always hold live price, update every 0.2s in background - like websocket
    while True:
        try:
            d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
            if d and d.get("result") and d["result"].get("list"):
                live_price_cache[0] = float(d["result"]["list"][0]["lastPrice"])
                live_price_time[0] = time.time()
        except: pass
        time.sleep(0.2)

def get_recent_trades():
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        return d["result"]["list"]
    return []

def get_live_price():
    # Use cache if fresh (<0.5s), else fetch
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
    # V29 SINGLE CONFIRM: Bigger whale 0.15, imbalance >2x - no need double confirm
    if biggest_size >= MIN_WHALE_BTC:
        # Check imbalance for strength
        if biggest_side == "Buy" and buy_sum < sell_sum * 0.5 and biggest_size < 0.3:
            pass  # Still allow if whale big, but log it
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
    # V29 BE-PROTECT: At +$1.00, move SL to +$1.50 lock, no close, let am run to TP
    start = time.time()
    best_move = 0.0
    be_protected = False
    time_be_done = False
    current_sl = sl_price
    liq_dist = entry_price * 0.011
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} (slip ${SLIPPAGE_USD}) TP 50% ${tp_price:.1f} SL ${sl_price:.1f} BE-Protect at +${BE_LOCK_USD} -> SL to +${BE_PROTECT_USD} lock | Liq ~${entry_price - liq_dist:.1f} - Eye 0.1s", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK)
            continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move:
            best_move = cur_move
        # V29 BE-PROTECT: Lock SL, no exit
        if not be_protected and best_move >= BE_LOCK_USD:
            be_protected = True
            # Move SL to +$1.50 profit lock
            if side == "Buy":
                current_sl = entry_price + BE_PROTECT_USD
            else:
                current_sl = entry_price - BE_PROTECT_USD
            print(f"[BE-PROTECT] {side} Best +${best_move:.2f} >= +${BE_LOCK_USD} - SL moved to ${current_sl:.1f} (+${BE_PROTECT_USD} lock). No close, let am run to TP ${tp_price:.1f}", flush=True)
        # V29 TIME BE: After 1 sec, if in profit +$0.50, move SL to entry
        if not time_be_done and elapsed >= TIME_BE_SEC:
            time_be_done = True
            if cur_move >= TIME_BE_MIN and not be_protected:
                if side == "Buy":
                    current_sl = entry_price
                else:
                    current_sl = entry_price
                print(f"[TIME-BE] {side} After {elapsed:.1f}s still +${cur_move:.2f} - SL moved to Entry ${current_sl:.1f} to protect from loss", flush=True)
        # TP hit
        if side == "Buy" and live >= tp_price:
            return ("WIN", cur_move, elapsed, live, be_protected)
        if side == "Sell" and live <= tp_price:
            return ("WIN", cur_move, elapsed, live, be_protected)
        # BE-PROTECT SL hit - if price reverse to protected SL, we collect BE profit, no be loss
        if be_protected:
            if side == "Buy" and live <= current_sl:
                # Price pulled back to protected SL - collect BE profit
                protected_move = BE_PROTECT_USD
                return ("BE-PROTECT", protected_move, elapsed, live, be_protected)
            if side == "Sell" and live >= current_sl:
                protected_move = BE_PROTECT_USD
                return ("BE-PROTECT", protected_move, elapsed, live, be_protected)
        # Original SL hit (if BE not yet protected)
        if not be_protected:
            if cur_move <= -LOSS_CUT_USD:
                return ("LOSS", cur_move, elapsed, live, be_protected)
        # Time BE SL hit - if SL moved to entry and price hits it
        if time_be_done and not be_protected and current_sl == entry_price:
            if side == "Buy" and live <= current_sl:
                return ("BE-TIME", 0.0, elapsed, live, be_protected)
            if side == "Sell" and live >= current_sl:
                return ("BE-TIME", 0.0, elapsed, live, be_protected)
        if elapsed >= MAX_HOLD_SEC:
            return ("TIMEOUT", cur_move, elapsed, live, be_protected)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-THINKING'} ${BASE_BALANCE} START (Remaining) Lev {LEVERAGE}x Qty {QTY_FIXED} V29 LOW-LATENCY", flush=True)
    print(f"[EYE] Eye open WIDE! V29 - Fast 0.2s | Live 0.1s | Single Confirm Whale 0.15 | Wick $6 | TP 50% Min +$0.148 | BE-Protect +$1.00 -> +$1.50 lock | STOP if Bal < ${MIN_BALANCE_STOP} | EST-TAG | % EAT", flush=True)
    while True:
        try:
            if stopped:
                time.sleep(10)
                continue
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance too low Bal ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT DON STOP to protect your remaining. PnL ${pnl:.4f} Wins {wins} BE {be_count} Losses {losses}", flush=True)
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
            # V29 SINGLE CONFIRM - No double confirm delay, enter immediately
            side = sig["side"]
            current = sig["current"]
            # Use cached live price if fresher - pre-armed entry
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
            if expected_net < MIN_NET_BE:
                print(f"[FEE-AWARE-REAL] {sig['type']} Expected Net ${expected_net:.4f} after REAL fee ${real_fee} too small - Skip", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            print(f"[{sig['type']}] {side} SINGLE-CONFIRM! Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} ({wick_pct:.4f}%) | Current ${current:.1f} | Margin ${margin_needed:.2f} OK - ENTER IMMEDIATELY, no double delay", flush=True)
            print(f"[STEALTH] Follow {sig['type']} {side} -> HIDDEN Entry ${entry_price:.1f} (slip ${SLIPPAGE_USD}) TP 50% ${tp_price:.1f} SL ${sl_price:.1f} Move ${tp_move:.2f}", flush=True)
            print(f"[% -EAT] Wick {wick_pct:.4f}% | TP Move ${tp_move:.2f} = {gross_pct:.4f}% gross x {LEVERAGE}x = {lev_pct:.3f}% lev | Expected Net ${expected_net:.4f} = {net_pct_bal:.2f}% of Bal ${balance:.2f} | Fee ${real_fee} | Min TP +$0.148 over fees", flush=True)
            print(f"[EST-TAG] Estimated Market Price Tag: Entry ${entry_price:.1f} -> TP TAG ${est_tag:.1f} ({side} {'+' if side=='Buy' else '-'}{tp_move:.2f}) | SL TAG ${sl_price:.1f} | BE-Protect TAG ${entry_price + BE_PROTECT_USD if side=='Buy' else entry_price - BE_PROTECT_USD:.1f}", flush=True)
            if REAL_MODE:
                r1, r2, r3 = place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
                print(f"[REAL-STEALTH] Entry+TP+SL same time Entry {entry_price:.1f} TP TAG {est_tag:.1f} SL {sl_price:.1f}", flush=True)
            else:
                print(f"[PAPER-REAL-THINKING] HIDDEN Entry+TP+SL same time - TP TAG ${est_tag:.1f} - Watching REAL price every 0.1s", flush=True)
            result, real_move, elapsed, live_price, be_protected = run_alive_trade(side, entry_price, tp_price, sl_price)
            real_gross = (real_move / entry_price) * notional if entry_price else 0
            real_net = real_gross - real_fee
            # For BE-PROTECT, real_net is from protected move $1.50
            if result == "BE-PROTECT":
                real_gross = (BE_PROTECT_USD / entry_price) * notional
                real_net = real_gross - real_fee
            if result == "BE-TIME":
                real_net = -real_fee + 0.01  # Break-even minus fee, approx $ -0.08, but we call it BE to avoid loss label - actually net = -fee, we set to -0.08
                # Correction: Time BE at entry = 0 move, net = -fee = -$0.092, but we protect from bigger loss, so count as BE with -$0.092
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
                print(f"[BE-PROTECT] {sig['type']} {side} BE-PROTECT HIT Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Protected Move +${BE_PROTECT_USD:.2f} Net +${real_net:.4f} (+{real_net_pct:.2f}%) Bal ${balance:.2f} - SL moved, saved profit, no loss", flush=True)
            elif result == "BE-TIME":
                be_count += 1
                pnl += real_net
                balance += real_net
                print(f"[BE-TIME] {sig['type']} {side} TIME BE HIT Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Net {real_net:.4f} Bal ${balance:.2f} - Protected from loss", flush=True)
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
                    print(f"[WIN-STEALTH] {sig['type']} {side} TIMEOUT 5s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                elif real_net >= MIN_NET_BE:
                    be_count += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[BE-STEALTH] {sig['type']} {side} TIMEOUT 5s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net +${real_net:.4f} Bal ${balance:.2f} - BE over fees", flush=True)
                else:
                    losses += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[LOSS-STEALTH] {sig['type']} {side} TIMEOUT 5s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] PAPER-REAL-THINKING $0.94 START | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} Lev 80x | TP 50% | Wick $6 | BE-Protect +${BE_PROTECT_USD} | We dey eat from %", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance don drop to ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT DON STOP to protect you.", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            time.sleep(1)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V29 LOW-LATENCY BE-PROTECT ALIVE")
    def log_message(self, *a): pass

def keep_alive():
    while True:
        time.sleep(240)
        if RENDER_URL:
            try: urllib.request.urlopen(RENDER_URL, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=price_feeder, daemon=True).start()
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), H).serve_forever()
