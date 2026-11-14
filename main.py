# ============================================================
# BTC SWEEP BOT - V13.1 FINAL - YOUR RULE + ADD-ON DOUBLE
# MaxTrade 20 -> SURE 85-90-95% | MaxLoss 5 -> SURE 90-95% | Cooldown 5min
# Balance -2% -> Calm 20min -> Back to Normal 80% | Balance >$10 -> DOUBLE Qty
# LONG + SHORT Both | FLIP + Mental SL + Wide SL + BE + Trailing + Live All
# Paper till Sun 8:30pm WAT (19:30 UTC 15 Nov) -> Auto REAL
# ============================================================

import time, requests, hmac, hashlib, os, threading
from datetime import datetime, timezone

# ================= FLASK =================
try:
    from flask import Flask
    _flask_app = Flask(__name__)
    @_flask_app.route("/")
    def _health(): return "BOT ALIVE - PAPER till Sun 8:30pm WAT, then REAL", 200
    @_flask_app.route("/health")
    def _health2(): return "OK", 200
    def _run_flask():
        try:
            port = int(os.getenv("PORT", 10000)); _flask_app.run(host="0.0.0.0", port=port, use_reloader=False)
        except Exception as e: print(f"Flask error {e}", flush=True)
    threading.Thread(target=_run_flask, daemon=True).start()
    print("Flask keep-alive ON", flush=True)
except Exception as e: print(f"Flask OFF {e}", flush=True)

# ================= SELF-PING =================
def _self_ping_loop():
    SELF_URL = os.getenv("RENDER_URL", "https://YOUR-BOT-NAME.onrender.com/")
    while True:
        try: time.sleep(240); requests.get(SELF_URL, timeout=10); print("SELF-PING OK", flush=True)
        except Exception as e: print(f"SELF-PING FAIL {e}", flush=True)
threading.Thread(target=_self_ping_loop, daemon=True).start()
print("Self-Ping ON - every 4 min", flush=True)

# ================= CONFIG - YOUR RULE =================
CONFIG = {
    "SYMBOL": "BTCUSDT", "LEVERAGE": 50, "PAPER_QTY": 0.002,
    "REAL_RISK_MARGIN_PCT": 0.10, "REAL_MIN_QTY": 0.001, "REAL_MAX_QTY": 0.010,
    "MIN_CERTAINTY_NORMAL": 80.0, "MIN_AGREE_NORMAL": 5, "MIN_SCORE_NORMAL": 0.75,
    "TOTAL_SIGNALS": 8, "SURE_CERTAINTY": 95.0, "SURE_AGREE": 6, "TP_MULT_NORMAL": 2.0, "TP_MULT_SURE": 3.5,
    "NEWS_ENABLED": True, "MIN_CERTAINTY_NEWS": 75.0, "MIN_AGREE_NEWS": 5, "MIN_SCORE_NEWS": 0.60,
    "SL_PCT": 0.0085, "WICK_BUFFER_PCT": 0.0011,
    "WIDE_SL_ENABLED": True, "WIDE_SL_PCT": 0.0120,
    "MENTAL_SL_ENABLED": True, "MENTAL_SL_HIDDEN": True, "REAL_SL_BACKUP_BUFFER_PCT": 0.006,
    "FLIP_ENABLED": True, "FLIP_CERTAINTY": 75.0, "FLIP_AGREE": 5,
    "NEVER_STOP": True,
    # YOUR RULE - SOFT, NOT STRICT
    "MAX_TRADES_PER_DAY": 20,
    "MAX_LOSSES_PER_DAY": 5,
    "AFTER_MAX_TRADE_CERTAINTY": 85.0,
    "AFTER_MAX_LOSS_CERTAINTY": 90.0,
    "COOLDOWN_AFTER_LOSS_MIN": 5,
    "AFTER_LOSS_CERTAINTY": 85.0, "AFTER_LOSS_AGREE": 6, "COOLDOWN_AFTER_WIN_MIN": 2,
    "MAX_DAILY_LOSS_PCT": 0.02,
    "DAILY_LOSS_CALM_MIN": 20,
    "CALM_CERTAINTY": 85.0,
    # ADD-ON DOUBLE
    "ADDON_DOUBLE_ENABLED": True, "ADDON_DOUBLE_BALANCE": 10.0, "ADDON_DOUBLE_MULT": 2.0,
    "TRAILING_ENABLED": True, "TRAIL_START_PCT": 0.004,
    "TRAIL_STEP_1": 0.008, "TRAIL_DIST_1": 0.004, "TRAIL_STEP_2": 0.012, "TRAIL_DIST_2": 0.006, "TRAIL_STEP_3": 0.020, "TRAIL_DIST_3": 0.008,
    "BE_OVER_FEES": True, "BE_TRIGGER_PCT": 0.0035, "FEE_RATE": 0.0006, "SLIPPAGE_PCT": 0.0005, "BE_BUFFER_PCT": 0.0024,
    "MIN_TP_OVER_FEES": 3.0, "MIN_RR": 1.8, "MIN_WINPROB": 52.0, "POLL_SEC": 5, "HEARTBEAT_MIN": 10,
    "AUTO_SWITCH_UTC": datetime(2026, 11, 15, 19, 30, tzinfo=timezone.utc), "BYBIT_BASE": "https://api.bybit.com",
    "ASIAN_ENABLED": True, "ASIAN_START_HOUR_UTC": 0, "ASIAN_END_HOUR_UTC": 8, "ASIAN_SWEEP_BUFFER_PCT": 0.0015,
    "SESSION_HUNT_ENABLED": True, "SESSIONS": [("ASIA", 0, 0), ("LONDON", 7, 0), ("NEWYORK", 13, 30)], "SESSION_HUNT_WINDOW_MIN": 30,
}
API_KEY = os.getenv("BYBIT_API_KEY", ""); API_SECRET = os.getenv("BYBIT_API_SECRET", "")
STATE = {"mode": "PAPER", "balance": 4.75, "real_balance": 0.0, "day_start_balance": 4.75, "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0, "flips": 0, "doubles": 0, "trades_today": 0, "losses_today": 0, "last_loss_time": None, "last_trade_time": None, "calm_until": None, "day": datetime.now(timezone.utc).date(), "open_position": None, "last_price": 0.0, "last_macro": {"DXY_CHG": 0.0, "NQ_CHG": 0.0, "SPX_CHG": 0.0, "GOLD_CHG": 0.0, "OI_CHG": 0.0}, "last_liq_map": {"long_liq": 0.0, "short_liq": 0.0, "asia_low": 0.0, "asia_high": 0.0, "hunt": "NONE"}, "last_session": "NONE"}
def now_utc(): return datetime.now(timezone.utc)
def log(msg): print(f"[{now_utc().strftime('%H:%M:%S %d %b')}] {msg}", flush=True)
def get_mode(): return "REAL" if now_utc() >= CONFIG["AUTO_SWITCH_UTC"] else "PAPER"
def bybit_sign(params):
    qs = "&".join([f"{k}={v}" for k, v in sorted(params.items())]); return hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
def bybit_post(path, params):
    params["api_key"] = API_KEY; params["timestamp"] = str(int(time.time()*1000)); params["recv_window"] = "5000"; params["sign"] = bybit_sign(params); r = requests.post(CONFIG["BYBIT_BASE"]+path, data=params, timeout=10); return r.json()
def bybit_get(path, params):
    params["api_key"] = API_KEY; params["timestamp"] = str(int(time.time()*1000)); params["recv_window"] = "5000"; params["sign"] = bybit_sign(params); r = requests.get(CONFIG["BYBIT_BASE"]+path, params=params, timeout=10); return r.json()
def get_real_balance():
    try:
        res = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"}); bal = float(res["result"]["list"][0]["coin"][0]["walletBalance"]); STATE["real_balance"] = bal; return bal
    except Exception as e: log(f"REAL BALANCE ERROR {e} - using last {STATE['real_balance']}"); return STATE["real_balance"] or 0.0
def get_current_balance(mode):
    return STATE["real_balance"] if mode == "REAL" else STATE["balance"]
def get_dynamic_qty(price, mode):
    # QTY CHANGING PER BALANCE - 50x FIXED LEVERAGE - DYNAMIC
    if mode == "PAPER":
        base_qty = CONFIG["PAPER_QTY"]
        bal = STATE["balance"]
    else:
        bal = get_real_balance()
        if bal <= 0: return CONFIG["REAL_MIN_QTY"]
        margin = bal * CONFIG["REAL_RISK_MARGIN_PCT"]; pos = margin * CONFIG["LEVERAGE"]; base_qty = max(CONFIG["REAL_MIN_QTY"], min(pos / price if price else CONFIG["REAL_MIN_QTY"], CONFIG["REAL_MAX_QTY"]))
        base_qty = round(base_qty, 3)
    # ADD-ON DOUBLE - Balance > $10 -> Double Qty
    if CONFIG["ADDON_DOUBLE_ENABLED"] and bal > CONFIG["ADDON_DOUBLE_BALANCE"]:
        doubled = round(base_qty * CONFIG["ADDON_DOUBLE_MULT"], 3)
        # Cap double to 0.020 so e no over-leverage
        doubled = min(doubled, 0.020)
        if doubled != base_qty:
            log(f"ADD-ON DOUBLE ACTIVE: Balance ${bal:.2f} > $10 - Qty {base_qty} -> {doubled} (Double Trade)")
            STATE["doubles"] += 1
        return doubled
    return base_qty
def place_real_order(side, price, mental_sl, real_sl_backup, tp, qty):
    if not API_KEY or not API_SECRET: log("REAL ORDER BLOCKED: No API keys"); return False
    try:
        bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": CONFIG["SYMBOL"], "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        res = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Buy" if side == "LONG" else "Sell", "orderType": "Market", "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(real_sl_backup, 1)), "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice", "timeInForce": "GTC"})
        log(f"REAL ORDER PLACED {side} Qty {qty} Entry ~${price:.0f} MentalSL(HIDDEN) ${mental_sl:.0f} RealSL(Backup) ${real_sl_backup:.0f} TP ${tp:.0f} Lev {CONFIG['LEVERAGE']}x FIXED Bybit: {res}"); return res.get("retCode") == 0
    except Exception as e: log(f"REAL ORDER ERROR {e}"); return False
def update_real_sl(new_real_sl, side):
    if STATE["mode"] != "REAL": return True
    if not API_KEY: return False
    try:
        res = bybit_post("/v5/position/trading-stop", {"category": "linear", "symbol": CONFIG["SYMBOL"], "stopLoss": str(round(new_real_sl, 1)), "slTriggerBy": "LastPrice", "positionIdx": 0}); log(f"REAL SL BACKUP UPDATED -> ${new_real_sl:.0f} Bybit: {res.get('retMsg')}"); return res.get("retCode") == 0
    except Exception as e: log(f"REAL SL UPDATE ERROR {e}"); return False
def close_real_position(side, qty):
    if STATE["mode"] != "REAL": return True
    try:
        res = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Sell" if side == "LONG" else "Buy", "orderType": "Market", "qty": str(qty), "timeInForce": "GTC"}); log(f"REAL POSITION CLOSED VIA FLIP {side} Qty {qty} Bybit: {res}"); return True
    except Exception as e: log(f"REAL CLOSE ERROR {e}"); return False
def get_price():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=5); price = float(r.json()["result"]["list"][0]["lastPrice"]); STATE["last_price"] = price; return price
    except: return STATE["last_price"] or 68000.0
def get_klines(limit=200):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=15&limit={limit}", timeout=5); kl = list(reversed(r.json()["result"]["list"])); return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "time": int(x[0])} for x in kl]
    except: return []
def get_klines_1m(limit=20):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&limit={limit}", timeout=5); kl = list(reversed(r.json()["result"]["list"])); return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4])} for x in kl]
    except: return []
def fetch_yahoo_chg(symbol):
    for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}; r = requests.get(f"{base}/v8/finance/chart/{symbol}?range=1d&interval=1m", headers=headers, timeout=6); meta = r.json()["chart"]["result"][0]["meta"]; price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0); prev = float(meta.get("previousClose") or meta.get("chartPreviousClose") or price)
            if price and prev: return round((price - prev) / prev * 100, 3)
        except Exception as e: print(f"Yahoo {base} {symbol} fail {e}", flush=True); continue
    return None
def fetch_stooq_chg(s):
    try:
        r = requests.get(f"https://stooq.com/q/d/l/?s={s}&i=d", timeout=6); lines = [l.strip().split(",") for l in r.text.strip().splitlines() if "," in l]; closes = []
        for row in lines[1:]:
            try: closes.append(float(row[4]))
            except: pass
        if len(closes) >= 2:
            last, prev = closes[-1], closes[-2]
            if prev: return round((last - prev) / prev * 100, 3)
    except Exception as e: print(f"Stooq {s} fail {e}", flush=True)
    return None
def fetch_live_chg(y, s):
    v = fetch_yahoo_chg(y)
    if v is not None: return v, "Yahoo"
    v = fetch_stooq_chg(s)
    if v is not None: return v, "Stooq"
    return None, "None"
def get_macro():
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5); oi_list = r.json()["result"]["list"]; oi_chg = (float(oi_list[-1]["openInterest"]) - float(oi_list[0]["openInterest"])) / float(oi_list[0]["openInterest"]) * 100
    except: oi_chg = STATE["last_macro"].get("OI_CHG", 0)
    dxy, src_dxy = fetch_live_chg("DX-Y.NYB", "dx.f"); nq, src_nq = fetch_live_chg("NQ=F", "nq.f"); spx, src_spx = fetch_live_chg("ES=F", "es.f"); gold, src_gold = fetch_live_chg("GC=F", "gc.f")
    if dxy is None: dxy = STATE["last_macro"]["DXY_CHG"]; src_dxy = "LastLive"
    if nq is None: nq = STATE["last_macro"]["NQ_CHG"]; src_nq = "LastLive"
    if spx is None: spx = STATE["last_macro"]["SPX_CHG"]; src_spx = "LastLive"
    if gold is None: gold = STATE["last_macro"]["GOLD_CHG"]; src_gold = "LastLive"
    macro = {"DXY_CHG": dxy, "NQ_CHG": nq, "SPX_CHG": spx, "GOLD_CHG": gold, "OI_CHG": oi_chg}; STATE["last_macro"] = macro; print(f"LIVE SRC DXY:{src_dxy} NQ:{src_nq} SPX:{src_spx} GOLD:{src_gold}", flush=True); return macro
def get_liquidation_map(price):
    long_liq = 0.0; short_liq = 0.0
    try:
        r = requests.get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50", timeout=5); lst = r.json().get("result", {}).get("list", [])
        for x in lst:
            try:
                sz = float(x.get("size", 0)) * float(x.get("price", price))
                if x.get("side") == "Sell": long_liq += sz
                elif x.get("side") == "Buy": short_liq += sz
            except: pass
    except Exception as e: print(f"Liq map fail {e}", flush=True)
    return long_liq, short_liq
def get_asian_range(klines_15m):
    asia_lows = []; asia_highs = []
    for k in klines_15m:
        try:
            dt = datetime.fromtimestamp(k["time"]/1000, tz=timezone.utc)
            if dt.date() == now_utc().date() and 0 <= dt.hour < 8: asia_lows.append(k["low"]); asia_highs.append(k["high"])
        except: pass
    if asia_lows and asia_highs: return min(asia_lows), max(asia_highs)
    if len(klines_15m) >= 32:
        w = klines_15m[-32:]; return min(x["low"] for x in w), max(x["high"] for x in w)
    return 0.0, 0.0
def get_asian_hunt(price, klines_15m, klines_1m):
    if not CONFIG["ASIAN_ENABLED"]: return "NEUTRAL", 0.0, 0.0, 0.0, 0.0
    asia_low, asia_high = get_asian_range(klines_15m); long_liq, short_liq = get_liquidation_map(price); hunt = "NEUTRAL"
    if asia_low and asia_high and klines_1m:
        buf = price * CONFIG["ASIAN_SWEEP_BUFFER_PCT"]; last = klines_1m[-1]
        if last["low"] < asia_low and last["close"] > asia_low and long_liq > short_liq: hunt = "LONG"
        elif last["high"] > asia_high and last["close"] < asia_high and short_liq > long_liq: hunt = "SHORT"
        elif last["low"] < asia_low - buf and last["close"] > asia_low: hunt = "LONG"
        elif last["high"] > asia_high + buf and last["close"] < asia_high: hunt = "SHORT"
    STATE["last_liq_map"] = {"long_liq": long_liq, "short_liq": short_liq, "asia_low": asia_low, "asia_high": asia_high, "hunt": hunt}; return hunt, asia_low, asia_high, long_liq, short_liq
def get_session_reopen_hunt(price, klines_1m, klines_15m):
    if not CONFIG["SESSION_HUNT_ENABLED"]: return "NEUTRAL", "NONE"
    now = now_utc()
    for name, hh, mm in CONFIG["SESSIONS"]:
        open_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0); mins_since = (now - open_dt).total_seconds() / 60
        if 0 <= mins_since <= CONFIG["SESSION_HUNT_WINDOW_MIN"]:
            STATE["last_session"] = name
            if klines_1m and len(klines_1m) >= 5:
                window = klines_1m[-5:]; s_low = min(x["low"] for x in window); s_high = max(x["high"] for x in window); last = klines_1m[-1]
                if last["low"] < s_low and last["close"] > s_low: return "LONG", name
                if last["high"] > s_high and last["close"] < s_high: return "SHORT", name
            return "NEUTRAL", name
    return "NEUTRAL", "NONE"
def get_news_score():
    if not CONFIG["NEWS_ENABLED"]: return False, 0, ""
    kl = get_klines_1m(15)
    if len(kl) >= 15:
        move = (kl[-1]["close"] - kl[0]["close"]) / kl[0]["close"] * 100
        if abs(move) >= 0.8: return True, 85.0, f"VOL SPIKE {move:.2f}% in 15m"
    return False, 0, ""
def get_signals(price, macro, klines_1m, asian_hunt, session_hunt):
    signals = []
    if macro["DXY_CHG"] > 0.10: signals.append(("DXY_LEVEL", "SHORT"))
    elif macro["DXY_CHG"] < -0.10: signals.append(("DXY_LEVEL", "LONG"))
    else: signals.append(("DXY_LEVEL", "NEUTRAL"))
    if macro["NQ_CHG"] > 0.20: signals.append(("NQ_MOMENTUM", "LONG"))
    elif macro["NQ_CHG"] < -0.20: signals.append(("NQ_MOMENTUM", "SHORT"))
    else: signals.append(("NQ_MOMENTUM", "NEUTRAL"))
    if macro["SPX_CHG"] > 0.20: signals.append(("SPX_MOMENTUM", "LONG"))
    elif macro["SPX_CHG"] < -0.20: signals.append(("SPX_MOMENTUM", "SHORT"))
    else: signals.append(("SPX_MOMENTUM", "NEUTRAL"))
    if macro["GOLD_CHG"] > 0.50: signals.append(("GOLD_AFTER_SWEEP", "SHORT"))
    elif macro["GOLD_CHG"] < -0.30: signals.append(("GOLD_AFTER_SWEEP", "LONG"))
    else: signals.append(("GOLD_AFTER_SWEEP", "NEUTRAL"))
    if klines_1m and len(klines_1m) >= 5:
        pc = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
        if macro["OI_CHG"] > 0.5 and pc < -0.2: signals.append(("OI_DIVERGENCE", "SHORT"))
        elif macro["OI_CHG"] < -0.5 and pc > 0.2: signals.append(("OI_DIVERGENCE", "LONG"))
        else: signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    else: signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    if klines_1m and len(klines_1m) >= 3:
        last = klines_1m[-1]; wd = last["close"] - last["low"]; wu = last["high"] - last["close"]; thr = price * 0.002
        if wd > thr and wd > wu * 1.5: signals.append(("LIQ_SWEEP", "LONG"))
        elif wu > thr and wu > wd * 1.5: signals.append(("LIQ_SWEEP", "SHORT"))
        else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
    else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
    signals.append(("ASIAN_LIQ_HUNT", asian_hunt if asian_hunt in ("LONG","SHORT") else "NEUTRAL"))
    signals.append(("SESSION_REOPEN_HUNT", session_hunt if session_hunt in ("LONG","SHORT") else "NEUTRAL"))
    return signals
def decide(signals):
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT"); decided = longs + shorts
    if longs > shorts: dest, agree = "LONG", longs
    elif shorts > longs: dest, agree = "SHORT", shorts
    else: dest, agree = "NONE", 0
    return dest, agree, decided, longs, shorts, (agree / decided * 100) if decided else 0
def calc_score(signals, dest, macro, is_news):
    _, agree, decided, _, _, certainty = decide(signals); base = (certainty / 100) * 1.0; align = 0
    if dest == "LONG" and macro["NQ_CHG"] > 0 and macro["SPX_CHG"] > 0: align = 0.4
    if dest == "SHORT" and macro["DXY_CHG"] > 0: align = 0.3
    return round(base + align + (0.4 if is_news else 0), 2)
def calc_sl_tp(price, side, klines, is_sure, session_hunt_active):
    use_wide = CONFIG["WIDE_SL_ENABLED"] and (is_sure or session_hunt_active)
    sl_pct = CONFIG["WIDE_SL_PCT"] if use_wide else CONFIG["SL_PCT"]
    sl_dist = price * sl_pct; wick_buf = price * CONFIG["WICK_BUFFER_PCT"]
    if klines:
        if side == "LONG": mental_sl = min(price - sl_dist, min(c["low"] for c in klines[-15:]) - wick_buf); mental_sl = max(mental_sl, price * 0.985)
        else: mental_sl = max(price + sl_dist, max(c["high"] for c in klines[-15:]) + wick_buf); mental_sl = min(mental_sl, price * 1.015)
    else: mental_sl = price - sl_dist if side == "LONG" else price + sl_dist
    buf = price * CONFIG["REAL_SL_BACKUP_BUFFER_PCT"]; real_sl = mental_sl - buf if side == "LONG" else mental_sl + buf
    sl_f = abs(price - mental_sl); mult = CONFIG["TP_MULT_SURE"] if is_sure else CONFIG["TP_MULT_NORMAL"]; tp_dist = sl_f * mult; tp = price + tp_dist if side == "LONG" else price - tp_dist
    return round(mental_sl, 1), round(real_sl, 1), round(tp, 1), round(sl_f, 1), round(tp_dist, 1), use_wide
def calc_fees_ev(price, sl_dist, tp_dist, winprob, qty):
    pos = qty * price; margin = pos / CONFIG["LEVERAGE"]; fees = pos * CONFIG["FEE_RATE"] * 2; slippage_cost = pos * CONFIG["SLIPPAGE_PCT"] * 2; total_cost = fees + slippage_cost; tp_profit = (qty * tp_dist) - total_cost; sl_loss = (qty * sl_dist) + total_cost; rr = tp_dist / sl_dist if sl_dist else 0; ev = (winprob/100 * tp_profit) - ((1-winprob/100) * sl_loss); be = tp_profit >= (total_cost * CONFIG["MIN_TP_OVER_FEES"]); return pos, margin, fees, slippage_cost, total_cost, tp_profit, sl_loss, rr, ev, be
def get_dynamic_thresholds(is_news, just_lost, mode):
    # YOUR RULE - Tiered, not strict 95% only
    bal = get_current_balance(mode)
    day_start = STATE.get("day_start_balance", bal) or bal
    daily_dd = (bal - day_start) / day_start if day_start else 0
    # Balance -2% -> Calm 20min, need 85%, after 20min back to Normal 80%
    if daily_dd <= -CONFIG["MAX_DAILY_LOSS_PCT"]:
        if STATE.get("calm_until") is None:
            from datetime import timedelta
            STATE["calm_until"] = now_utc() + timedelta(minutes=CONFIG["DAILY_LOSS_CALM_MIN"])
            log(f"DAILY GUARD: Balance drop -2% (${day_start:.2f} -> ${bal:.2f}) - Calm 20min, need 85% only, then back to Normal 80%")
        if now_utc() < STATE["calm_until"]:
            return CONFIG["CALM_CERTAINTY"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "CALM -2% 20min"
        else:
            STATE["calm_until"] = None
            return CONFIG["MIN_CERTAINTY_NORMAL"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "CALM OVER - Back to Normal 80%"
    if STATE["losses_today"] >= CONFIG["MAX_LOSSES_PER_DAY"]:
        return CONFIG["AFTER_MAX_LOSS_CERTAINTY"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "MAX LOSS 5 - Need 90-95% (Try 90% first)"
    if STATE["trades_today"] >= CONFIG["MAX_TRADES_PER_DAY"]:
        return CONFIG["AFTER_MAX_TRADE_CERTAINTY"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "MAX TRADE 20 - Need 85-90-95% (Try 85% first)"
    if just_lost: return CONFIG["AFTER_LOSS_CERTAINTY"], CONFIG["AFTER_LOSS_AGREE"], CONFIG["MIN_SCORE_NORMAL"], "AFTER LOSS - 5min Cooldown + 85%"
    if is_news: return CONFIG["MIN_CERTAINTY_NEWS"], CONFIG["MIN_AGREE_NEWS"], CONFIG["MIN_SCORE_NEWS"], "NEWS HUNTER"
    return CONFIG["MIN_CERTAINTY_NORMAL"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "NORMAL"
def check_loss_control():
    today = now_utc().date()
    if STATE["day"] != today:
        STATE["day"] = today; STATE["trades_today"] = 0; STATE["losses_today"] = 0; STATE["last_loss_time"] = None; STATE["calm_until"] = None
        STATE["day_start_balance"] = STATE["balance"] if STATE["mode"] == "PAPER" else STATE["real_balance"]
    if STATE["open_position"]: return False, "BLOCK: Already in position - Flip check still runs"
    if STATE["last_loss_time"]:
        mins = (now_utc() - STATE["last_loss_time"]).total_seconds() / 60
        if mins < CONFIG["COOLDOWN_AFTER_LOSS_MIN"]: return False, f"WARY: Cooldown {mins:.0f}/{CONFIG['COOLDOWN_AFTER_LOSS_MIN']}min (5min only)"
    return True, ""
def manage_position(price, klines, qty, flip_dest, flip_certainty, flip_agree):
    if not STATE["open_position"]: return False
    p = STATE["open_position"]; entry = float(p["entry"]); side = p["side"]; profit_pct = (price - entry) / entry if side == "LONG" else (entry - price) / entry
    if CONFIG["MENTAL_SL_ENABLED"]:
        wick_cross = (price < p["sl"] if side == "LONG" else price > p["sl"])
        if wick_cross and not p.get("mental_warned"): log(f"MENTAL SL WICK PROTECTION: Price wicked past Mental SL ${p['sl']:.0f} - holding, MM wick ignored, waiting for BE/Trailing/Flip"); p["mental_warned"] = True
        elif not wick_cross: p["mental_warned"] = False
    if CONFIG["BE_OVER_FEES"] and not p.get("be_done"):
        if profit_pct >= CONFIG["BE_TRIGGER_PCT"]:
            be_buffer = entry * CONFIG["BE_BUFFER_PCT"]; be_sl = entry + be_buffer if side == "LONG" else entry - be_buffer
            if (side == "LONG" and be_sl > p["sl"]) or (side == "SHORT" and be_sl < p["sl"]):
                p["sl"] = be_sl; p["be_done"] = True; buf = entry * CONFIG["REAL_SL_BACKUP_BUFFER_PCT"]; p["real_sl"] = be_sl - buf if side == "LONG" else be_sl + buf
                log(f"BE OVER FEES WITH PROFIT: Mental SL -> ${be_sl:.0f} (Entry ${entry:.0f} + 0.24% = fees+slippage+profit) | Real Backup -> ${p['real_sl']:.0f}"); update_real_sl(p["real_sl"], side)
    if CONFIG["TRAILING_ENABLED"] and profit_pct >= CONFIG["TRAIL_START_PCT"]:
        if profit_pct >= CONFIG["TRAIL_STEP_3"]: td = CONFIG["TRAIL_DIST_3"]; label = "Trail 0.80% behind"
        elif profit_pct >= CONFIG["TRAIL_STEP_2"]: td = CONFIG["TRAIL_DIST_2"]; label = "Trail 0.60% behind"
        elif profit_pct >= CONFIG["TRAIL_STEP_1"]: td = CONFIG["TRAIL_DIST_1"]; label = "Trail 0.40% behind"
        else: td = None; label = ""
        if td is not None:
            new_sl = price - (price * td) if side == "LONG" else price + (price * td)
            if (side == "LONG" and new_sl > p["sl"]) or (side == "SHORT" and new_sl < p["sl"]):
                p["sl"] = new_sl; buf = price * CONFIG["REAL_SL_BACKUP_BUFFER_PCT"]; p["real_sl"] = new_sl - buf if side == "LONG" else new_sl + buf
                log(f"TRAILING {side}: Mental SL -> ${new_sl:.0f} | Price ${price:.0f} Profit {profit_pct*100:.2f}% - {label}"); update_real_sl(p["real_sl"], side)
    hit_tp = (price >= p["tp"] if side == "LONG" else price <= p["tp"])
    if hit_tp:
        profit = abs(price - entry) * qty; STATE["balance"] += profit; STATE["pnl"] += profit; STATE["wins"] += 1; log(f"TP HIT +${profit:.2f} - Closed {side} at ${price:.0f} - NEVER STOPS"); STATE["open_position"] = None; return False
    if CONFIG["FLIP_ENABLED"] and flip_dest != "NONE" and flip_dest != side:
        if flip_certainty >= CONFIG["FLIP_CERTAINTY"] and flip_agree >= CONFIG["FLIP_AGREE"]:
            profit = (price - entry) * qty if side == "LONG" else (entry - price) * qty
            if p.get("be_done") or profit >= 0:
                STATE["balance"] += profit; STATE["pnl"] += profit; STATE["wins"] += 1 if profit >= 0 else 0; STATE["flips"] += 1
                log(f"FLIP {side} -> {flip_dest} WITH PROFIT +${profit:.2f} | Cert {flip_certainty:.0f}% Agree {flip_agree} - Brains flip, no wait for SL loss")
            else:
                STATE["balance"] += profit; STATE["pnl"] += profit; STATE["losses"] += 1; STATE["losses_today"] += 1; STATE["flips"] += 1; STATE["last_loss_time"] = now_utc()
                log(f"FLIP {side} -> {flip_dest} EARLY EXIT {profit:.2f} | Cert {flip_certainty:.0f}% Agree {flip_agree} - Flip before SL loss")
            if STATE["mode"] == "REAL": close_real_position(side, qty)
            STATE["open_position"] = None; return True
    return False
def main():
    log("BOT V13.1 STARTED - YOUR RULE 20/5/5min/-2% 20min + DOUBLE >$10 + LONG+SHORT + FLIP + Paper till Sun 8:30pm WAT -> Auto REAL")
    last_heartbeat = now_utc()
    while True:
        try:
            new_mode = get_mode()
            if new_mode != STATE["mode"]:
                STATE["mode"] = new_mode
                if new_mode == "REAL":
                    bal = get_real_balance(); log(f"*** AUTO SWITCH TO REAL *** Sun 8:30pm WAT reached - Real Balance met: ${bal:.2f} USDT - Bot go trade real now, Asia opening, good boy mode ON ***")
                    if STATE["open_position"]: log("Closing paper position before REAL switch"); STATE["open_position"] = None
            mode = STATE["mode"]; price = get_price(); klines_1m = get_klines_1m(20); klines_15m = get_klines(200); macro = get_macro()
            asian_hunt, asia_low, asia_high, long_liq, short_liq = get_asian_hunt(price, klines_15m, klines_1m)
            session_hunt, session_name = get_session_reopen_hunt(price, klines_1m, klines_15m)
            is_news, _, news_reason = get_news_score()
            signals = get_signals(price, macro, klines_1m, asian_hunt, session_hunt)
            dest, agree, decided, longs, shorts, certainty = decide(signals)
            score = calc_score(signals, dest, macro, is_news)
            winprob = max(50, min(75, 50 + (certainty - 50) * 0.4))
            just_lost = STATE["last_loss_time"] is not None and (now_utc() - STATE["last_loss_time"]).total_seconds() < 3600
            need_cert, need_agree, need_score, thresh_label = get_dynamic_thresholds(is_news, just_lost, mode)
            is_sure = (certainty >= CONFIG["SURE_CERTAINTY"] and agree >= CONFIG["SURE_AGREE"])
            mode_str = "SURE 95%+ WIDE TP" if is_sure else ("NEWS HUNTER" if is_news else thresh_label)
            qty = get_dynamic_qty(price, mode)
            flipped = False
            if STATE["open_position"]:
                flipped = manage_position(price, klines_1m, qty, dest, certainty, agree)
                if flipped: log(f"FLIP DONE - Next cycle go open new {dest} trade if gates still pass - No candle close loss")
            ok_control, control_reason = check_loss_control()
            session_active = session_hunt in ("LONG","SHORT")
            if dest in ("LONG", "SHORT") and not STATE["open_position"]:
                mental_sl, real_sl, tp, sl_dist, tp_dist, use_wide = calc_sl_tp(price, dest, klines_1m, is_sure, session_active)
                pos, margin, fees, slip, total_cost, tp_profit, sl_loss, rr, ev, be = calc_fees_ev(price, sl_dist, tp_dist, winprob, qty)
            else:
                if STATE["open_position"]:
                    p = STATE["open_position"]; mental_sl = p["sl"]; real_sl = p.get("real_sl", mental_sl); tp = p["tp"]; sl_dist = abs(price - mental_sl); tp_dist = abs(tp - price); pos, margin, fees, slip, total_cost, tp_profit, sl_loss, rr, ev, be = 0,0,0,0,0,0,0,0,0,False
                else: mental_sl = real_sl = tp = sl_dist = tp_dist = pos = margin = fees = slip = total_cost = tp_profit = sl_loss = rr = ev = 0; be = False; use_wide = False
                if not STATE["open_position"]: use_wide = False
                else: use_wide = False
            gates = []
            gates.append((f"Agree {agree}/{decided} Need {need_agree}", agree >= need_agree and decided >= need_agree))
            gates.append((f"Certainty {certainty:.0f}% Need {need_cert:.0f}% [{thresh_label}]", certainty >= need_cert))
            gates.append((f"Score {score:.2f} / Thr {need_score:.2f}", score >= need_score))
            gates.append((f"WinProb {winprob:.0f}% Need {CONFIG['MIN_WINPROB']:.0f}%", winprob >= CONFIG["MIN_WINPROB"]))
            gates.append((f"TP Profit ${tp_profit:.4f} >= 3x TotalCost ${total_cost:.4f} (Fees ${fees:.4f}+Slip ${slip:.4f})", be if not STATE["open_position"] else True))
            gates.append((f"RR {rr:.2f} Need {CONFIG['MIN_RR']}", rr >= CONFIG["MIN_RR"] if not STATE["open_position"] else True))
            gates.append((f"EV ${ev:.4f} > 0", ev > 0 if not STATE["open_position"] else True))
            gates.append((f"LossControl", ok_control))
            all_pass = all(p for _, p in gates); failed = [n for n, p in gates if not p]
            bal_show = STATE["real_balance"] if mode == "REAL" else STATE["balance"]
            log(f"MODE {mode} | Long {longs} Short {shorts} DEST {dest} Cert {certainty:.0f}% Agree {agree}/{decided} {mode_str} {'Pass True' if all_pass else 'Pass False'}")
            log(f"LIVE MACRO DXY {macro['DXY_CHG']:.2f}% NQ {macro['NQ_CHG']:.2f}% SPX {macro['SPX_CHG']:.2f}% GOLD {macro['GOLD_CHG']:.2f}% OI {macro['OI_CHG']:.2f}%")
            log(f"LIQ MAP LongLiq ${long_liq:,.0f} ShortLiq ${short_liq:,.0f} | Asia Low ${asia_low:,.0f} Asia High ${asia_high:,.0f} | Hunt {asian_hunt}")
            log(f"SESSION {session_name} Reopen Hunt {session_hunt} | SL {'WIDE 1.20%' if use_wide else 'NORMAL 0.85%'} | MENTAL SL Hidden + Wick Protection + FLIP 75%")
            log(f"Qty {qty} Bal ${bal_show:.2f} DayStart ${STATE.get('day_start_balance', bal_show):.2f} Pos ${pos:.0f} Margin ${margin:.2f} Lev {CONFIG['LEVERAGE']}x FIXED | Price ${price:.0f} MentalSL ${mental_sl:.0f} RealBackup ${real_sl:.0f} TP ${tp:.0f}")
            log(f"FEES ${fees:.4f} + SLIPPAGE ${slip:.4f} = Total ${total_cost:.4f} TP Profit ${tp_profit:.4f} >=3x {be} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} FLIP{STATE['flips']} DOUBLE{STATE['doubles']} Trades {STATE['trades_today']}/20 Losses {STATE['losses_today']}/5 NEVER_STOP True")
            if STATE["open_position"] and not flipped:
                log(f"HOLDING {STATE['open_position']['side']} - BE/Trailing/Flip dey manage am, no candle close loss")
            elif not all_pass and not STATE["open_position"]:
                log(f"BLOCK/WARY: {'; '.join(failed)} {control_reason} - Bot still alive, will trade next cycle")
            elif all_pass and not STATE["open_position"]:
                log(f"TRADE SIGNAL - {mode} {dest} {mode_str} Entry ${price:.0f} MentalSL ${mental_sl:.0f} RealBackup ${real_sl:.0f} TP ${tp:.0f} Qty {qty} {'WIDE SL' if use_wide else ''} Lev {CONFIG['LEVERAGE']}x")
                if mode == "REAL":
                    ok = place_real_order(dest, price, mental_sl, real_sl, tp, qty)
                    if not ok: log("REAL ORDER FAILED - No trade opened, will retry next cycle"); time.sleep(CONFIG["POLL_SEC"]); continue
                STATE["open_position"] = {"side": dest, "entry": price, "sl": mental_sl, "real_sl": real_sl, "tp": tp, "certainty": certainty, "is_sure": is_sure, "be_done": False, "mental_warned": False}; STATE["trades_today"] += 1; STATE["last_trade_time"] = now_utc(); log(f"ORDER PLACED ({mode}) {dest} - Mental SL Hidden + Wick Protection + BE/Trailing/Flip ACTIVE - LONG+SHORT Ready")
            if (now_utc() - last_heartbeat).total_seconds() > CONFIG["HEARTBEAT_MIN"] * 60: log(f"HEARTBEAT OK - MODE {mode} - Bal ${bal_show:.2f} PnL ${STATE['pnl']:.2f}"); last_heartbeat = now_utc()
            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e: log(f"ERROR {e}"); time.sleep(10)
if __name__ == "__main__": main()
