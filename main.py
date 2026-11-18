# V15 FINAL - ATR Wide SL + $500 BE + Instant Re-Entry + Fees + Smart News + Cross Margin
# LONG = SHORT Equal | No Add-On | No Hardcoded Balance/Price
# main.py = HAND ONLY. data_engine.py = BRAIN. main.py must call data_engine every loop.

import os, time, math, hmac, hashlib, json, requests
from datetime import datetime, timezone

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
BASE = "https://api.bybit.com"
SYMBOL = "BTCUSDT"
CATEGORY = "linear"

# === V15 CONFIG - YOUR RULES ===
USE_ATR_SL = True  # If you no like ATR SL, change to False -> go back to your fixed SL
ATR_PERIOD = 14
ATR_SL_MULT = 5.0
ATR_TP_MULT = 6.5
ATR_BE_TRIGGER_MULT = 2.0
ATR_BE_BUFFER_MULT = 0.5
WICK_BUFFER_PCT = 0.0015  # 0.15% of price
FEE_RATE_TOTAL = 0.0022  # 0.06%*2 fee + 0.05%*2 slippage = 0.22%
BE_MIN_TRIGGER = 500.0  # YOUR RULE: Minimum $500 wicks
BE_MIN_BASE_PRICE = 65000.0  # $500 at $65k, grows with price
BE_SAFETY = 50.0  # $50 safety above fees in buffer
CRITICAL_CERT = 90.0
NORMAL_CERT = 75.0
FLIP_CERT = 85.0
COOLDOWN_SEC = 60
REENTRY_GAP_MULT = 0.5
MAX_QTY = 0.100

# State
position = None  # {'side':'Buy'/'Sell','entry':float,'qty':float,'best':float,'sl':float,'tp':float}
last_trade_time = 0
last_close_price = 0
pause_long = False
pause_short = False
balance_cache = 0
news_critical = False
news_not_critical_wait_until = 0
instant_reentry_allowed = False

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

def tg(msg):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT, "text": msg}, timeout=5)
    except: pass

def sign(params):
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def api(method, path, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    params["timestamp"] = str(int(time.time()*1000))
    params["recv_window"] = "5000"
    params["sign"] = sign(params)
    try:
        if method == "GET":
            r = requests.get(BASE+path, params=params, timeout=10)
        else:
            r = requests.post(BASE+path, json=params, timeout=10)
        return r.json()
    except Exception as e:
        log(f"API ERR {e}")
        return {}

# === MARKET DATA ===
def get_price():
    try:
        r = requests.get(f"{BASE}/v5/market/tickers", params={"category": CATEGORY, "symbol": SYMBOL}, timeout=5).json()
        return float(r["result"]["list"][0]["lastPrice"])
    except: return 0

def get_candles(limit=20):
    try:
        r = requests.get(f"{BASE}/v5/market/kline", params={"category": CATEGORY, "symbol": SYMBOL, "interval": "1", "limit": limit}, timeout=5).json()
        out = []
        for c in r["result"]["list"][::-1]:
            out.append({"open": float(c[1]), "high": float(c[2]), "low": float(c[3]), "close": float(c[4])})
        return out
    except: return []

def calc_atr(candles):
    if len(candles) < 15: return 200.0
    trs = []
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i-1]
        trs.append(max(c["high"]-c["low"], abs(c["high"]-p["close"]), abs(c["low"]-p["close"])))
    return sum(trs[-ATR_PERIOD:]) / ATR_PERIOD

def longest_wick(candles):
    if not candles: return 0
    m = 0
    for c in candles[-5:]:
        body = abs(c["close"]-c["open"])
        wick = (c["high"]-c["low"]) - body
        m = max(m, wick)
    return m

def fees_in_price(price):
    # Fees in price distance = price * 0.0022 (scales with BTC price)
    return price * FEE_RATE_TOTAL

# === BALANCE & QTY - DYNAMIC, NO HARDCODE ===
def get_balance():
    global balance_cache
    res = api("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
    try:
        bal = float(res["result"]["list"][0]["coin"][0]["walletBalance"])
        balance_cache = bal
        return bal
    except:
        log("BALANCE FAIL — NO TRADE")
        return None

def get_leverage(balance):
    if balance >= 20: return 50
    if balance >= 10: return 25
    if balance >= 5: return 20
    return 15

def calc_qty(balance, price, lev):
    base = 0.010 + max(0, (balance - 20) / 8) * 0.005
    max_aff = balance * 0.90 * lev / price if price > 0 else 0
    return min(base, max_aff, MAX_QTY)

# === PATCHED: CALL DATA ENGINE FROM SAME REPO - NO STUB ===
# main.py NO BE BRAIN. data_engine.py NA BRAIN.
# Your data_engine.py must dey same folder / same GitHub repo as main.py
try:
    import data_engine as DE
    log("✅ Data Engine Connected")
except Exception as e:
    log(f"❌ Data Engine NOT Found: {e}")
    DE = None

def _normalize_votes(raw):
    # Data engine fit return different keys - normalize am to wetin main.py need
    if not isinstance(raw, dict):
        return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False}
    direction = str(raw.get("direction") or raw.get("side") or raw.get("signal") or "NONE").upper()
    if direction not in ("LONG", "SHORT"):
        # Allow Buy/Sell style from data_engine
        if direction == "BUY": direction = "LONG"
        elif direction == "SELL": direction = "SHORT"
        else: direction = "NONE"
    return {
        "cert": float(raw.get("cert", raw.get("certainty", raw.get("confidence", 0))) or 0),
        "direction": direction,
        "agree": int(raw.get("agree", raw.get("agree_count", raw.get("votes", 0))) or 0),
        "hunt_soon": bool(raw.get("hunt_soon", raw.get("hunt", False))),
        "hunt_cert": float(raw.get("hunt_cert", raw.get("hunt_certainty", 0)) or 0),
        "cvd_buy_pct": float(raw.get("cvd_buy_pct", raw.get("cvd_buy", 50)) or 50),
        "news_critical": bool(raw.get("news_critical", raw.get("critical_news", raw.get("is_critical", False)))),
        "news_wait": int(raw.get("news_wait", raw.get("news_wait_sec", 0)) or 0),
        "pause_long": bool(raw.get("pause_long", raw.get("PAUSE_LONG", False))),
        "pause_short": bool(raw.get("pause_short", raw.get("PAUSE_SHORT", False))),
    }

def get_votes(price, atr, candles):
    """
    ONLY bridge between main.py and data_engine.py.
    main.py go ask data_engine every loop: 'Wetin market dey talk now?'
    """
    if DE is None:
        log("DATA ENGINE MISSING - NO TRADE")
        return _normalize_votes({})
    try:
        # Try common function names in order - whichever dey for your repo, e go pick am
        if hasattr(DE, "get_signal"):
            return _normalize_votes(DE.get_signal(price, atr, candles))
        if hasattr(DE, "analyze"):
            return _normalize_votes(DE.analyze(price, atr, candles))
        if hasattr(DE, "get_votes"):
            return _normalize_votes(DE.get_votes(price, atr, candles))
        if hasattr(DE, "check_market"):
            return _normalize_votes(DE.check_market(price))
        if hasattr(DE, "get_decision"):
            return _normalize_votes(DE.get_decision(price, atr, candles))
        log(f"Data Engine functions: {[x for x in dir(DE) if not x.startswith('_')]} - NO KNOWN FUNCTION")
        return _normalize_votes({})
    except Exception as e:
        log(f"Data Engine Error: {e}")
        return _normalize_votes({})

def is_hunt_soon(votes):
    return votes.get("hunt_soon", False)

# === ORDERS ===
def set_cross_margin():
    # Bybit: tradeMode 0 = Cross, 1 = Isolated
    api("POST", "/v5/position/switch-isolated", {"category": CATEGORY, "symbol": SYMBOL, "tradeMode": 0, "buyLeverage": "50", "sellLeverage": "50"})
    log("Margin set to CROSS")

def place_order(side, qty, price, sl, tp):
    # side: Buy / Sell
    res = api("POST", "/v5/order/create", {
        "category": CATEGORY, "symbol": SYMBOL, "side": side, "orderType": "Market",
        "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(sl, 1)),
        "tpslMode": "Full", "positionIdx": 0
    })
    log(f"ORDER {side} qty={qty} sl={sl:.1f} tp={tp:.1f} -> {res.get('retMsg')}")
    return res

def close_position(side, qty):
    # close by opposite market order
    opp = "Sell" if side == "Buy" else "Buy"
    res = api("POST", "/v5/order/create", {
        "category": CATEGORY, "symbol": SYMBOL, "side": opp, "orderType": "Market",
        "qty": str(qty), "positionIdx": 0, "reduceOnly": True
    })
    log(f"CLOSE {side} qty={qty}")
    return res

def sync_position_from_exchange():
    # If Bybit SL/TP close am, our local position must clear - no ghost position
    try:
        res = api("GET", "/v5/position/list", {"category": CATEGORY, "symbol": SYMBOL})
        lst = res.get("result", {}).get("list", [])
        for p in lst:
            sz = float(p.get("size", 0) or 0)
            if sz > 0:
                return {"side": p.get("side"), "entry": float(p.get("avgPrice", 0) or 0), "qty": sz, "best": float(p.get("avgPrice", 0) or 0)}
        return None
    except:
        return None

# === V15 CORE MATH ===
def calc_levels(entry, direction, atr, candles, price):
    fees = fees_in_price(price)
    wick_shield = longest_wick(candles) + price * WICK_BUFFER_PCT
    if USE_ATR_SL:
        sl_dist = atr * ATR_SL_MULT + wick_shield + fees
    else:
        # YOUR OLD FIXED STYLE - fallback if you turn ATR off
        sl_dist = 1200 + fees
    tp_dist = atr * ATR_TP_MULT
    # BE Trigger - YOUR $500 MIN RULE
    price_scaled_be = BE_MIN_TRIGGER * (price / BE_MIN_BASE_PRICE)
    be_trigger = max(BE_MIN_TRIGGER, atr * ATR_BE_TRIGGER_MULT, price_scaled_be)
    # BE Buffer - must cover fees + safety
    be_buffer = max(fees + BE_SAFETY, atr * ATR_BE_BUFFER_MULT, 50 * (price / BE_MIN_BASE_PRICE))
    if direction == "LONG":
        sl = entry - sl_dist
        tp = entry + tp_dist
    else:
        sl = entry + sl_dist
        tp = entry - tp_dist
    return {"sl": sl, "tp": tp, "sl_dist": sl_dist, "tp_dist": tp_dist, "be_trigger": be_trigger, "be_buffer": be_buffer, "fees": fees}

# === MAIN LOOP ===
def main():
    global position, last_trade_time, last_close_price, news_not_critical_wait_until, news_critical, pause_long, pause_short, instant_reentry_allowed
    log("V15 STARTED | CROSS | ATR SL | $500 BE | Instant Re-Entry | Fees Inside | Data Engine Connected")
    tg("🤖 V15 STARTED\nCROSS | ATR SL x5 | $500 BE Min | Fees Inside | LONG=SHORT | Data Engine Connected")
    set_cross_margin()
    while True:
        try:
            price = get_price()
            if price == 0:
                time.sleep(5); continue
            candles = get_candles(20)
            atr = calc_atr(candles)
            balance = get_balance()
            if balance is None:
                time.sleep(5); continue
            if balance < 5:
                log("Balance too small - warning")
            lev = get_leverage(balance)
            # PATCHED: main.py calls data_engine every loop
            votes = get_votes(price, atr, candles)
            news_critical = votes.get("news_critical", False)
            pause_long = votes.get("pause_long", False)
            pause_short = votes.get("pause_short", False)

            # === NEWS BRAIN - from data_engine ===
            # If data_engine say news NOT critical but need confirm, wait 5 mins (300s)
            if votes.get("news_wait", 0) > 0 and news_not_critical_wait_until == 0:
                news_not_critical_wait_until = time.time() + votes["news_wait"]
            if news_not_critical_wait_until > time.time():
                log(f"News wait {int(news_not_critical_wait_until-time.time())}s")
                time.sleep(2); continue
            else:
                news_not_critical_wait_until = 0

            # === SYNC: If exchange don close position (SL/TP hit), clear local ===
            if position:
                live = sync_position_from_exchange()
                if live is None:
                    log("Exchange shows no position - SL/TP must don hit, clearing local")
                    last_close_price = price
                    last_trade_time = time.time()
                    position = None
                    instant_reentry_allowed = False
                    time.sleep(2); continue

            # === MANAGE OPEN POSITION ===
            if position:
                side = position["side"]
                entry = position["entry"]
                qty = position["qty"]
                # Update best price
                if side == "Buy":
                    profit_move = price - entry
                    position["best"] = max(position["best"], price)
                else:
                    profit_move = entry - price
                    position["best"] = min(position["best"], price)

                levels = calc_levels(entry, "LONG" if side == "Buy" else "SHORT", atr, candles, price)
                be_trigger = levels["be_trigger"]
                be_buffer = levels["be_buffer"]

                # --- YOUR $500 BE = TP + Instant Re-Entry ---
                if profit_move >= be_trigger:
                    # Close immediately as TP, lock profit
                    close_position(side, qty)
                    net = (profit_move * qty) - (price * qty * FEE_RATE_TOTAL)
                    log(f"✅ BE TP HIT! Move ${profit_move:.0f} | Net ${net:.2f} | ATR {atr:.0f}")
                    tg(f"✅ BE TP +${net:.2f}\nMove ${profit_move:.0f} | Price {price:.0f}")
                    last_close_price = price
                    last_trade_time = time.time()
                    position = None

                    # Instant Re-Entry Check - same second, no 1-min cooldown - PATCHED: call data_engine again
                    v2 = get_votes(price, atr, candles)
                    same_dir = (v2["direction"] == "LONG" and side == "Buy") or (v2["direction"] == "SHORT" and side == "Sell")
                    if same_dir and v2["cert"] >= NORMAL_CERT and not is_hunt_soon(v2):
                        log("🔁 Instant Re-Entry - cert still same + no hunt soon")
                        instant_reentry_allowed = True
                        votes = v2  # Use fresh votes for entry below, no need fetch again
                        # Fall through to entry logic below immediately - do NOT continue
                    elif same_dir and is_hunt_soon(v2):
                        log("⏳ Hunt soon - WAIT for sweep, no instant re-entry")
                        instant_reentry_allowed = False
                        time.sleep(5); continue
                    else:
                        log("No re-entry - cert changed")
                        instant_reentry_allowed = False
                        time.sleep(2); continue
                else:
                    # Normal SL/TP check (Bybit TP/SL already set, but we also watch)
                    # If SL hit by price, Bybit will close - we sync by checking position
                    time.sleep(2 if news_critical else 5)
                    continue

            # === ENTRY LOGIC ===
            # PATCHED: Cooldown now REAL - only instant BE re-entry fit skip am
            if not instant_reentry_allowed and position is None and last_close_price != 0:
                if time.time() - last_trade_time < COOLDOWN_SEC:
                    log(f"Cooldown {int(COOLDOWN_SEC - (time.time()-last_trade_time))}s")
                    time.sleep(2); continue
            # Reset flag after one use
            instant_reentry_allowed = False

            # Pause checks - LONG = SHORT equal - from data_engine
            if pause_long and votes["direction"] == "LONG":
                log("PAUSE_LONG active"); time.sleep(5); continue
            if pause_short and votes["direction"] == "SHORT":
                log("PAUSE_SHORT active"); time.sleep(5); continue

            # Critical news = enter now, Not critical = need 75%+
            need_cert = CRITICAL_CERT if news_critical else NORMAL_CERT
            if votes["cert"] >= need_cert and votes["direction"] in ("LONG", "SHORT"):
                # Re-entry gap - ATR based, not fixed $20 - skip gap for instant BE re-entry
                if last_close_price != 0 and abs(price - last_close_price) < atr * REENTRY_GAP_MULT:
                    # If we just did BE TP and cert still strong, gap na new entry point, no block am
                    # Only block if price never move at all
                    if abs(price - last_close_price) < 5:
                        log(f"Re-entry gap too small {abs(price-last_close_price):.0f} < {atr*REENTRY_GAP_MULT:.0f}")
                        time.sleep(2); continue
                qty = calc_qty(balance, price, lev)
                if qty < 0.001:
                    log(f"Qty too small {qty} - balance {balance}"); time.sleep(5); continue
                levels = calc_levels(price, votes["direction"], atr, candles, price)
                side = "Buy" if votes["direction"] == "LONG" else "Sell"
                res = place_order(side, qty, price, levels["sl"], levels["tp"])
                if res.get("retCode") == 0:
                    position = {"side": side, "entry": price, "qty": qty, "best": price, "sl": levels["sl"], "tp": levels["tp"]}
                    log(f"🚀 ENTER {side} {price:.0f} qty={qty} SL {levels['sl']:.0f} TP {levels['tp']:.0f} BE Trig ${levels['be_trigger']:.0f} Buffer ${levels['be_buffer']:.0f} ATR {atr:.0f} Fees ${levels['fees']:.0f}")
                    tg(f"🚀 ENTER {side} @{price:.0f}\nQty {qty} | SL {levels['sl']:.0f} | TP {levels['tp']:.0f}\nBE ${levels['be_trigger']:.0f} | ATR {atr:.0f}")
                    last_trade_time = time.time()
                else:
                    log(f"Order failed {res}")
            time.sleep(2 if news_critical else 5)
        except Exception as e:
            log(f"LOOP ERR {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
