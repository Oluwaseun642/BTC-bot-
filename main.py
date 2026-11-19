# ============================================================
# MAIN.PY V15.2.2 - CLEAN + HUNTER WIRED
# ISOLATED | WIDE SL $1200 | TP $1500 | BE $500 -> LOCK $20
# DYNAMIC LEV/QTY FROM V13 | NO ATR SL | NO ADDON | NO DOUBLE TRADE
# HUNTER LIVE: hunter_wait / hunter_bias / funding_cascade / spot_premium / pause_reason
# ============================================================
import os, time, threading, hmac, hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# ------------------------------------------------------------
# 0. FAKE PORT - USED by Render + UptimeRobot
# ------------------------------------------------------------
def _keep_port():
    try:
        port = int(os.environ.get("PORT", 10000))
        class H(BaseHTTPRequestHandler):
            def _ok(self, with_body=True):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", "19" if with_body else "0")
                self.end_headers()
                if with_body:
                    try: self.wfile.write(b"BTC-BOT V15 RUNNING")
                    except: pass
            def do_GET(self): self._ok(True)
            def do_HEAD(self): self._ok(False)
            def do_POST(self): self._ok(True)
            def do_PUT(self): self._ok(True)
            def do_DELETE(self): self._ok(True)
            def do_OPTIONS(self): self._ok(True)
            def log_message(self, *a): pass
        HTTPServer(("0.0.0.0", port), H).serve_forever()
    except Exception as e:
        print(f"Port keep-alive error: {e}", flush=True)
threading.Thread(target=_keep_port, daemon=True).start()

# ------------------------------------------------------------
# 1. DATA ENGINE
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
# 2. CONFIG
# ------------------------------------------------------------
BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SYMBOL = "BTCUSDT"
CATEGORY = "linear"
BASE_URL = "https://api.bybit.com"

WIDE_SL_USD = 1200.0
TP_DIST_USD = 1500.0
BE_TRIGGER = 500.0
BE_LOCK = 20.0
CERT_MIN = 75.0
CERT_HUNT = 85.0
MAX_DAILY_LOSS = 50.0

QTY_BASE = 0.010
QTY_STEP = 0.005
QTY_MIN = 0.001
REAL_MAX_QTY = 0.100
FEE_RATE = 0.0006

balance = 0.0
leverage = 25
in_position = False
side = None
entry = 0.0
qty = 0.0
be_done = False
daily_pnl = 0.0
wins = 0
losses = 0
breakevens = 0
votes = {"cert": 0, "direction": "NONE", "agree": 0}

# ------------------------------------------------------------
# 3. HELPERS - ALL USED
# ------------------------------------------------------------
def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

def tg(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

def _sign(params):
    qs = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(BYBIT_API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def bybit_get(path, params):
    try:
        ts = str(int(time.time() * 1000))
        params["api_key"] = BYBIT_API_KEY; params["timestamp"] = ts; params["recv_window"] = "5000"
        params["sign"] = _sign(params)
        return requests.get(BASE_URL + path, params=params, timeout=10).json()
    except Exception as e:
        log(f"Bybit GET error {e}"); return {}

def bybit_post(path, params):
    try:
        ts = str(int(time.time() * 1000))
        params["api_key"] = BYBIT_API_KEY; params["timestamp"] = ts; params["recv_window"] = "5000"
        params["sign"] = _sign(params)
        return requests.post(BASE_URL + path, data=params, timeout=10).json()
    except Exception as e:
        log(f"Bybit POST error {e}"); return {}

# ------------------------------------------------------------
# 4. BYBIT - ALL USED
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

def get_dynamic_leverage(bal=None):
    global leverage
    if bal is None: bal = balance or 12.58
    if bal >= 20: lev = 50
    elif bal >= 10: lev = 25
    elif bal >= 5: lev = 20
    else: lev = 15
    leverage = lev
    return lev

def get_dynamic_qty(price, lev):
    bal = get_balance() or 12.58
    if price <= 0: return 0.0
    base_qty = QTY_BASE if bal < 20 else round(QTY_BASE + int((bal - 20) // 8) * QTY_STEP, 3)
    max_affordable = (bal * 0.90 * lev) / price
    if max_affordable < QTY_MIN:
        log(f"QTY BLOCK Bal ${bal:.2f} Lev {lev}x too small")
        return 0.0
    qty_calc = max(QTY_MIN, min(min(base_qty, max_affordable), REAL_MAX_QTY))
    qty_calc = int(qty_calc * 1000) / 1000.0
    log(f"DYN LEV {lev}x QTY Bal ${bal:.2f} Base {base_qty} MaxAfford {max_affordable:.4f} -> Qty {qty_calc} Margin ${qty_calc*price/lev:.2f} LiqDist ~${price/lev:.0f}")
    return qty_calc

def set_isolated_margin():
    try:
        lev = get_dynamic_leverage()
        r = bybit_post("/v5/position/switch-isolated", {"category": CATEGORY, "symbol": SYMBOL, "tradeMode": 1, "buyLeverage": str(lev), "sellLeverage": str(lev)})
        log(f"Margin set to ISOLATED | Lev {lev}x | {r.get('retMsg','')}")
        bybit_post("/v5/position/set-leverage", {"category": CATEGORY, "symbol": SYMBOL, "buyLeverage": str(lev), "sellLeverage": str(lev)})
    except Exception as e:
        log(f"Margin ISOLATED error {e}")

def calc_sl_tp(price, side_):
    if side_ == "LONG": return (round(price - WIDE_SL_USD, 1), round(price + TP_DIST_USD, 1))
    return (round(price + WIDE_SL_USD, 1), round(price - TP_DIST_USD, 1))

def place_order(order_side, qty_, sl, tp):
    try:
        lev = get_dynamic_leverage()
        bybit_post("/v5/position/set-leverage", {"category": CATEGORY, "symbol": SYMBOL, "buyLeverage": str(lev), "sellLeverage": str(lev)})
        r = bybit_post("/v5/order/create", {"category": CATEGORY, "symbol": SYMBOL, "side": order_side, "orderType": "Market", "qty": str(qty_), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(sl, 1)), "tpslMode": "Full", "positionIdx": 0})
        log(f"Order {order_side} {qty_} Lev {lev}x -> {r.get('retMsg', '')}")
        return r
    except Exception as e:
        log(f"Order error {e}"); return {}

def set_sl_to_be():
    global be_done
    try:
        if get_position() is None: return
        new_sl = entry + BE_LOCK if side == "LONG" else entry - BE_LOCK
        bybit_post("/v5/position/trading-stop", {"category": CATEGORY, "symbol": SYMBOL, "stopLoss": str(round(new_sl, 1)), "positionIdx": 0})
        be_done = True
        log(f"🔒 BE DONE | SL moved to {new_sl:.1f} (Lock +${BE_LOCK})")
        tg(f"🔒 <b>BE TRIGGERED</b>\nSL moved to {new_sl:.1f}\nLocked +${BE_LOCK}")
    except Exception as e:
        log(f"BE SL error {e}")

# ------------------------------------------------------------
# 5. DATA ENGINE BRIDGE - HUNTER WIRED
# ------------------------------------------------------------
def get_votes(price, atr, candles):
    global votes
    default = {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0,
               "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False,
               "pause_reason": "", "hunter_score": 0, "hunter_bias": "NEUTRAL", "hunter_wait": False,
               "hunter_wait_reason": "", "hunter_reasons": [], "spot_premium_usd": 0,
               "funding_cascade": {}, "liq_clusters": {}, "ob_clusters": {}, "cvd_live": {}}
    if not HAS_DE or DE is None:
        return default
    try:
        fn = next((getattr(DE, n) for n in ["get_signal", "get_votes"] if hasattr(DE, n)), None)
        if fn is None: return default
        res = fn(price, atr, candles)
        if isinstance(res, dict):
            votes = res
            return res
    except Exception as e: log(f"get_votes error {e}")
    return default

def get_price_and_candles():
    # FIXED: keep volume + time, else Data Engine Asia Range / CVD go break
    if HAS_DE:
        try:
            price, _ = DE.get_price_live()
            k1 = DE.get_klines("1", 20)
            candles = [{"open": k["open"], "high": k["high"], "low": k["low"], "close": k["close"],
                        "volume": k.get("volume", 1), "time": k.get("time", 0)} for k in k1]
            return price, candles
        except: pass
    try:
        r = requests.get(f"{BASE_URL}/v5/market/tickers?category=linear&symbol={SYMBOL}", timeout=5).json()
        return float(r["result"]["list"][0]["lastPrice"]), []
    except: return 0.0, []

def calc_atr(candles):
    if not candles or len(candles) < 15: return 0.0
    trs = [max(candles[i]["high"]-candles[i]["low"], abs(candles[i]["high"]-candles[i-1]["close"]), abs(candles[i]["low"]-candles[i-1]["close"])) for i in range(1, len(candles))]
    return sum(trs[-14:]) / len(trs[-14:]) if trs else 0.0

# ------------------------------------------------------------
# 6. MAIN LOOP - HUNTER WIRED
# ------------------------------------------------------------
def main():
    global in_position, side, entry, qty, be_done, daily_pnl, wins, losses, breakevens

    log("V15.2.2 CLEAN + HUNTER STARTED | ISOLATED | WIDE SL $1200 | TP $1500 | BE $500 -> LOCK $20")
    tg("🤖 <b>BTC Bot V15.2.2 CLEAN + HUNTER STARTED</b>\nISOLATED | Wide SL $1200 | TP $1500\nBE $500 -> Lock $20\nDyn Lev/Qty from V13\nHunter Live ON")
    set_isolated_margin()
    get_balance()
    log(f"Balance ${balance:.2f} | Lev {get_dynamic_leverage()}x")
    last_vote_time = 0
    news_wait_until = 0

    while True:
        try:
            time.sleep(2)
            price, candles = get_price_and_candles()
            if price == 0: continue
            atr = calc_atr(candles)

            # --- IN POSITION ---
            if in_position:
                profit_move = (price - entry) if side == "LONG" else (entry - price)
                if not be_done and profit_move >= BE_TRIGGER:
                    log(f"🎯 BE TRIGGER | Move ${profit_move:.1f} >= ${BE_TRIGGER}")
                    set_sl_to_be()

                if get_position() is None:
                    sl, tp = calc_sl_tp(entry, side)
                    fees = qty * entry * FEE_RATE * 2
                    gross = (price - entry) * qty if side == "LONG" else (entry - price) * qty
                    net = gross - fees
                    if be_done: result = "BE"; breakevens += 1
                    elif net > 0: result = "WIN"; wins += 1
                    else: result = "LOSS"; losses += 1
                    daily_pnl += net
                    log(f"🔴 CLOSED {result} | Exit {price:.1f} | Gross ${gross:.2f} Fees ${fees:.2f} Net ${net:.2f} | Daily ${daily_pnl:.2f}")
                    log(f"W{wins} L{losses} BE{breakevens} | PnL ${daily_pnl:.2f}")
                    tg(f"🔴 <b>CLOSED {result}</b>\nExit {price:.1f}\nNet ${net:.2f}\nW{wins} L{losses} BE{breakevens}\nDaily PNL ${daily_pnl:.2f}")
                    if HAS_DE and hasattr(DE, "save_trade"):
                        try: DE.save_trade({"time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "side": side, "entry": entry, "exit": price, "move": round(profit_move, 1), "qty": qty, "net_pnl": round(net, 2), "result": result, "balance_after": round(balance, 2), "cert": votes.get("cert", 0), "atr": round(atr, 1), "sl": sl, "tp": tp, "lev": leverage, "margin": "ISOLATED", "hunter_score": votes.get("hunter_score", 0), "hunter_bias": votes.get("hunter_bias", "NEUTRAL")})
                        except Exception as e: log(f"Save trade error {e}")
                    in_position = False; side = None; entry = 0.0; qty = 0.0; be_done = False
                    get_balance()
                    continue
                sl, tp = calc_sl_tp(entry, side)
                log(f"HOLDING {side} Entry ${entry:.0f} Price ${price:.0f} Move ${profit_move:.0f} | SL ${sl:.0f} BE {'DONE' if be_done else 'WAIT $500'} TP ${tp:.0f} | W{wins} L{losses} BE{breakevens}")
                continue

            # --- NOT IN POSITION ---
            if time.time() - last_vote_time < 5: continue
            last_vote_time = time.time()

            # Real news wait - if we set news_wait_until, actually wait
            if time.time() < news_wait_until:
                log(f"📰 NEWS WAIT until {int(news_wait_until - time.time())}s left")
                continue

            v = get_votes(price, atr, candles)
            cert = v.get("cert", 0); direction = v.get("direction", "NONE"); agree = v.get("agree", 0)
            # HUNTER FIELDS - NEW
            hunter_score = v.get("hunter_score", 0); hunter_bias = v.get("hunter_bias", "NEUTRAL")
            hunter_wait = v.get("hunter_wait", False); hunter_wait_reason = v.get("hunter_wait_reason", "")
            spot_prem = v.get("spot_premium_usd", 0)
            fc = v.get("funding_cascade", {}) or {}
            liq_c = v.get("liq_clusters", {}) or {}
            pause_reason = v.get("pause_reason", "")
            lev = get_dynamic_leverage()
            qty_preview = get_dynamic_qty(price, lev)
            wsl_preview, tp_preview = calc_sl_tp(price, direction) if direction in ("LONG", "SHORT") else (0, 0)

            log(f"Price ${price:.0f} | ATR {atr:.0f} (log only) | {direction} Cert {cert}% Agree {agree}/8 | Bal ${balance:.2f}")
            log(f"HUNTER {hunter_bias} {hunter_score} Wait={hunter_wait} | Liq Long ${liq_c.get('long_liq',0):,.0f} Short ${liq_c.get('short_liq',0):,.0f} ({liq_c.get('dominant','?')}) | Spot Prem ${spot_prem:.0f} | CVD Live {v.get('cvd_live',{}).get('buy_pct',50)}% | FundingCascade {fc.get('risk','NONE')} | PauseReason {pause_reason}")
            if hunter_wait_reason:
                log(f"👀 HUNTER WAIT: {hunter_wait_reason}")
            log(f"Qty {qty_preview} Lev {lev}x | WideSL ${wsl_preview:.0f} TP ${tp_preview:.0f} BE $500 | W{wins} L{losses} BE{breakevens} PnL ${daily_pnl:.2f}")

            if daily_pnl <= -MAX_DAILY_LOSS:
                log(f"🛑 DAILY LOSS LIMIT ${daily_pnl:.2f}"); time.sleep(60); continue
            if v.get("news_critical") and cert < 90: log(f"📰 NEWS CRITICAL - Skip Cert {cert}%"); continue
            if v.get("news_wait", 0) > 0:
                news_wait_until = time.time() + int(v.get("news_wait", 0))
                log(f"📰 NEWS WAIT {v.get('news_wait')}s - set wait until")
                continue
            # HUNTER WAIT - NEW: hunters go sweep first, no enter yet
            # Only block if hunter_wait AND hunter disagrees with our direction
            # If hunter_bias == direction, e don agree, allow. If hunter_bias opposite, block.
            if hunter_wait and hunter_bias != "NEUTRAL" and hunter_bias != direction and direction != "NONE":
                log(f"👀 HUNTER WAIT BLOCK {direction} | Hunter {hunter_bias} {hunter_score} | {hunter_wait_reason}")
                continue
            if direction == "LONG" and v.get("pause_long"): log(f"⏸️ PAUSE LONG | {pause_reason}"); continue
            if direction == "SHORT" and v.get("pause_short"): log(f"⏸️ PAUSE SHORT | {pause_reason}"); continue
            if v.get("hunt_soon") and cert < CERT_HUNT: log(f"👀 HUNT SOON - Waiting Cert {cert}%"); continue

            if direction in ("LONG", "SHORT") and cert >= CERT_MIN:
                if qty_preview == 0: log("BLOCK QTY TOO SMALL"); continue
                sl, tp = calc_sl_tp(price, direction)
                fees = qty_preview * price * FEE_RATE * 2
                log(f"FEES CHECK TP Profit ${TP_DIST_USD * qty_preview:.2f} vs Fees ${fees:.2f} | SL Loss ${WIDE_SL_USD * qty_preview:.2f}")
                order_side = "Buy" if direction == "LONG" else "Sell"
                log(f"🚀 ENTER {direction} | Price ${price:.0f} | Qty {qty_preview} Lev {lev}x ISOLATED | SL ${sl:.0f} (-$1200) | TP ${tp:.0f} (+$1500) | BE $500 -> Lock $20 | Cert {cert}% Agree {agree} | Hunter {hunter_bias} {hunter_score}")
                tg(f"🚀 <b>ENTER {direction}</b>\nPrice ${price:.0f}\nQty {qty_preview} Lev {lev}x ISOLATED\nSL ${sl:.0f} (-$1200)\nTP ${tp:.0f} (+$1500)\nBE $500 -> Lock $20\nCert {cert}% Agree {agree}/8\nHunter {hunter_bias} {hunter_score}")
                r = place_order(order_side, qty_preview, sl, tp)
                if r.get("retCode", 1) == 0 or r.get("retMsg") == "OK":
                    in_position = True; side = direction; entry = price; qty = qty_preview; be_done = False
                else: log(f"Order failed: {r}")
            elif direction != "NONE":
                log(f"⏳ Cert {cert}% < {CERT_MIN}% - No trade")

        except Exception as e:
            log(f"MAIN LOOP ERROR: {e}"); time.sleep(5)

if __name__ == "__main__":
    main()
