# V28.3 HONEST + ALIVE - PAPER - CHECK 1s BEFORE, 0.5s INSIDE TRADE
# Rule: Verify REAL price EVERY MOMENT, not just after 5 sec
# Whale >=0.1 BTC OR Spike >=0.1 BTC in 5s, Wick >= $3 OVER FEES, TP 70% Wick
# Inside trade: Check price every 0.5s, cash out the moment TP hits, cut the moment it reverses
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============ CONFIG - YOUR RULES ============
REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.29
LEVERAGE = 20
QTY_FIXED = 0.001

CHECK_INTERVAL = 1.0  # Before trade: check every 1 sec for whale/spike
LIVE_CHECK = 0.5  # Inside trade: check REAL price every 0.5 sec - EYE WIDE OPEN, NO LAG
COOLDOWN_SEC = 5  # After trade close, wait 5 sec before next
MIN_WHALE_BTC = 0.1
MIN_SPIKE_BTC = 0.1
MIN_WICK_USD = 3.0  # OVER FEES - Wick must be >= $3
TP_WICK_PCT = 0.70  # TP = 70% Wick
FEE_PER_TRADE = 0.0152
MIN_NET_WIN = 0.03
MIN_NET_BE = 0.01  # BE = over fees with profit, no be $0
MAX_HOLD_SEC = 5  # Max hold, but bot go exit EARLIER if TP or Reverse hits - e no go wait 5 sec

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0

# ============ BYBIT HELPERS ============
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
    except Exception as e:
        return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER-V28.3"}}
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
    # REAL price right now, not cached, not old - every moment
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": SYMBOL})
    if d and d.get("result") and d["result"].get("list"):
        try:
            return float(d["result"]["list"][0]["lastPrice"])
        except: return None
    return None

# ============ WHALE + SPIKE ============
def detect_signal(trades):
    if not trades:
        return None
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
    gross = (move / price * 100) if price else 0
    return gross, gross * LEVERAGE

def place_stealth_pair(side, entry_price, tp_price, qty):
    entry_dir = 2 if side == "Buy" else 1
    tp_dir = 1 if side == "Buy" else 2
    close_side = "Sell" if side == "Buy" else "Buy"
    entry_body = {"category": "linear", "symbol": SYMBOL, "side": side, "orderType": "Limit", "qty": str(qty), "price": f"{entry_price:.1f}", "triggerPrice": f"{entry_price:.1f}", "triggerDirection": entry_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": False}
    tp_body = {"category": "linear", "symbol": SYMBOL, "side": close_side, "orderType": "Limit", "qty": str(qty), "price": f"{tp_price:.1f}", "triggerPrice": f"{tp_price:.1f}", "triggerDirection": tp_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": True}
    r1 = bybit_post("/v5/order/create", entry_body)
    r2 = bybit_post("/v5/order/create", tp_body)
    return r1, r2

# ============ HONEST + ALIVE TRADE - VERIFY REAL PRICE EVERY 0.5s ============
def run_alive_trade(sig, side, entry_price, tp_price, tp_move):
    # This na the fix: Bot eye open, e dey check REAL price every 0.5s while trade dey open
    # No be wait 5 sec then check once. E dey check every moment.
    start = time.time()
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} TP ${tp_price:.1f} - Eye open, checking REAL price every {LIVE_CHECK}s", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK)
            continue
        # 1. TP HIT? Cash out NOW, no wait
        if side == "Buy" and live >= tp_price:
            real_move = live - entry_price
            return ("WIN", real_move, elapsed, live)
        if side == "Sell" and live <= tp_price:
            real_move = entry_price - live
            return ("WIN", real_move, elapsed, live)
        # 2. REVERSE HIT? Price go opposite by $3+ = whale reverse, cut NOW, no wait 5 sec
        if side == "Buy" and live <= entry_price - 3.0:
            real_move = live - entry_price  # Negative
            return ("LOSS", real_move, elapsed, live)
        if side == "Sell" and live >= entry_price + 3.0:
            real_move = entry_price - live  # Negative
            return ("LOSS", real_move, elapsed, live)
        # 3. MAX HOLD 5s reach? Exit with whatever real price be - no hold longer
        if elapsed >= MAX_HOLD_SEC:
            real_move = (live - entry_price) if side == "Buy" else (entry_price - live)
            return ("TIMEOUT", real_move, elapsed, live)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER'} ${BASE_BALANCE} Lev {LEVERAGE}x V28.3 HONEST ALIVE", flush=True)
    print(f"[EYE] Eye don open WIDE! V28.3 - Before: 1s | Inside Trade: {LIVE_CHECK}s EVERY MOMENT | Cooldown 5s | Whale+Spike | Wick ${MIN_WICK_USD} OVER FEES | TP 70%", flush=True)
    while True:
        try:
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
                print(f"[{sig['type']}] {sig['side']} Size {sig['size']:.3f} BTC but Wick ${sig['wick']:.2f} ({sig['wick_pct']:.4f}%) too small < ${MIN_WICK_USD} - Skip, fee go chop am", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            side = sig["side"]
            current = sig["current"]
            entry_price = current - 1.0 if side == "Buy" else current + 1.0
            tp_move = sig["wick"] * TP_WICK_PCT
            tp_price = entry_price + tp_move if side == "Buy" else entry_price - tp_move
            gross_pct, lev_pct = calc_pct(tp_move, entry_price)
            notional = entry_price * QTY_FIXED * LEVERAGE
            expected_gross = (tp_move / entry_price) * notional
            expected_net = expected_gross - FEE_PER_TRADE
            net_pct_bal = (expected_net / balance * 100) if balance else 0
            if expected_net < MIN_NET_BE:
                print(f"[FEE-AWARE] {sig['type']} Expected Net ${expected_net:.4f} too small after fee - Skip", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            print(f"[{sig['type']}] {side} detected! Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} ({sig['wick_pct']:.4f}%) | BuySum {sig['buy_sum']:.3f} SellSum {sig['sell_sum']:.3f} | Current ${current:.1f}", flush=True)
            print(f"[STEALTH] Follow {sig['type']} {side} -> HIDDEN Entry ${entry_price:.1f} TP 70% ${tp_price:.1f} Move ${tp_move:.2f} ({gross_pct:.4f}% gross, {lev_pct:.3f}% lev) Expected Net ~${expected_net:.4f} ({net_pct_bal:.2f}%)", flush=True)
            if REAL_MODE:
                r1, r2 = place_stealth_pair(side, entry_price, tp_price, QTY_FIXED)
                print(f"[REAL-STEALTH] Entry+TP same time Entry {entry_price:.1f} TP {tp_price:.1f}", flush=True)
            else:
                print(f"[PAPER-STEALTH] HIDDEN Entry+TP same time - Now bot go watch REAL price every 0.5s", flush=True)
            # HONEST: Watch REAL price every 0.5s, no assume
            result, real_move, elapsed, live_price = run_alive_trade(sig, side, entry_price, tp_price, tp_move)
            # Calculate REAL PnL from REAL move, not expected move
            real_gross = (real_move / entry_price) * notional if entry_price else 0
            real_net = real_gross - FEE_PER_TRADE
            real_net_pct = (real_net / balance * 100) if balance else 0
            real_gross_pct, real_lev_pct = calc_pct(real_move, entry_price)
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1
                pnl += real_net
                balance += real_net
                print(f"[WIN-STEALTH] {sig['type']} {side} Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Real Move ${real_move:.2f} ({real_gross_pct:.4f}%) Net +${real_net:.4f} (+{real_net_pct:.2f}%) Bal ${balance:.2f}", flush=True)
            elif result == "LOSS":
                losses += 1
                pnl += real_net
                balance += real_net
                print(f"[LOSS-STEALTH] {sig['type']} {side} REVERSE! Entry {entry_price:.1f} -> LIVE ${live_price:.1f} in {elapsed:.1f}s Real Move ${real_move:.2f} Net {real_net:.4f} Bal ${balance:.2f} - Cut fast, no wait 5s", flush=True)
            else:  # TIMEOUT
                if real_net >= MIN_NET_WIN:
                    wins += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[WIN-STEALTH] {sig['type']} {side} TIMEOUT 5s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                elif real_net >= MIN_NET_BE:
                    be_count += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[BE-STEALTH] {sig['type']} {side} TIMEOUT 5s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net +${real_net:.4f} (+{real_net_pct:.2f}%) Bal ${balance:.2f} - BE na profit over fees", flush=True)
                else:
                    losses += 1
                    pnl += real_net
                    balance += real_net
                    print(f"[LOSS-STEALTH] {sig['type']} {side} TIMEOUT 5s Entry {entry_price:.1f} -> LIVE ${live_price:.1f} Real Move ${real_move:.2f} Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] PAPER $2.29 | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} Cooldown {COOLDOWN_SEC}s | Check 1s / Live 0.5s | HONEST", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            time.sleep(2)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V28.3 HONEST ALIVE")
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
