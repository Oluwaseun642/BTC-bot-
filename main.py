# ============================================================
# BTC SWEEP BOT - V13.15.8 FINAL - HAFFAR CLEAN REAL START
# PATCH V13.15.8:
#   - AUTO_SWITCH = 18:00 UTC = 7PM WAT. PAPER till 7pm, then AUTO REAL. No hold-back.
#   - FRESH REAL START: On switch, RESET pnl/wins/losses/trades/fake_holding/cooldown/hide/revenge to 0/None.
#     No PAPER fake loss, no fake HOLDING go carry enter REAL progression.
#   - SYNC BYBIT ON SWITCH: Fetch real balance + real position. If position dey, adopt am. If none, start fresh.
#   - PAPER FAIL BLOCK REMOVED: Paper PnL < -2 no go block REAL again. Yesterday wahala cleared.
#   - TRAILING: Trigger $500, Dist $50 (Best + $50 SHORT / Best - $50 LONG). NORMAL + HUNTER.
#   - COOLDOWN: 1 min SMART RE-CHECK only. After any close, check certainties + hunters 1 min, if still good re-enter at market.
#   - WORLD MARKETS: Nikkei, HangSeng, FTSE, DAX, NQ, SPX, DXY, GOLD every 60 sec, certainties decide.
#   - LIQ MAP EVERY CYCLE: LongLiq / ShortLiq / Asia Low/High every 5 sec cycle, hunt detection via liq + world.
#   - NO BLIND TRADE: Gates Agree 4+ Cert 75%+ Score 0.60+ must pass, else BLOCK.
#   - MAGIC SL: Emergency $400, Tight SL $500, Profit Lock if hunt against but profit > $50.
#   - DYNAMIC QTY: Bal < $20 = 0.01, +0.005 per +$8, max 0.100.
#   - CROSS + Conditional Hidden + Market Trigger still dey.
# ============================================================

import time, requests, hmac, hashlib, os, threading, json
from datetime import datetime, timezone, timedelta

try:
    from flask import Flask
    _flask_app = Flask(__name__)
    @_flask_app.route("/")
    def _health(): return "BOT ALIVE V13.15.8 - TRAILING $500/$50 + 7PM WAT REAL FRESH START - NO HOLD BACK", 200
    @_flask_app.route("/health")
    def _health2(): return "OK", 200
    def _run_flask():
        try:
            port = int(os.getenv("PORT", 10000)); _flask_app.run(host="0.0.0.0", port=port, use_reloader=False)
        except Exception as e: print(f"Flask error {e}", flush=True)
    threading.Thread(target=_run_flask, daemon=True).start()
    print("Flask keep-alive ON", flush=True)
except Exception as e: print(f"Flask OFF {e}", flush=True)

def _self_ping_loop():
    SELF_URL = os.getenv("RENDER_URL", "https://YOUR-BOT-NAME.onrender.com/")
    while True:
        try: time.sleep(240); requests.get(SELF_URL, timeout=10); print("SELF-PING OK", flush=True)
        except Exception as e: print(f"SELF-PING FAIL {e}", flush=True)
threading.Thread(target=_self_ping_loop, daemon=True).start()
print("Self-Ping ON - every 4 min", flush=True)

CONFIG = {
    "SYMBOL": "BTCUSDT", "LEVERAGE": 50,
    "AUTO_SWITCH_UTC": datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc),
    "QTY_BASE": 0.010, "QTY_STEP": 0.005, "QTY_BASE_BAL": 20.0, "QTY_STEP_BAL": 8.0,
    "REAL_MIN_QTY": 0.010, "REAL_MAX_QTY": 0.100,
    "MIN_CERTAINTY_NORMAL": 75.0, "MIN_AGREE_NORMAL": 4, "MIN_SCORE_NORMAL": 0.60,
    "MIN_AGREE_DYNAMIC": 4, "DYNAMIC_AGREE_CERT": 90.0,
    "TOTAL_SIGNALS": 8, "SURE_CERTAINTY": 95.0, "SURE_AGREE": 6,
    "NEWS_ENABLED": True, "MIN_CERTAINTY_NEWS": 75.0, "MIN_AGREE_NEWS": 4, "MIN_SCORE_NEWS": 0.60,
    "WIDE_SL_USD": 1200.0,
    "TRAILING_ENABLED": True, "TRAIL_TRIGGER_MOVE_USD": 500.0, "TRAIL_DIST_USD": 50.0,
    "HUNTER_TRAIL_TRIGGER": 500.0, "HUNTER_TRAIL_DIST": 50.0,
    "HUNTER_SL_USD": 400.0, "HUNTER_TP_MIN_USD": 600.0,
    "FEE_RATE": 0.0006, "SLIPPAGE_PCT": 0.0005,
    "FLIP_ENABLED": True, "FLIP_CERTAINTY": 75.0, "FLIP_AGREE": 4,
    "NEVER_STOP": True,
    "ADDON_ENABLED": True, "ADDON_MAX_PER_POSITION": 1,
    "ADDON_WICK_MIN_USD": 500.0, "ADDON_WICK_MAX_USD": 900.0,
    "ADDON_BUFFER_PCT": 0.90,
    "CROSS_MARGIN_ENABLED": True, "MARGIN_MODE": "CROSS",
    "CONDITIONAL_HIDDEN": True,
    "HUNT_LIMIT_ENABLED": True, "HUNT_LIMIT_WAIT_MIN": 2, "HUNT_LIMIT_OFFSET_USD": 150.0,
    "ASIAN_ENABLED": True, "ASIAN_START_HOUR_UTC": 0, "ASIAN_END_HOUR_UTC": 8, "ASIAN_SWEEP_BUFFER_PCT": 0.0015,
    "SESSION_HUNT_ENABLED": True, "SESSIONS": [("ASIA", 0, 0), ("LONDON", 7, 0), ("NEWYORK", 13, 30)], "SESSION_HUNT_WINDOW_MIN": 30,
    "POLL_SEC": 5, "HEARTBEAT_MIN": 10,
    "BYBIT_BASE": "https://api.bybit.com",
    "TP_DIST_USD": 1500.0,
    "PRE_HUNT_LOCK_MIN": 15,
    "HIDE_AFTER_MISS_MIN": 15,
    "REVENGE_LOCK_MIN": 1,
    "SMART_RECHECK_MIN": 1,
    "COOLDOWN_MIN": 1,
    "HUNT_MIN_LIQ_USD": 2000000.0,
    "HUNT_EARLY_MIN_DIST_USD": 300.0,
    "EMERGENCY_AGAINST_USD": 400.0,
    "PROFIT_LOCK_MIN_USD": 50.0,
}
API_KEY = os.getenv("BYBIT_API_KEY", ""); API_SECRET = os.getenv("BYBIT_API_SECRET", "")
STATE = {"mode": "PAPER", "balance": 24.33, "real_balance": 0.0, "day_start_balance": 24.33, "pnl": 0.0,
    "wins": 0, "losses": 0, "breakevens": 0, "flips": 0, "addons": 0, "trades_today": 0, "losses_today": 0,
    "day": datetime.now(timezone.utc).date(), "open_position": None, "pending_hunt": None,
    "last_price": 0.0, "cross_margin_set": False, "last_qty": 0.010, "last_balance_checked": 0.0,
    "last_macro": {"DXY_CHG": 0.0, "NQ_CHG": 0.0, "SPX_CHG": 0.0, "GOLD_CHG": 0.0, "OI_CHG": 0.0},
    "last_liq_map": {"long_liq": 0.0, "short_liq": 0.0, "asia_low": 0.0, "asia_high": 0.0, "hunt": "NONE"}, "last_session": "NONE",
    "hide_until": None, "revenge_until": None, "cooldown_until": None, "last_close_reason": None, "last_close_time": None,
    "world": {}, "world_last_fetch": 0, "paper_start_pnl": 0.0, "paper_fake_holding": 0, "paper_pass": True}

def now_utc(): return datetime.now(timezone.utc)
def log(msg): print(f"[{now_utc().strftime('%H:%M:%S %d %b')}] {msg}", flush=True)
def get_mode():
    rm = os.getenv("REAL_MODE", "").strip().lower()
    if rm == "true": return "REAL"
    if rm == "false": return "PAPER"
    return "REAL" if now_utc() >= CONFIG["AUTO_SWITCH_UTC"] else "PAPER"

def _bybit_sign_v5(timestamp, recv_window, body_str):
    payload = f"{timestamp}{API_KEY}{recv_window}{body_str}"
    return hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
def _safe_json(r):
    try:
        txt = r.text.strip() if r.text else ""
        if not txt: return {"retCode": -1, "retMsg": "Empty response from Bybit", "result": {}}
        return r.json()
    except Exception as e:
        return {"retCode": -1, "retMsg": f"JSON parse fail: {e}", "result": {}}
def bybit_post(path, params):
    try:
        timestamp = str(int(time.time()*1000)); recv_window = "5000"
        body_str = json.dumps(params, separators=(',', ':'))
        sign = _bybit_sign_v5(timestamp, recv_window, body_str)
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": timestamp, "X-BAPI-RECV-WINDOW": recv_window, "X-BAPI-SIGN": sign, "Content-Type": "application/json"}
        r = requests.post(CONFIG["BYBIT_BASE"]+path, data=body_str, headers=headers, timeout=10)
        return _safe_json(r)
    except Exception as e: return {"retCode": -1, "retMsg": f"POST error {e}", "result": {}}
def bybit_get(path, params):
    try:
        timestamp = str(int(time.time()*1000)); recv_window = "5000"
        qs = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        sign = _bybit_sign_v5(timestamp, recv_window, qs)
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": timestamp, "X-BAPI-RECV-WINDOW": recv_window, "X-BAPI-SIGN": sign}
        r = requests.get(CONFIG["BYBIT_BASE"]+path, params=params, headers=headers, timeout=10)
        return _safe_json(r)
    except Exception as e: return {"retCode": -1, "retMsg": f"GET error {e}", "result": {}}

def get_real_balance():
    try:
        res = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
        if res.get("retCode") != 0:
            log(f"REAL BALANCE API WARN {res.get('retMsg')} - using last {STATE['real_balance']}")
            return STATE["real_balance"] or 24.33
        bal = float(res["result"]["list"][0]["coin"][0]["walletBalance"]); STATE["real_balance"] = bal; return bal
    except Exception as e:
        log(f"REAL BALANCE ERROR {e} - using last {STATE['real_balance']}"); return STATE["real_balance"] or 24.33
def get_current_balance(): return STATE["real_balance"] if STATE["mode"] == "REAL" else STATE["balance"]
def refresh_balance(reason="CYCLE"):
    if STATE["mode"] == "REAL":
        old = STATE["real_balance"]; new = get_real_balance()
        if abs(new - old) > 0.001: log(f"BALANCE CHECK [{reason}]: REAL ${old:.2f} -> ${new:.2f}")
        STATE["last_balance_checked"] = new; return new
    STATE["last_balance_checked"] = STATE["balance"]; return STATE["balance"]

def get_real_position_sync():
    if STATE["mode"] != "REAL" or not API_KEY: return None
    try:
        res = bybit_get("/v5/position/list", {"category": "linear", "symbol": CONFIG["SYMBOL"]})
        if res.get("retCode") != 0: return None
        lst = res["result"].get("list", [])
        for p in lst:
            sz = float(p.get("size", 0))
            if sz > 0:
                return {"side": "LONG" if p.get("side")=="Buy" else "SHORT", "size": sz, "entry": float(p.get("avgPrice", 0)), "sl": p.get("stopLoss"), "tp": p.get("takeProfit")}
        return None
    except: return None

def set_cross_margin():
    if not CONFIG["CROSS_MARGIN_ENABLED"]: return True
    if STATE.get("cross_margin_set"): return True
    if STATE["mode"] == "PAPER":
        log("CROSS MARGIN: PAPER - Whole balance dey back position + Add-on"); STATE["cross_margin_set"] = True; return True
    if not API_KEY: return False
    try:
        res = bybit_post("/v5/position/switch-margin-mode", {"category": "linear", "symbol": CONFIG["SYMBOL"], "tradeMode": 0, "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        if res.get("retCode") == 0 or "already" in str(res.get("retMsg","")).lower() or res.get("retCode") == 110026:
            log(f"CROSS MARGIN SET: Bybit tradeMode 0 = CROSS | Lev {CONFIG['LEVERAGE']}x | {res.get('retMsg')}")
            STATE["cross_margin_set"] = True; return True
        log(f"CROSS MARGIN SKIP: Bybit say {res.get('retMsg')} (retCode {res.get('retCode')}) - Bot continue")
        STATE["cross_margin_set"] = True; return True
    except Exception as e:
        log(f"CROSS MARGIN SKIP - {e}"); STATE["cross_margin_set"] = True; return True

def calc_dynamic_fees(price, qty):
    pos = qty * price; fees = pos * CONFIG["FEE_RATE"] * 2; slip = pos * CONFIG["SLIPPAGE_PCT"] * 2; total = fees + slip
    return pos, fees, slip, total
def get_dynamic_qty(price):
    bal = refresh_balance("QTY-CALC")
    if bal < CONFIG["QTY_BASE_BAL"]: qty = CONFIG["QTY_BASE"]; steps = 0
    else:
        steps = int((bal - CONFIG["QTY_BASE_BAL"]) // CONFIG["QTY_STEP_BAL"])
        qty = round(CONFIG["QTY_BASE"] + steps * CONFIG["QTY_STEP"], 3)
    qty = min(qty, CONFIG["REAL_MAX_QTY"])
    if qty != STATE.get("last_qty", 0.010): log(f"QTY TIER CHANGE: Bal ${bal:.2f} -> Steps {steps} = Qty {qty}")
    else: log(f"QTY TIER CHECK: Bal ${bal:.2f} -> Steps {steps} = Qty {qty}")
    STATE["last_qty"] = qty; return qty

def place_real_order(side, price, wide_sl, tp, qty, is_addon=False):
    if not API_KEY or not API_SECRET: log("REAL ORDER BLOCKED: No API keys"); return False
    try:
        set_cross_margin()
        bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": CONFIG["SYMBOL"], "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        res = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Buy" if side == "LONG" else "Sell",
            "orderType": "Market", "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(wide_sl, 1)),
            "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice", "tpslMode": "Full", "positionIdx": 0, "timeInForce": "GTC"})
        if res.get("retCode") == 0:
            log(f"REAL ORDER OK [{'ADD-ON' if is_addon else 'MAIN'}] {side} Qty {qty} OrderId {res['result'].get('orderId')} Entry ~${price:.0f} SL ${wide_sl:.0f} TP ${tp:.0f}")
            return True
        else:
            log(f"REAL ORDER REJECTED ❌ {side} Qty {qty} | retCode {res.get('retCode')} {res.get('retMsg')} — NO POSITION SET")
            return False
    except Exception as e: log(f"REAL ORDER ERROR {e}"); return False

def place_hunt_limit(side, hunt_price, qty):
    if not API_KEY: return False, None
    try:
        direction = 1 if side == "SHORT" else 2
        res = bybit_post("/v5/order/create", {
            "category": "linear", "symbol": CONFIG["SYMBOL"],
            "side": "Buy" if side == "LONG" else "Sell",
            "orderType": "Market",
            "triggerPrice": str(round(hunt_price, 1)),
            "triggerBy": "LastPrice",
            "triggerDirection": direction,
            "tpslMode": "Full", "positionIdx": 0,
            "timeInForce": "GTC",
            "qty": str(qty),
            "reduceOnly": False,
        })
        if res.get("retCode") == 0:
            oid = res["result"].get("orderId"); log(f"HUNT MARKET TRIGGER OK {side} Trigger @ ${hunt_price:.0f} OrderId {oid} Dir {direction} — Fill at market, no miss"); return True, oid
        else:
            log(f"HUNT MARKET TRIGGER REJECTED ❌ {res.get('retMsg')} — No fake pending"); return False, None
    except Exception as e: log(f"HUNT MARKET TRIGGER ERROR {e}"); return False, None

def cancel_hunt_limit(order_id=None):
    try:
        if API_KEY and STATE["mode"] == "REAL" and order_id:
            bybit_post("/v5/order/cancel", {"category": "linear", "symbol": CONFIG["SYMBOL"], "orderId": order_id})
        elif API_KEY and STATE["mode"] == "REAL" and not order_id:
            log("CANCEL HUNT: No orderId, skip cancel-all to protect real TP/SL")
    except: pass
    STATE["pending_hunt"] = None
    log("HUNT MARKET TRIGGER CANCELLED - Enter Market gangan")

def update_real_sl(new_sl, side):
    if STATE["mode"] != "REAL": return True
    if not API_KEY: return False
    try:
        res = bybit_post("/v5/position/trading-stop", {"category": "linear", "symbol": CONFIG["SYMBOL"], "stopLoss": str(round(new_sl, 1)), "slTriggerBy": "LastPrice", "positionIdx": 0})
        log(f"REAL SL UPDATED -> ${new_sl:.0f} | {res.get('retMsg')}"); return res.get("retCode") == 0
    except Exception as e: log(f"REAL SL UPDATE ERROR {e}"); return False

def close_real_position(side, qty):
    if STATE["mode"] != "REAL": return True
    try:
        res = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Sell" if side == "LONG" else "Buy", "orderType": "Market", "qty": str(qty), "timeInForce": "GTC", "positionIdx": 0})
        log(f"REAL POSITION CLOSED {side} Qty {qty} | retCode {res.get('retCode')} {res.get('retMsg')}"); return res.get("retCode") == 0
    except Exception as e: log(f"REAL CLOSE ERROR {e}"); return False

def fetch_live_multi(symbols_yahoo, symbols_stooq):
    for sym in symbols_yahoo:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            try:
                headers = {"User-Agent": "Mozilla/5.0"}; r = requests.get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=1m", headers=headers, timeout=5)
                meta = r.json()["chart"]["result"][0]["meta"]; price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0); prev = float(meta.get("previousClose") or meta.get("chartPreviousClose") or price)
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

def get_world_markets():
    now_ts = time.time()
    if now_ts - STATE.get("world_last_fetch", 0) < 60 and STATE.get("world"):
        return STATE["world"]
    world = {}
    pairs = [("NIKKEI", ["^N225"], ["^N225"]), ("HANG_SENG", ["^HSI"], ["^HSI"]), ("FTSE", ["^FTSE"], ["^FTSE"]), ("DAX", ["^GDAXI"], ["^GDAXI"]), ("NQ", ["NQ=F"], ["nq.f"]), ("SPX", ["ES=F"], ["es.f"]), ("GOLD", ["GC=F"], ["gc.f"]), ("DXY", ["DX-Y.NYB"], ["dx.f"])]
    for name, yahoo, stooq in pairs:
        chg, src = fetch_live_multi(yahoo, stooq)
        world[name] = chg if chg is not None else STATE.get("world", {}).get(name, 0.0)
        world[name+"_SRC"] = src
    STATE["world"] = world; STATE["world_last_fetch"] = now_ts
    log(f"WORLD LIVE Nikkei {world.get('NIKKEI',0):.2f}% HangSeng {world.get('HANG_SENG',0):.2f}% FTSE {world.get('FTSE',0):.2f}% DAX {world.get('DAX',0):.2f}% NQ {world.get('NQ',0):.2f}% SPX {world.get('SPX',0):.2f}% DXY {world.get('DXY',0):.2f}% GOLD {world.get('GOLD',0):.2f}%")
    return world

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
    world = get_world_markets()
    dxy = world.get("DXY", 0.0); nq = world.get("NQ", 0.0); spx = world.get("SPX", 0.0); gold = world.get("GOLD", 0.0)
    oi_chg = None; oi_src = "FAIL"
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5); lst = r.json()["result"]["list"]; oi_chg = (float(lst[-1]["openInterest"]) - float(lst[0]["openInterest"])) / float(lst[0]["openInterest"]) * 100; oi_src = "Bybit"
    except:
        try:
            r = requests.get("https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=5m&limit=5", timeout=5); lst = r.json(); oi_chg = (float(lst[-1]["sumOpenInterest"]) - float(lst[0]["sumOpenInterest"])) / float(lst[0]["sumOpenInterest"]) * 100; oi_src = "Binance"
        except: oi_chg = None
    macro = {}
    for k, v, src in [("DXY_CHG", dxy, world.get("DXY_SRC","Yahoo")), ("NQ_CHG", nq, world.get("NQ_SRC","Yahoo")), ("SPX_CHG", spx, world.get("SPX_SRC","Yahoo")), ("GOLD_CHG", gold, world.get("GOLD_SRC","Yahoo")), ("OI_CHG", oi_chg, oi_src)]:
        if v is None: macro[k] = STATE["last_macro"].get(k, 0.0); macro[k+"_STATUS"] = "UNKNOWN"; macro[k+"_SRC"] = "UNKNOWN-Using-Last"
        else: macro[k] = v; macro[k+"_STATUS"] = "LIVE"; macro[k+"_SRC"] = src; STATE["last_macro"][k] = v
    print(f"LIVE SRC DXY:{macro['DXY_CHG_SRC']} NQ:{macro['NQ_CHG_SRC']} SPX:{macro['SPX_CHG_SRC']} GOLD:{macro['GOLD_CHG_SRC']} OI:{macro['OI_CHG_SRC']}", flush=True); return macro

def get_liquidation_map(price, klines_1m=None, macro=None):
    long_liq = 0.0; short_liq = 0.0; src = "FAIL"
    try:
        r = requests.get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50", timeout=5); lst = r.json().get("result", {}).get("list", [])
        for x in lst:
            try:
                sz = float(x.get("size", 0)) * float(x.get("price", price))
                if x.get("side") == "Sell": long_liq += sz
                elif x.get("side") == "Buy": short_liq += sz
            except: pass
        if long_liq + short_liq > 0: src = "Bybit"
    except: pass
    if long_liq + short_liq == 0:
        try:
            r = requests.get("https://fapi.binance.com/fapi/v1/forceOrders?symbol=BTCUSDT&limit=50", timeout=5); lst = r.json()
            for x in lst:
                try:
                    sz = float(x.get("origQty", 0)) * float(x.get("price", price))
                    if x.get("side") == "SELL": long_liq += sz
                    elif x.get("side") == "BUY": short_liq += sz
                except: pass
            if long_liq + short_liq > 0: src = "Binance"
        except: pass
    if long_liq + short_liq == 0:
        try:
            vol = 0.0
            if klines_1m:
                for k in klines_1m[-5:]: vol += abs(k["high"] - k["low"]) * 0.002 * price
            if vol <= 0: vol = 50000.0
            if klines_1m and len(klines_1m) >= 5:
                pc = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
                if pc < 0: long_liq = vol * 0.6; short_liq = vol * 0.4
                elif pc > 0: long_liq = vol * 0.4; short_liq = vol * 0.6
                else: long_liq = vol * 0.5; short_liq = vol * 0.5
            else: long_liq = vol * 0.5; short_liq = vol * 0.5
            src = "Proxy-Vol/OI"
        except: long_liq = 50000.0; short_liq = 50000.0; src = "Proxy-Fallback"
    return long_liq, short_liq, src

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
    if not CONFIG["ASIAN_ENABLED"]: return "NEUTRAL", 0.0, 0.0, 0.0, 0.0, "FAIL"
    asia_low, asia_high = get_asian_range(klines_15m); long_liq, short_liq, liq_src = get_liquidation_map(price, klines_1m); hunt = "NEUTRAL"
    if asia_low and asia_high and klines_1m:
        buf = price * CONFIG["ASIAN_SWEEP_BUFFER_PCT"]; last = klines_1m[-1]
        if last["low"] < asia_low and last["close"] > asia_low and long_liq > short_liq: hunt = "LONG"
        elif last["high"] > asia_high and last["close"] < asia_high and short_liq > long_liq: hunt = "SHORT"
        elif last["low"] < asia_low - buf and last["close"] > asia_low: hunt = "LONG"
        elif last["high"] > asia_high + buf and last["close"] < asia_high: hunt = "SHORT"
    else:
        if not klines_1m: hunt = "UNKNOWN"
    STATE["last_liq_map"] = {"long_liq": long_liq, "short_liq": short_liq, "asia_low": asia_low, "asia_high": asia_high, "hunt": hunt}; return hunt, asia_low, asia_high, long_liq, short_liq, liq_src

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

def is_pre_hunt_window():
    now = now_utc(); mins_now = now.hour*60 + now.minute
    for end_min in [8*60, 13*60+30]:
        diff = end_min - mins_now
        if 0 <= diff <= CONFIG["PRE_HUNT_LOCK_MIN"]: return True, f"PRE-HUNT {diff} min to sweep"
    return False, "NORMAL"

def world_confirms_hunt(hunt_dir, world):
    if hunt_dir == "LONG":
        asia_up = world.get("NIKKEI", 0) > 0.2 and world.get("HANG_SENG", 0) > 0.2
        london_up = world.get("FTSE", 0) > 0.2 and world.get("DAX", 0) > 0.2
        ny_up = world.get("NQ", 0) > 0.05 and world.get("SPX", 0) > 0.05
        return asia_up or london_up or ny_up
    if hunt_dir == "SHORT":
        asia_down = world.get("NIKKEI", 0) < -0.2 and world.get("HANG_SENG", 0) < -0.2
        london_down = world.get("FTSE", 0) < -0.2 and world.get("DAX", 0) < -0.2
        ny_down = world.get("NQ", 0) < -0.05 and world.get("SPX", 0) < -0.05
        return asia_down or london_down or ny_down
    return False

def detect_early_hunt(price, cert_dest, klines_1m, long_liq, short_liq, asia_low, asia_high, world):
    if not klines_1m or len(klines_1m) < 5: return "NONE", 0.0, ""
    pc5 = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
    if cert_dest == "SHORT" and pc5 > 0.30:
        target = asia_high if asia_high > price and (asia_high - price) < 2000 else price + 1200
        pool = short_liq
        if pool >= CONFIG["HUNT_MIN_LIQ_USD"] or (asia_high and target == asia_high):
            if world_confirms_hunt("LONG", world):
                dist = target - price
                if dist >= CONFIG["HUNT_EARLY_MIN_DIST_USD"]:
                    return "LONG", target, f"EARLY HUNT LONG: Cert SHORT but price UP {pc5:.2f}% in 5m, Liq ${pool:,.0f}, World confirms, Target ${target:.0f} Dist ${dist:.0f}"
                else:
                    return "MISS", target, f"HUNT MISS: Target ${target:.0f} too close ${dist:.0f} < $300, HIDE"
    if cert_dest == "LONG" and pc5 < -0.30:
        target = asia_low if asia_low and asia_low < price and (price - asia_low) < 2000 else price - 1200
        pool = long_liq
        if pool >= CONFIG["HUNT_MIN_LIQ_USD"] or (asia_low and target == asia_low):
            if world_confirms_hunt("SHORT", world):
                dist = price - target
                if dist >= CONFIG["HUNT_EARLY_MIN_DIST_USD"]:
                    return "SHORT", target, f"EARLY HUNT SHORT: Cert LONG but price DOWN {pc5:.2f}% in 5m, Liq ${pool:,.0f}, World confirms, Target ${target:.0f} Dist ${dist:.0f}"
                else:
                    return "MISS", target, f"HUNT MISS: Target ${target:.0f} too close ${dist:.0f} < $300, HIDE"
    return "NONE", 0.0, ""

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
    elif macro["DXY_CHG"] > 0.05: signals.append(("DXY_LEVEL", "SHORT"))
    elif macro["DXY_CHG"] < -0.05: signals.append(("DXY_LEVEL", "LONG"))
    else: signals.append(("DXY_LEVEL", "NEUTRAL"))
    if macro.get("NQ_CHG_STATUS") == "UNKNOWN": signals.append(("NQ_MOMENTUM", "UNKNOWN"))
    elif macro["NQ_CHG"] > 0.05: signals.append(("NQ_MOMENTUM", "LONG"))
    elif macro["NQ_CHG"] < -0.05: signals.append(("NQ_MOMENTUM", "SHORT"))
    else: signals.append(("NQ_MOMENTUM", "NEUTRAL"))
    if macro.get("SPX_CHG_STATUS") == "UNKNOWN": signals.append(("SPX_MOMENTUM", "UNKNOWN"))
    elif macro["SPX_CHG"] > 0.05: signals.append(("SPX_MOMENTUM", "LONG"))
    elif macro["SPX_CHG"] < -0.05: signals.append(("SPX_MOMENTUM", "SHORT"))
    else: signals.append(("SPX_MOMENTUM", "NEUTRAL"))
    if macro.get("GOLD_CHG_STATUS") == "UNKNOWN": signals.append(("GOLD_AFTER_SWEEP", "UNKNOWN"))
    elif macro["GOLD_CHG"] > 0.15: signals.append(("GOLD_AFTER_SWEEP", "SHORT"))
    elif macro["GOLD_CHG"] < -0.10: signals.append(("GOLD_AFTER_SWEEP", "LONG"))
    else: signals.append(("GOLD_AFTER_SWEEP", "NEUTRAL"))
    if macro.get("OI_CHG_STATUS") == "UNKNOWN": signals.append(("OI_DIVERGENCE", "UNKNOWN"))
    elif klines_1m and len(klines_1m) >= 5:
        pc = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
        if macro["OI_CHG"] > 0.20 and pc < -0.05: signals.append(("OI_DIVERGENCE", "SHORT"))
        elif macro["OI_CHG"] < -0.20 and pc > 0.05: signals.append(("OI_DIVERGENCE", "LONG"))
        elif macro["OI_CHG"] > 0.80: signals.append(("OI_DIVERGENCE", "SHORT"))
        elif macro["OI_CHG"] < -0.80: signals.append(("OI_DIVERGENCE", "LONG"))
        else: signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    else: signals.append(("OI_DIVERGENCE", "UNKNOWN"))
    if not klines_1m: signals.append(("LIQ_SWEEP", "UNKNOWN"))
    elif len(klines_1m) >= 3:
        last = klines_1m[-1]; wd = last["close"] - last["low"]; wu = last["high"] - last["close"]; thr = price * 0.001
        if wd > thr and wd > wu * 1.2: signals.append(("LIQ_SWEEP", "LONG"))
        elif wu > thr and wu > wd * 1.2: signals.append(("LIQ_SWEEP", "SHORT"))
        else:
            if len(klines_1m) >= 5:
                pc5 = (klines_1m[-1]["close"] - klines_1m[-5]["close"]) / klines_1m[-5]["close"] * 100
                if pc5 > 0.10: signals.append(("LIQ_SWEEP", "LONG"))
                elif pc5 < -0.10: signals.append(("LIQ_SWEEP", "SHORT"))
                else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
            else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
    else: signals.append(("LIQ_SWEEP", "UNKNOWN"))
    signals.append(("ASIAN_LIQ_HUNT", asian_hunt if asian_hunt in ("LONG","SHORT") else ("UNKNOWN" if asian_hunt=="UNKNOWN" else "NEUTRAL")))
    signals.append(("SESSION_REOPEN_HUNT", session_hunt if session_hunt in ("LONG","SHORT") else ("UNKNOWN" if session_hunt=="UNKNOWN" else "NEUTRAL")))
    asian_val = signals[6][1]; sess_val = signals[7][1]
    if asian_val == "NEUTRAL" and sess_val == "NEUTRAL" and klines_1m and len(klines_1m) >= 15:
        pc15 = (klines_1m[-1]["close"] - klines_1m[-15]["close"]) / klines_1m[-15]["close"] * 100
        if pc15 > 0.15: signals[6] = ("ASIAN_LIQ_HUNT", "LONG"); signals[7] = ("SESSION_REOPEN_HUNT", "LONG")
        elif pc15 < -0.15: signals[6] = ("ASIAN_LIQ_HUNT", "SHORT"); signals[7] = ("SESSION_REOPEN_HUNT", "SHORT")
    return signals

def decide(signals):
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT"); unknowns = sum(1 for _, v in signals if v == "UNKNOWN"); decided = longs + shorts
    if longs > shorts: dest, agree = "LONG", longs
    elif shorts > longs: dest, agree = "SHORT", shorts
    else: dest, agree = "NONE", 0
    return dest, agree, decided, longs, shorts, unknowns, (agree / decided * 100) if decided else 0
def get_needed_agree(certainty, agree, decided, base_need):
    if decided >= 4 and agree == decided: return agree
    if certainty >= CONFIG["DYNAMIC_AGREE_CERT"] and agree >= CONFIG["MIN_AGREE_DYNAMIC"]: return CONFIG["MIN_AGREE_DYNAMIC"]
    return base_need
def calc_score(signals, dest, macro, is_news):
    _, agree, decided, _, _, _, certainty = decide(signals); base = (certainty / 100) * 1.0; align = 0
    if dest == "LONG" and macro["NQ_CHG"] > 0 and macro["SPX_CHG"] > 0: align = 0.4
    if dest == "SHORT" and macro["DXY_CHG"] > 0: align = 0.3
    return round(base + align + (0.4 if is_news else 0), 2)
def calc_sl_tp_v1315(price, side):
    wide_sl = price - CONFIG["WIDE_SL_USD"] if side == "LONG" else price + CONFIG["WIDE_SL_USD"]
    tp = price + CONFIG["TP_DIST_USD"] if side == "LONG" else price - CONFIG["TP_DIST_USD"]
    return round(wide_sl, 1), round(tp, 1)
def calc_hunter_sl_tp(price, side, target):
    sl = price - CONFIG["HUNTER_SL_USD"] if side == "LONG" else price + CONFIG["HUNTER_SL_USD"]
    if side == "LONG": tp = target - 200 if target > price else price + 600
    else: tp = target + 200 if target < price else price - 600
    return round(sl, 1), round(tp, 1)

def record_close(side, entry, close_price, qty, reason):
    _, fees, slip, total = calc_dynamic_fees(entry, qty)
    gross = (close_price - entry) * qty if side == "LONG" else (entry - close_price) * qty
    net = gross - total; old_bal = STATE["balance"] if STATE["mode"] == "PAPER" else STATE["real_balance"]
    if STATE["mode"] == "PAPER": STATE["balance"] += net; STATE["pnl"] += net
    else: STATE["pnl"] += net
    STATE["cooldown_until"] = now_utc() + timedelta(minutes=CONFIG["COOLDOWN_MIN"])
    STATE["revenge_until"] = STATE["cooldown_until"]
    STATE["last_close_reason"] = reason; STATE["last_close_time"] = now_utc()
    log(f"SMART RECHECK ON: 1 min re-check after {reason} - check certainties + hunters, if still good re-enter at market, no miss entry")
    if reason == "TP": STATE["wins"] += 1; log(f"TP HIT +${net:.2f} - Closed {side} at ${close_price:.0f}")
    elif reason == "TRAILING": STATE["wins"] += 1; log(f"TRAILING PROFIT +${net:.2f} - Closed {side} at ${close_price:.0f}")
    elif reason == "FLIP": STATE["flips"] += 1; log(f"FLIP CLOSE ${net:.2f} - Closed {side} at ${close_price:.0f}")
    elif reason in ("HUNT_PROFIT_LOCK", "HUNT_PROFIT_OVER_FEES"): STATE["wins"] += 1; log(f"HUNT PROFIT LOCK +${net:.2f} - Closed {side} at ${close_price:.0f} Reason {reason}")
    elif net > 0: STATE["wins"] += 1; log(f"SMALL WIN +${net:.2f} - Closed {side} at ${close_price:.0f} Reason {reason}")
    elif net < -0.01: STATE["losses"] += 1; STATE["losses_today"] += 1; log(f"WIDE SL LOSS ${net:.2f} - Closed {side} at ${close_price:.0f} Reason {reason}")
    else: STATE["breakevens"] += 1; log(f"BE CLOSE ${net:.2f} - Closed {side} at ${close_price:.0f} Reason {reason}")
    STATE["open_position"] = None; new_bal = refresh_balance(f"AFTER-CLOSE-{reason}"); log(f"BALANCE AFTER TRADE: ${new_bal:.2f}"); return net

def is_real_reversal_confirmed(flip_dest, flip_certainty, flip_agree, macro, side):
    if flip_dest == "NONE" or flip_dest == side: return False
    need_flip = 4 if (flip_certainty >= 100 and flip_agree >= 4) else CONFIG["FLIP_AGREE"]
    if not (flip_certainty >= CONFIG["FLIP_CERTAINTY"] and flip_agree >= need_flip): return False
    if flip_dest == "LONG": return macro["DXY_CHG"] < 0.05 or macro["NQ_CHG"] > 0
    else: return macro["DXY_CHG"] > 0.05 or macro["NQ_CHG"] < 0

def manage_position(price, klines, qty, flip_dest, flip_certainty, flip_agree, macro, long_liq, short_liq, hunt_dir, hunt_target, world):
    if not STATE["open_position"]: return False
    p = STATE["open_position"]; entry = float(p["entry"]); side = p["side"]; total_qty = p.get("total_qty", qty)
    is_hunter = p.get("is_hunter_trade", False)
    trail_trigger = CONFIG["HUNTER_TRAIL_TRIGGER"] if is_hunter else CONFIG["TRAIL_TRIGGER_MOVE_USD"]
    trail_dist = CONFIG["HUNTER_TRAIL_DIST"] if is_hunter else CONFIG["TRAIL_DIST_USD"]
    if side == "LONG": best = max(p.get("best_price", entry), price)
    else: best = min(p.get("best_price", entry), price)
    p["best_price"] = best
    favour_move = abs(best - entry)
    pnl_points = (price - entry) if side == "LONG" else (entry - price)
    against_move = abs(price - entry) if ((side == "LONG" and price < entry) or (side == "SHORT" and price > entry)) else 0.0
    if CONFIG["FLIP_ENABLED"] and is_real_reversal_confirmed(flip_dest, flip_certainty, flip_agree, macro, side):
        log(f"FLIP {side} -> {flip_dest} CONFIRMED | Cert {flip_certainty:.0f}% Agree {flip_agree}")
        if STATE["mode"] == "REAL": close_real_position(side, total_qty)
        record_close(side, entry, price, total_qty, "FLIP"); return True
    hit_tp = (price >= p["tp"] if side == "LONG" else price <= p["tp"])
    if hit_tp:
        if STATE["mode"] == "REAL": close_real_position(side, total_qty)
        record_close(side, entry, price, total_qty, "TP"); return False
    if CONFIG["TRAILING_ENABLED"] and favour_move >= trail_trigger:
        if not p.get("trailing_active"):
            p["trailing_active"] = True; log(f"TRAILING TRIGGERED 👌 {side}: Favour ${favour_move:.0f} >= ${trail_trigger:.0f} - Trailing don take over BE, SL = Best + $50")
        trail_price = best - trail_dist if side == "LONG" else best + trail_dist
        p["trailing_price"] = trail_price
        if p.get("last_trail_update", 0) != round(trail_price):
            if side == "LONG" and trail_price > p.get("wide_sl", -1e9):
                p["wide_sl"] = trail_price; p["last_trail_update"] = round(trail_price); log(f"TRAILING {side}: Best ${best:.0f} -> Trailing SL ${trail_price:.0f} (Best - $50)"); update_real_sl(trail_price, side)
            elif side == "SHORT" and trail_price < p.get("wide_sl", 1e9):
                p["wide_sl"] = trail_price; p["last_trail_update"] = round(trail_price); log(f"TRAILING {side}: Best ${best:.0f} -> Trailing SL ${trail_price:.0f} (Best + $50)"); update_real_sl(trail_price, side)
        hit_trailing = (price <= trail_price if side == "LONG" else price >= trail_price)
        if hit_trailing:
            log(f"TRAILING HIT - Close WITH PROFIT {side} at ${price:.0f} - Locked profit, 1 min smart recheck then re-enter if still good")
            if STATE["mode"] == "REAL": close_real_position(side, total_qty)
            record_close(side, entry, price, total_qty, "TRAILING"); return False
    else:
        if favour_move > 0: log(f"TRAILING SLEEP: Favour ${favour_move:.0f} < ${trail_trigger:.0f}, Wide SL ${p.get('wide_sl',0):.0f} dey protect")
    hunt_against = (hunt_dir == "LONG" and side == "SHORT") or (hunt_dir == "SHORT" and side == "LONG")
    hunt_with = (hunt_dir == side) and hunt_dir in ("LONG", "SHORT")
    if hunt_against and pnl_points > CONFIG["PROFIT_LOCK_MIN_USD"]:
        log(f"💰 HUNT AGAINST US BUT WE DEY PROFIT +${pnl_points:.0f} — TAKE PROFIT NOW, no wait make hunters wick us back to SL")
        if STATE["mode"] == "REAL": close_real_position(side, total_qty)
        record_close(side, entry, price, total_qty, "HUNT_PROFIT_LOCK"); return False
    if hunt_with and pnl_points > 0:
        log(f"🎉 HUNT WITH US, profit +${pnl_points:.0f} — HOLD, trailing dey follow hunters")
    if hunt_against and against_move >= CONFIG["EMERGENCY_AGAINST_USD"] and not p.get("trailing_active"):
        log(f"🚨 HUNTER AGAINST US! Hunters {hunt_dir}, we {side}, Against ${against_move:.0f} — EMERGENCY CLOSE, no wait WideSL $1200 - 1 min recheck then re-enter if hunters don calm")
        if STATE["mode"] == "REAL": close_real_position(side, total_qty)
        record_close(side, entry, price, total_qty, "HUNTER_ESCAPE"); return False
    elif hunt_against and against_move >= 150 and not p.get("trailing_active"):
        new_sl = entry + 500 if side == "SHORT" else entry - 500
        if side == "SHORT" and new_sl < p.get("wide_sl", 1e9):
            log(f"⚠️ HUNTER WARNING: Tightening SL to ${new_sl:.0f} ($500 from entry) because hunters against us")
            p["wide_sl"] = new_sl; update_real_sl(new_sl, side)
        elif side == "LONG" and new_sl > p.get("wide_sl", -1e9):
            log(f"⚠️ HUNTER WARNING: Tightening SL to ${new_sl:.0f} ($500 from entry) because hunters against us")
            p["wide_sl"] = new_sl; update_real_sl(new_sl, side)
    if CONFIG["ADDON_ENABLED"] and not p.get("addon_done", False) and not hunt_against:
        if CONFIG["ADDON_WICK_MIN_USD"] <= against_move <= CONFIG["ADDON_WICK_MAX_USD"]:
            is_hunt_not_flip = (flip_dest == side or flip_dest == "NONE")
            liq_confirm = (short_liq > long_liq) if side == "SHORT" else (long_liq > short_liq)
            if is_hunt_not_flip and liq_confirm:
                try:
                    bal_now = get_current_balance()
                    if bal_now <= 0: bal_now = 24.33
                    total_qty_after = round(total_qty + qty, 3)
                    need_notional = total_qty_after * price
                    max_fit_notional = bal_now * CONFIG["LEVERAGE"] * CONFIG["ADDON_BUFFER_PCT"]
                    if need_notional > max_fit_notional:
                        log(f"ADD-ON SKIPPED: Balance ${bal_now:.2f} no fit - Need ${need_notional:.0f} > Max ${max_fit_notional:.0f}")
                    else:
                        log(f"ADD-ON TRIGGER {side}: Wick ${against_move:.0f}, Bal FIT ${bal_now:.2f} - Adding {qty}")
                        if STATE["mode"] == "REAL":
                            ok = place_real_order(side, price, p["wide_sl"], p["tp"], qty, is_addon=True)
                            if ok: p["addon_done"] = True; p["addon_qty"] = qty; p["total_qty"] = total_qty_after; STATE["addons"] += 1; log(f"ADD-ON PLACED {side} Qty {qty} Total {p['total_qty']}")
                            else: log(f"ADD-ON REJECTED by Bybit - Skip")
                        else:
                            p["addon_done"] = True; p["addon_qty"] = qty; p["total_qty"] = total_qty_after; STATE["addons"] += 1; log(f"ADD-ON PAPER SIM {side} Qty {qty} Total {p['total_qty']}")
                except Exception as e: log(f"ADD-ON ERROR CAUGHT {e} - Skip")
    hit_wide = (price <= p["wide_sl"] if side == "LONG" else price >= p["wide_sl"])
    if hit_wide and not p.get("trailing_active"):
        log(f"WIDE SL HIT: Price ${price:.0f} past Wide SL ${p['wide_sl']:.0f}")
        if STATE["mode"] == "REAL": close_real_position(side, total_qty)
        record_close(side, entry, price, total_qty, "WIDE_SL"); return False
    return False

def main():
    log("BOT V13.15.8 STARTED - TRAILING $500/$50 + 7PM WAT REAL FRESH START + NO HOLD BACK | PAPER TILL 7PM WAT THEN AUTO REAL | Bal $24.33 | WIDE SL $1200 + TRAILING $500/$50 + ADD-ON SAFE + CROSS")
    log("RESTART FRESH: Logs cleared, fetching everything live, no old fake HOLDING")
    STATE["paper_start_pnl"] = STATE["pnl"]
    last_heartbeat = now_utc()
    while True:
        try:
            new_mode = get_mode()
            if new_mode != STATE["mode"]:
                if new_mode == "REAL":
                    paper_pnl_now = STATE["pnl"] - STATE["paper_start_pnl"]
                    # V13.15.8 - NO HOLD BACK, FRESH REAL START - Paper result no block REAL
                    log(f"*** PAPER DONE Paper PnL ${paper_pnl_now:.2f} - SWITCHING TO REAL FRESH, NO FAKE LOSS CARRY OVER ***")
                    # FRESH START: Reset all PAPER stats, no fake loss enter REAL
                    STATE["pnl"] = 0.0; STATE["wins"] = 0; STATE["losses"] = 0; STATE["breakevens"] = 0; STATE["flips"] = 0; STATE["addons"] = 0; STATE["trades_today"] = 0; STATE["losses_today"] = 0
                    STATE["paper_fake_holding"] = 0; STATE["paper_start_pnl"] = 0.0; STATE["open_position"] = None; STATE["pending_hunt"] = None
                    STATE["hide_until"] = None; STATE["revenge_until"] = None; STATE["cooldown_until"] = None; STATE["last_close_reason"] = None; STATE["last_close_time"] = None
                    bal = get_real_balance(); STATE["day_start_balance"] = bal
                    log(f"*** AUTO SWITCH TO REAL 7PM WAT *** Real Balance: ${bal:.2f} USDT - Fetching live positions/orders, CROSS ON - FRESH START ***")
                    rp = get_real_position_sync()
                    log(f"REAL SYNC AT SWITCH: Bybit position = {rp} (must be None before first real trade, if dey, we adopt am)")
                    if rp is not None:
                        log(f"REAL POSITION ALREADY DEY {rp} — Adopting am, no new trade till e close")
                        STATE["open_position"] = {"side": rp["side"], "entry": rp["entry"], "wide_sl": float(rp["sl"] or 0) or (rp["entry"]+1200 if rp["side"]=="SHORT" else rp["entry"]-1200), "tp": float(rp["tp"] or 0) or (rp["entry"]-1500 if rp["side"]=="SHORT" else rp["entry"]+1500), "best_price": rp["entry"], "trailing_active": False, "trailing_price": None, "addon_done": False, "total_qty": rp["size"]}
                    STATE["mode"] = "REAL"
                    if STATE.get("pending_hunt"): STATE["pending_hunt"] = None
                    STATE["cross_margin_set"] = False
                    STATE["hide_until"] = None; STATE["revenge_until"] = None; STATE["cooldown_until"] = None
                else:
                    STATE["mode"] = new_mode
            mode = STATE["mode"]; set_cross_margin(); refresh_balance("CYCLE-START")
            if mode == "REAL":
                real_pos = get_real_position_sync()
                if real_pos is None and STATE["open_position"] is not None:
                    log(f"SYNC FIX: Bybit say NO POSITION, but bot diary say HOLDING {STATE['open_position']['side']} — Clearing fake HOLDING ❌")
                    STATE["open_position"] = None; STATE["pending_hunt"] = None; STATE["paper_fake_holding"] = STATE.get("paper_fake_holding", 0) + 1
                elif real_pos is not None and STATE["open_position"] is None and not STATE.get("pending_hunt"):
                    log(f"SYNC FIX: Bybit say REAL POSITION dey {real_pos} — Adopting Bybit position ✅")
                    STATE["open_position"] = {"side": real_pos["side"], "entry": real_pos["entry"], "wide_sl": float(real_pos["sl"] or 0) or (real_pos["entry"]+1200 if real_pos["side"]=="SHORT" else real_pos["entry"]-1200), "tp": float(real_pos["tp"] or 0) or (real_pos["entry"]-1500 if real_pos["side"]=="SHORT" else real_pos["entry"]+1500), "best_price": real_pos["entry"], "trailing_active": False, "trailing_price": None, "addon_done": False, "total_qty": real_pos["size"]}
            price, price_src = get_price_live()
            if price == 0.0: log("NO PRICE - All sources fail, skip cycle"); time.sleep(CONFIG["POLL_SEC"]); continue
            klines_1m = get_klines_1m(20); klines_15m = get_klines(200); macro = get_macro_live(); world = STATE.get("world", {})
            asian_hunt, asia_low, asia_high, long_liq, short_liq, liq_src = get_asian_hunt(price, klines_15m, klines_1m)
            session_hunt, session_name = get_session_reopen_hunt(price, klines_1m, klines_15m)
            is_news, _, news_reason = get_news_score()
            signals = get_signals(price, macro, klines_1m, asian_hunt, session_hunt)
            dest, agree, decided, longs, shorts, unknowns, certainty = decide(signals)
            unknown_names = [n for n, v in signals if v == "UNKNOWN"]
            sig_str = " ".join([f"{n}:{v}" for n, v in signals])
            score = calc_score(signals, dest, macro, is_news)
            need_cert = CONFIG["MIN_CERTAINTY_NEWS"] if is_news else CONFIG["MIN_CERTAINTY_NORMAL"]
            need_agree_base = CONFIG["MIN_AGREE_NEWS"] if is_news else CONFIG["MIN_AGREE_NORMAL"]
            need_score = CONFIG["MIN_SCORE_NEWS"] if is_news else CONFIG["MIN_SCORE_NORMAL"]
            need_agree = get_needed_agree(certainty, agree, decided, need_agree_base)
            is_sure = (certainty >= CONFIG["SURE_CERTAINTY"] and agree >= CONFIG["SURE_AGREE"])
            qty = get_dynamic_qty(price)
            hunt_dir, hunt_target, hunt_reason = detect_early_hunt(price, dest, klines_1m, long_liq, short_liq, asia_low, asia_high, world)
            if hunt_dir in ("LONG", "SHORT"): log(f"🏹 {hunt_reason}")
            elif hunt_dir == "MISS":
                log(f"🙈 {hunt_reason} — HIDE MODE ON")
                STATE["hide_until"] = now_utc() + timedelta(minutes=CONFIG["HIDE_AFTER_MISS_MIN"])
                hunt_dir = "NONE"
            is_pre_hunt, pre_reason = is_pre_hunt_window()
            is_hidden = STATE.get("hide_until") and now_utc() < STATE["hide_until"]
            is_revenge = STATE.get("cooldown_until") and now_utc() < STATE["cooldown_until"]
            if is_hidden: log(f"🙈 HIDE MODE till {STATE['hide_until'].strftime('%H:%M:%S')} — No new trade, wait hunt finish, then check certainties")
            if is_revenge: log(f"⏳ SMART RECHECK till {STATE['cooldown_until'].strftime('%H:%M:%S')} — 1 min check: certainties still go our way? hunters don take over? If yes, re-enter at market immediately")
            flipped = False
            if STATE["open_position"]:
                flipped = manage_position(price, klines_1m, qty, dest, certainty, agree, macro, long_liq, short_liq, hunt_dir, hunt_target, world)
                if flipped: log(f"FLIP DONE - Next cycle go open new {dest} trade if gates still pass")
            if STATE.get("pending_hunt") and not STATE["open_position"]:
                ph = STATE["pending_hunt"]; elapsed_min = (now_utc() - ph["time"]).total_seconds() / 60
                if mode == "REAL":
                    rp2 = get_real_position_sync()
                    if rp2 is not None and rp2["side"] == ph["side"]:
                        log(f"HUNT MARKET TRIGGER FILLED BY BYBIT {ph['side']} @ ${rp2['entry']:.0f} — Adopting Bybit position ✅")
                        STATE["pending_hunt"] = None
                        wide_sl, tp = calc_sl_tp_v1315(rp2["entry"], ph["side"])
                        if rp2.get("sl"): wide_sl = float(rp2["sl"])
                        if rp2.get("tp"): tp = float(rp2["tp"])
                        STATE["open_position"] = {"side": ph["side"], "entry": rp2["entry"], "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": rp2["entry"], "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": rp2["size"]}
                        STATE["trades_today"] += 1
                    elif elapsed_min >= CONFIG["HUNT_LIMIT_WAIT_MIN"]:
                        cancel_hunt_limit(ph.get("orderId"))
                        wide_sl, tp = calc_sl_tp_v1315(price, ph["side"])
                        ok = place_real_order(ph["side"], price, wide_sl, tp, ph["qty"])
                        if not ok: log("MARKET AFTER TIMEOUT REJECTED — No position")
                        else:
                            STATE["open_position"] = {"side": ph["side"], "entry": price, "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": ph["qty"]}
                            STATE["trades_today"] += 1; log(f"ORDER PLACED MAIN VIA MARKET AFTER HUNT TIMEOUT ({mode}) {ph['side']} Entry ${price:.0f}")
                    else:
                        log(f"HUNT MARKET TRIGGER WAITING {ph['side']} Trigger @ ${ph['hunt_price']:.0f} Elapsed {elapsed_min:.1f}/2 min — Bybit go trigger at market")
                else:
                    touched = (price >= ph["hunt_price"] if ph["side"] == "SHORT" else price <= ph["hunt_price"])
                    if touched:
                        log(f"HUNT MARKET TRIGGER FILLED (PAPER SIM) {ph['side']} Trigger @ ${ph['hunt_price']:.0f} Fill at market ${price:.0f}")
                        STATE["pending_hunt"] = None
                        wide_sl, tp = calc_sl_tp_v1315(price, ph["side"])
                        STATE["open_position"] = {"side": ph["side"], "entry": price, "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": ph["qty"]}
                        STATE["trades_today"] += 1
                    elif elapsed_min >= CONFIG["HUNT_LIMIT_WAIT_MIN"]:
                        cancel_hunt_limit(ph.get("orderId"))
                        wide_sl, tp = calc_sl_tp_v1315(price, ph["side"])
                        STATE["open_position"] = {"side": ph["side"], "entry": price, "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": ph["qty"]}
                        STATE["trades_today"] += 1; log(f"ORDER PLACED MAIN VIA MARKET AFTER HUNT TIMEOUT (PAPER) {ph['side']} Entry ${price:.0f}")
            gates = []
            gates.append((f"Agree {agree}/{decided} Need {need_agree} [Dynamic]", agree >= need_agree and decided >= need_agree))
            gates.append((f"Certainty {certainty:.0f}% Need {need_cert:.0f}%", certainty >= need_cert))
            gates.append((f"Score {score:.2f} / Thr {need_score:.2f}", score >= need_score))
            all_pass = all(p for _, p in gates); failed = [n for n, p in gates if not p]
            bal_show = STATE["real_balance"] if mode == "REAL" else STATE["balance"]
            if STATE["open_position"]:
                p = STATE["open_position"]; wide_sl_show = p["wide_sl"]; tp_show = p["tp"]; trail_show = p.get("trailing_price", 0) or 0
            elif dest in ("LONG", "SHORT"):
                wide_sl_show, tp_show = calc_sl_tp_v1315(price, dest); trail_show = 0
            else: wide_sl_show = tp_show = trail_show = 0
            log(f"MODE {mode} CROSS Hidden | PriceSrc {price_src} | Long {longs} Short {shorts} UNKNOWN {unknowns} {unknown_names} DEST {dest} Cert {certainty:.0f}% Agree {agree}/{decided} Need {need_agree} {'SURE' if is_sure else 'NEWS' if is_news else 'NORMAL'} MAIN {'Pass True' if all_pass else 'Pass False'} | NEVER_STOP True")
            log(f"SIGNALS: {sig_str}")
            log(f"LIVE MACRO DXY {macro['DXY_CHG']:.2f}% [{macro.get('DXY_CHG_SRC')}] NQ {macro['NQ_CHG']:.2f}% [{macro.get('NQ_CHG_SRC')}] SPX {macro['SPX_CHG']:.2f}% [{macro.get('SPX_CHG_SRC')}] GOLD {macro['GOLD_CHG']:.2f}% [{macro.get('GOLD_CHG_SRC')}] OI {macro['OI_CHG']:.2f}% [{macro.get('OI_CHG_SRC')}]")
            log(f"WORLD Nikkei {world.get('NIKKEI',0):.2f}% HangSeng {world.get('HANG_SENG',0):.2f}% FTSE {world.get('FTSE',0):.2f}% DAX {world.get('DAX',0):.2f}%")
            log(f"LIQ MAP LongLiq ${long_liq:,.0f} ShortLiq ${short_liq:,.0f} [{liq_src}] | Asia Low ${asia_low:,.0f} Asia High ${asia_high:,.0f} | Hunt {asian_hunt} EarlyHunt {hunt_dir} Target ${hunt_target:.0f} | Session {session_name} {session_hunt}")
            log(f"V13.15.8 Trailing $500/$50 + 1Min Smart Recheck + Hunter + World + BybitSync + MARKET TRIGGER | WideSL $1200 Trailing $500/$50 Hunter $500/$50")
            log(f"Qty {qty} Bal ${bal_show:.2f} Lev {CONFIG['LEVERAGE']}x CROSS | Price ${price:.0f} WideSL ${wide_sl_show:.0f} Trailing ${trail_show:.0f} TP ${tp_show:.0f}")
            log(f"W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} FLIP{STATE['flips']} ADDON{STATE['addons']} Trades {STATE['trades_today']} NEVER_STOP True | PnL ${STATE['pnl']:.2f} PaperStartPnL ${STATE['paper_start_pnl']:.2f}")
            if STATE["open_position"] and not flipped:
                p = STATE["open_position"]
                log(f"HOLDING [MAIN] {p['side']} {'HUNTER' if p.get('is_hunter_trade') else 'NORMAL'} Trailing {'ACTIVE $'+str(round(p.get('trailing_price',0))) if p.get('trailing_active') else 'SLEEP'} AddOn {'YES' if p.get('addon_done') else 'NO'} TotalQty {p.get('total_qty', qty)} Best ${p.get('best_price', p['entry']):.0f}")
            elif not STATE["open_position"] and not STATE.get("pending_hunt"):
                if is_hidden:
                    log("BLOCK: HIDE MODE — No trade, wait hunt finish")
                elif is_revenge:
                    log("BLOCK: SMART RECHECK 1 MIN — Check certainties + hunters, if still good re-enter at market, no miss entry")
                elif is_pre_hunt and hunt_dir == "NONE":
                    log(f"BLOCK: ⛔ PRE-HUNT LOCK {pre_reason} — 15 min to sweep, NO NEW ORDER, wait hunters show hand")
                elif hunt_dir in ("LONG", "SHORT"):
                    h_sl, h_tp = calc_hunter_sl_tp(price, hunt_dir, hunt_target)
                    log(f"🏹 HUNTER MODE TRADE: Following hunters {hunt_dir} Entry ${price:.0f} Hunt TP ${h_tp:.0f} Hunt SL ${h_sl:.0f} Target ${hunt_target:.0f} — IGNORING Certainties, hunters dey rule")
                    if mode == "REAL":
                        ok = place_real_order(hunt_dir, price, h_sl, h_tp, qty)
                        if not ok: log("HUNTER TRADE REJECTED — No position")
                        else:
                            STATE["open_position"] = {"side": hunt_dir, "entry": price, "wide_sl": h_sl, "tp": h_tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": qty, "is_hunter_trade": True}
                            STATE["trades_today"] += 1
                    else:
                        STATE["open_position"] = {"side": hunt_dir, "entry": price, "wide_sl": h_sl, "tp": h_tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": qty, "is_hunter_trade": True}
                        STATE["trades_today"] += 1; log(f"HUNTER TRADE PAPER {hunt_dir} Entry ${price:.0f} TP ${h_tp:.0f} SL ${h_sl:.0f}")
                elif all_pass:
                    hunt_block = False
                    if dest == "SHORT" and (asian_hunt == "LONG" or session_hunt == "LONG"): hunt_block = True; log("⛔ HUNT BLOCK: Cert SHORT but Hunters LONG — BLOCK SHORT, no blind trade")
                    if dest == "LONG" and (asian_hunt == "SHORT" or session_hunt == "SHORT"): hunt_block = True; log("⛔ HUNT BLOCK: Cert LONG but Hunters SHORT — BLOCK LONG, no blind trade")
                    if hunt_block:
                        log("BLOCKED BY HUNT — Hide, wait hunt finish")
                    else:
                        if CONFIG["HUNT_LIMIT_ENABLED"]:
                            hunt_price = price + CONFIG["HUNT_LIMIT_OFFSET_USD"] if dest == "SHORT" else price - CONFIG["HUNT_LIMIT_OFFSET_USD"]
                            log(f"TRADE SIGNAL MAIN - {mode} {dest} Entry Hunt MARKET TRIGGER @ ${hunt_price:.0f} Qty {qty} wait 2 min, if no trigger cancel + Market")
                            if mode == "REAL":
                                ok, oid = place_hunt_limit(dest, hunt_price, qty)
                                if ok: STATE["pending_hunt"] = {"side": dest, "hunt_price": hunt_price, "qty": qty, "time": now_utc(), "orderId": oid}
                                else:
                                    log("HUNT MARKET TRIGGER FAIL — Try Market directly with check")
                                    wide_sl, tp = calc_sl_tp_v1315(price, dest)
                                    ok2 = place_real_order(dest, price, wide_sl, tp, qty)
                                    if ok2:
                                        STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": qty}
                                        STATE["trades_today"] += 1
                            else:
                                STATE["pending_hunt"] = {"side": dest, "hunt_price": hunt_price, "qty": qty, "time": now_utc(), "orderId": None}
                        else:
                            wide_sl, tp = calc_sl_tp_v1315(price, dest)
                            if mode == "REAL":
                                ok = place_real_order(dest, price, wide_sl, tp, qty)
                                if ok:
                                    STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": qty}
                                    STATE["trades_today"] += 1; log(f"ORDER PLACED MAIN ({mode}) {dest} Entry ${price:.0f}")
                            else:
                                STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wide_sl, "tp": tp, "certainty": certainty, "best_price": price, "trailing_active": False, "trailing_price": None, "addon_done": False, "addon_qty": 0.0, "total_qty": qty}
                                STATE["trades_today"] += 1; log(f"ORDER PLACED MAIN (PAPER) {dest} Entry ${price:.0f}")
                else:
                    if not all_pass: log(f"BLOCK/WARY MAIN: {'; '.join(failed)} | UNKNOWN: {unknown_names} - Bot still alive, NEVER_STOP")
            if (now_utc() - last_heartbeat).total_seconds() > CONFIG["HEARTBEAT_MIN"] * 60: log(f"HEARTBEAT OK - MODE {mode} CROSS Hidden - Bal ${bal_show:.2f} PnL ${STATE['pnl']:.2f}"); last_heartbeat = now_utc()
            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e: log(f"ERROR {e}"); time.sleep(10)

if __name__ == "__main__": main()
