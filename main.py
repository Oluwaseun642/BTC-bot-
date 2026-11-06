# V28.7 - BALANCE RESET + BANKRUPTCY PROTECTION + SMALLER LOSS - LEV 80x QTY 0.001
# Rule: Bot go STOP if Bal < $1.00, never go negative again. Loss Cut -$1.50, BE Lock +$1.50
# TP 50% Wick, Min Wick $8, % Eating, EST-TAG, Double Confirm, Real SL Trio, Live 0.5s
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.20  # FRESH RESET - V28.7 start from $2.20 again, -$1.17 run don die
LEVERAGE = 80
QTY_FIXED = 0.001

CHECK_INTERVAL = 1.0
LIVE_CHECK = 0.5
COOLDOWN_SEC = 5
MIN_WHALE_BTC = 0.1
MIN_SPIKE_BTC = 0.1
MIN_WICK_USD = 8.0
TP_WICK_PCT = 0.50
SLIPPAGE_USD = 0.5
LOSS_CUT_USD = 1.50  # V28.7: Was $2.00, now $1.50 - smaller loss
BE_LOCK_USD = 1.50  # V28.7: Was $2.00, now $1.50 - faster BE lock
TRAIL_PULLBACK = 0.75  # V28.7: Was 1.0, now 0.75 - lock BE quicker
MAX_HOLD_SEC = 5
MIN_NET_WIN = 0.10
MIN_NET_BE = 0.03
MIN_BALANCE_STOP = 1.00  # V28.7 BANKRUPTCY PROTECTION: If Bal < $1.00, bot STOP, never go negative

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
last_signal_side = None
stopped = False

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
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except: return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER-V28.7"}}
    try:
        ts = str(int(time.time()*1000))
        payload = json.dumps(body)
        sig = hmac.new(API_SECRET.encode(), (ts + API_KEY + "5000" + payload).encode(), hashlib.sha256).hexdigest()
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "X-BAPI-SIGN": sig, "Content-Type": "application/json"}
        req = urllib.request.Request(f"https://api.bybit.com{path}", data=payload.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERR] POST {e}", flush=True)
        return None

def get_recent_trades():
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        return d["result"]["list"]
    return []

def get_live_price():
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
    if d and d.get("result") and d["result"].get("list"):
        try: return float(d["result"]["list"][0]["lastPrice"])
        except: return None
    return None

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
    if buy_sum >= MIN_SPIKE_BTC and buy_sum > sell_sum * 1.5:
        return {"type": "SMALL-SPIKE", "side": "Buy", "size": buy_sum, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    if sell_sum >= MIN_SPIKE_BTC and sell_sum > buy_sum * 1.5:
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
    start = time.time()
    best_move = 0.0
    liq_dist = entry_price * 0.011
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} (slip ${SLIPPAGE_USD}) TP 50% ${tp_price:.1f} Real SL ${sl_price:.1f} Liq ~${entry_price - liq_dist:.1f} - Eye open 0.5s", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK)
            continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move:
            best_move = cur_move
        if side == "Buy" and live >= tp_price:
            return ("WIN", cur_move, elapsed, live)
        if side == "Sell" and live <= tp_price:
            return ("WIN", cur_move, elapsed, live)
        if best_move >= BE_LOCK_USD and cur_move <= best_move - TRAIL_PULLBACK and cur_move > 0:
            return ("BE-TRAIL", cur_move, elapsed, live)
        if cur_move <= -LOSS_CUT_USD and best_move < BE_LOCK_USD:
            return ("LOSS", cur_move, elapsed, live)
        if elapsed >= MAX_HOLD_SEC:
            return ("TIMEOUT", cur_move, elapsed, live)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, last_signal_side, stopped
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-THINKING'} ${BASE_BALANCE} FRESH RESET Lev {LEVERAGE}x Qty {QTY_FIXED} V28.7", flush=True)
    print(f"[EYE] Eye open WIDE! V28.7 - We dey eat from % | TP 50% Wick | Min Wick ${MIN_WICK_USD} | Loss Cut -${LOSS_CUT_USD} | BE Lock +${BE_LOCK_USD} | STOP if Bal < ${MIN_BALANCE_STOP} | Real SL | Live 0.5s | EST-TAG", flush=True)
    while True:
        try:
            # V28.7 BANKRUPTCY PROTECTION - Check every loop
            if stopped:
                time.sleep(10)
                continue
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance too low Bal ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT DON STOP to protect your $2.20. E no go trade again. Redeploy to reset. PnL ${pnl:.4f} Wins {wins} BE {be_count} Losses {losses}", flush=True)
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
            if last_signal_side != sig["side"]:
                print(f"[CONFIRM] First {sig['side']} signal, waiting 2nd same side - Skip", flush=True)
                last_signal_side = sig["side"]
                time.sleep(CHECK_INTERVAL)
                continue
            last_signal_side = None
            side = sig["side"]
            current = sig["current"]
            margin_needed = (current * QTY_FIXED) / LEVERAGE
            if margin_needed > balance:
                print(f"[MARGIN] Margin needed ${margin_needed:.2f} > Bal ${balance:.2f} - REJECT like Bybit, no enter", flush=True)
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
            print(f"[{sig['type']}] {side} CONFIRMED x2! Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} ({wick_pct:.4f}%) | Current ${current:.1f} | Margin ${margin_needed:.2f} OK", flush=True)
            print(f"[STEALTH] Follow {sig['type']} {side} -> HIDDEN Entry ${entry_price:.1f} (slip ${SLIPPAGE_USD}) TP 50% ${tp_price:.1f} Real SL ${sl_price:.1f} Move ${tp_move:.2f}", flush=True)
            print(f"[% -EAT] Wick {wick_pct:.4f}% | TP Move ${tp_move:.2f} = {gross_pct:.4f}% gross x {LEVERAGE}x = {lev_pct:.3f}% lev | Expected Net ${expected_net:.4f} = {net_pct_bal:.2f}% of Bal ${balance:.2f} | Fee ${real_fee}", flush=True)
            print(f"[EST-TAG] Estimated Market Price Tag: Entry ${entry_price:.1f} -> TP TAG ${est_tag:.1f} ({side} {'+' if side=='Buy' else '-'}{tp_move:.2f}) | SL TAG ${sl_price:.1f} | Bot go place HIDDEN TP for ${est_tag:.1f}", flush=True)
            if REAL_MODE:
                r1, r2, r3 = place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
                print(f"[REAL-STEALTH] Entry+TP+SL same time Entry {entry_price:.1f} TP TAG {est_tag:.1f} SL {sl_price:.1f}", flush=True)
            else:
                print(f"[PAPER-REAL-THINKING] HIDDEN Entry+TP+SL same time - TP TAG ${est_tag:.1f} - Watching REAL price every 0.5s", flush=True)
            result, real_move, elapsed, live_price = run_alive_trade(side, entry_price, tp_price, sl_price)
            real_gross = (real_move / entry_price) * notional if entry_price else 0
            real_net = real_gross - real_fee
            real_net_pct = (real_net / balance * 100) if balance else 0
            real_gross_pct, real_lev_pct = calc_pct(real_move, entry_price)
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1
                pnl += real_net
                balance += real_net
                print(f"[WIN-STEALTH] {sig['type']} {side} Entry {entry_price:.1f} -> LIVE ${live_price:.1f} (EST-TAG ${est_tag:.1f} HIT) in {elapsed:.1f}s Real Move ${real_move:.2f} ({real_gross_pct:.4f}% gross, {real_lev_pct:.3f}% lev) Net +${real_net:.4f} (+{real_net_pct:.2f}% of Bal) Bal ${balance:.2f}", flush=True)
            elif result == "BE-TRAIL":
                be_count += 1
                pnl += real_net
                balance += real_net
                print(f"[BE-STEALTH] {sig['type']} {side} TRAILING BE LOCKED Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Real Move ${real_move:.2f} ({real_lev_pct:.3f}% lev) Net +${real_net:.4f} (+{real_net_pct:.2f}%) Bal ${balance:.2f} - Locked profit over fees", flush=True)
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
            print(f"[SUMMARY] PAPER-REAL-THINKING $2.20 | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} Lev 80x | TP 50% | Wick $8 | Loss -${LOSS_CUT_USD} | BE +${BE_LOCK_USD} | We dey eat from %", flush=True)
            # Check bankruptcy right after trade
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance don drop to ${balance:.2f} < ${MIN_BALANCE_STOP} - BOT DON STOP to protect you. No more trades.", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            time.sleep(2)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V28.7 BANKRUPTCY PROTECTION ALIVE")
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
    HTTPServer(("0.0.0.0", port), H).serve_forever()
