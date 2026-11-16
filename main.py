# BTC SWEEP BOT V13.16.2 SLIM FINAL - GOLD PICKER SMART - HUNTER DEAD
# FROM V13.15.9 -> V13.16.0 Slim -> V13.16.2 LIQ 5-LAYER FIX
# CLEANED: Duplicates + Cache + Hunter + Dead Coinglass placeholder REMOVED
# KEEP: Trailing $500/$50, WideSL $1200, TP $1500, Macro LIVE no cache,
# News, AddOn, CROSS, Dynamic Qty, NEVER_STOP, No Max Trade/Loss
# NEW: Sweep Hide Conditional 2min, 85% Bypass, Flip Only If Both Flip,
# Small Chops 75-84%, Skip Fake <75%
# NEW V13.16.2: LIQ 5-LAYER Binance > Bybit > OKX > Coinbase/Kraken Vol > Proxy-REAL

import time, requests, hmac, hashlib, os, threading, json
from datetime import datetime, timezone, timedelta
try:
    from flask import Flask
    _a = Flask(__name__)
    @_a.route("/")
    def _h(): return "BOT ALIVE V13.16.2 SLIM GOLD PICKER LIQ 5-LAYER", 200
    def _rf():
        try: _a.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)), use_reloader=False)
        except Exception as e: print(f"Flask {e}", flush=True)
    threading.Thread(target=_rf, daemon=True).start()
except Exception as e: print(f"Flask OFF {e}", flush=True)

CONFIG = {
    "SYMBOL": "BTCUSDT", "LEVERAGE": 50,
    "AUTO_SWITCH_UTC": datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc),
    "QTY_BASE": 0.010, "QTY_STEP": 0.005, "QTY_BASE_BAL": 20.0, "QTY_STEP_BAL": 8.0, "REAL_MAX_QTY": 0.100,
    "MIN_CERTAINTY_NORMAL": 75.0, "MIN_AGREE_NORMAL": 4, "MIN_SCORE_NORMAL": 0.60,
    "SURE_CERTAINTY": 95.0, "SURE_AGREE": 6,
    "NEWS_ENABLED": True, "MIN_CERTAINTY_NEWS": 75.0, "MIN_AGREE_NEWS": 4, "MIN_SCORE_NEWS": 0.60,
    "WIDE_SL_USD": 1200.0, "TP_DIST_USD": 1500.0,
    "TRAILING_ENABLED": True, "TRAIL_TRIGGER_MOVE_USD": 500.0, "TRAIL_DIST_USD": 50.0,
    "FEE_RATE": 0.0006, "SLIPPAGE_PCT": 0.0005,
    "FLIP_ENABLED": True, "FLIP_CERTAINTY": 75.0, "FLIP_AGREE": 4,
    "NEVER_STOP": True, "ADDON_ENABLED": True, "ADDON_WICK_MIN_USD": 500.0, "ADDON_WICK_MAX_USD": 900.0, "ADDON_BUFFER_PCT": 0.90,
    "GOLD_PICKER_ENABLED": True, "HUNTER_ENABLED": False,
    "HIGH_CERT_BYPASS": 85.0, "SWEEP_WAIT_MIN": 2, "HUNT_MIN_LIQ_USD": 2000000.0,
    "POLL_SEC": 5, "HEARTBEAT_MIN": 10, "BYBIT_BASE": "https://api.bybit.com",
    "COOLDOWN_MIN": 1, "EMERGENCY_AGAINST_USD": 400.0, "PROFIT_LOCK_MIN_USD": 50.0,
    "MACRO_BRAIN_ENABLED": True, "MACRO_ALERT_DXY_DROP": -0.5, "MACRO_ALERT_JPY_DROP": -0.8,
    "MACRO_CONFIRM_DXY_DROP": -1.0, "MACRO_CONFIRM_JPY_DROP": -1.5, "MACRO_CONFIRM_DXY_PUMP": 1.0,
    "MACRO_RECLAIM_LONG": 65746.0, "MACRO_BREAK_SHORT": 62978.0,
    "MACRO_FLIP_PULLBACK_LOW": 65800.0, "MACRO_FLIP_PULLBACK_HIGH": 66000.0,
    "MACRO_FLIP_SL": 64900.0, "MACRO_FLIP_TP1": 68000.0, "MACRO_FLIP_TP2": 70500.0,
    "MACRO_CONFIRM_MIN": 15, "MACRO_VOLUME_MULT": 2.0,
}
API_KEY = os.getenv("BYBIT_API_KEY", ""); API_SECRET = os.getenv("BYBIT_API_SECRET", "")
STATE = {"mode": "PAPER", "balance": 24.33, "real_balance": 0.0, "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0, "flips": 0, "addons": 0, "trades_today": 0,
    "open_position": None, "last_price": 0.0, "cross_margin_set": False, "last_qty": 0.010,
    "hide_until": None, "cooldown_until": None, "world": {},
    "macro_brain": {"score": 0.0, "bias": "NEUTRAL", "alert": None, "alert_time": None, "confirm_count": 0, "flip_pending": None},
    "sweep_wait": None, "sweep_wait_dir": None}

def now_utc(): return datetime.now(timezone.utc)
def log(m): print(f"[{now_utc().strftime('%H:%M:%S %d %b')}] {m}", flush=True)
def get_mode():
    rm = os.getenv("REAL_MODE", "").strip().lower()
    if rm == "true": return "REAL"
    if rm == "false": return "PAPER"
    return "REAL" if now_utc() >= CONFIG["AUTO_SWITCH_UTC"] else "PAPER"

def _sign(ts, rw, body):
    return hmac.new(API_SECRET.encode(), f"{ts}{API_KEY}{rw}{body}".encode(), hashlib.sha256).hexdigest()
def _safe(r):
    try:
        t = r.text.strip()
        return r.json() if t else {"retCode": -1, "retMsg": "Empty", "result": {}}
    except Exception as e: return {"retCode": -1, "retMsg": f"JSON {e}", "result": {}}
def bybit_post(path, p):
    try:
        ts = str(int(time.time()*1000)); body = json.dumps(p, separators=(',', ':')); s = _sign(ts, "5000", body)
        h = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "X-BAPI-SIGN": s, "Content-Type": "application/json"}
        return _safe(requests.post(CONFIG["BYBIT_BASE"]+path, data=body, headers=h, timeout=10))
    except Exception as e: return {"retCode": -1, "retMsg": str(e), "result": {}}
def bybit_get(path, p):
    try:
        ts = str(int(time.time()*1000)); qs = "&".join([f"{k}={v}" for k, v in sorted(p.items())]); s = _sign(ts, "5000", qs)
        h = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "X-BAPI-SIGN": s}
        return _safe(requests.get(CONFIG["BYBIT_BASE"]+path, params=p, headers=h, timeout=10))
    except Exception as e: return {"retCode": -1, "retMsg": str(e), "result": {}}

def get_real_balance():
    try:
        r = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
        if r.get("retCode") != 0: return STATE["real_balance"] or 24.33
        b = float(r["result"]["list"][0]["coin"][0]["walletBalance"]); STATE["real_balance"] = b; return b
    except: return STATE["real_balance"] or 24.33
def get_current_balance(): return STATE["real_balance"] if STATE["mode"] == "REAL" else STATE["balance"]
def refresh_balance():
    return get_real_balance() if STATE["mode"] == "REAL" else STATE["balance"]
def get_real_position_sync():
    if STATE["mode"] != "REAL" or not API_KEY: return None
    try:
        r = bybit_get("/v5/position/list", {"category": "linear", "symbol": CONFIG["SYMBOL"]})
        if r.get("retCode") != 0: return None
        for p in r["result"].get("list", []):
            if float(p.get("size", 0)) > 0:
                return {"side": "LONG" if p.get("side") == "Buy" else "SHORT", "size": float(p.get("size", 0)), "entry": float(p.get("avgPrice", 0)), "sl": p.get("stopLoss"), "tp": p.get("takeProfit")}
    except: pass
    return None
def set_cross_margin():
    if STATE.get("cross_margin_set"): return True
    if STATE["mode"] == "PAPER": STATE["cross_margin_set"] = True; return True
    if not API_KEY: return False
    try:
        bybit_post("/v5/position/switch-margin-mode", {"category": "linear", "symbol": CONFIG["SYMBOL"], "tradeMode": 0, "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        STATE["cross_margin_set"] = True; return True
    except: STATE["cross_margin_set"] = True; return True
def calc_fees(price, qty):
    pos = qty*price; return pos, pos*CONFIG["FEE_RATE"]*2, pos*CONFIG["SLIPPAGE_PCT"]*2, pos*CONFIG["FEE_RATE"]*2 + pos*CONFIG["SLIPPAGE_PCT"]*2
def get_dynamic_qty(price):
    bal = refresh_balance()
    qty = CONFIG["QTY_BASE"] if bal < 20 else round(CONFIG["QTY_BASE"] + int((bal-20)//8)*CONFIG["QTY_STEP"], 3)
    return min(qty, CONFIG["REAL_MAX_QTY"])
def place_real_order(side, price, sl, tp, qty, is_addon=False):
    if not API_KEY: log("REAL BLOCKED No API"); return False
    try:
        set_cross_margin()
        bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": CONFIG["SYMBOL"], "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        r = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Buy" if side == "LONG" else "Sell", "orderType": "Market", "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(sl, 1)), "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice", "tpslMode": "Full", "positionIdx": 0, "timeInForce": "GTC"})
        log(f"REAL ORDER {'OK' if r.get('retCode')==0 else 'REJECTED '+str(r.get('retMsg'))} {side} Qty {qty} Entry ${price:.0f} SL ${sl:.0f} TP ${tp:.0f}")
        return r.get("retCode") == 0
    except Exception as e: log(f"REAL ORDER ERR {e}"); return False
def update_real_sl(sl, side):
    if STATE["mode"] != "REAL" or not API_KEY: return True
    try:
        r = bybit_post("/v5/position/trading-stop", {"category": "linear", "symbol": CONFIG["SYMBOL"], "stopLoss": str(round(sl, 1)), "slTriggerBy": "LastPrice", "positionIdx": 0})
        return r.get("retCode") == 0
    except: return False
def close_real_position(side, qty):
    if STATE["mode"] != "REAL": return True
    try:
        r = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Sell" if side == "LONG" else "Buy", "orderType": "Market", "qty": str(qty), "timeInForce": "GTC", "positionIdx": 0})
        return r.get("retCode") == 0
    except: return False

# --- LIVE FETCH - NO CACHE ---
def yahoo_chg(sym):
    try:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            r = requests.get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=1m", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            meta = r.json()["chart"]["result"][0]["meta"]; price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0); prev = float(meta.get("previousClose") or price)
            if price and prev and price != prev: return round((price-prev)/prev*100, 3), price, prev
    except: pass
    return None, None, None
def yahoo_price_1h(sym):
    try:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            r = requests.get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=5m", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            res = r.json()["chart"]["result"][0]; closes = [c for c in res["indicators"]["quote"][0].get("close", []) if c is not None]
            if closes:
                cur = float(closes[-1]); prev = float(res["meta"].get("previousClose") or closes[0])
                chg_day = (cur-prev)/prev*100 if prev else 0; chg_1h = (cur-closes[-13])/closes[-13]*100 if len(closes) >= 13 and closes[-13] else 0
                return cur, chg_day, chg_1h
    except Exception as e: log(f"YAHOO FAIL {sym} {e}")
    return None, None, None
def get_world():
    w = {}
    for name, sym in [("NIKKEI", "^N225"), ("HANG_SENG", "^HSI"), ("FTSE", "^FTSE"), ("DAX", "^GDAXI"), ("NQ", "NQ=F"), ("SPX", "ES=F"), ("GOLD", "GC=F"), ("DXY", "DX-Y.NYB")]:
        chg, _, _ = yahoo_chg(sym); w[name] = chg if chg is not None else 0.0
    STATE["world"] = w
    log(f"WORLD LIVE Nikkei {w['NIKKEI']:.2f}% HSI {w['HANG_SENG']:.2f}% FTSE {w['FTSE']:.2f}% DAX {w['DAX']:.2f}% NQ {w['NQ']:.2f}% SPX {w['SPX']:.2f}% DXY {w['DXY']:.2f}% GOLD {w['GOLD']:.2f}%")
    return w
def get_price_live():
    for url, fn in [("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", "bybit"), ("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", "binance"), ("https://api.exchange.coinbase.com/products/BTC-USD/ticker", "coinbase")]:
        try:
            r = requests.get(url, timeout=5)
            if fn == "bybit": p = float(r.json()["result"]["list"][0]["lastPrice"])
            elif fn == "binance": p = float(r.json()["price"])
            else: p = float(r.json()["price"])
            STATE["last_price"] = p; return p, fn
        except: continue
    return STATE["last_price"] or 0.0, "Cached"
def get_klines(interval, limit):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}", timeout=5)
        kl = list(reversed(r.json()["result"]["list"])); return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "time": int(x[0])} for x in kl]
    except:
        try:
            bi = "1m" if interval == "1" else "15m"; r = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={bi}&limit={limit}", timeout=5)
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "time": int(x[0])} for x in r.json()]
        except: return []
def calc_rsi(klines, period=14):
    if not klines or len(klines) < period+1: return 50.0
    closes = [k["close"] for k in klines]; gains = []; losses = []
    for i in range(1, len(closes)):
        d = closes[i]-closes[i-1]; gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[-period:])/period; al = sum(losses[-period:])/period
    if al == 0: return 100.0
    return round(100 - (100/(1+ag/al)), 1)
def get_funding():
    try:
        r = requests.get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1", timeout=5)
        lst = r.json()["result"].get("list", [])
        if lst: return float(lst[0].get("fundingRate", 0))*100, "Bybit-LIVE"
    except: pass
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1", timeout=5)
        d = r.json()
        if d: return float(d[0].get("fundingRate", 0))*100, "Binance-LIVE"
    except: pass
    return 0.0, "FAIL"
def get_fear():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5); return int(r.json()["data"][0]["value"]), "Alternative-LIVE"
    except: return 50, "FAIL"

def get_macro_brain(price, k1, k15, macro_old):
    if not CONFIG["MACRO_BRAIN_ENABLED"]: return {"score": 0.0, "bias": "NEUTRAL", "alert": None, "flip": None}
    try:
        dxy_p, dxy_d, dxy_1h = yahoo_price_1h("DX-Y.NYB"); jpy_p, jpy_d, jpy_1h = yahoo_price_1h("USDJPY=X"); tnx_p, tnx_d, tnx_1h = yahoo_price_1h("^TNX")
        funding, fsrc = get_funding(); fng, fsrc2 = get_fear(); rsi = calc_rsi(k15[-60:] if k15 else [], 14)
        vol_spike = False; vol_mult = 1.0
        if k1 and len(k1) >= 15:
            rec = sum(abs(k["high"]-k["low"]) for k in k1[-5:]); avg = sum(abs(k["high"]-k["low"]) for k in k1[-15:-5])/10
            if avg > 0: vol_mult = rec/max(avg, 1); vol_spike = vol_mult >= CONFIG["MACRO_VOLUME_MULT"]
        score = 0.0; det = []
        if dxy_1h is not None:
            if dxy_1h > 0.2: score -= 2; det.append(f"DXY 1h +{dxy_1h:.2f}% SHORT+2")
            elif dxy_1h < -0.5: score += 2; det.append(f"DXY 1h {dxy_1h:.2f}% LONG+2")
            if dxy_p and dxy_p > 102.5: score -= 1; det.append("DXY>102.5 SHORT+1")
        if jpy_1h is not None:
            if jpy_1h < -1.5: score += 2; det.append("USDJPY -1.5% INTERVENTION LONG+2")
            elif jpy_1h < -0.8: score += 1; det.append("USDJPY dropping LONG+1")
        if tnx_d is not None and tnx_d > 0.5: score -= 1; det.append("US10Y up SHORT+1")
        if funding < -0.01: score += 1; det.append("Funding shorts crowded LONG+1")
        elif funding > 0.02: score -= 1; det.append("Funding high SHORT+1")
        if rsi < 25: score += 1; det.append(f"RSI {rsi} oversold LONG+1")
        elif rsi > 70: score -= 1; det.append("RSI overbought SHORT+1")
        if fng <= 10: score += 0.5; det.append(f"Fear {fng} bounce risk")
        if macro_old.get("NQ_CHG", 0) < -0.5: score -= 1; det.append("NQ down SHORT+1")
        bias = "SHORT" if score <= -2 else "LONG" if score >= 2 else "NEUTRAL"
        mb = STATE["macro_brain"]; alert = None; flip = None
        if (dxy_1h is not None and dxy_1h <= -0.5) or (jpy_1h is not None and jpy_1h <= -0.8):
            if mb.get("alert") is None: mb["alert"] = "DXY/JPY DROP"; mb["alert_time"] = now_utc(); mb["confirm_count"] = 0; log(f"MACRO ALERT DXY {dxy_1h} JPY {jpy_1h} - PAUSE new SHORT 15m")
            alert = "PAUSE_SHORT"
        if mb.get("alert"):
            el = (now_utc()-mb["alert_time"]).total_seconds()/60 if mb.get("alert_time") else 99; conf = 0; cd = []
            if dxy_1h is not None and dxy_1h <= -1.0: conf += 1; cd.append("DXY -1%")
            if jpy_1h is not None and jpy_1h <= -1.5: conf += 1; cd.append("JPY -1.5%")
            if price >= CONFIG["MACRO_RECLAIM_LONG"]: conf += 1; cd.append("BTC reclaim 65746")
            if vol_spike: conf += 1; cd.append(f"Vol {vol_mult:.1f}x")
            if k1 and len(k1) >= 15:
                mv = (k1[-1]["close"]-k1[-15]["close"])/k1[-15]["close"]*100
                if abs(mv) >= 0.8: conf += 1; cd.append(f"News {mv:.2f}%")
            mb["confirm_count"] = conf
            if conf >= 4:
                flip = {"dir": "LONG", "sl": CONFIG["MACRO_FLIP_SL"], "tp1": CONFIG["MACRO_FLIP_TP1"], "tp2": CONFIG["MACRO_FLIP_TP2"], "reasons": cd}
                log(f"MACRO FLIP CONFIRMED 4/5 {cd} - FLIP TO LONG"); mb["alert"] = None; mb["flip_pending"] = flip
            elif el >= 15: log(f"MACRO ALERT FAKE {el:.0f}m {conf}/5 - Back to SHORT"); mb["alert"] = None; mb["flip_pending"] = None; alert = None
        if dxy_1h is not None and dxy_1h >= 1.0 and price < CONFIG["MACRO_BREAK_SHORT"] and vol_spike:
            flip = {"dir": "SHORT", "sl": 65000, "tp1": 62000, "tp2": 60000, "reasons": ["DXY +1%", "BTC break 62978", "Vol spike"]}; log("MACRO DUMP CONFIRMED SHORT")
        mb["score"] = score; mb["bias"] = bias
        log(f"MACRO BRAIN Score {score:+.1f} Bias {bias} | DXY 1h {dxy_1h} JPY 1h {jpy_1h} | Funding {funding:.4f}% {fsrc} | Fear {fng} | RSI {rsi} | Vol {vol_mult:.1f}x | {' | '.join(det)}")
        return {"score": score, "bias": bias, "alert": alert, "flip": flip}
    except Exception as e: log(f"MACRO ERR {e}"); return {"score": 0.0, "bias": "NEUTRAL", "alert": None, "flip": None}

def get_macro_live():
    w = get_world(); oi = 0.0; oi_src = "FAIL"
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5); lst = r.json()["result"]["list"]; oi = (float(lst[-1]["openInterest"])-float(lst[0]["openInterest"]))/float(lst[0]["openInterest"])*100; oi_src = "Bybit"
    except: pass
    return {"DXY_CHG": w["DXY"], "NQ_CHG": w["NQ"], "SPX_CHG": w["SPX"], "GOLD_CHG": w["GOLD"], "OI_CHG": oi, "OI_SRC": oi_src}

# --- V13.16.2 LIQ 5-LAYER - CORRECTED ---
def get_liq(price, k1):
    ll = sl = 0.0
    # 1) BINANCE - Real liq
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100", timeout=5)
        d = r.json()
        if isinstance(d, list) and len(d) > 0:
            for x in d:
                sz = float(x.get("origQty", 0)) * float(x.get("price", price))
                if x.get("side") == "SELL": ll += sz
                elif x.get("side") == "BUY": sl += sz
            if ll + sl > 0:
                log(f"LIQ LIVE Binance Long ${ll:,.0f} Short ${sl:,.0f}")
                return ll, sl, "Binance-LIVE"
    except Exception as e: log(f"LIQ Binance fail {e}")
    # 2) BYBIT
    try:
        r = requests.get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50", timeout=5)
        lst = r.json().get("result", {}).get("list", [])
        for x in lst:
            sz = float(x.get("size", 0)) * float(x.get("price", price))
            if x.get("side") == "Sell": ll += sz
            elif x.get("side") == "Buy": sl += sz
        if ll + sl > 0:
            log(f"LIQ LIVE Bybit Long ${ll:,.0f} Short ${sl:,.0f}")
            return ll, sl, "Bybit-LIVE"
    except Exception as e: log(f"LIQ Bybit fail {e}")
    # 3) OKX - CORRECTED parsing: data -> details list
    try:
        r = requests.get("https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT-SWAP&limit=100", timeout=5)
        j = r.json()
        d = j.get("data", [])
        ll2 = sl2 = 0.0
        if d and len(d) > 0:
            for grp in d:
                details = grp.get("details", []) if isinstance(grp, dict) else []
                for x in details:
                    try:
                        sz = float(x.get("sz", 0)) * float(x.get("bkPx", price))
                        if x.get("side") == "sell": ll2 += sz
                        elif x.get("side") == "buy": sl2 += sz
                    except: pass
            if ll2 + sl2 > 0:
                log(f"LIQ LIVE OKX Long ${ll2:,.0f} Short ${sl2:,.0f}")
                return ll2, sl2, "OKX-LIVE"
    except Exception as e: log(f"LIQ OKX fail {e}")
    # 4) COINBASE + KRAKEN - Real volume for proxy, CORRECTED math
    coinbase_vol_usd_per_min = 0.0
    try:
        r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/stats", timeout=5)
        d = r.json()
        # Coinbase stats: volume = BTC volume last 30 days, volume_30day is in BTC
        vol_30d_btc = float(d.get("volume", 0) or d.get("volume_30day", 0) or 0)
        # Per-min USD vol = (30d BTC / 30 / 1440) * price
        if vol_30d_btc > 0: coinbase_vol_usd_per_min = (vol_30d_btc / 30 / 1440) * price
        log(f"LIQ BACKUP Coinbase 1m Vol ~${coinbase_vol_usd_per_min:,.0f}")
    except Exception as e: log(f"Coinbase vol fail {e}")
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=5)
        d = r.json().get("result", {})
        for k, v in d.items():
            kraken_vol_24h = float(v.get("v", [0, 0])[1]) * price
            log(f"LIQ BACKUP Kraken 24h Vol ${kraken_vol_24h:,.0f}")
            break
    except Exception as e: log(f"Kraken fail {e}")
    # 5) FINAL REAL PROXY
    try:
        if k1 and len(k1) >= 20:
            total_range = sum(abs(k["high"] - k["low"]) for k in k1[-20:])
            est_total = total_range * price * 0.05
            if coinbase_vol_usd_per_min > 0: est_total = max(est_total, coinbase_vol_usd_per_min * 20)
            if est_total < 500000: est_total = 500000.0
            pc = (k1[-1]["close"] - k1[-20]["close"]) / k1[-20]["close"] * 100 if k1[-20]["close"] else 0
            if pc < 0: ll, sl = est_total * 0.65, est_total * 0.35
            elif pc > 0: ll, sl = est_total * 0.35, est_total * 0.65
            else: ll, sl = est_total * 0.5, est_total * 0.5
            log(f"LIQ PROXY-REAL Long ${ll:,.0f} Short ${sl:,.0f} Est ${est_total:,.0f} Coinbase+BybitVol")
            return ll, sl, "Proxy-REAL-Coinbase-Vol"
    except: pass
    return 500000.0, 500000.0, "Proxy-Fallback"

def get_asia_range(k15):
    lows = []; highs = []
    for k in k15:
        try:
            dt = datetime.fromtimestamp(k["time"]/1000, tz=timezone.utc)
            if dt.date() == now_utc().date() and 0 <= dt.hour < 8: lows.append(k["low"]); highs.append(k["high"])
        except: pass
    if lows: return min(lows), max(highs)
    if len(k15) >= 32: return min(x["low"] for x in k15[-32:]), max(x["high"] for x in k15[-32:])
    return 0.0, 0.0
def get_sweep(price, k15, k1):
    a_low, a_high = get_asia_range(k15); ll, sl, src = get_liq(price, k1); hunt = "NEUTRAL"
    if a_low and a_high and k1:
        last = k1[-1]
        if last["low"] < a_low and last["close"] > a_low and ll > sl: hunt = "LONG"
        elif last["high"] > a_high and last["close"] < a_high and sl > ll: hunt = "SHORT"
    return hunt, a_low, a_high, ll, sl, src

def is_hunt_expected(dest, ll, sl, macro_bias):
    if macro_bias == dest: return False, "Macro already decided"
    pool = sl if dest == "LONG" else ll if dest == "SHORT" else 0
    now = now_utc(); mins = now.hour*60+now.minute; to_next = min([(o-mins) % 1440 for o in [0, 420, 810]])
    if pool >= CONFIG["HUNT_MIN_LIQ_USD"] and (to_next <= 30 or macro_bias == "NEUTRAL"):
        return True, f"HUNT EXPECTED Liq ${pool:,.0f} + session {to_next}m Macro {macro_bias}"
    return False, f"No hunt Liq ${pool:,.0f} Macro {macro_bias} Next {to_next}m"
def is_sweep_done(dest, k1, a_low, a_high):
    if not k1: return False
    last = k1[-1]
    if dest == "LONG" and a_low: return last["low"] < a_low and last["close"] > a_low
    if dest == "SHORT" and a_high: return last["high"] > a_high and last["close"] < a_high
    return False
def get_news():
    if not CONFIG["NEWS_ENABLED"]: return False, ""
    kl = get_klines("1", 15)
    if len(kl) >= 15:
        mv = (kl[-1]["close"]-kl[0]["close"])/kl[0]["close"]*100
        if abs(mv) >= 0.8: return True, f"VOL SPIKE {mv:.2f}% 15m"
    return False, ""
def get_signals(price, macro, k1, hunt):
    s = []
    s.append(("DXY", "SHORT" if macro["DXY_CHG"] > 0.05 else "LONG" if macro["DXY_CHG"] < -0.05 else "NEUTRAL"))
    s.append(("NQ", "LONG" if macro["NQ_CHG"] > 0.05 else "SHORT" if macro["NQ_CHG"] < -0.05 else "NEUTRAL"))
    s.append(("SPX", "LONG" if macro["SPX_CHG"] > 0.05 else "SHORT" if macro["SPX_CHG"] < -0.05 else "NEUTRAL"))
    s.append(("GOLD", "SHORT" if macro["GOLD_CHG"] > 0.15 else "LONG" if macro["GOLD_CHG"] < -0.10 else "NEUTRAL"))
    if k1 and len(k1) >= 5:
        pc = (k1[-1]["close"]-k1[-5]["close"])/k1[-5]["close"]*100
        if macro["OI_CHG"] > 0.8: s.append(("OI", "SHORT"))
        elif macro["OI_CHG"] < -0.8: s.append(("OI", "LONG"))
        elif macro["OI_CHG"] > 0.2 and pc < -0.05: s.append(("OI", "SHORT"))
        elif macro["OI_CHG"] < -0.2 and pc > 0.05: s.append(("OI", "LONG"))
        else: s.append(("OI", "NEUTRAL"))
    else: s.append(("OI", "NEUTRAL"))
    if k1 and len(k1) >= 3:
        last = k1[-1]; wd = last["close"]-last["low"]; wu = last["high"]-last["close"]; thr = price*0.001
        if wd > thr and wd > wu*1.2: s.append(("SWEEP", "LONG"))
        elif wu > thr and wu > wd*1.2: s.append(("SWEEP", "SHORT"))
        else:
            pc5 = (k1[-1]["close"]-k1[-5]["close"])/k1[-5]["close"]*100 if len(k1) >= 5 else 0
            s.append(("SWEEP", "LONG" if pc5 > 0.10 else "SHORT" if pc5 < -0.10 else "NEUTRAL"))
    else: s.append(("SWEEP", "NEUTRAL"))
    s.append(("HUNT", hunt if hunt in ("LONG", "SHORT") else "NEUTRAL"))
    if s[-1][1] == "NEUTRAL" and k1 and len(k1) >= 15:
        pc15 = (k1[-1]["close"]-k1[-15]["close"])/k1[-15]["close"]*100
        if pc15 > 0.15: s[-1] = ("HUNT", "LONG")
        elif pc15 < -0.15: s[-1] = ("HUNT", "SHORT")
    return s
def decide(signals):
    L = sum(1 for _, v in signals if v == "LONG"); S = sum(1 for _, v in signals if v == "SHORT"); D = L+S
    dest = "LONG" if L > S else "SHORT" if S > L else "NONE"; agree = L if L > S else S if S > L else 0
    return dest, agree, D, L, S, (agree/D*100 if D else 0)
def calc_score(signals, dest, macro, is_news):
    _, agree, D, _, _, cert = decide(signals); base = cert/100; align = 0.4 if dest == "LONG" and macro["NQ_CHG"] > 0 and macro["SPX_CHG"] > 0 else 0.3 if dest == "SHORT" and macro["DXY_CHG"] > 0 else 0
    return round(base+align+(0.4 if is_news else 0), 2)
def calc_sl_tp(price, side):
    return (round(price-1200, 1), round(price+1500, 1)) if side == "LONG" else (round(price+1200, 1), round(price-1500, 1))
def record_close(side, entry, close_p, qty, reason):
    _, _, _, total = calc_fees(entry, qty); gross = (close_p-entry)*qty if side == "LONG" else (entry-close_p)*qty; net = gross-total
    if STATE["mode"] == "PAPER": STATE["balance"] += net
    STATE["pnl"] += net; STATE["cooldown_until"] = now_utc()+timedelta(minutes=CONFIG["COOLDOWN_MIN"])
    if reason in ("TP", "TRAILING"): STATE["wins"] += 1
    elif reason == "FLIP": STATE["flips"] += 1
    elif net > 0: STATE["wins"] += 1
    elif net < -0.01: STATE["losses"] += 1
    else: STATE["breakevens"] += 1
    log(f"CLOSE {reason} {side} ${net:.2f} at ${close_p:.0f} - 1 min Smart Recheck")
    STATE["open_position"] = None; log(f"BALANCE ${refresh_balance():.2f}"); return net
def is_flip_confirmed(flip_dest, cert, agree, macro, side):
    if flip_dest == "NONE" or flip_dest == side: return False
    if not (cert >= CONFIG["FLIP_CERTAINTY"] and agree >= CONFIG["FLIP_AGREE"]): return False
    mb = STATE["macro_brain"]["bias"]
    if mb != flip_dest: log(f"FLIP BLOCKED Cert {flip_dest} but Macro {mb} - NO FLIP"); return False
    return True
def manage_position(price, qty, flip_dest, cert, agree, macro, ll, sl):
    if not STATE["open_position"]: return False
    p = STATE["open_position"]; entry = float(p["entry"]); side = p["side"]; tq = p.get("total_qty", qty)
    best = max(p.get("best_price", entry), price) if side == "LONG" else min(p.get("best_price", entry), price)
    p["best_price"] = best; favour = abs(best-entry); pnl_pts = (price-entry) if side == "LONG" else (entry-price)
    against = abs(price-entry) if ((side == "LONG" and price < entry) or (side == "SHORT" and price > entry)) else 0
    if CONFIG["FLIP_ENABLED"] and is_flip_confirmed(flip_dest, cert, agree, macro, side):
        log(f"FLIP {side}->{flip_dest} CONFIRMED Macro+Cert BOTH")
        if STATE["mode"] == "REAL": close_real_position(side, tq)
        record_close(side, entry, price, tq, "FLIP"); return True
    if (price >= p["tp"] if side == "LONG" else price <= p["tp"]):
        if STATE["mode"] == "REAL": close_real_position(side, tq)
        record_close(side, entry, price, tq, "TP"); return False
    if CONFIG["TRAILING_ENABLED"] and favour >= 500:
        if not p.get("trailing_active"): p["trailing_active"] = True; log(f"TRAILING ON {side} Favour ${favour:.0f} SL=Best-$50")
        tp_price = best-50 if side == "LONG" else best+50; p["trailing_price"] = tp_price
        if side == "LONG" and tp_price > p["wide_sl"]: p["wide_sl"] = tp_price; update_real_sl(tp_price, side)
        elif side == "SHORT" and tp_price < p["wide_sl"]: p["wide_sl"] = tp_price; update_real_sl(tp_price, side)
        if (price <= tp_price if side == "LONG" else price >= tp_price):
            log(f"TRAILING HIT Close PROFIT {side} ${price:.0f}")
            if STATE["mode"] == "REAL": close_real_position(side, tq)
            record_close(side, entry, price, tq, "TRAILING"); return False
    elif favour > 0: log(f"TRAILING SLEEP Favour ${favour:.0f}<500 WideSL ${p['wide_sl']:.0f}")
    if pnl_pts > 50 and against > 0: log(f"PROFIT +${pnl_pts:.0f} HOLD Trailing go lock")
    if against >= 400 and not p.get("trailing_active"):
        log(f"EMERGENCY AGAINST ${against:.0f} - CLOSE, no wait WideSL")
        if STATE["mode"] == "REAL": close_real_position(side, tq)
        record_close(side, entry, price, tq, "EMERGENCY"); return False
    if CONFIG["ADDON_ENABLED"] and not p.get("addon_done", False) and 500 <= against <= 900:
        if (flip_dest == side or flip_dest == "NONE") and ((sl > ll) if side == "SHORT" else (ll > sl)):
            bal = get_current_balance() or 24.33; after = round(tq+qty, 3)
            if after*price <= bal*50*0.90:
                if STATE["mode"] == "REAL":
                    if place_real_order(side, price, p["wide_sl"], p["tp"], qty, True): p["addon_done"] = True; p["total_qty"] = after; STATE["addons"] += 1
                else: p["addon_done"] = True; p["total_qty"] = after; STATE["addons"] += 1; log(f"ADD-ON PAPER {side} {qty} Total {after}")
    # FIXED: WideSL check must still work even if trailing active - trailing SL is wide_sl itself
    if (price <= p["wide_sl"] if side == "LONG" else price >= p["wide_sl"]):
        # If trailing active, wide_sl == trailing price, so this IS trailing hit, already handled above, but keep as safety
        if not p.get("trailing_active") or (price <= p["wide_sl"] if side == "LONG" else price >= p["wide_sl"]):
            # Avoid double close if trailing already handled - check if we already returned, else close
            log(f"WIDE SL HIT ${price:.0f} vs ${p['wide_sl']:.0f}")
            if STATE["mode"] == "REAL": close_real_position(side, tq)
            record_close(side, entry, price, tq, "WIDE_SL"); return False
    return False

def main():
    log("BOT V13.16.2 SLIM FINAL GOLD PICKER STARTED - HUNTER DEAD LIQ 5-LAYER | Trailing $500/$50 WideSL $1200")
    last_hb = now_utc()
    while True:
        try:
            nm = get_mode()
            if nm != STATE["mode"]:
                if nm == "REAL":
                    STATE["pnl"] = 0; STATE["wins"] = STATE["losses"] = STATE["breakevens"] = STATE["flips"] = STATE["addons"] = STATE["trades_today"] = 0; STATE["open_position"] = None; STATE["hide_until"] = STATE["cooldown_until"] = None
                    bal = get_real_balance(); log(f"*** AUTO SWITCH REAL *** Bal ${bal:.2f} - Sync Bybit")
                    rp = get_real_position_sync()
                    if rp: STATE["open_position"] = {"side": rp["side"], "entry": rp["entry"], "wide_sl": float(rp["sl"] or 0) or (rp["entry"]+1200 if rp["side"] == "SHORT" else rp["entry"]-1200), "tp": float(rp["tp"] or 0) or (rp["entry"]-1500 if rp["side"] == "SHORT" else rp["entry"]+1500), "best_price": rp["entry"], "trailing_active": False, "addon_done": False, "total_qty": rp["size"]}
                    STATE["mode"] = "REAL"; STATE["cross_margin_set"] = False
                else: STATE["mode"] = nm
            mode = STATE["mode"]; set_cross_margin(); refresh_balance()
            if mode == "REAL":
                rp = get_real_position_sync()
                if rp is None and STATE["open_position"] is not None: log("SYNC FIX Bybit NO POS - Clear fake HOLDING"); STATE["open_position"] = None
                elif rp is not None and STATE["open_position"] is None:
                    log(f"SYNC FIX Adopt Bybit {rp}"); STATE["open_position"] = {"side": rp["side"], "entry": rp["entry"], "wide_sl": float(rp["sl"] or 0) or (rp["entry"]+1200 if rp["side"] == "SHORT" else rp["entry"]-1200), "tp": float(rp["tp"] or 0) or (rp["entry"]-1500 if rp["side"] == "SHORT" else rp["entry"]+1500), "best_price": rp["entry"], "trailing_active": False, "addon_done": False, "total_qty": rp["size"]}
            price, psrc = get_price_live()
            if price == 0: log("NO PRICE skip"); time.sleep(5); continue
            k1 = get_klines("1", 20); k15 = get_klines("15", 200); macro = get_macro_live(); world = STATE.get("world", {})
            mb = get_macro_brain(price, k1, k15, macro)
            hunt, a_low, a_high, ll, sl, liq_src = get_sweep(price, k15, k1)
            is_news, news_r = get_news(); signals = get_signals(price, macro, k1, hunt)
            dest, agree, decided, L, S, cert = decide(signals); score = calc_score(signals, dest, macro, is_news)
            need_cert = CONFIG["MIN_CERTAINTY_NEWS"] if is_news else CONFIG["MIN_CERTAINTY_NORMAL"]; need_agree = CONFIG["MIN_AGREE_NEWS"] if is_news else CONFIG["MIN_AGREE_NORMAL"]; need_score = CONFIG["MIN_SCORE_NEWS"] if is_news else CONFIG["MIN_SCORE_NORMAL"]
            qty = get_dynamic_qty(price); macro_bias = mb.get("bias", "NEUTRAL")
            high_bypass = (cert >= 85.0 and macro_bias == dest and dest in ("LONG", "SHORT"))
            if high_bypass: log(f"HIGH CERT BYPASS {cert:.0f}% + Macro {macro_bias} {dest} - ENTER NOW no wait wick")
            hunt_exp, hunt_reason = is_hunt_expected(dest, ll, sl, macro_bias) if dest in ("LONG", "SHORT") else (False, "No dest")
            log(f"GOLD PICKER HuntExp {hunt_exp} {hunt_reason} | HighBypass {high_bypass} Macro {macro_bias} Cert {cert:.0f}% Dest {dest}")
            sweep_wait = False
            if hunt_exp and not high_bypass and dest in ("LONG", "SHORT"):
                if STATE.get("sweep_wait") is None: STATE["sweep_wait"] = now_utc(); STATE["sweep_wait_dir"] = dest; log(f"HIDE 2min wait sweep {dest}")
                el = (now_utc()-STATE["sweep_wait"]).total_seconds()/60
                if el < 2: sweep_wait = True; log(f"SWEEP WAIT {el:.1f}/2min {dest}")
                else:
                    if is_sweep_done(dest, k1, a_low, a_high): log(f"SWEEP DONE {dest} ENTER NOW"); STATE["sweep_wait"] = None
                    else: log(f"SWEEP NOT DONE {dest} reset wait no blind"); STATE["sweep_wait"] = now_utc(); sweep_wait = True
            else: STATE["sweep_wait"] = None
            pause_short = mb.get("alert") == "PAUSE_SHORT"
            if pause_short: log("MACRO PAUSE SHORT 15m - no new SHORT")
            mflip = mb.get("flip")
            if mflip: log(f"MACRO FLIP READY {mflip['dir']} {mflip.get('reasons')} Need Cert agree too")
            is_revenge = STATE.get("cooldown_until") and now_utc() < STATE["cooldown_until"]
            flipped = False
            if STATE["open_position"]: flipped = manage_position(price, qty, dest, cert, agree, macro, ll, sl)
            gates = [(f"Agree {agree}/{decided} Need {need_agree}", agree >= need_agree and decided >= need_agree), (f"Cert {cert:.0f}% Need {need_cert:.0f}%", cert >= need_cert), (f"Score {score:.2f}/{need_score:.2f}", score >= need_score)]
            all_pass = all(p for _, p in gates); failed = [n for n, p in gates if not p]
            bal_show = STATE["real_balance"] if mode == "REAL" else STATE["balance"]
            if STATE["open_position"]: p = STATE["open_position"]; wsl, tp_s, trail = p["wide_sl"], p["tp"], p.get("trailing_price", 0) or 0
            elif dest in ("LONG", "SHORT"): wsl, tp_s = calc_sl_tp(price, dest); trail = 0
            else: wsl = tp_s = trail = 0
            log(f"MODE {mode} | Long {L} Short {S} DEST {dest} Cert {cert:.0f}% Agree {agree}/{decided} {'PASS' if all_pass else 'FAIL'} | MACRO {macro_bias} Score {mb.get('score',0):+.1f} Flip {mflip['dir'] if mflip else 'None'}")
            log(f"SIGNALS {' '.join([f'{n}:{v}' for n,v in signals])}")
            log(f"LIQ Long ${ll:,.0f} Short ${sl:,.0f} [{liq_src}] Asia Low ${a_low:,.0f} High ${a_high:,.0f} Hunt {hunt} HuntExp {hunt_exp} SweepWait {sweep_wait} HighBypass {high_bypass}")
            log(f"Qty {qty} Bal ${bal_show:.2f} Lev 50x | Price ${price:.0f} WideSL ${wsl:.0f} Trail ${trail:.0f} TP ${tp_s:.0f}")
            log(f"W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} FLIP{STATE['flips']} ADDON{STATE['addons']} Trades {STATE['trades_today']} NEVER_STOP True | PnL ${STATE['pnl']:.2f}")
            if STATE["open_position"] and not flipped:
                p = STATE["open_position"]; log(f"HOLDING [MAIN] {p['side']} NORMAL Trailing {'ACTIVE' if p.get('trailing_active') else 'SLEEP'} AddOn {'YES' if p.get('addon_done') else 'NO'} TotalQty {p.get('total_qty', qty)} Best ${p.get('best_price', p['entry']):.0f}")
            elif not STATE["open_position"]:
                if sweep_wait: log("BLOCK GOLD PICKER SWEEP WAIT 2 MIN - Hide during wick, enter after sweep")
                elif is_revenge: log("BLOCK SMART RECHECK 1 MIN")
                elif pause_short and dest == "SHORT": log("BLOCK MACRO PAUSE SHORT")
                elif all_pass:
                    if mflip and mflip["dir"] != dest: log(f"BLOCK Macro Flip {mflip['dir']} vs Cert {dest} - WAIT both")
                    else:
                        if mflip and mflip["dir"] == dest:
                            f_sl, f_tp = mflip["sl"], mflip["tp1"]; log(f"MACRO FLIP TRADE {mode} {dest} Entry ${price:.0f} SL ${f_sl:.0f} TP1 ${f_tp:.0f} TP2 {mflip['tp2']}")
                            if mode == "REAL":
                                if place_real_order(dest, price, f_sl, f_tp, qty): STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": f_sl, "tp": f_tp, "best_price": price, "trailing_active": False, "addon_done": False, "total_qty": qty}; STATE["trades_today"] += 1
                            else: STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": f_sl, "tp": f_tp, "best_price": price, "trailing_active": False, "addon_done": False, "total_qty": qty}; STATE["trades_today"] += 1
                            STATE["macro_brain"]["flip_pending"] = None
                        else:
                            wsl2, tp2 = calc_sl_tp(price, dest); tag = "HIGH CERT ENTER NOW" if high_bypass else "SMALL CHOP CERT ENTER" if cert < 85 else "GOLD PICKER AFTER SWEEP"
                            log(f"TRADE GOLD PICKER {mode} {dest} {tag} Entry ${price:.0f} SL ${wsl2:.0f} TP ${tp2:.0f} Qty {qty}")
                            if mode == "REAL":
                                if place_real_order(dest, price, wsl2, tp2, qty): STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wsl2, "tp": tp2, "best_price": price, "trailing_active": False, "addon_done": False, "total_qty": qty}; STATE["trades_today"] += 1
                            else: STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wsl2, "tp": tp2, "best_price": price, "trailing_active": False, "addon_done": False, "total_qty": qty}; STATE["trades_today"] += 1
                else: log(f"BLOCK SKIP FAKE: {'; '.join(failed)} - NEVER_STOP")
            if (now_utc()-last_hb).total_seconds() > 600: log(f"HEARTBEAT MODE {mode} Bal ${bal_show:.2f} PnL ${STATE['pnl']:.2f}"); last_hb = now_utc()
            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e: log(f"ERROR {e}"); time.sleep(10)
if __name__ == "__main__": main()
# END V13.16.2 SLIM FINAL
