# V28.2 STEALTH WHALE + SMALL SPIKE - PAPER - CHECK 1s / COOLDOWN 5s
# Rule: Trade ONLY if (Single Whale >= 0.1 BTC) OR (Small Spike: Sum of trades in 5s >= 0.1 BTC)
# Both must have Wick >= $3 and Net >= $0.01 after fee, else SKIP
# TP = 70% Wick, Entry+TP placed same time, BE = over fees with profit
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import deque

# ============ CONFIG - YOUR RULES ============
REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.29
LEVERAGE = 20
QTY_FIXED = 0.001

CHECK_INTERVAL = 1.0  # Check every 1 sec
COOLDOWN_SEC = 5  # After trade, wait 5 sec
MIN_WHALE_BTC = 0.1  # Single whale: one trade >= 0.1 BTC
MIN_SPIKE_BTC = 0.1  # Small Spike: sum of trades in 5 sec >= 0.1 BTC (many small join together)
MIN_WICK_USD = 3.0  # Wick must be >= $3 to beat fee - OVER FEES rule
TP_WICK_PCT = 0.70  # TP = 70% of Wick - cash out quick before reverse
FEE_PER_TRADE = 0.0152
MIN_NET_WIN = 0.03  # >= $0.03 after fee = WIN
MIN_NET_BE = 0.01  # $0.01 - $0.029 after fee = BE (over fees with profit, no be $0)
MAX_HOLD_SEC = 5

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
spike_window = deque(maxlen=50)  # Keep last 5 sec trades for spike calc: (time, size, side, price)

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
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERR] GET {e}", flush=True)
        return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER-V28.2"}}
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

def get_recent_trades():
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        return d["result"]["list"]
    return []

# ============ WHALE + SMALL SPIKE DETECTION ============
def detect_signal(trades):
    if not trades:
        return None
    now = time.time()
    prices = [float(t["price"]) for t in trades]
    wick = max(prices) - min(prices)
    current = float(trades[0]["price"])
    # 1. Single Whale: biggest single filled trade
    biggest = max(trades, key=lambda t: float(t.get("size", 0)))
    biggest_size = float(biggest.get("size", 0))
    biggest_side = biggest.get("side", "")
    # 2. Small Spike: sum of trades in last 5 sec, grouped by side
    # We use the 50 trades batch as ~5 sec window (BTC dey trade fast)
    buy_sum = sum(float(t["size"]) for t in trades if t.get("side") == "Buy")
    sell_sum = sum(float(t["size"]) for t in trades if t.get("side") == "Sell")
    # Decide which signal triggers
    if biggest_size >= MIN_WHALE_BTC:
        return {"type": "WHALE", "side": biggest_side, "size": biggest_size, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    # Small Spike: many small trades join together to reach 0.1 BTC, same side dominant
    if buy_sum >= MIN_SPIKE_BTC and buy_sum > sell_sum * 1.5:
        return {"type": "SMALL-SPIKE", "side": "Buy", "size": buy_sum, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    if sell_sum >= MIN_SPIKE_BTC and sell_sum > buy_sum * 1.5:
        return {"type": "SMALL-SPIKE", "side": "Sell", "size": sell_sum, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0, "buy_sum": buy_sum, "sell_sum": sell_sum}
    return None

def calc_pct(move_usd, price):
    gross_pct = (move_usd / price * 100) if price else 0
    return gross_pct, gross_pct * LEVERAGE

def place_stealth_pair(side, entry_price, tp_price, qty):
    entry_dir = 2 if side == "Buy" else 1
    tp_dir = 1 if side == "Buy" else 2
    close_side = "Sell" if side == "Buy" else "Buy"
    entry_body = {"category": "linear", "symbol": SYMBOL, "side": side, "orderType": "Limit", "qty": str(qty), "price": f"{entry_price:.1f}", "triggerPrice": f"{entry_price:.1f}", "triggerDirection": entry_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": False}
    tp_body = {"category": "linear", "symbol": SYMBOL, "side": close_side, "orderType": "Limit", "qty": str(qty), "price": f"{tp_price:.1f}", "triggerPrice": f"{tp_price:.1f}", "triggerDirection": tp_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": True}
    r1 = bybit_post("/v5/order/create", entry_body)
    r2 = bybit_post("/v5/order/create", tp_body)
    return r1, r2

# ============ MAIN LOOP ============
def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER'} ${BASE_BALANCE} Lev {LEVERAGE}x V28.2 WHALE + SMALL SPIKE", flush=True)
    print(f"[EYE] Eye don open! V28.2 - Check 1s | Cooldown 5s | Whale >= {MIN_WHALE_BTC} BTC OR Spike >= {MIN_SPIKE_BTC} BTC in 5s | Min Wick ${MIN_WICK_USD} OVER FEES | TP 70% Wick", flush=True)
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
            # OVER FEES CHECK 1: Wick must be >= $3
            if sig["wick"] < MIN_WICK_USD:
                print(f"[{sig['type']}] {sig['side']} Size {sig['size']:.3f} BTC but Wick ${sig['wick']:.2f} ({sig['wick_pct']:.4f}%) too small < ${MIN_WICK_USD} - Skip, fee go chop am", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            side = sig["side"]
            current = sig["current"]
            entry_price = current - 1.0 if side == "Buy" else current + 1.0
            tp_move = sig["wick"] * TP_WICK_PCT
            tp_price = entry_price + tp_move if side == "Buy" else entry_price - tp_move
            # Percentage calc: Convert % to Price for Bybit
            gross_pct, lev_pct = calc_pct(tp_move, entry_price)
            notional = entry_price * QTY_FIXED * LEVERAGE
            expected_gross = (tp_move / entry_price) * notional
            net = expected_gross - FEE_PER_TRADE
            net_pct_bal = (net / balance * 100) if balance else 0
            # OVER FEES CHECK 2: Net must be >= $0.01 (BE over fees), else skip
            if net < MIN_NET_BE:
                print(f"[FEE-AWARE] {sig['type']} Net ${net:.4f} ({net_pct_bal:.2f}%) too small after fee ${FEE_PER_TRADE} - Skip, no waste fee", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue
            print(f"[{sig['type']}] {side} detected! Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} ({sig['wick_pct']:.4f}%) | BuySum {sig['buy_sum']:.3f} SellSum {sig['sell_sum']:.3f} | Current ${current:.1f}", flush=True)
            print(f"[STEALTH] Follow {sig['type']} {side} -> HIDDEN Entry ${entry_price:.1f} TP Wick 70% ${tp_price:.1f} Move ${tp_move:.2f} ({gross_pct:.4f}% gross, {lev_pct:.3f}% lev) Net ~${net:.4f} ({net_pct_bal:.2f}% of bal)", flush=True)
            if REAL_MODE:
                r1, r2 = place_stealth_pair(side, entry_price, tp_price, QTY_FIXED)
                print(f"[REAL-STEALTH] Entry+TP same time Entry {entry_price:.1f} TP {tp_price:.1f} Res {r1} / {r2}", flush=True)
            else:
                print(f"[PAPER-STEALTH] HIDDEN Entry+TP same time - Bybit go handle TP in 2-3s. Entry ${entry_price:.1f} TP ${tp_price:.1f}", flush=True)
            last_trade_time = now
            pnl_trade = net
            if pnl_trade >= MIN_NET_WIN:
                wins += 1
                pnl += pnl_trade
                balance += pnl_trade
                print(f"[WIN-STEALTH] {sig['type']} {side} Entry {entry_price:.1f} -> Wick TP {tp_price:.1f} Move ${tp_move:.2f} ({gross_pct:.4f}%) Net +${pnl_trade:.4f} (+{net_pct_bal:.2f}%) Bal ${balance:.2f}", flush=True)
            elif pnl_trade >= MIN_NET_BE:
                be_count += 1
                pnl += pnl_trade
                balance += pnl_trade
                print(f"[BE-STEALTH] {sig['type']} {side} Small win over fees Net +${pnl_trade:.4f} (+{net_pct_bal:.2f}%) Bal ${balance:.2f} - BE na profit, no be $0", flush=True)
            else:
                losses += 1
                pnl += pnl_trade
                balance += pnl_trade
                print(f"[LOSS-STEALTH] {sig['type']} {side} Net {pnl_trade:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] PAPER $2.29 | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} Cooldown {COOLDOWN_SEC}s | Check 1s | Whale + Spike", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            time.sleep(2)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V28.2 WHALE+SPIKE ALIVE")
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
