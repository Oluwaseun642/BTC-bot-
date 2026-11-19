# ============================================================
# MAIN.PY V15.1.0 - TRADING BRAIN
# CROSS | ATR SL | $500 BE TRIGGER | JSON via DATA ENGINE
# + FAKE PORT for Render Free Web Service (No open ports fix)
# ============================================================
import os, time, threading, hmac, hashlib, json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# ------------------------------------------------------------
# 0. FAKE PORT - FOR RENDER FREE WEB SERVICE
# Render Web Service dey expect port. Bot no be website, so we open
# small fake port make Render see "open port" and no kill am.
# This must be FIRST, before anything else.
# ------------------------------------------------------------
def _keep_port():
    try:
        port = int(os.environ.get("PORT", 10000))
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b"BTC-BOT V15 RUNNING")
            def log_message(self, *a): pass
        HTTPServer(("0.0.0.0", port), H).serve_forever()
    except Exception as e:
        print(f"Port keep-alive error: {e}", flush=True)
threading.Thread(target=_keep_port, daemon=True).start()

# ------------------------------------------------------------
# 1. IMPORT DATA ENGINE
# ------------------------------------------------------------
try:
    import data_engine as DE
    print("✅ Data Engine Connected", flush=True)
    HAS_DE = True
except Exception as e:
    DE = None
    HAS_DE = False
    print(f"❌ Data Engine NOT Found: {e}", flush=True)

# ------------------------------------------------------------
# 2. CONFIG - FROM RENDER ENV VARS
# ------------------------------------------------------------
BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SYMBOL = "BTCUSDT"
CATEGORY = "linear"
BASE_URL = "https://api.bybit.com"

# Risk / Strategy - V15 Rules
BE_TRIGGER = 500.0      # $500 move -> move SL to BE + lock small profit
BE_LOCK = 20.0          # Lock $20 when BE hits
RISK_PCT = 0.02         # 2% risk per trade
MAX_DAILY_LOSS = 50.0   # Stop for day if -$50
CERT_MIN = 75.0         # Minimum cert to enter
CERT_HUNT = 85.0        # Hunt needs higher cert

balance = 0.0
in_position = False
side = None
entry = 0.0
qty = 0.0
sl_price = 0.0
be_done = False
be_trigger = 0.0
daily_pnl = 0.0
daily_trades = 0
votes = {"cert": 0, "direction": "NONE", "agree": 0}

# ------------------------------------------------------------
# 3. HELPERS - LOG + TELEGRAM + BYBIT SIGN
# ------------------------------------------------------------
def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

def tg(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except: pass

def _sign(params):
    qs = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(BYBIT_API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def bybit_get(path, params):
    try:
        ts = str(int(time.time() * 1000))
        params["api_key"] = BYBIT_API_KEY
        params["timestamp"] = ts
        params["recv_window"] = "5000"
        params["sign"] = _sign(params)
        r = requests.get(BASE_URL + path, params=params, timeout=10)
        return r.json()
    except Exception as e:
        log(f"Bybit GET error {e}")
        return {}

def bybit_post(path, params):
    try:
        ts = str(int(time.time() * 1000))
        params["api_key"] = BYBIT_API_KEY
        params["timestamp"] = ts
        params["recv_window"] = "5000"
        params["sign"] = _sign(params)
        r = requests.post(BASE_URL + path, data=params, timeout=10)
        return r.json()
    except Exception as e:
        log(f"Bybit POST error {e}")
        return {}

# ------------------------------------------------------------
# 4. BYBIT - BALANCE / POSITION / ORDER
# ------------------------------------------------------------
def get_balance():
    global balance
    try:
        j = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        lst = j.get("result", {}).get("list", [])
        if lst:
            for coin in lst[0].get("coin", []):
                if coin.get("coin") == "USDT":
                    balance = float(coin.get("walletBalance", 0))
                    return balance
    except: pass
    return balance

def get_position():
    try:
        j = bybit_get("/v5/position/list", {"category": CATEGORY, "symbol": SYMBOL})
        lst = j.get("result", {}).get("list", [])
        if lst and float(lst[0].get("size", 0)) > 0:
            return lst[0]
    except: pass
    return None

def set_leverage():
    try:
        bybit_post("/v5/position/set-leverage", {"category": CATEGORY, "symbol": SYMBOL, "buyLeverage": "10", "sellLeverage": "10"})
        log("Leverage set 10x")
    except: pass

def set_margin_cross():
    try:
        # 0 = CROSS, 1 = ISOLATED for Bybit v5
        r = bybit_post("/v5/position/switch-isolated", {"category": CATEGORY, "symbol": SYMBOL, "tradeMode": 0, "buyLeverage": "10", "sellLeverage": "10"})
        log(f"Margin set to CROSS | {r.get('retMsg', '')}")
    except Exception as e:
        log(f"Margin CROSS error {e}")

def place_order(order_side, qty_, sl=None, tp=None):
    try:
        p = {"category": CATEGORY, "symbol": SYMBOL, "side": order_side, "orderType": "Market", "qty": str(qty_)}
        if sl: p["stopLoss"] = str(round(sl, 1))
        if tp: p["takeProfit"] = str(round(tp, 1))
        r = bybit_post("/v5/order/create", p)
        log(f"Order {order_side} {qty_} -> {r.get('retMsg', '')}")
        return r
    except Exception as e:
        log(f"Order error {e}")
        return {}

def close_position():
    try:
        pos = get_position()
        if not pos:
            return True
        sz = float(pos.get("size", 0))
        s = pos.get("side", "")
        close_side = "Sell" if s == "Buy" else "Buy"
        r = bybit_post("/v5/order/create", {"category": CATEGORY, "symbol": SYMBOL, "side": close_side, "orderType": "Market", "qty": str(sz), "reduceOnly": True})
        log(f"Close {close_side} {sz} -> {r.get('retMsg', '')}")
        return True
    except Exception as e:
        log(f"Close error {e}")
        return False

def set_sl_to_be():
    global be_done
    try:
        pos = get_position()
        if not pos:
            return
        # Move SL to entry + $20 lock (for LONG) or entry - $20 (for SHORT)
        if side == "LONG":
            new_sl = entry + BE_LOCK
        else:
            new_sl = entry - BE_LOCK
        # Bybit: set trading stop
        bybit_post("/v5/position/trading-stop", {"category": CATEGORY, "symbol": SYMBOL, "stopLoss": str(round(new_sl, 1))})
        be_done = True
        log(f"🔒 BE DONE | SL moved to {new_sl:.1f} (Lock +${BE_LOCK})")
        tg(f"🔒 <b>BE TRIGGERED</b>\nSL moved to {new_sl:.1f}\nLocked +${BE_LOCK}")
    except Exception as e:
        log(f"BE SL error {e}")

# ------------------------------------------------------------
# 5. DATA ENGINE BRIDGE - get_votes
# ------------------------------------------------------------
def get_votes(price, atr, candles):
    global votes
    if not HAS_DE or DE is None:
        log("DATA ENGINE MISSING - NO TRADE")
        return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False}
    try:
        # DE V15 has get_signal. V14 no get am, so check all names
        fn = None
        for name in ["get_signal", "get_votes", "analyze", "check_market", "get_decision"]:
            if hasattr(DE, name):
                fn = getattr(DE, name)
                break
        if fn is None:
            log(f"Data Engine functions: {[x for x in dir(DE) if not x.startswith('_')]} - NO KNOWN FUNCTION")
            return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False}
        res = fn(price, atr, candles)
        if isinstance(res, dict):
            votes = res
            return res
    except Exception as e:
        log(f"get_votes error {e}")
    return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False}

def get_price_and_candles():
    # Use DE for price + klines if available, else direct Bybit
    if HAS_DE:
        try:
            price, _ = DE.get_price_live()
            k1 = DE.get_klines("1", 20)
            # Normalize to main.py format
            candles = [{"open": k["open"], "high": k["high"], "low": k["low"], "close": k["close"]} for k in k1]
            return price, candles, k1
        except: pass
    # Fallback direct
    try:
        r = requests.get(f"{BASE_URL}/v5/market/tickers?category=linear&symbol={SYMBOL}", timeout=5).json()
        price = float(r["result"]["list"][0]["lastPrice"])
        return price, [], []
    except:
        return 0.0, [], []

def calc_atr(candles):
    if not candles or len(candles) < 15:
        return 200.0
    trs = []
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i-1]
        trs.append(max(c["high"]-c["low"], abs(c["high"]-p["close"]), abs(c["low"]-p["close"])))
    return sum(trs[-14:]) / len(trs[-14:]) if trs else 200.0

# ------------------------------------------------------------
# 6. SAVE TRADE - VIA DATA ENGINE JSON KEEPER
# main.py NO touch json again. DE.save_trade() dey handle trades.json + daily.json
# ------------------------------------------------------------
def save_trade_to_de(trade_dict):
    try:
        if HAS_DE and hasattr(DE, "save_trade"):
            DE.save_trade(trade_dict)
            log(f"💾 Saved to trades.json via DE | PNL ${trade_dict.get('net_pnl', 0):.2f}")
        else:
            log("DE.save_trade not found - trade NOT saved to JSON")
    except Exception as e:
        log(f"Save trade error {e}")

# ------------------------------------------------------------
# 7. MAIN LOOP
# ------------------------------------------------------------
def main():
    global in_position, side, entry, qty, sl_price, be_done, be_trigger, daily_pnl, daily_trades, balance

    log("V15 STARTED | CROSS | ATR SL | $500 BE")
    tg("🤖 <b>BTC Bot V15 STARTED</b>\nCROSS | ATR SL | $500 BE Trigger\nData Engine: " + ("✅ Connected" if HAS_DE else "❌ Missing"))
    set_leverage()
    set_margin_cross()
    get_balance()
    log(f"Balance ${balance:.2f}")

    last_vote_time = 0

    while True:
        try:
            time.sleep(2)

            price, candles, k1_raw = get_price_and_candles()
            if price == 0:
                log("Price 0 - retry")
                continue

            atr = calc_atr(candles) if candles else 200.0

            # --- IF IN POSITION: CHECK BE + SL ---
            if in_position:
                profit_move = (price - entry) if side == "LONG" else (entry - price)
                # BE Trigger: $500 move and not yet done
                if not be_done and profit_move >= BE_TRIGGER:
                    log(f"🎯 BE TRIGGER | Move ${profit_move:.1f} >= ${BE_TRIGGER}")
                    set_sl_to_be()
                    # Save BE hit to JSON via DE (partial - we save full on close, but log BE)
                    be_trigger = profit_move

                # Check SL hit (approx - Bybit go close am, we detect no position)
                pos = get_position()
                if pos is None:
                    # Position closed by SL/TP on exchange - calculate
                    # We estimate exit = sl_price if be_done else sl_price, else price
                    exit_price = price
                    net = 0
                    result = "SL"
                    if be_done:
                        # BE - small win
                        net = BE_LOCK * qty - (qty * price * 0.0006)  # minus fees approx
                        result = "BE_TP"
                    else:
                        # SL loss
                        loss_move = abs(exit_price - entry)
                        net = -(loss_move * qty) - (qty * price * 0.0006)
                        result = "SL"
                    daily_pnl += net
                    daily_trades += 1
                    log(f"🔴 CLOSED {result} | Exit {exit_price:.1f} | Net ${net:.2f} | Daily ${daily_pnl:.2f}")
                    tg(f"🔴 <b>CLOSED {result}</b>\nExit {exit_price:.1f}\nNet ${net:.2f}\nDaily PNL ${daily_pnl:.2f}\nBalance ${balance:.2f}")
                    save_trade_to_de({
                        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        "side": side,
                        "entry": entry,
                        "exit": exit_price,
                        "move": round(profit_move if 'profit_move' in locals() else 0, 1),
                        "qty": qty,
                        "net_pnl": round(net, 2),
                        "result": result,
                        "balance_after": round(balance, 2),
                        "cert": votes.get("cert", 0),
                        "atr": round(atr, 1),
                        "be_trigger": round(be_trigger, 1),
                    })
                    in_position = False
                    side = None
                    entry = 0.0
                    qty = 0.0
                    be_done = False
                    be_trigger = 0.0
                    get_balance()
                    continue
                continue

            # --- NOT IN POSITION: CHECK FOR ENTRY ---
            # Only vote every 5s to avoid hammering
            if time.time() - last_vote_time < 5:
                continue
            last_vote_time = time.time()

            v = get_votes(price, atr, candles)
            cert = v.get("cert", 0)
            direction = v.get("direction", "NONE")
            agree = v.get("agree", 0)
            hunt_soon = v.get("hunt_soon", False)
            news_critical = v.get("news_critical", False)
            news_wait = v.get("news_wait", 0)
            pause_long = v.get("pause_long", False)
            pause_short = v.get("pause_short", False)

            log(f"Price ${price:.0f} | ATR {atr:.0f} | {direction} Cert {cert}% Agree {agree}/8 | HuntSoon {hunt_soon} | NewsCrit {news_critical} | Bal ${balance:.2f}")

            # Daily loss stop
            if daily_pnl <= -MAX_DAILY_LOSS:
                log(f"🛑 DAILY LOSS LIMIT ${daily_pnl:.2f} - NO MORE TRADES TODAY")
                time.sleep(60)
                continue

            # News critical = only trade if cert very high
            if news_critical and cert < 90:
                log(f"📰 NEWS CRITICAL - Skip, Cert {cert}% < 90%")
                continue
            if news_wait > 0:
                log(f"📰 NEWS WAIT {news_wait}s - Skip")
                continue

            # Pause checks
            if direction == "LONG" and pause_long:
                log("⏸️ PAUSE LONG - Macro says pause")
                continue
            if direction == "SHORT" and pause_short:
                log("⏸️ PAUSE SHORT - Macro says pause")
                continue

            # Hunt soon - wait for hunt, no enter normal
            if hunt_soon:
                log(f"👀 HUNT SOON - Waiting for sweep, Cert {cert}%")
                # Only enter hunt if cert high
                if cert < CERT_HUNT:
                    continue

            # Entry rule
            if direction in ("LONG", "SHORT") and cert >= CERT_MIN:
                # Calc qty: risk 2% / ATR distance
                get_balance()
                risk_usd = balance * RISK_PCT
                if risk_usd < 1:
                    risk_usd = 1
                sl_dist = atr * 1.5  # ATR SL
                if sl_dist <= 0:
                    sl_dist = 200
                qty_calc = risk_usd / sl_dist
                # Bybit min 0.001, max based on balance
                qty_calc = max(0.001, round(qty_calc, 3))
                # Cap to not use too much margin (10x lev, max 20% balance)
                max_qty = (balance * 0.20 * 10) / price
                qty_calc = min(qty_calc, max_qty)
                if qty_calc < 0.001:
                    log("Qty too small - skip")
                    continue

                order_side = "Buy" if direction == "LONG" else "Sell"
                if direction == "LONG":
                    sl = price - sl_dist
                    tp = price + (sl_dist * 3)
                else:
                    sl = price + sl_dist
                    tp = price - (sl_dist * 3)

                log(f"🚀 ENTER {direction} | Price ${price:.0f} | Qty {qty_calc} | SL {sl:.0f} | TP {tp:.0f} | Cert {cert}% Agree {agree}")
                tg(f"🚀 <b>ENTER {direction}</b>\nPrice ${price:.0f}\nQty {qty_calc}\nSL {sl:.0f}\nTP {tp:.0f}\nCert {cert}% Agree {agree}/8\nATR {atr:.0f}\nBalance ${balance:.2f}")

                r = place_order(order_side, qty_calc, sl=sl, tp=tp)
                if r.get("retCode", 1) == 0 or r.get("retMsg") == "OK":
                    in_position = True
                    side = direction
                    entry = price
                    qty = qty_calc
                    sl_price = sl
                    be_done = False
                    be_trigger = 0.0
                else:
                    log(f"Order failed: {r}")
            else:
                if direction != "NONE":
                    log(f"⏳ Cert {cert}% < {CERT_MIN}% - No trade")

        except Exception as e:
            log(f"MAIN LOOP ERROR: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
