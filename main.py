# BTC SWEEP BOT V13.16.4.6 REAL-FIXED - GOLD PICKER SMART
# FIX V13.16.4.6: REAL CLOSE with reduceOnly, STATE PERSISTENCE bot_state.json, STRONG SYNC
# KEEP: Macro -1.5/+1.5, HuntExp Session-Only + REAL Liq Only, HighBypass Allow NEUTRAL, Sweep Wait 6min, WideSL $1200, Dynamic Lev 15x/20x/25x/50x, Dynamic Qty Min 0.001, CROSS, AddOn, 3-Cycle Confirm, Emergency Hunt Cert 90%
# KEEP: AUTO_SWITCH 2026-11-16 01:00 UTC -> REAL (as owner requested)
# DYNAMIC TRAILING: Trigger = (Fees*1.2 + $1.50)/Qty, Floor $300, Round $50, Dist 0, Wide TP $1500, Re-entry $20 Gap

import time, requests, hmac, hashlib, os, threading, json, math
from datetime import datetime, timezone, timedelta
try:
    from flask import Flask
    _a = Flask(__name__)
    @_a.route("/")
    def _h(): return "BOT ALIVE V13.16.4.6 REAL-FIXED", 200
    def _rf():
        try: _a.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)), use_reloader=False)
        except Exception as e: print(f"Flask {e}", flush=True)
    threading.Thread(target=_rf, daemon=True).start()
except Exception as e: print(f"Flask OFF {e}", flush=True)

CONFIG = {
    "SYMBOL": "BTCUSDT",
    "AUTO_SWITCH_UTC": datetime(2026, 11, 16, 1, 0, tzinfo=timezone.utc),
    "QTY_BASE": 0.010, "QTY_STEP": 0.005, "QTY_MIN": 0.001, "REAL_MAX_QTY": 0.100,
    "MIN_CERTAINTY_NORMAL": 75.0, "MIN_AGREE_NORMAL": 4, "MIN_SCORE_NORMAL": 0.60,
    "NEWS_ENABLED": True, "MIN_CERTAINTY_NEWS": 75.0, "MIN_AGREE_NEWS": 4, "MIN_SCORE_NEWS": 0.60,
    "WIDE_SL_USD": 1200.0, "TP_DIST_USD": 1500.0,
    "TRAILING_ENABLED": True,
    "TRAIL_TARGET_NET": 1.50,
    "TRAIL_SAFETY": 1.2,
    "TRAIL_FLOOR_USD": 300.0,
    "TRAIL_ROUND_USD": 50.0,
    "REENTRY_GAP_USD": 20.0,
    "FEE_RATE": 0.0006, "SLIPPAGE_PCT": 0.0005,
    "FLIP_ENABLED": True, "FLIP_CERTAINTY": 75.0, "FLIP_AGREE": 4,
    "ADDON_ENABLED": True, "ADDON_BUFFER_PCT": 0.90,
    "HIGH_CERT_BYPASS": 85.0, "SWEEP_WAIT_MIN": 2, "SWEEP_TIMEOUT_MIN": 6, "HUNT_MIN_LIQ_USD": 2000000.0,
    "POLL_SEC": 5, "BYBIT_BASE": "https://api.bybit.com",
    "COOLDOWN_MIN": 1,
    "CONFIRM_CYCLES": 3, "EMERGENCY_HUNT_CERT": 90.0, "EMERGENCY_BLOCK_MIN": 5,
    "MACRO_BRAIN_ENABLED": True, "MACRO_VOLUME_MULT": 2.0,
    "MACRO_RECLAIM_LONG": 65746.0, "MACRO_BREAK_SHORT": 62978.0,
    "MACRO_THRESHOLD": 1.5,
}
API_KEY = os.getenv("BYBIT_API_KEY", ""); API_SECRET = os.getenv("BYBIT_API_SECRET", "")
STATE = {"mode": "PAPER", "balance": 24.33, "real_balance": 0.0, "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0, "flips": 0, "addons": 0, "trades_today": 0,
    "open_position": None, "last_price": 0.0, "cross_margin_set": False, "leverage": 50,
    "cooldown_until": None, "world": {},
    "macro_brain": {"score": 0.0, "bias": "NEUTRAL", "alert": None, "alert_time": None, "confirm_count": 0, "flip_pending": None},
    "sweep_wait": None, "sweep_wait_dir": None,
    "hunt_confirm_count": 0, "hunt_confirm_dest": None,
    "flip_confirm_count": 0, "flip_confirm_dest": None,
    "emergency_block_until": None, "emergency_block_side": None,
    "last_trail_exit_price": None, "last_trail_exit_side": None, "last_trail_exit_time": None}

def now_utc(): return datetime.now(timezone.utc)
def log(m): print(f"[{now_utc().strftime('%H:%M:%S %d %b')}] {m}", flush=True)
def get_mode():
    rm = os.getenv("REAL_MODE", "").strip().lower()
    if rm == "true": return "REAL"
    if rm == "false": return "PAPER"
    return "REAL" if now_utc() >= CONFIG["AUTO_SWITCH_UTC"] else "PAPER"

# --- FIX 3: STATE PERSISTENCE ---
STATE_FILE = "bot_state.json"
def save_state():
    try:
        data = {}
        for k, v in STATE.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            elif isinstance(v, dict):
                nd = {}
                for kk, vv in v.items():
                    nd[kk] = vv.isoformat() if isinstance(vv, datetime) else vv
                data[k] = nd
            elif k == "open_position" and v is not None:
                # save open_position too, but sync will verify with Bybit
                nd = {}
                for kk, vv in v.items():
                    nd[kk] = vv.isoformat() if isinstance(vv, datetime) else vv
                data[k] = nd
            else:
                data[k] = v
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        log(f"SAVE STATE FAIL {e}")

def load_state():
    try:
        if not os.path.exists(STATE_FILE):
            return
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in ("cooldown_until", "emergency_block_until", "last_trail_exit_time", "sweep_wait"):
                if v:
                    try: STATE[k] = datetime.fromisoformat(v)
                    except: STATE[k] = None
                else: STATE[k] = None
            elif k == "macro_brain" and isinstance(v, dict):
                for kk, vv in v.items():
                    if kk == "alert_time" and vv:
                        try: STATE["macro_brain"][kk] = datetime.fromisoformat(vv)
                        except: pass
                    else: STATE["macro_brain"][kk] = vv
            elif k == "open_position" and isinstance(v, dict):
                STATE[k] = v
            elif k in STATE:
                STATE[k] = v
        log(f"STATE RESTORED Wins {STATE.get('wins')} PnL ${STATE.get('pnl',0):.2f} LastTrailExit {STATE.get('last_trail_exit_price')} OpenPos {STATE.get('open_position') is not None}")
    except Exception as e:
        log(f"LOAD STATE FAIL {e} - start fresh but sync Bybit")

load_state()

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
def refresh_balance(): return get_real_balance() if STATE["mode"] == "REAL" else STATE["balance"]
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

def get_dynamic_leverage(bal=None):
    if bal is None: bal = get_current_balance() or 24.33
    if bal >= 20: lev = 50
    elif bal >= 10: lev = 25
    elif bal >= 5: lev = 20
    else: lev = 15
    STATE["leverage"] = lev
    return lev
def set_cross_margin():
    if STATE.get("cross_margin_set"): return True
    if STATE["mode"] == "PAPER": STATE["cross_margin_set"] = True; return True
    if not API_KEY: return False
    try:
        lev = get_dynamic_leverage()
        bybit_post("/v5/position/switch-margin-mode", {"category": "linear", "symbol": CONFIG["SYMBOL"], "tradeMode": 0, "buyLeverage": str(lev), "sellLeverage": str(lev)})
        STATE["cross_margin_set"] = True; return True
    except: STATE["cross_margin_set"] = True; return True
def calc_fees(price, qty):
    pos = qty*price; return pos, pos*CONFIG["FEE_RATE"]*2, pos*CONFIG["SLIPPAGE_PCT"]*2, pos*CONFIG["FEE_RATE"]*2 + pos*CONFIG["SLIPPAGE_PCT"]*2

def get_dynamic_trigger(entry_price, qty=None):
    if qty is None: qty = CONFIG["QTY_BASE"]
    if not qty or qty <= 0: qty = CONFIG["QTY_BASE"]
    pos = qty * entry_price
    fees = pos * (CONFIG["FEE_RATE"]*2 + CONFIG["SLIPPAGE_PCT"]*2)
    need_gross = fees * CONFIG["TRAIL_SAFETY"] + CONFIG["TRAIL_TARGET_NET"]
    raw = need_gross / qty
    trigger = math.ceil(raw / CONFIG["TRAIL_ROUND_USD"]) * CONFIG["TRAIL_ROUND_USD"]
    trigger = max(CONFIG["TRAIL_FLOOR_USD"], trigger)
    log(f"DYN TRAIL Entry ${entry_price:.0f} Qty {qty} Fees ${fees:.2f} -> Trigger ${trigger:.0f} (Net at trigger ${trigger*qty-fees:.2f})")
    return trigger

def get_dynamic_qty(price, lev=None):
    bal = refresh_balance()
    if not bal or bal <= 0: bal = 24.33
    if price is None or price <= 0: return 0.0
    if lev is None: lev = get_dynamic_leverage(bal)
    if bal < 20: base_qty = CONFIG["QTY_BASE"]
    else: base_qty = round(CONFIG["QTY_BASE"] + int((bal-20)//8)*CONFIG["QTY_STEP"], 3)
    max_affordable = (bal * 0.90 * lev) / price
    if max_affordable < CONFIG["QTY_MIN"]:
        log(f"QTY BLOCK Bal ${bal:.2f} Lev {lev}x too small - wait deposit")
        return 0.0
    qty = min(base_qty, max_affordable)
    qty = max(CONFIG["QTY_MIN"], min(qty, CONFIG["REAL_MAX_QTY"]))
    qty = int(qty * 1000) / 1000.0
    if qty < CONFIG["QTY_MIN"]: qty = CONFIG["QTY_MIN"]
    liq_dist = price / lev
    log(f"DYN LEV {lev}x QTY Bal ${bal:.2f} Base {base_qty} MaxAfford {max_affordable:.4f} -> Qty {qty} Margin ${qty*price/lev:.2f} LiqDist ~${liq_dist:.0f} (WideSL $1200 {'SAFE' if liq_dist > 1200 else 'TIGHT'})")
    return qty

def place_real_order(side, price, sl, tp, qty, is_addon=False):
    if not API_KEY: log("REAL BLOCKED No API"); return False
    if not qty or qty < CONFIG["QTY_MIN"]: log(f"REAL BLOCK Qty {qty} < Min"); return False
    try:
        set_cross_margin()
        lev = get_dynamic_leverage()
        bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": CONFIG["SYMBOL"], "buyLeverage": str(lev), "sellLeverage": str(lev)})
        r = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": "Buy" if side == "LONG" else "Sell", "orderType": "Market", "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(sl, 1)), "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice", "tpslMode": "Full", "positionIdx": 0, "timeInForce": "GTC"})
        log(f"REAL ORDER {'OK' if r.get('retCode')==0 else 'REJECTED '+str(r.get('retMsg'))} {side} Qty {qty} Lev {lev}x Entry ${price:.0f} SL ${sl:.0f} TP ${tp:.0f}")
        return r.get("retCode") == 0
    except Exception as e: log(f"REAL ORDER ERR {e}"); return False

def update_real_sl(sl, side):
    if STATE["mode"] != "REAL" or not API_KEY: return True
    try:
        r = bybit_post("/v5/position/trading-stop", {"category": "linear", "symbol": CONFIG["SYMBOL"], "stopLoss": str(round(sl, 1)), "slTriggerBy": "LastPrice", "positionIdx": 0})
        return r.get("retCode") == 0
    except: return False

# --- FIX 1: REAL CLOSE WEY DEY REALLY CLOSE ---
def close_real_position(side, qty):
    if STATE["mode"] != "REAL":
        return True
    if not API_KEY:
        log("REAL CLOSE BLOCKED No API"); return False
    try:
        close_side = "Sell" if side == "LONG" else "Buy"
        r = bybit_post("/v5/order/create", {"category": "linear", "symbol": CONFIG["SYMBOL"], "side": close_side, "orderType": "Market", "qty": str(qty), "timeInForce": "GTC", "positionIdx": 0, "reduceOnly": True})
        ok = r.get("retCode") == 0
        log(f"REAL CLOSE {'OK' if ok else 'FAILED '+str(r.get('retMsg'))} {side} Qty {qty}")
        return ok
    except Exception as e:
        log(f"REAL CLOSE ERR {e}"); return False

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
            if p > 0: STATE["last_price"] = p; return p, fn
        except: continue
    return 0.0, "LIVE-FAIL"
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
    return 0.0, "LIVE-FAIL"
def get_fear():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5); return int(r.json()["data"][0]["value"]), "Alternative-LIVE"
    except: return 50, "LIVE-FAIL"

def get_macro_brain(price, k1, k15, macro_old):
    if not CONFIG["MACRO_BRAIN_ENABLED"]: return {"score": 0.0, "bias": "NEUTRAL", "alert": None, "flip": None}
    try:
        dxy_p, dxy_d, dxy_1h = yahoo_price_1h("DX-Y.NYB"); jpy_p, jpy_d, jpy_1h = yahoo_price_1h("USDJPY=X"); tnx_p, tnx_d, tnx_1h = yahoo_price_1h("^TNX")
        funding, fsrc = get_funding(); fng, _ = get_fear(); rsi = calc_rsi(k15[-60:] if k15 else [], 14)
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
        th = CONFIG["MACRO_THRESHOLD"]
        bias = "SHORT" if score <= -th else "LONG" if score >= th else "NEUTRAL"
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
                flip = {"dir": "LONG", "reasons": cd}
                log(f"MACRO FLIP CONFIRMED 4/5 {cd} - FLIP TO LONG"); mb["alert"] = None; mb["flip_pending"] = flip
            elif el >= 15: log(f"MACRO ALERT FAKE {el:.0f}m {conf}/5 - Back to SHORT"); mb["alert"] = None; mb["flip_pending"] = None; alert = None
        if dxy_1h is not None and dxy_1h >= 1.0 and price < CONFIG["MACRO_BREAK_SHORT"] and vol_spike:
            flip = {"dir": "SHORT", "reasons": ["DXY +1%", "BTC break 62978", "Vol spike"]}; log("MACRO DUMP CONFIRMED SHORT")
        mb["score"] = score; mb["bias"] = bias
        log(f"MACRO BRAIN Score {score:+.1f} Bias {bias} Th {th} | DXY 1h {dxy_1h} JPY 1h {jpy_1h} | Funding {funding:.4f}% {fsrc} | Fear {fng} | RSI {rsi} | Vol {vol_mult:.1f}x | {' | '.join(det)}")
        return {"score": score, "bias": bias, "alert": alert, "flip": flip}
    except Exception as e: log(f"MACRO ERR {e}"); return {"score": 0.0, "bias": "NEUTRAL", "alert": None, "flip": None}
def get_macro_live():
    w = get_world(); oi = 0.0; oi_src = "LIVE-FAIL"
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5); lst = r.json()["result"]["list"]; oi = (float(lst[-1]["openInterest"])-float(lst[0]["openInterest"]))/float(lst[0]["openInterest"])*100; oi_src = "Bybit"
    except: pass
    return {"DXY_CHG": w["DXY"], "NQ_CHG": w["NQ"], "SPX_CHG": w["SPX"], "GOLD_CHG": w["GOLD"], "OI_CHG": oi, "OI_SRC": oi_src}
def get_liq(price, k1):
    ll = sl = 0.0
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100", timeout=5)
        if not r.text.strip(): raise ValueError("Empty Binance")
        d = r.json()
        if isinstance(d, list) and len(d) > 0:
            for x in d:
                sz = float(x.get("origQty", 0)) * float(x.get("price", price))
                if x.get("side") == "SELL": ll += sz
                elif x.get("side") == "BUY": sl += sz
            if ll + sl > 0: log(f"LIQ LIVE Binance Long ${ll:,.0f} Short ${sl:,.0f}"); return ll, sl, "Binance-LIVE"
    except Exception as e: log(f"LIQ Binance fail {e}")
    try:
        r = requests.get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50", timeout=5)
        if not r.text.strip(): raise ValueError("Empty Bybit")
        lst = r.json().get("result", {}).get("list", [])
        for x in lst:
            sz = float(x.get("size", 0)) * float(x.get("price", price))
            if x.get("side") == "Sell": ll += sz
            elif x.get("side") == "Buy": sl += sz
        if ll + sl > 0: log(f"LIQ LIVE Bybit Long ${ll:,.0f} Short ${sl:,.0f}"); return ll, sl, "Bybit-LIVE"
    except Exception as e: log(f"LIQ Bybit fail {e}")
    try:
        r = requests.get("https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT-SWAP&limit=100", timeout=5); j = r.json(); d = j.get("data", []); ll2 = sl2 = 0.0
        if d and len(d) > 0:
            for grp in d:
                details = grp.get("details", []) if isinstance(grp, dict) else []
                for x in details:
                    try:
                        sz = float(x.get("sz", 0)) * float(x.get("bkPx", price))
                        if x.get("side") == "sell": ll2 += sz
                        elif x.get("side") == "buy": sl2 += sz
                    except: pass
            if ll2 + sl2 > 0: log(f"LIQ LIVE OKX Long ${ll2:,.0f} Short ${sl2:,.0f}"); return ll2, sl2, "OKX-LIVE"
    except Exception as e: log(f"LIQ OKX fail {e}")
    coin_vol = 0.0
    try:
        r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/stats", timeout=5); d = r.json(); vol_30d = float(d.get("volume", 0) or 0)
        if vol_30d > 0: coin_vol = (vol_30d / 30 / 1440) * price
    except: pass
    try:
        if k1 and len(k1) >= 20:
            total_range = sum(abs(k["high"] - k["low"]) for k in k1[-20:]); est_total = total_range * price * 0.05
            if coin_vol > 0: est_total = max(est_total, coin_vol * 20)
            if est_total < 500000: est_total = 500000.0
            pc = (k1[-1]["close"] - k1[-20]["close"]) / k1[-20]["close"] * 100 if k1[-20]["close"] else 0
            if pc < 0: ll, sl = est_total * 0.65, est_total * 0.35
            elif pc > 0: ll, sl = est_total * 0.35, est_total * 0.65
            else: ll, sl = est_total * 0.5, est_total * 0.5
            log(f"LIQ VOID-EST Long ${ll:,.0f} Short ${sl:,.0f} Est ${est_total:,.0f} [Proxy-VOID, not REAL - no hunt block]")
            return ll, sl, "Proxy-VOID"
    except: pass
    return 0.0, 0.0, "LIVE-FAIL"
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
def is_hunt_expected(dest, ll, sl, macro_bias, liq_src=""):
    if "Proxy" in str(liq_src) or liq_src == "LIVE-FAIL":
        return False, f"No hunt {liq_src} - fake liq no block"
    if macro_bias == dest: return False, "Macro already decided"
    pool = sl if dest == "LONG" else ll if dest == "SHORT" else 0
    now = now_utc(); mins = now.hour*60+now.minute
    opens = [0, 420, 810]
    to_next = min([(o - mins) % 1440 for o in opens])
    if to_next > 30:
        return False, f"No hunt Next session in {to_next}m - broad daylight, no wait"
    if pool < CONFIG["HUNT_MIN_LIQ_USD"]:
        return False, f"No hunt Liq ${pool:,.0f} < $2M Next {to_next}m"
    return True, f"HUNT EXPECTED Liq ${pool:,.0f} + session in {to_next}m Macro {macro_bias}"
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
    STATE["pnl"] += net
    if reason in ("TP", "TRAILING"):
        STATE["cooldown_until"] = now_utc()
        if reason == "TRAILING":
            STATE["last_trail_exit_price"] = close_p; STATE["last_trail_exit_side"] = side; STATE["last_trail_exit_time"] = now_utc()
    else: STATE["cooldown_until"] = now_utc()+timedelta(minutes=CONFIG["COOLDOWN_MIN"])
    if reason in ("TP", "TRAILING"): STATE["wins"] += 1
    elif reason == "FLIP": STATE["flips"] += 1
    elif net > 0: STATE["wins"] += 1
    elif net < -0.01: STATE["losses"] += 1
    else: STATE["breakevens"] += 1
    log(f"CLOSE {reason} {side} ${net:.2f} at ${close_p:.0f}")
    STATE["open_position"] = None
    save_state()
    log(f"BALANCE ${refresh_balance():.2f}"); return net
def calc_hunt_cert(side, dest, cert, agree, macro, world, ll, sl, liq_src, price, a_low, a_high):
    hunt_cert = 0.0; reasons = []
    if dest != "NONE" and dest != side and cert >= 90 and agree >= 6:
        hunt_cert += 30; reasons.append(f"Cert flip {dest} {cert:.0f}% Agree {agree} +30")
    elif dest != "NONE" and dest != side and cert >= 75 and agree >= 4:
        hunt_cert += 15; reasons.append(f"Cert flip weak {dest} {cert:.0f}% Agree {agree} +15 (need 90% for Emergency)")
    if STATE["macro_brain"].get("bias") == dest:
        hunt_cert += 20; reasons.append(f"Macro {dest} +20")
    if world:
        if dest == "LONG": checks = [world.get("DXY",0) < -0.05, world.get("NQ",0) > 0.05, world.get("SPX",0) > 0.05, world.get("GOLD",0) < -0.10]
        elif dest == "SHORT": checks = [world.get("DXY",0) > 0.05, world.get("NQ",0) < -0.05, world.get("SPX",0) < -0.05, world.get("GOLD",0) > 0.15]
        else: checks = []
        opp = sum(1 for c in checks if c); total = len(checks)
        if total: hunt_cert += (opp/total)*25; reasons.append(f"World {opp}/{total} opposite {dest} +{(opp/total)*25:.0f}")
    liq_us = ll if side == "SHORT" else sl
    liq_opp = sl if side == "SHORT" else ll
    if liq_src == "LIVE-FAIL" or liq_us == 0: reasons.append("Liq LIVE-FAIL +0, no fake confirm")
    elif "Proxy" in str(liq_src):
        if liq_us > 1000000 and liq_us > liq_opp * 1.5:
            hunt_cert += 12.5; reasons.append(f"Liq VOID-EST hunt us ${liq_us:,.0f} +12.5 (half, Proxy)")
        else: reasons.append(f"Liq VOID small ${liq_us:,.0f} +0")
    else:
        if liq_us > 1000000 and liq_us > liq_opp * 1.2:
            hunt_cert += 25; reasons.append(f"REAL Liq hunt us ${liq_us:,.0f} [{liq_src}] +25")
    return hunt_cert, reasons
def is_flip_confirmed(flip_dest, cert, agree, macro, side, world=None, ll=0, sl=0, is_news=False, macro_score=0):
    if flip_dest == "NONE" or flip_dest == side: return False, "No flip dest"
    if cert >= 95 and agree >= 7 and abs(macro_score) >= 5 and is_news:
        STATE["flip_confirm_count"] = 0; STATE["flip_confirm_dest"] = None
        return True, f"HIGH VITALITY FLIP IMMEDIATE Cert {cert:.0f}% Agree {agree} Macro {macro_score} News {is_news}"
    if STATE.get("flip_confirm_dest") != flip_dest:
        STATE["flip_confirm_dest"] = flip_dest; STATE["flip_confirm_count"] = 1
        return False, f"FLIP CHECK 1/3 {flip_dest} Cert {cert:.0f}% Agree {agree} - wait 3 cycles"
    STATE["flip_confirm_count"] += 1
    if STATE["flip_confirm_count"] < CONFIG["CONFIRM_CYCLES"]:
        return False, f"FLIP CHECK {STATE['flip_confirm_count']}/3 {flip_dest} - wait 3 cycles"
    if not (cert >= CONFIG["FLIP_CERTAINTY"] and agree >= CONFIG["FLIP_AGREE"]):
        STATE["flip_confirm_count"] = 0; return False, f"FLIP BLOCKED after 3 cycles Cert {cert:.0f}% Agree {agree} < need"
    if STATE["macro_brain"].get("bias") != flip_dest:
        STATE["flip_confirm_count"] = 0; return False, f"FLIP BLOCKED Macro {STATE['macro_brain'].get('bias')} != {flip_dest}"
    STATE["flip_confirm_count"] = 0; STATE["flip_confirm_dest"] = None
    return True, f"FLIP CONFIRMED 3 CYCLES {flip_dest} Cert {cert:.0f}% Agree {agree} Macro {flip_dest}"
def manage_position(price, qty, flip_dest, cert, agree, macro, ll, sl, world=None, is_news=False, macro_score=0, liq_src="", a_low=0, a_high=0, k1=None):
    if not STATE["open_position"]: return False
    p = STATE["open_position"]; entry = float(p["entry"]); side = p["side"]; tq = p.get("total_qty", qty)
    if "trail_trigger" not in p or not p.get("trail_trigger"):
        p["trail_trigger"] = get_dynamic_trigger(entry, tq)
    trail_trigger = p["trail_trigger"]
    best = max(p.get("best_price", entry), price) if side == "LONG" else min(p.get("best_price", entry), price)
    p["best_price"] = best; favour = abs(best-entry); pnl_pts = (price-entry) if side == "LONG" else (entry-price)
    against = abs(price-entry) if ((side == "LONG" and price < entry) or (side == "SHORT" and price > entry)) else 0
    if CONFIG["FLIP_ENABLED"]:
        flip_ok, flip_reason = is_flip_confirmed(flip_dest, cert, agree, macro, side, world, ll, sl, is_news, macro_score)
        if flip_ok:
            log(f"FLIP {side}->{flip_dest} {flip_reason}")
            STATE["flip_confirm_count"] = 0
            if STATE["mode"] == "REAL": close_real_position(side, tq)
            record_close(side, entry, price, tq, "FLIP"); return True
        elif flip_dest != "NONE" and flip_dest != side:
            log(f"FLIP CHECK BLOCKED {flip_reason}")
    if (price >= p["tp"] if side == "LONG" else price <= p["tp"]):
        if STATE["mode"] == "REAL": close_real_position(side, tq)
        record_close(side, entry, price, tq, "TP"); return False
    if CONFIG["TRAILING_ENABLED"] and favour >= trail_trigger:
        if not p.get("trailing_active"): p["trailing_active"] = True; log(f"TRAILING ON {side} Favour ${favour:.0f} Trigger ${trail_trigger:.0f} SL=Best-$0")
        tp_price = best
        p["trailing_price"] = tp_price
        if side == "LONG" and tp_price > p["wide_sl"]: p["wide_sl"] = tp_price; update_real_sl(tp_price, side)
        elif side == "SHORT" and tp_price < p["wide_sl"]: p["wide_sl"] = tp_price; update_real_sl(tp_price, side)
        if (price <= tp_price if side == "LONG" else price >= tp_price):
            log(f"TRAILING HIT Close PROFIT {side} ${price:.0f} Trigger ${trail_trigger:.0f} Dist 0")
            if STATE["mode"] == "REAL": close_real_position(side, tq)
            record_close(side, entry, price, tq, "TRAILING"); return False
    elif favour > 0: log(f"TRAILING SLEEP Favour ${favour:.0f}<Trigger ${trail_trigger:.0f} WideSL ${p['wide_sl']:.0f}")
    if pnl_pts > 50 and against > 0: log(f"PROFIT +${pnl_pts:.0f} HOLD Trailing go lock")
    if against >= 400 and not p.get("trailing_active"):
        hunt_cert, hunt_reasons = calc_hunt_cert(side, flip_dest, cert, agree, macro, world or STATE.get("world", {}), ll, sl, liq_src, price, a_low, a_high)
        if hunt_cert >= CONFIG["EMERGENCY_HUNT_CERT"]:
            if STATE.get("hunt_confirm_dest") != flip_dest: STATE["hunt_confirm_dest"] = flip_dest; STATE["hunt_confirm_count"] = 1
            else: STATE["hunt_confirm_count"] += 1
            log(f"EMERGENCY HUNT CHECK {STATE['hunt_confirm_count']}/3 HuntCert {hunt_cert:.0f}% {hunt_reasons} Against ${against:.0f}")
            if STATE["hunt_confirm_count"] >= CONFIG["CONFIRM_CYCLES"]:
                log(f"EMERGENCY HUNT CONFIRMED 3 CYCLES HuntCert {hunt_cert:.0f}% - CLOSE")
                STATE["hunt_confirm_count"] = 0; STATE["hunt_confirm_dest"] = None
                STATE["emergency_block_until"] = now_utc() + timedelta(minutes=CONFIG["EMERGENCY_BLOCK_MIN"])
                STATE["emergency_block_side"] = side
                if STATE["mode"] == "REAL": close_real_position(side, tq)
                record_close(side, entry, price, tq, "EMERGENCY"); return False
            else: log(f"EMERGENCY WAIT {STATE['hunt_confirm_count']}/3 cycles")
        else:
            STATE["hunt_confirm_count"] = 0; STATE["hunt_confirm_dest"] = None
            log(f"EMERGENCY HOLD Against ${against:.0f} HuntCert {hunt_cert:.0f}% <90% - HOLD")
            if against >= 1200:
                log(f"EMERGENCY HARD WideSL $1200 reached - CLOSE")
                if STATE["mode"] == "REAL": close_real_position(side, tq)
                record_close(side, entry, price, tq, "EMERGENCY"); return False
    if CONFIG["ADDON_ENABLED"] and not p.get("addon_done", False) and 500 <= against <= 900:
        if (flip_dest == side or flip_dest == "NONE") and ((sl > ll) if side == "SHORT" else (ll > sl)):
            bal = get_current_balance() or 24.33; lev = STATE.get("leverage", 50); after = round(tq+qty, 3)
            if after*price <= bal*lev*0.90:
                if STATE["mode"] == "REAL":
                    if place_real_order(side, price, p["wide_sl"], p["tp"], qty, True): p["addon_done"] = True; p["total_qty"] = after; STATE["addons"] += 1; save_state()
                else: p["addon_done"] = True; p["total_qty"] = after; STATE["addons"] += 1; log(f"ADD-ON PAPER {side} {qty} Total {after}"); save_state()
    if (price <= p["wide_sl"] if side == "LONG" else price >= p["wide_sl"]):
        log(f"WIDE SL HIT ${price:.0f} vs ${p['wide_sl']:.0f}")
        if STATE["mode"] == "REAL": close_real_position(side, tq)
        record_close(side, entry, price, tq, "WIDE_SL"); return False
    return False

def sync_real_position():
    # STRONG SYNC: Bybit na truth, STATE na copy
    rp = get_real_position_sync()
    if rp is None:
        if STATE["open_position"] is not None:
            log("SYNC FIX Bybit NO POS - Clear fake HOLDING"); STATE["open_position"] = None; save_state()
        return
    # Bybit get position
    if STATE["open_position"] is None:
        log(f"SYNC FIX Adopt Bybit {rp}")
        trig = get_dynamic_trigger(rp["entry"], rp["size"])
        STATE["open_position"] = {"side": rp["side"], "entry": rp["entry"], "wide_sl": float(rp["sl"] or 0) or (rp["entry"]+1200 if rp["side"] == "SHORT" else rp["entry"]-1200), "tp": float(rp["tp"] or 0) or (rp["entry"]-1500 if rp["side"] == "SHORT" else rp["entry"]+1500), "best_price": rp["entry"], "trailing_active": False, "addon_done": False, "total_qty": rp["size"], "trail_trigger": trig}
        save_state()
    else:
        # Keep our trailing/addon memory, only update size
        STATE["open_position"]["total_qty"] = rp["size"]

def main():
    log("BOT V13.16.4.6 REAL-FIXED STARTED - DYNAMIC TRAILING $300-550 Dist 0 WideSL $1200 TP $1500 ALL-LIVE")
    while True:
        try:
            nm = get_mode()
            if nm != STATE["mode"]:
                if nm == "REAL":
                    # NOTE: Do NOT wipe pnl/wins on auto-switch if we restored from file - keep history
                    STATE["open_position"] = None; STATE["cooldown_until"] = None
                    bal = get_real_balance(); log(f"*** AUTO SWITCH REAL *** Bal ${bal:.2f} - Sync Bybit")
                    STATE["mode"] = "REAL"; STATE["cross_margin_set"] = False
                    save_state()
                else: STATE["mode"] = nm; save_state()
            mode = STATE["mode"]; set_cross_margin(); refresh_balance()
            if mode == "REAL":
                sync_real_position()
            price, psrc = get_price_live()
            if price == 0: log("NO PRICE LIVE-FAIL skip"); time.sleep(5); continue
            k1 = get_klines("1", 20); k15 = get_klines("15", 200); macro = get_macro_live(); world = STATE.get("world", {})
            mb = get_macro_brain(price, k1, k15, macro)
            hunt, a_low, a_high, ll, sl, liq_src = get_sweep(price, k15, k1)
            is_news, news_r = get_news(); signals = get_signals(price, macro, k1, hunt)
            dest, agree, decided, L, S, cert = decide(signals); score = calc_score(signals, dest, macro, is_news)
            need_cert = CONFIG["MIN_CERTAINTY_NEWS"] if is_news else CONFIG["MIN_CERTAINTY_NORMAL"]; need_agree = CONFIG["MIN_AGREE_NEWS"] if is_news else CONFIG["MIN_AGREE_NORMAL"]; need_score = CONFIG["MIN_SCORE_NEWS"] if is_news else CONFIG["MIN_SCORE_NORMAL"]
            lev = get_dynamic_leverage(); qty = get_dynamic_qty(price, lev); macro_bias = mb.get("bias", "NEUTRAL")
            high_bypass = (cert >= CONFIG["HIGH_CERT_BYPASS"] and dest in ("LONG", "SHORT") and (macro_bias == dest or macro_bias == "NEUTRAL"))
            if high_bypass: log(f"HIGH CERT BYPASS {cert:.0f}% + Macro {macro_bias} {dest} - ENTER NOW")
            hunt_exp, hunt_reason = is_hunt_expected(dest, ll, sl, macro_bias, liq_src) if dest in ("LONG", "SHORT") else (False, "No dest")
            log(f"GOLD PICKER HuntExp {hunt_exp} {hunt_reason} | HighBypass {high_bypass} Macro {macro_bias} Cert {cert:.0f}% Dest {dest}")
            sweep_wait = False
            if hunt_exp and not high_bypass and dest in ("LONG", "SHORT"):
                if STATE.get("sweep_wait") is None: STATE["sweep_wait"] = now_utc(); STATE["sweep_wait_dir"] = dest; log(f"HIDE 2min wait sweep {dest}")
                el = (now_utc()-STATE["sweep_wait"]).total_seconds()/60
                if el < CONFIG["SWEEP_WAIT_MIN"]:
                    sweep_wait = True; log(f"SWEEP WAIT {el:.1f}/{CONFIG['SWEEP_WAIT_MIN']}min {dest}")
                elif is_sweep_done(dest, k1, a_low, a_high):
                    log(f"SWEEP DONE {dest} ENTER NOW"); STATE["sweep_wait"] = None
                elif el >= CONFIG["SWEEP_TIMEOUT_MIN"]:
                    log(f"SWEEP TIMEOUT {CONFIG['SWEEP_TIMEOUT_MIN']}min {dest} no sweep, ENTER NOW"); STATE["sweep_wait"] = None
                else:
                    sweep_wait = True; log(f"SWEEP NOT DONE {dest} wait till {CONFIG['SWEEP_TIMEOUT_MIN']}min timeout {el:.1f}/{CONFIG['SWEEP_TIMEOUT_MIN']}min")
            else: STATE["sweep_wait"] = None
            pause_short = mb.get("alert") == "PAUSE_SHORT"
            if pause_short: log("MACRO PAUSE SHORT 15m - no new SHORT")
            mflip = mb.get("flip")
            if mflip: log(f"MACRO FLIP READY {mflip['dir']} {mflip.get('reasons')}")
            cooldown_active = STATE.get("cooldown_until") and now_utc() < STATE["cooldown_until"]
            emb = STATE.get("emergency_block_until")
            emergency_block_active = emb and now_utc() < emb and STATE.get("emergency_block_side") == dest
            if emergency_block_active: log(f"BLOCK EMERGENCY 5 MIN Hide {dest}")
            reentry_blocked = False
            if STATE.get("last_trail_exit_price") is not None and STATE.get("last_trail_exit_side") == dest:
                gap = CONFIG["REENTRY_GAP_USD"]
                moved = price - STATE["last_trail_exit_price"] if dest == "LONG" else STATE["last_trail_exit_price"] - price
                if moved < gap:
                    reentry_blocked = True; log(f"BLOCK RE-ENTRY GAP {dest} moved ${moved:.0f} < ${gap:.0f} from trail exit ${STATE['last_trail_exit_price']:.0f}")
                else:
                    log(f"RE-ENTRY GAP PASS {dest} moved ${moved:.0f} >= ${gap:.0f}")
                    STATE["last_trail_exit_price"] = None; STATE["last_trail_exit_side"] = None; save_state()
            flipped = False
            if STATE["open_position"]: flipped = manage_position(price, qty, dest, cert, agree, macro, ll, sl, world, is_news, mb.get("score", 0), liq_src, a_low, a_high, k1)
            gates = [(f"Agree {agree}/{decided} Need {need_agree}", agree >= need_agree and decided >= need_agree), (f"Cert {cert:.0f}% Need {need_cert:.0f}%", cert >= need_cert), (f"Score {score:.2f}/{need_score:.2f}", score >= need_score)]
            all_pass = all(p for _, p in gates); failed = [n for n, p in gates if not p]
            bal_show = STATE["real_balance"] if mode == "REAL" else STATE["balance"]
            if STATE["open_position"]: p = STATE["open_position"]; wsl, tp_s, trail = p["wide_sl"], p["tp"], p.get("trailing_price", 0) or 0
            elif dest in ("LONG", "SHORT"): wsl, tp_s = calc_sl_tp(price, dest); trail = 0
            else: wsl = tp_s = trail = 0
            log(f"MODE {mode} | Long {L} Short {S} DEST {dest} Cert {cert:.0f}% Agree {agree}/{decided} {'PASS' if all_pass else 'FAIL'} | MACRO {macro_bias} Score {mb.get('score',0):+.1f} Flip {mflip['dir'] if mflip else 'None'}")
            log(f"SIGNALS {' '.join([f'{n}:{v}' for n,v in signals])}")
            log(f"LIQ Long ${ll:,.0f} Short ${sl:,.0f} [{liq_src}] Asia Low ${a_low:,.0f} High ${a_high:,.0f} Hunt {hunt} HuntExp {hunt_exp} SweepWait {sweep_wait} HighBypass {high_bypass} EmergencyBlock {emergency_block_active} ReentryBlock {reentry_blocked}")
            log(f"Qty {qty} Lev {lev}x Bal ${bal_show:.2f} | Price ${price:.0f} WideSL ${wsl:.0f} Trail ${trail:.0f} TP ${tp_s:.0f} DynTrailTrigger {get_dynamic_trigger(price, qty) if qty else 300:.0f}")
            log(f"W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} FLIP{STATE['flips']} ADDON{STATE['addons']} Trades {STATE['trades_today']} | PnL ${STATE['pnl']:.2f}")
            if STATE["open_position"] and not flipped:
                p = STATE["open_position"]; log(f"HOLDING [MAIN] {p['side']} Trailing {'ACTIVE' if p.get('trailing_active') else 'SLEEP'} Trigger ${p.get('trail_trigger',0):.0f} AddOn {'YES' if p.get('addon_done') else 'NO'} TotalQty {p.get('total_qty', qty)} Best ${p.get('best_price', p['entry']):.0f}")
                save_state()
            elif not STATE["open_position"]:
                if qty == 0: log("BLOCK QTY TOO SMALL")
                elif sweep_wait: log("BLOCK GOLD PICKER SWEEP WAIT")
                elif emergency_block_active: log("BLOCK EMERGENCY 5 MIN")
                elif cooldown_active: log("BLOCK SMART RECHECK 1 MIN")
                elif reentry_blocked: log("BLOCK RE-ENTRY GAP $20")
                elif pause_short and dest == "SHORT": log("BLOCK MACRO PAUSE SHORT")
                elif all_pass:
                    if mflip and mflip["dir"] != dest: log(f"BLOCK Macro Flip {mflip['dir']} vs Cert {dest} - WAIT both")
                    else:
                        wsl2, tp2 = calc_sl_tp(price, dest); tag = "HIGH CERT ENTER NOW" if high_bypass else "SMALL CHOP CERT ENTER" if cert < 85 else "GOLD PICKER AFTER SWEEP"
                        trig = get_dynamic_trigger(price, qty)
                        log(f"TRADE GOLD PICKER {mode} {dest} {tag} Entry ${price:.0f} SL ${wsl2:.0f} TP ${tp2:.0f} Qty {qty} Lev {lev}x DynTrailTrigger ${trig:.0f}")
                        if mode == "REAL":
                            if place_real_order(dest, price, wsl2, tp2, qty):
                                STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wsl2, "tp": tp2, "best_price": price, "trailing_active": False, "addon_done": False, "total_qty": qty, "trail_trigger": trig}; STATE["trades_today"] += 1; save_state()
                        else:
                            STATE["open_position"] = {"side": dest, "entry": price, "wide_sl": wsl2, "tp": tp2, "best_price": price, "trailing_active": False, "addon_done": False, "total_qty": qty, "trail_trigger": trig}; STATE["trades_today"] += 1; save_state()
                        STATE["macro_brain"]["flip_pending"] = None
                else: log(f"BLOCK SKIP FAKE: {'; '.join(failed)}")
            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e: log(f"ERROR {e}"); time.sleep(10)
if __name__ == "__main__": main()
# END V13.16.4.6 REAL-FIXED
