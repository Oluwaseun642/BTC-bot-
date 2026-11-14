# ============================================================
# BTC SWEEP BOT - V13.8 FINAL - MAIN + SIDE HUSTLE + LIVE WORLDWIDE
# MAIN: Certainties / News = Lifestyle | 80%+ Agree 5+ | MaxTrade 20 -> SURE 85-90-95% | MaxLoss 5 -> SURE 90-95% | Cooldown 5min
# Balance -2% -> Calm 20min -> Back to Normal 80%
# LONG + SHORT BOTH - Certainty Decide Side, No One-Side Bias
# FLIP Boss + MentalSL FRONT + RealBackup BEHIND $75 GAP + BE Ladder + Trailing Early
# ADD-ON: Hunt No Be Flip, Bal >= $10 REAL, Once Per Position, Same Side Same Qty - ONLY WHEN MAIN DEY RUN
# SIDE HUSTLE: Liq Map Hunt - ONLY WHEN NO POSITION + MAIN FAIL + Cert 60-79% + Price Move + Hunt Confirm - TP 1.5x Quick
# LIVE WORLDWIDE: NO HARDCODE, NO FAKE NEUTRAL - UNKNOWN != NEUTRAL - If 1 source fail, check elsewhere same cycle
# CROSS MARGIN ON - Whole Balance Back Position + Add-on + Side Hustle
# QTY: First REAL 0.002 50x | After: +0.005 per +$8 from $10 Upwards | $9-10 Raise = Still +0.005 Once
# Balance Checked After EVERY Trade + Every Cycle | Qty Fit Go Up Or Down
# Paper $4.75 till Sun 8:30pm WAT (19:30 UTC 15 Nov) -> Auto REAL, Ready for Asian
# ============================================================

import time, requests, hmac, hashlib, os, threading
from datetime import datetime, timezone

# ================= FLASK =================
try:
    from flask import Flask
    _flask_app = Flask(__name__)
    @_flask_app.route("/")
    def _health(): return "BOT ALIVE V13.8 - PAPER till Sun 8:30pm WAT, then REAL", 200
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

# ================= CONFIG =================
CONFIG = {
    "SYMBOL": "BTCUSDT", "LEVERAGE": 50, "PAPER_QTY": 0.002,
    "REAL_RISK_MARGIN_PCT": 0.10, "REAL_MIN_QTY": 0.002, "REAL_MAX_QTY": 0.100,
    "QTY_BASE": 0.002, "QTY_STEP": 0.005, "QTY_BASE_BAL": 10.0, "QTY_STEP_BAL": 8.0,
    "MIN_CERTAINTY_NORMAL": 80.0, "MIN_AGREE_NORMAL": 5, "MIN_SCORE_NORMAL": 0.75,
    "TOTAL_SIGNALS": 8, "SURE_CERTAINTY": 95.0, "SURE_AGREE": 6, "TP_MULT_NORMAL": 2.0, "TP_MULT_SURE": 3.5,
    "NEWS_ENABLED": True, "MIN_CERTAINTY_NEWS": 75.0, "MIN_AGREE_NEWS": 5, "MIN_SCORE_NEWS": 0.60,
    "SL_PCT": 0.0085, "WICK_BUFFER_PCT": 0.0011,
    "WIDE_SL_ENABLED": True, "WIDE_SL_PCT": 0.0120,
    "MENTAL_SL_ENABLED": True, "MENTAL_SL_HIDDEN": True,
    "FLIP_ENABLED": True, "FLIP_CERTAINTY": 75.0, "FLIP_AGREE": 5,
    "NEVER_STOP": True,
    "MAX_TRADES_PER_DAY": 20, "MAX_LOSSES_PER_DAY": 5,
    "AFTER_MAX_TRADE_CERTAINTY": 85.0, "AFTER_MAX_LOSS_CERTAINTY": 90.0,
    "COOLDOWN_AFTER_LOSS_MIN": 5, "AFTER_LOSS_CERTAINTY": 85.0, "AFTER_LOSS_AGREE": 6, "COOLDOWN_AFTER_WIN_MIN": 2,
    "MAX_DAILY_LOSS_PCT": 0.02, "DAILY_LOSS_CALM_MIN": 20, "CALM_CERTAINTY": 85.0,
    "ADDON_DOUBLE_ENABLED": True, "ADDON_DOUBLE_BALANCE": 10.0, "ADDON_DOUBLE_MULT": 2.0,
    "ADDON_ENABLED": True, "ADDON_MIN_BAL": 10.0, "ADDON_MAX_PER_POSITION": 1,
    "CROSS_MARGIN_ENABLED": True, "MARGIN_MODE": "CROSS",
    "SL_GAP_USD": 75.0,
    "TRAILING_ENABLED": True, "TRAIL_START_PCT": 0.0005,
    "TRAIL_STEP_1": 0.008, "TRAIL_DIST_1": 0.004, "TRAIL_STEP_2": 0.012, "TRAIL_DIST_2": 0.006, "TRAIL_STEP_3": 0.020, "TRAIL_DIST_3": 0.008,
    "BE_OVER_FEES": True, "BE_TRIGGER_PCT": 0.0035, "FEE_RATE": 0.0006, "SLIPPAGE_PCT": 0.0005, "BE_BUFFER_PCT": 0.0024,
    "BE_LADDER_ENABLED": True, "BE_LADDER_STEP_PCT": 0.0035, "BE_LADDER_MAX_LEVEL": 10,
    "MIN_TP_OVER_FEES": 3.0, "MIN_RR": 1.8, "MIN_WINPROB": 52.0, "POLL_SEC": 5, "HEARTBEAT_MIN": 10,
    "AUTO_SWITCH_UTC": datetime(2026, 11, 15, 19, 30, tzinfo=timezone.utc), "BYBIT_BASE": "https://api.bybit.com",
    "ASIAN_ENABLED": True, "ASIAN_START_HOUR_UTC": 0, "ASIAN_END_HOUR_UTC": 8, "ASIAN_SWEEP_BUFFER_PCT": 0.0015,
    "SESSION_HUNT_ENABLED": True, "SESSIONS": [("ASIA", 0, 0), ("LONDON", 7, 0), ("NEWYORK", 13, 30)], "SESSION_HUNT_WINDOW_MIN": 30,
    "SIDE_HUSTLE_ENABLED": True, "SIDE_MIN_CERT": 60.0, "SIDE_MAX_CERT": 79.9, "SIDE_MIN_AGREE": 3,
    "SIDE_TP_MULT": 1.5, "SIDE_MIN_MOVE_PCT": 0.008, "SIDE_COOLDOWN_MIN": 10, "SIDE_MIN_RR": 1.2,
}
API_KEY = os.getenv("BYBIT_API_KEY", ""); API_SECRET = os.getenv("BYBIT_API_SECRET", "")
STATE = {"mode": "PAPER", "balance": 4.75, "real_balance": 0.0, "day_start_balance": 4.75, "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0, "flips": 0, "doubles": 0, "addons": 0, "side_hustles": 0, "trades_today": 0, "losses_today": 0, "last_loss_time": None, "last_trade_time": None, "last_side_hustle_time": None, "calm_until": None, "day": datetime.now(timezone.utc).date(), "open_position": None, "last_price": 0.0, "first_real_trade_done": False, "cross_margin_set": False, "last_qty": 0.002, "last_balance_checked": 0.0, "last_macro": {"DXY_CHG": 0.0, "NQ_CHG": 0.0, "SPX_CHG": 0.0, "GOLD_CHG": 0.0, "OI_CHG": 0.0}, "last_liq_map": {"long_liq": 0.0, "short_liq": 0.0, "asia_low": 0.0, "asia_high": 0.0, "hunt": "NONE"}, "last_session": "NONE"}
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
def get_current_balance(mode): return STATE["real_balance"] if mode == "REAL" else STATE["balance"]
def refresh_balance(mode, reason="CYCLE"):
    if mode == "REAL":
        old = STATE["real_balance"]; new = get_real_balance()
        if abs(new - old) > 0.001: log(f"BALANCE CHECK [{reason}]: REAL ${old:.2f} -> ${new:.2f} | Next Qty go recalc by +$8 tier")
        STATE["last_balance_checked"] = new; return new
    else:
        STATE["last_balance_checked"] = STATE["balance"]; return STATE["balance"]
def set_cross_margin():
    if not CONFIG["CROSS_MARGIN_ENABLED"]: return True
    if STATE.get("cross_margin_set"): return True
    if STATE["mode"] == "PAPER":
        log("CROSS MARGIN MODE: PAPER - Whole balance dey back position + Add-on + Side Hustle (LONG & SHORT)"); STATE["cross_margin_set"] = True; return True
    if not API_KEY: return False
    try:
        res = bybit_post("/v5/position/switch-margin-mode", {"category": "linear", "symbol": CONFIG["SYMBOL"], "tradeMode": 0, "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])}); log(f"CROSS MARGIN SET: Bybit tradeMode 0 = CROSS | Lev {CONFIG['LEVERAGE']}x | {res}"); STATE["cross_margin_set"] = True; return True
    except Exception as e: log(f"CROSS MARGIN SET ERROR {e} - will retry"); return False
def calc_dynamic_fees(price, qty):
    pos = qty * price; fees = pos * CONFIG["FEE_RATE"] * 2; slip = pos * CONFIG["SLIPPAGE_PCT"] * 2; total = fees + slip; fee_dist = total / qty if qty else 0
    return pos, fees, slip, total, fee_dist
def calc_real_backup(entry, side, qty, profit_lock_usd=3.0):
    _, _, _, total, fee_dist = calc_dynamic_fees(entry, qty); lock = fee_dist + profit_lock_usd
    if side == "LONG": return round(entry + lock, 1), round(total, 4), round(fee_dist, 1)
    else: return round(entry - lock, 1), round(total, 4), round(fee_dist, 1)
def calc_mental_from_real(real_backup, side):
    gap = CONFIG["SL_GAP_USD"]
    if side == "LONG": return round(real_backup + gap, 1)
    else: return round(real_backup - gap, 1)
def calc_real_from_initial_mental(initial_mental, side):
    gap = CONFIG["SL_GAP_USD"]
    if side == "LONG": return round(initial_mental - gap, 1)
    else: return round(initial_mental + gap, 1)
def get_dynamic_qty(price, mode):
    if mode == "PAPER":
        bal = refresh_balance(mode, "QTY-CALC-PAPER"); base_qty = CONFIG["PAPER_QTY"]
        if CONFIG["ADDON_DOUBLE_ENABLED"] and bal > CONFIG["ADDON_DOUBLE_BALANCE"]:
            doubled = min(round(base_qty * 2, 3), 0.020)
            if doubled != base_qty: log(f"ADD-ON DOUBLE PAPER: Balance ${bal:.2f} > $10 - Qty {base_qty} -> {doubled} (Paper test only, REAL Add-on na second trade)"); STATE["doubles"] += 1
            STATE["last_qty"] = doubled; return doubled
        STATE["last_qty"] = base_qty; return base_qty
    bal = refresh_balance(mode, "QTY-CALC-REAL")
    if not STATE.get("first_real_trade_done", False):
        log(f"FIRST REAL TRADE: Qty 0.002 with 50x Lev CROSS Margin - Testing real water small-small | Bal ${bal:.2f}"); STATE["last_qty"] = 0.002; return 0.002
    if bal < CONFIG["QTY_BASE_BAL"]: qty = CONFIG["QTY_BASE"]; steps = 0
    else: steps = int((bal - CONFIG["QTY_BASE_BAL"]) // CONFIG["QTY_STEP_BAL"]); qty = round(CONFIG["QTY_BASE"] + steps * CONFIG["QTY_STEP"], 3)
    qty = min(qty, CONFIG["REAL_MAX_QTY"])
    if qty != STATE.get("last_qty", 0.002): log(f"QTY TIER CHANGE: Bal ${bal:.2f} -> Steps {steps} x $8 = Qty {STATE.get('last_qty', 0.002)} -> {qty}")
    else: log(f"QTY TIER CHECK: Bal ${bal:.2f} -> Steps {steps} = Qty {qty} (Hold previous Qty till next +$8 complete, next tier at ${CONFIG['QTY_BASE_BAL'] + (steps+1)*CONFIG['QTY_STEP_BAL']:.0f})")
    STATE["last_qty"] = qty; return qty
def place_real_order(side, price, mental_sl, real_sl_backup, tp, qty, is_addon=False, is_side=False):
    if not API_KEY or not API_SECRET: log("REAL ORDER BLOCKED: No API keys"); return False
    try:
        set_cross_margin(); bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": CONFIG["SYMBOL"], "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        res = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Buy" if side == "LONG" else "Sell", "orderType": "Market", "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(real_sl_backup, 1)), "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice", "timeInForce": "GTC"})
        tag = "ADD-ON" if is_addon else ("SIDE-HUSTLE" if is_side else "MAIN")
        log(f"REAL ORDER PLACED [{tag}] {side} Qty {qty} Entry ~${price:.0f} MentalSL(FRONT) ${mental_sl:.0f} RealSL(BEHIND) ${real_sl_backup:.0f} GAP $75 TP ${tp:.0f} Lev {CONFIG['LEVERAGE']}x CROSS Bybit: {res}"); return res.get("retCode") == 0
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

# ========== V13.8 LIVE WORLDWIDE - NO HARDCODE, NO FAKE NEUTRAL ==========
def fetch_live_multi(symbols_yahoo, symbols_stooq):
    for sym in symbols_yahoo:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}; r = requests.get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=1m", headers=headers, timeout=5); meta = r.json()["chart"]["result"][0]["meta"]; price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0); prev = float(meta.get("previousClose") or meta.get("chartPreviousClose") or price)
                if price and prev and price != prev: return round((price - prev) / prev * 100, 3), f"Yahoo:{sym}"
            except: continue
    for s in symbols_stooq:
        try:
            r = requests.get(f"https://stooq.com/q/d/l/?s={s}&i=d", timeout=5); lines = [l.strip().split(",") for l in r.text.strip().splitlines() if "," in l]; closes = []
            for row in lines[1:]:
                try: closes.append(float(row[4]))
                except: pass
            if len(closes) >= 2 and closes[-2]: return round((closes[-1]-closes[-2])/closes[-2]*100, 3), f"Stooq:{s}"
        except: continue
    return None, "FAIL"
def get_price_live():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=5); p = float(r.json()["result"]["list"][0]["lastPrice"]); STATE["last_price"] = p; return p, "Bybit"
    except: pass
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5); p = float(r.json()["price"]); STATE["last_price"] = p; return p, "Binance"
    except: pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5); p = float(r.json()["bitcoin"]["usd"]); STATE["last_price"] = p; return p, "CoinGecko"
    except: pass
    if STATE["last_price"]: return STATE["last_price"], "LastPrice-Cached"
    return 0.0, "NO-PRICE"
def get_klines_live(interval, limit):
    # Bybit -> Binance fallback, same format
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}", timeout=5); kl = list(reversed(r.json()["result"]["list"])); return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "time": int(x[0])} for x in kl], "Bybit"
    except: pass
    try:
        b_interval = "1m" if interval == "1" else "15m"; r = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={b_interval}&limit={limit}", timeout=5); kl = r.json(); return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "time": int(x[0])} for x in kl], "Binance"
    except: pass
    return [], "FAIL"
def get_klines(limit=200):
    kl, _ = get_klines_live("15", limit); return kl
def get_klines_1m(limit=20):
    kl, _ = get_klines_live("1", limit); return kl
def get_macro_live():
    dxy, src_dxy = fetch_live_multi(["DX-Y.NYB", "DX=F", "UUP"], ["dx.f"])
    nq, src_nq = fetch_live_multi(["NQ=F", "^NDX", "QQQ"], ["nq.f"])
    spx, src_spx = fetch_live_multi(["ES=F", "^SPX", "SPY"], ["es.f"])
    gold, src_gold = fetch_live_multi(["GC=F", "GLD"], ["gc.f"])
    oi_chg = None; oi_src = "FAIL"
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5); lst = r.json()["result"]["list"]; oi_chg = (float(lst[-1]["openInterest"]) - float(lst[0]["openInterest"])) / float(lst[0]["openInterest"]) * 100; oi_src = "Bybit"
    except: oi_chg = None
    macro = {}
    for k, v, src in [("DXY_CHG", dxy, src_dxy), ("NQ_CHG", nq, src_nq), ("SPX_CHG", spx, src_spx), ("GOLD_CHG", gold, src_gold), ("OI_CHG", oi_chg, oi_src)]:
        if v is None:
            macro[k] = STATE["last_macro"].get(k, 0.0); macro[k+"_STATUS"] = "UNKNOWN"; macro[k+"_SRC"] = "UNKNOWN-Using-Last"
        else:
            macro[k] = v; macro[k+"_STATUS"] = "LIVE"; macro[k+"_SRC"] = src; STATE["last_macro"][k] = v
    print(f"LIVE SRC DXY:{macro['DXY_CHG_SRC']} {macro['DXY_CHG_STATUS']} NQ:{macro['NQ_CHG_SRC']} {macro['NQ_CHG_STATUS']} SPX:{macro['SPX_CHG_SRC']} {macro['SPX_CHG_STATUS']} GOLD:{macro['GOLD_CHG_SRC']} {macro['GOLD_CHG_STATUS']} OI:{macro['OI_CHG_SRC']} {macro['OI_CHG_STATUS']}", flush=True); return macro
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
    else:
        if not klines_1m: hunt = "UNKNOWN"
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
            elif not klines_1m: return "UNKNOWN", name
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
    if macro.get("DXY_CHG_STATUS") == "UNKNOWN": signals.append(("DXY_LEVEL", "UNKNOWN"))
    elif macro["DXY_CHG"] > 0.10: signals.append(("DXY_LEVEL", "SHORT"))
    elif macro["DXY_CHG"] < -0.10: signals.append(("DXY_LEVEL", "LONG"))
    else: signals.append(("DXY_LEVEL", "NEUTRAL"))
    if macro.get("NQ_CHG_STATUS") == "UNKNOWN": signals.append(("NQ_MOMENTUM", "UNKNOWN"))
    elif macro["NQ_CHG"] > 0.20: signals.append(("NQ_MOMENTUM", "LONG"))
    elif macro["NQ_CHG"] < -0.20: signals.append(("NQ_MOMENTUM", "SHORT"))
    else: signals.append(("NQ_MOMENTUM", "NEUTRAL"))
    if macro.get("SPX_CHG_STATUS") == "UNKNOWN": signals.append(("SPX_MOMENTUM", "UNKNOWN"))
    elif macro["SPX_CHG"] > 0.20: signals.append(("SPX_MOMENTUM", "LONG"))
    elif macro["SPX_CHG"] < -0.20: signals.append(("SPX_MOMENTUM", "SHORT"))
    else: signals.append(("SPX_MOMENTUM", "NEUTRAL"))
    if macro.get("GOLD_CHG_STATUS") == "UNKNOWN": signals.append(("GOLD_AFTER_SWEEP", "UNKNOWN"))
    elif macro["GOLD_CHG"] > 0.50: signals.append(("GOLD_AFTER_SWEEP", "SHORT"))
    elif macro["GOLD_CHG"] < -0.30: signals.append(("GOLD_AFTER_SWEEP", "LONG"))
    else: signals.append(("GOLD_AFTER_SWEEP", "NEUTRAL"))
    if macro.get("OI_CHG_STATUS") == "UNKNOWN": signals.append(("OI_DIVERGENCE", "UNKNOWN"))
    elif klines_1m and len(klines_1m) >= 5:
        pc = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
        if macro["OI_CHG"] > 0.5 and pc < -0.2: signals.append(("OI_DIVERGENCE", "SHORT"))
        elif macro["OI_CHG"] < -0.5 and pc > 0.2: signals.append(("OI_DIVERGENCE", "LONG"))
        else: signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    else: signals.append(("OI_DIVERGENCE", "UNKNOWN"))
    if not klines_1m: signals.append(("LIQ_SWEEP", "UNKNOWN"))
    elif len(klines_1m) >= 3:
        last = klines_1m[-1]; wd = last["close"] - last["low"]; wu = last["high"] - last["close"]; thr = price * 0.002
        if wd > thr and wd > wu * 1.5: signals.append(("LIQ_SWEEP", "LONG"))
        elif wu > thr and wu > wd * 1.5: signals.append(("LIQ_SWEEP", "SHORT"))
        else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
    else: signals.append(("LIQ_SWEEP", "UNKNOWN"))
    signals.append(("ASIAN_LIQ_HUNT", asian_hunt if asian_hunt in ("LONG","SHORT") else ("UNKNOWN" if asian_hunt=="UNKNOWN" else "NEUTRAL")))
    signals.append(("SESSION_REOPEN_HUNT", session_hunt if session_hunt in ("LONG","SHORT") else ("UNKNOWN" if session_hunt=="UNKNOWN" else "NEUTRAL")))
    return signals
def decide(signals):
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT"); unknowns = sum(1 for _, v in signals if v == "UNKNOWN"); decided = longs + shorts
    if longs > shorts: dest, agree = "LONG", longs
    elif shorts > longs: dest, agree = "SHORT", shorts
    else: dest, agree = "NONE", 0
    return dest, agree, decided, longs, shorts, unknowns, (agree / decided * 100) if decided else 0
def calc_score(signals, dest, macro, is_news):
    _, agree, decided, _, _, _, certainty = decide(signals); base = (certainty / 100) * 1.0; align = 0
    if dest == "LONG" and macro["NQ_CHG"] > 0 and macro["SPX_CHG"] > 0: align = 0.4
    if dest == "SHORT" and macro["DXY_CHG"] > 0: align = 0.3
    return round(base + align + (0.4 if is_news else 0), 2)
def calc_sl_tp(price, side, klines, is_sure, session_hunt_active, is_side=False):
    use_wide = CONFIG["WIDE_SL_ENABLED"] and (is_sure or session_hunt_active) and not is_side
    sl_pct = CONFIG["WIDE_SL_PCT"] if use_wide else CONFIG["SL_PCT"]; sl_dist = price * sl_pct; wick_buf = price * CONFIG["WICK_BUFFER_PCT"]
    if klines:
        if side == "LONG": initial_mental = min(price - sl_dist, min(c["low"] for c in klines[-15:]) - wick_buf); initial_mental = max(initial_mental, price * 0.985)
        else: initial_mental = max(price + sl_dist, max(c["high"] for c in klines[-15:]) + wick_buf); initial_mental = min(initial_mental, price * 1.015)
    else: initial_mental = price - sl_dist if side == "LONG" else price + sl_dist
    real_sl = calc_real_from_initial_mental(initial_mental, side); sl_f = abs(price - initial_mental); mult = CONFIG["SIDE_TP_MULT"] if is_side else (CONFIG["TP_MULT_SURE"] if is_sure else CONFIG["TP_MULT_NORMAL"]); tp_dist = sl_f * mult; tp = price + tp_dist if side == "LONG" else price - tp_dist
    return round(initial_mental, 1), round(real_sl, 1), round(tp, 1), round(sl_f, 1), round(tp_dist, 1), use_wide
def calc_fees_ev(price, sl_dist, tp_dist, winprob, qty):
    pos, fees, slip, total_cost, _ = calc_dynamic_fees(price, qty); margin = pos / CONFIG["LEVERAGE"]; tp_profit = (qty * tp_dist) - total_cost; sl_loss = (qty * sl_dist) + total_cost; rr = tp_dist / sl_dist if sl_dist else 0; ev = (winprob/100 * tp_profit) - ((1-winprob/100) * sl_loss); be = tp_profit >= (total_cost * CONFIG["MIN_TP_OVER_FEES"]); return pos, margin, fees, slip, total_cost, tp_profit, sl_loss, rr, ev, be
def get_dynamic_thresholds(is_news, just_lost, mode):
    bal = get_current_balance(mode); day_start = STATE.get("day_start_balance", bal) or bal; daily_dd = (bal - day_start) / day_start if day_start else 0
    if daily_dd <= -CONFIG["MAX_DAILY_LOSS_PCT"]:
        if STATE.get("calm_until") is None:
            from datetime import timedelta
            STATE["calm_until"] = now_utc() + timedelta(minutes=CONFIG["DAILY_LOSS_CALM_MIN"]); log(f"DAILY GUARD: Balance drop -2% (${day_start:.2f} -> ${bal:.2f}) - Calm 20min, need 85% only, then back to Normal 80%")
        if now_utc() < STATE["calm_until"]: return CONFIG["CALM_CERTAINTY"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "CALM -2% 20min"
        else: STATE["calm_until"] = None; return CONFIG["MIN_CERTAINTY_NORMAL"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "CALM OVER - Back to Normal 80%"
    if STATE["losses_today"] >= CONFIG["MAX_LOSSES_PER_DAY"]: return CONFIG["AFTER_MAX_LOSS_CERTAINTY"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "MAX LOSS 5 - Need 90-95% (Try 90% first)"
    if STATE["trades_today"] >= CONFIG["MAX_TRADES_PER_DAY"]: return CONFIG["AFTER_MAX_TRADE_CERTAINTY"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "MAX TRADE 20 - Need 85-90-95% (Try 85% first)"
    if just_lost: return CONFIG["AFTER_LOSS_CERTAINTY"], CONFIG["AFTER_LOSS_AGREE"], CONFIG["MIN_SCORE_NORMAL"], "AFTER LOSS - 5min Cooldown + 85%"
    if is_news: return CONFIG["MIN_CERTAINTY_NEWS"], CONFIG["MIN_AGREE_NEWS"], CONFIG["MIN_SCORE_NEWS"], "NEWS HUNTER"
    return CONFIG["MIN_CERTAINTY_NORMAL"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"], "NORMAL"
def check_loss_control():
    today = now_utc().date()
    if STATE["day"] != today:
        STATE["day"] = today; STATE["trades_today"] = 0; STATE["losses_today"] = 0; STATE["last_loss_time"] = None; STATE["calm_until"] = None; STATE["day_start_balance"] = STATE["balance"] if STATE["mode"] == "PAPER" else STATE["real_balance"]
    if STATE["open_position"]: return False, "BLOCK: Already in position - Flip check still runs"
    if STATE["last_loss_time"]:
        mins = (now_utc() - STATE["last_loss_time"]).total_seconds() / 60
        if mins < CONFIG["COOLDOWN_AFTER_LOSS_MIN"]: return False, f"WARY: Cooldown {mins:.0f}/{CONFIG['COOLDOWN_AFTER_LOSS_MIN']}min (5min only)"
    return True, ""
def check_side_hustle(price, klines_1m, klines_15m, dest, certainty, agree, main_pass, asian_hunt, session_hunt, long_liq, short_liq, macro):
    if not CONFIG["SIDE_HUSTLE_ENABLED"]: return False, "NONE", ""
    if STATE["open_position"]: return False, "NONE", "Side Hustle BLOCK: Position already open (MAIN/Add-on dey run)"
    if main_pass: return False, "NONE", "Side Hustle SKIP: MAIN pass, MAIN be lifestyle"
    if STATE.get("last_side_hustle_time"):
        mins = (now_utc() - STATE["last_side_hustle_time"]).total_seconds() / 60
        if mins < CONFIG["SIDE_COOLDOWN_MIN"]: return False, "NONE", f"Side Hustle Cooldown {mins:.0f}/{CONFIG['SIDE_COOLDOWN_MIN']}min"
    if not (CONFIG["SIDE_MIN_CERT"] <= certainty <= CONFIG["SIDE_MAX_CERT"]): return False, "NONE", f"Side Hustle Cert {certainty:.0f}% no be 60-79% (MAIN fail range)"
    if agree < CONFIG["SIDE_MIN_AGREE"]: return False, "NONE", f"Side Hustle Agree {agree} < 3"
    if dest not in ("LONG", "SHORT"): return False, "NONE", "Side Hustle No Dest"
    hunt_ok = (asian_hunt == dest or session_hunt == dest); liq_ok = (long_liq > short_liq) if dest == "LONG" else (short_liq > long_liq)
    if not (hunt_ok or liq_ok): return False, "NONE", f"Side Hustle No Hunt: Asian {asian_hunt} Session {session_hunt} LongLiq ${long_liq:,.0f} ShortLiq ${short_liq:,.0f} no confirm {dest}"
    move_ok = False; move_pct = 0.0
    if klines_1m and len(klines_1m) >= 15:
        move_pct = abs(klines_1m[-1]["close"] - klines_1m[-15]["close"]) / klines_1m[-15]["close"] * 100
        if move_pct >= CONFIG["SIDE_MIN_MOVE_PCT"] * 100: move_ok = True
    wick_ok = False
    if klines_15m:
        asia_low, asia_high = get_asian_range(klines_15m)
        if klines_1m:
            last = klines_1m[-1]
            if dest == "LONG" and asia_low and last["low"] < asia_low and last["close"] > asia_low: wick_ok = True
            if dest == "SHORT" and asia_high and last["high"] > asia_high and last["close"] < asia_high: wick_ok = True
    if not (move_ok or wick_ok): return False, "NONE", f"Side Hustle No Move: Move {move_pct:.2f}% < 0.80% and No Wick Sweep"
    if abs(macro["OI_CHG"]) > 2.0: return False, "NONE", f"Side Hustle OI too high {macro['OI_CHG']:.2f}% - na real trend, no be hunt"
    reason = f"SIDE HUSTLE READY {dest}: MAIN fail Cert {certainty:.0f}% (60-79) Agree {agree} | Hunt Asian {asian_hunt} Session {session_hunt} Liq Long ${long_liq:,.0f} Short ${short_liq:,.0f} | Move {move_pct:.2f}% Wick {wick_ok} | Join body chop quick"
    return True, dest, reason
def record_close(side, entry, close_price, qty, reason, be_level=0):
    _, fees, slip, total, _ = calc_dynamic_fees(entry, qty); gross = (close_price - entry) * qty if side == "LONG" else (entry - close_price) * qty; net = gross - total; old_bal = STATE["balance"] if STATE["mode"] == "PAPER" else STATE["real_balance"]
    if STATE["mode"] == "PAPER": STATE["balance"] += net; STATE["pnl"] += net
    else: STATE["pnl"] += net
    if reason == "TP": STATE["wins"] += 1; log(f"TP HIT +${net:.2f} (Gross ${gross:.2f} - Fees ${total:.4f}) - Closed {side} at ${close_price:.0f} | Bal ${old_bal:.2f} -> ${old_bal+net:.2f} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']}")
    elif reason == "BE": STATE["breakevens"] += 1; log(f"BE{be_level} HIT +${net:.2f} (Gross ${gross:.2f} - Fees ${total:.4f}) - Closed {side} at ${close_price:.0f} | Bal ${old_bal:.2f} -> ${old_bal+net:.2f} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} - BE counts, never $0")
    elif net > 0: STATE["wins"] += 1; log(f"SMALL WIN +${net:.2f} (Gross ${gross:.2f} - Fees ${total:.4f}) - Closed {side} at ${close_price:.0f} Reason {reason} | Bal ${old_bal:.2f} -> ${old_bal+net:.2f} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']}")
    elif net < -0.01: STATE["losses"] += 1; STATE["losses_today"] += 1; STATE["last_loss_time"] = now_utc(); log(f"LOSS ${net:.2f} (Gross ${gross:.2f} - Fees ${total:.4f}) - Closed {side} at ${close_price:.0f} Reason {reason} | Bal ${old_bal:.2f} -> ${old_bal+net:.2f} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']}")
    else: STATE["breakevens"] += 1; log(f"BE CLOSE ${net:.2f} - Closed {side} at ${close_price:.0f} Reason {reason} | Bal ${old_bal:.2f} -> ${old_bal+net:.2f}")
    STATE["open_position"] = None; new_bal = refresh_balance(STATE["mode"], f"AFTER-CLOSE-{reason}"); log(f"BALANCE AFTER TRADE: ${new_bal:.2f} - Next Qty go check if e fit higher step (+0.005) or lesser step"); return net
def is_real_reversal_confirmed(flip_dest, flip_certainty, flip_agree, macro, side):
    if flip_dest == "NONE" or flip_dest == side: return False
    if not (flip_certainty >= CONFIG["FLIP_CERTAINTY"] and flip_agree >= CONFIG["FLIP_AGREE"]): return False
    if flip_dest == "LONG": return macro["DXY_CHG"] < 0.05 or macro["NQ_CHG"] > 0
    else: return macro["DXY_CHG"] > 0.05 or macro["NQ_CHG"] < 0
def manage_position(price, klines, qty, flip_dest, flip_certainty, flip_agree, macro):
    if not STATE["open_position"]: return False
    p = STATE["open_position"]; entry = float(p["entry"]); side = p["side"]; profit_pct = (price - entry) / entry if side == "LONG" else (entry - price) / entry; be_level = p.get("be_level", 0); total_qty = p.get("total_qty", qty); is_side = p.get("is_side_hustle", False)
    if CONFIG["FLIP_ENABLED"] and is_real_reversal_confirmed(flip_dest, flip_certainty, flip_agree, macro, side):
        STATE["flips"] += 1; log(f"FLIP {side} -> {flip_dest} CONFIRMED FIRST | Cert {flip_certainty:.0f}% Agree {flip_agree} + Macro DXY {macro['DXY_CHG']:.2f}% NQ {macro['NQ_CHG']:.2f}% - Closing WITH PROFIT at ${price:.0f}, no wait for MentalSL")
        if p.get("be_done"): record_close(side, entry, price, total_qty, "BE", be_level=p.get("be_level", 1))
        else: record_close(side, entry, price, total_qty, "FLIP")
        if STATE["mode"] == "REAL": close_real_position(side, total_qty)
        return True
    hit_tp = (price >= p["tp"] if side == "LONG" else price <= p["tp"])
    if hit_tp:
        if is_side: STATE["last_side_hustle_time"] = now_utc()
        record_close(side, entry, price, total_qty, "TP"); return False
    if CONFIG["BE_LADDER_ENABLED"]:
        target_level = int(profit_pct // CONFIG["BE_LADDER_STEP_PCT"])
        if target_level > be_level and target_level <= CONFIG["BE_LADDER_MAX_LEVEL"]:
            profit_lock = 3.0 * target_level; new_real, total_fees, fee_dist = calc_real_backup(entry, side, total_qty, profit_lock_usd=profit_lock); new_mental = calc_mental_from_real(new_real, side)
            if (side == "LONG" and new_real > p.get("real_sl", -1e9)) or (side == "SHORT" and new_real < p.get("real_sl", 1e9)):
                p["real_sl"] = new_real; p["sl"] = new_mental; p["be_level"] = target_level; p["be_done"] = True; log(f"BE{target_level} STAMPED: MentalSL(FRONT) -> ${new_mental:.0f} | RealBackup(BEHIND) -> ${new_real:.0f} GAP $75 | Entry ${entry:.0f} + Fees ${total_fees:.4f} + ${profit_lock:.0f} profit | Price ${price:.0f} Profit {profit_pct*100:.2f}%"); update_real_sl(p["real_sl"], side)
    if CONFIG["TRAILING_ENABLED"] and profit_pct >= CONFIG["TRAIL_START_PCT"]:
        if profit_pct < CONFIG["BE_TRIGGER_PCT"] and not p.get("be_done"):
            early_real, _, _ = calc_real_backup(entry, side, total_qty, profit_lock_usd=1.0); early_mental = calc_mental_from_real(early_real, side)
            if (side == "LONG" and early_real > p.get("real_sl", -1e9)) or (side == "SHORT" and early_real < p.get("real_sl", 1e9)):
                p["real_sl"] = early_real; p["sl"] = early_mental; log(f"TRAILING EARLY: MentalSL(FRONT) -> ${early_mental:.0f} | RealBackup(BEHIND) -> ${early_real:.0f} GAP $75 | Price ${price:.0f} Profit {profit_pct*100:.2f}% - Lock Fees+$1 before BE1"); update_real_sl(p["real_sl"], side)
        if profit_pct >= CONFIG["TRAIL_STEP_3"]: td = CONFIG["TRAIL_DIST_3"]; label = "Trail 0.80% behind"
        elif profit_pct >= CONFIG["TRAIL_STEP_2"]: td = CONFIG["TRAIL_DIST_2"]; label = "Trail 0.60% behind"
        elif profit_pct >= CONFIG["TRAIL_STEP_1"]: td = CONFIG["TRAIL_DIST_1"]; label = "Trail 0.40% behind"
        else: td = None; label = ""
        if td is not None:
            trail_real = price - (price * td) if side == "LONG" else price + (price * td)
            if p.get("be_done"):
                be_real, _, _ = calc_real_backup(entry, side, total_qty, profit_lock_usd=3.0 * max(1, p.get("be_level", 1)))
                if side == "LONG": trail_real = max(trail_real, be_real)
                else: trail_real = min(trail_real, be_real)
            trail_mental = calc_mental_from_real(trail_real, side)
            if (side == "LONG" and trail_real > p["real_sl"]) or (side == "SHORT" and trail_real < p["real_sl"]):
                p["sl"] = trail_mental; p["real_sl"] = trail_real; log(f"TRAILING {side}: MentalSL(FRONT) -> ${trail_mental:.0f} | RealBackup(BEHIND) -> ${trail_real:.0f} GAP $75 | Price ${price:.0f} Profit {profit_pct*100:.2f}% - {label}"); update_real_sl(p["real_sl"], side)
    if CONFIG["MENTAL_SL_ENABLED"]:
        wick_cross = (price < p["sl"] if side == "LONG" else price > p["sl"])
        if wick_cross:
            if not p.get("mental_warned"): log(f"MENTAL SL FRONT WICK: Price wicked past MentalSL(FRONT) ${p['sl']:.0f} - HOLDING, hunt wick ignored, RealBackup(BEHIND) ${p['real_sl']:.0f} still dey protect"); p["mental_warned"] = True
            if CONFIG["ADDON_ENABLED"] and not p.get("addon_done", False) and not is_side:
                bal_now = get_current_balance(STATE["mode"])
                if STATE["mode"] == "PAPER": bal_now = STATE["balance"]
                is_hunt_not_flip = (flip_dest == side or flip_dest == "NONE"); still_certain = (flip_certainty >= 80.0 and flip_agree >= 5) if flip_dest == side else False
                if flip_dest == "NONE":
                    if side == "LONG": still_certain = (macro["DXY_CHG"] < 0.10 and macro["NQ_CHG"] > -0.10)
                    else: still_certain = (macro["DXY_CHG"] > -0.10 and macro["NQ_CHG"] < 0.10)
                if bal_now >= CONFIG["ADDON_MIN_BAL"] and is_hunt_not_flip and still_certain:
                    log(f"ADD-ON TRIGGER {side}: MM Hunt against {side}, No Be Flip, Bal ${bal_now:.2f} >= $10, Dest still {side} - Adding ONE more {side} Qty {qty} to chop double when market return to original destination")
                    if STATE["mode"] == "REAL":
                        ok = place_real_order(side, price, p["sl"], p["real_sl"], p["tp"], qty, is_addon=True)
                        if ok: p["addon_done"] = True; p["addon_qty"] = qty; p["total_qty"] = round(total_qty + qty, 3); STATE["addons"] += 1; log(f"ADD-ON PLACED {side} Qty {qty} Total Qty Now {p['total_qty']} CROSS Margin - Same TP ${p['tp']:.0f} Same RealBackup ${p['real_sl']:.0f}")
                    else: p["addon_done"] = True; p["addon_qty"] = qty; p["total_qty"] = round(total_qty + qty, 3); STATE["addons"] += 1; log(f"ADD-ON PAPER SIM {side} Qty {qty} Total Qty Now {p['total_qty']} - Same TP ${p['tp']:.0f}")
            real_hit = (price <= p["real_sl"] if side == "LONG" else price >= p["real_sl"])
            if real_hit:
                beyond = abs(price - p["real_sl"]) / entry
                if beyond > 0.002:
                    log(f"REALBACKUP BEHIND HIT + 0.20% BEYOND: Price ${price:.0f} past RealBackup ${p['real_sl']:.0f} - Closing with profit locked (Total Qty {total_qty})")
                    if is_side: STATE["last_side_hustle_time"] = now_utc()
                    if p.get("be_done"): record_close(side, entry, price, total_qty, "BE", be_level=p.get("be_level", 1))
                    else: record_close(side, entry, price, total_qty, "REALBACKUP")
                    if STATE["mode"] == "REAL": close_real_position(side, total_qty)
                    return False
        else: p["mental_warned"] = False
    return False
def main():
    log("BOT V13.8 STARTED - MAIN Lifestyle + SIDE HUSTLE + LIVE WORLDWIDE NO HARDCODE NO FAKE NEUTRAL + ADD-ON + CROSS + LONG+SHORT | Mental FRONT + Real BEHIND $75 + Flip Boss + BE Ladder + Trailing Early + QTY First 0.002 + Step +0.005 per +$8 from $10 + Paper till Sun 8:30pm WAT -> Auto REAL")
    last_heartbeat = now_utc()
    while True:
        try:
            new_mode = get_mode()
            if new_mode != STATE["mode"]:
                STATE["mode"] = new_mode
                if new_mode == "REAL":
                    bal = get_real_balance(); log(f"*** AUTO SWITCH TO REAL *** Sun 8:30pm WAT reached - Real Balance met: ${bal:.2f} USDT - Bot go trade real now, CROSS Margin ON, Asia opening, good boy mode ON ***")
                    if STATE["open_position"]: log("Closing paper position before REAL switch"); STATE["open_position"] = None
            mode = STATE["mode"]; set_cross_margin(); refresh_balance(mode, "CYCLE-START")
            price, price_src = get_price_live()
            if price == 0.0: log("NO PRICE - All sources fail, skip cycle"); time.sleep(CONFIG["POLL_SEC"]); continue
            klines_1m = get_klines_1m(20); klines_15m = get_klines(200); macro = get_macro_live()
            asian_hunt, asia_low, asia_high, long_liq, short_liq = get_asian_hunt(price, klines_15m, klines_1m)
            session_hunt, session_name = get_session_reopen_hunt(price, klines_1m, klines_15m)
            is_news, _, news_reason = get_news_score()
            signals = get_signals(price, macro, klines_1m, asian_hunt, session_hunt)
            dest, agree, decided, longs, shorts, unknowns, certainty = decide(signals)
            unknown_names = [n for n, v in signals if v == "UNKNOWN"]
            score = calc_score(signals, dest, macro, is_news)
            winprob = max(50, min(75, 50 + (certainty - 50) * 0.4))
            just_lost = STATE["last_loss_time"] is not None and (now_utc() - STATE["last_loss_time"]).total_seconds() < 3600
            need_cert, need_agree, need_score, thresh_label = get_dynamic_thresholds(is_news, just_lost, mode)
            is_sure = (certainty >= CONFIG["SURE_CERTAINTY"] and agree >= CONFIG["SURE_AGREE"])
            mode_str = "SURE 95%+ WIDE TP" if is_sure else ("NEWS HUNTER" if is_news else thresh_label)
            qty = get_dynamic_qty(price, mode)
            flipped = False
            if STATE["open_position"]:
                flipped = manage_position(price, klines_1m, qty, dest, certainty, agree, macro)
                if flipped: log(f"FLIP DONE - Next cycle go open new {dest} trade if gates still pass - No candle close loss")
            ok_control, control_reason = check_loss_control()
            session_active = session_hunt in ("LONG","SHORT")
            main_mental = main_real = main_tp = main_sl_dist = main_tp_dist = 0; main_pos = main_margin = main_fees = main_slip = main_total = main_tp_profit = main_sl_loss = main_rr = main_ev = 0; main_be = False; main_use_wide = False
            if dest in ("LONG", "SHORT") and not STATE["open_position"]:
                main_mental, main_real, main_tp, main_sl_dist, main_tp_dist, main_use_wide = calc_sl_tp(price, dest, klines_1m, is_sure, session_active, is_side=False)
                main_pos, main_margin, main_fees, main_slip, main_total, main_tp_profit, main_sl_loss, main_rr, main_ev, main_be = calc_fees_ev(price, main_sl_dist, main_tp_dist, winprob, qty)
            side_mental, side_real, side_tp, side_sl_dist, side_tp_dist, side_use_wide = (0,0,0,0,0,False); side_pos = side_margin = side_fees = side_slip = side_total = side_tp_profit = side_sl_loss = side_rr = side_ev = 0; side_be = False
            if dest in ("LONG", "SHORT") and not STATE["open_position"]:
                side_mental, side_real, side_tp, side_sl_dist, side_tp_dist, side_use_wide = calc_sl_tp(price, dest, klines_1m, False, False, is_side=True)
                side_pos, side_margin, side_fees, side_slip, side_total, side_tp_profit, side_sl_loss, side_rr, side_ev, side_be = calc_fees_ev(price, side_sl_dist, side_tp_dist, winprob, qty)
            if STATE["open_position"]:
                p = STATE["open_position"]; mental_sl = p["sl"]; real_sl = p.get("real_sl", mental_sl); tp = p["tp"]; sl_dist = abs(price - mental_sl); tp_dist = abs(tp - price); pos, margin, fees, slip, total_cost, tp_profit, sl_loss, rr, ev, be = 0,0,0,0,0,0,0,0,0,False; use_wide = False; mental_sl_show = mental_sl; real_sl_show = real_sl; tp_show = tp
            elif dest in ("LONG", "SHORT"):
                mental_sl_show = main_mental; real_sl_show = main_real; tp_show = main_tp; pos = main_pos; margin = main_margin; fees = main_fees; slip = main_slip; total_cost = main_total; tp_profit = main_tp_profit; sl_loss = main_sl_loss; rr = main_rr; ev = main_ev; be = main_be; use_wide = main_use_wide
            else: mental_sl_show = real_sl_show = tp_show = pos = margin = fees = slip = total_cost = tp_profit = sl_loss = rr = ev = 0; be = False; use_wide = False
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
            side_ok, side_dest, side_reason = check_side_hustle(price, klines_1m, klines_15m, dest, certainty, agree, all_pass, asian_hunt, session_hunt, long_liq, short_liq, macro)
            if side_ok:
                if not (side_tp_profit >= (side_total * CONFIG["MIN_TP_OVER_FEES"])): side_ok = False; side_reason += f" | Side Fees FAIL TP ${side_tp_profit:.4f} < 3x ${side_total:.4f}"
                if not (side_rr >= CONFIG["SIDE_MIN_RR"]): side_ok = False; side_reason += f" | Side RR {side_rr:.2f} < 1.2"
                if not ok_control: side_ok = False; side_reason += f" | Side LossControl BLOCK {control_reason}"
            bal_show = STATE["real_balance"] if mode == "REAL" else STATE["balance"]
            log(f"MODE {mode} CROSS | PriceSrc {price_src} | Long {longs} Short {shorts} UNKNOWN {unknowns} {unknown_names} DEST {dest} Cert {certainty:.0f}% Agree {agree}/{decided} {mode_str} MAIN {'Pass True' if all_pass else 'Pass False'} | SIDE {'READY '+side_dest if side_ok else 'No'}")
            log(f"LIVE MACRO DXY {macro['DXY_CHG']:.2f}% [{macro.get('DXY_CHG_SRC')}] NQ {macro['NQ_CHG']:.2f}% [{macro.get('NQ_CHG_SRC')}] SPX {macro['SPX_CHG']:.2f}% [{macro.get('SPX_CHG_SRC')}] GOLD {macro['GOLD_CHG']:.2f}% [{macro.get('GOLD_CHG_SRC')}] OI {macro['OI_CHG']:.2f}% [{macro.get('OI_CHG_SRC')}]")
            log(f"LIQ MAP LongLiq ${long_liq:,.0f} ShortLiq ${short_liq:,.0f} | Asia Low ${asia_low:,.0f} Asia High ${asia_high:,.0f} | Hunt {asian_hunt} | SIDE HUSTLE: {side_reason if side_reason else 'N/A'}")
            log(f"SESSION {session_name} Reopen Hunt {session_hunt} | SL {'WIDE 1.20%' if use_wide else 'NORMAL 0.85%'} | MENTAL FRONT + REAL BEHIND $75 + BE LADDER + FLIP BOSS 75% + ADD-ON Hunt No Flip + SIDE HUSTLE + CROSS")
            log(f"Qty {qty} Bal ${bal_show:.2f} DayStart ${STATE.get('day_start_balance', bal_show):.2f} Pos ${pos:.0f} Margin ${margin:.2f} Lev {CONFIG['LEVERAGE']}x CROSS FIXED | Price ${price:.0f} MentalSL(FRONT) ${mental_sl_show:.0f} RealBackup(BEHIND) ${real_sl_show:.0f} GAP $75 TP ${tp_show:.0f} | SIDE TP ${side_tp:.0f} 1.5x")
            log(f"FEES ${fees:.4f} + SLIPPAGE ${slip:.4f} = Total ${total_cost:.4f} TP Profit ${tp_profit:.4f} >=3x {be} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} FLIP{STATE['flips']} ADDON{STATE['addons']} SIDE{STATE['side_hustles']} DOUBLE{STATE['doubles']} Trades {STATE['trades_today']}/20 Losses {STATE['losses_today']}/5 NEVER_STOP True")
            if STATE["open_position"] and not flipped:
                kind = "SIDE-HUSTLE" if STATE["open_position"].get("is_side_hustle") else "MAIN"
                log(f"HOLDING [{kind}] {STATE['open_position']['side']} BE{STATE['open_position'].get('be_level',0)} AddOn {'YES' if STATE['open_position'].get('addon_done') else 'NO'} TotalQty {STATE['open_position'].get('total_qty', qty)} - Mental FRONT / Real BEHIND / BE Ladder / Flip / Add-on dey manage am")
            elif all_pass and not STATE["open_position"]:
                log(f"TRADE SIGNAL MAIN - {mode} {dest} {mode_str} Entry ${price:.0f} MentalSL(FRONT) ${main_mental:.0f} RealBackup(BEHIND) ${main_real:.0f} TP ${main_tp:.0f} Qty {qty} {'WIDE SL' if main_use_wide else ''} Lev {CONFIG['LEVERAGE']}x CROSS")
                if mode == "REAL":
                    ok = place_real_order(dest, price, main_mental, main_real, main_tp, qty, is_addon=False, is_side=False)
                    if not ok: log("REAL ORDER FAILED - No trade opened, will retry next cycle"); time.sleep(CONFIG["POLL_SEC"]); continue
                    if not STATE.get("first_real_trade_done", False): STATE["first_real_trade_done"] = True; log(f"FIRST REAL TRADE DONE - Next trade go use Step +0.005 per +$8 from $10")
                STATE["open_position"] = {"side": dest, "entry": price, "sl": main_mental, "real_sl": main_real, "tp": main_tp, "certainty": certainty, "is_sure": is_sure, "be_done": False, "be_level": 0, "mental_warned": False, "addon_done": False, "addon_qty": 0.0, "total_qty": qty, "is_side_hustle": False}; STATE["trades_today"] += 1; STATE["last_trade_time"] = now_utc(); log(f"ORDER PLACED MAIN ({mode}) {dest} - Mental FRONT + Real BEHIND $75 + BE Ladder + Trailing Early + Flip Boss + Add-on Ready + CROSS - LONG+SHORT Ready")
            elif side_ok and not STATE["open_position"]:
                log(f"TRADE SIGNAL SIDE-HUSTLE - {mode} {side_dest} Entry ${price:.0f} MentalSL(FRONT) ${side_mental:.0f} RealBackup(BEHIND) ${side_real:.0f} TP ${side_tp:.0f} 1.5x Quick Chop Qty {qty} Lev {CONFIG['LEVERAGE']}x CROSS | Reason: {side_reason}")
                if mode == "REAL":
                    ok = place_real_order(side_dest, price, side_mental, side_real, side_tp, qty, is_addon=False, is_side=True)
                    if not ok: log("REAL SIDE ORDER FAILED - No trade opened, will retry next cycle"); time.sleep(CONFIG["POLL_SEC"]); continue
                    if not STATE.get("first_real_trade_done", False): STATE["first_real_trade_done"] = True; log(f"FIRST REAL TRADE DONE (via Side Hustle) - Next trade go use Step +0.005 per +$8 from $10")
                STATE["open_position"] = {"side": side_dest, "entry": price, "sl": side_mental, "real_sl": side_real, "tp": side_tp, "certainty": certainty, "is_sure": False, "be_done": False, "be_level": 0, "mental_warned": False, "addon_done": True, "addon_qty": 0.0, "total_qty": qty, "is_side_hustle": True}; STATE["trades_today"] += 1; STATE["last_trade_time"] = now_utc(); STATE["side_hustles"] += 1; STATE["last_side_hustle_time"] = now_utc(); log(f"ORDER PLACED SIDE-HUSTLE ({mode}) {side_dest} - Chop Quick 1.5x TP, No Add-on, BE + Trailing still dey protect - LONG+SHORT Ready")
            elif not all_pass and not side_ok and not STATE["open_position"]:
                log(f"BLOCK/WARY MAIN: {'; '.join(failed)} {control_reason} | SIDE: {side_reason} | UNKNOWN: {unknown_names} - Bot still alive, will trade next cycle")
            if (now_utc() - last_heartbeat).total_seconds() > CONFIG["HEARTBEAT_MIN"] * 60: log(f"HEARTBEAT OK - MODE {mode} CROSS - Bal ${bal_show:.2f} PnL ${STATE['pnl']:.2f}"); last_heartbeat = now_utc()
            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e: log(f"ERROR {e}"); time.sleep(10)
if __name__ == "__main__": main()
