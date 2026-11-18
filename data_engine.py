# ============================================================
# DATA ENGINE V15.0.0 - BRAIN + JSON RECORD KEEPER
# ONLY FETCH DATA + VOTE + SAVE RECORDS. NO ORDERS. NO TRADING.
# main.py go call get_signal() -> data_engine go answer cert/direction/hunt/news
# main.py go call save_trade() -> data_engine go write trades.json + daily.json
# If one source fails, it returns LIVE-FAIL / 0, it never crashes.
# ============================================================
import requests, time, json, os
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc)

def _safe_get(url, timeout=5, headers=None):
    try:
        r = requests.get(url, timeout=timeout, headers=headers or {"User-Agent": "Mozilla/5.0"})
        if not r.text.strip():
            return None
        return r.json()
    except Exception:
        return None

def _safe_get_text(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        return r.text
    except Exception:
        return ""

# ------------------------------------------------------------
# 0. JSON RECORD KEEPER - DATA ENGINE OWNS THIS NOW
# main.py NO go touch json again. E go call DE.save_trade()
# ------------------------------------------------------------
TRADES_FILE = "trades.json"
DAILY_FILE = "daily.json"

def save_trade(trade):
    """
    trade = {"time":..., "side":..., "entry":..., "exit":..., "move":...,
             "qty":..., "net_pnl":..., "result":..., "balance_after":...,
             "cert":..., "atr":..., "be_trigger":...}
    Called by main.py after every close (BE_TP / SL / TP / FLIP)
    Returns daily summary dict.
    """
    try:
        try:
            with open(TRADES_FILE, "r") as f:
                all_trades = json.load(f)
        except:
            all_trades = []
        all_trades.append(trade)
        with open(TRADES_FILE, "w") as f:
            json.dump(all_trades, f, indent=2)

        day = str(trade.get("time", _now().strftime("%Y-%m-%d %H:%M:%S")))[:10]
        try:
            with open(DAILY_FILE, "r") as f:
                daily = json.load(f)
        except:
            daily = {}
        if day not in daily:
            daily[day] = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "be_tp_hits": 0, "sl_hits": 0, "tp_hits": 0}
        d = daily[day]
        d["trades"] += 1
        d["total_pnl"] = round(d["total_pnl"] + float(trade.get("net_pnl", 0)), 2)
        if float(trade.get("net_pnl", 0)) > 0:
            d["wins"] += 1
        else:
            d["losses"] += 1
        res = str(trade.get("result", "")).upper()
        if res == "BE_TP":
            d["be_tp_hits"] += 1
        elif res in ("SL", "STOP_LOSS"):
            d["sl_hits"] += 1
        elif res == "TP":
            d["tp_hits"] += 1
        with open(DAILY_FILE, "w") as f:
            json.dump(daily, f, indent=2)
        print(f"[{_now().strftime('%H:%M:%S')}] 💾 Saved to trades.json | {day} PNL ${d['total_pnl']:.2f} | Trades {d['trades']}", flush=True)
        return daily
    except Exception as e:
        print(f"JSON Save Error: {e}", flush=True)
        return {}

def get_daily_summary(day=None):
    """main.py / you fit call this to see today summary"""
    if day is None:
        day = _now().strftime("%Y-%m-%d")
    try:
        with open(DAILY_FILE, "r") as f:
            daily = json.load(f)
        return daily.get(day, {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "be_tp_hits": 0, "sl_hits": 0, "tp_hits": 0})
    except:
        return {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "be_tp_hits": 0, "sl_hits": 0, "tp_hits": 0}

def get_all_trades():
    try:
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    except:
        return []

# ------------------------------------------------------------
# 1. PRICE - BTCUSDT LIVE
# ------------------------------------------------------------
def get_price_live():
    """Returns (price, source) - tries Bybit -> Binance -> Coinbase"""
    try:
        j = _safe_get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT")
        if j:
            p = float(j["result"]["list"][0]["lastPrice"])
            if p > 0:
                return p, "Bybit-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
        if j:
            p = float(j["price"])
            if p > 0:
                return p, "Binance-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        if j:
            p = float(j["price"])
            if p > 0:
                return p, "Coinbase-LIVE"
    except: pass
    return 0.0, "LIVE-FAIL"

# ------------------------------------------------------------
# 2. KLINES - Candles
# ------------------------------------------------------------
def get_klines(interval="1", limit=100):
    """interval: Bybit style '1','5','15','60' . Returns list of dicts"""
    try:
        j = _safe_get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}")
        if j:
            kl = list(reversed(j["result"]["list"]))
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])} for x in kl]
    except: pass
    try:
        bi = {"1":"1m","5":"5m","15":"15m","60":"1h"}.get(interval, "1m")
        j = _safe_get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={bi}&limit={limit}")
        if isinstance(j, list):
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])} for x in j]
    except: pass
    return []

def calc_rsi(klines, period=14):
    if not klines or len(klines) < period+1:
        return 50.0
    closes = [k["close"] for k in klines]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i]-closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[-period:])/period
    al = sum(losses[-period:])/period
    if al == 0:
        return 100.0
    return round(100 - (100/(1+ag/al)), 1)

def calc_atr_from_klines(klines, period=14):
    if not klines or len(klines) < period+1:
        return 200.0
    trs = []
    for i in range(1, len(klines)):
        c, p = klines[i], klines[i-1]
        trs.append(max(c["high"]-c["low"], abs(c["high"]-p["close"]), abs(c["low"]-p["close"])))
    return sum(trs[-period:]) / period

# ------------------------------------------------------------
# 3. YAHOO - Worldwide Markets
# ------------------------------------------------------------
def yahoo_chg(sym):
    try:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            j = _safe_get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=1m")
            if j:
                meta = j["chart"]["result"][0]["meta"]
                price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0)
                prev = float(meta.get("previousClose") or price)
                if price and prev and price != prev:
                    return round((price-prev)/prev*100, 3), price, prev
    except: pass
    return None, None, None

def yahoo_price_1h(sym):
    try:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            j = _safe_get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=5m")
            if j:
                res = j["chart"]["result"][0]
                closes = [c for c in res["indicators"]["quote"][0].get("close", []) if c is not None]
                if closes:
                    cur = float(closes[-1])
                    prev = float(res["meta"].get("previousClose") or closes[0])
                    chg_day = (cur-prev)/prev*100 if prev else 0
                    chg_1h = (cur-closes[-13])/closes[-13]*100 if len(closes) >= 13 and closes[-13] else 0
                    return cur, chg_day, chg_1h
    except: pass
    return None, None, None

def get_world():
    """Worldwide live checker - Asia, Europe, US, Gold, DXY"""
    w = {}
    for name, sym in [("NIKKEI","^N225"),("HANG_SENG","^HSI"),("FTSE","^FTSE"),("DAX","^GDAXI"),("NQ","NQ=F"),("SPX","ES=F"),("GOLD","GC=F"),("DXY","DX-Y.NYB"),("US10Y","^TNX"),("USDJPY","USDJPY=X"),("OIL","CL=F"),("VIX","^VIX")]:
        chg, _, _ = yahoo_chg(sym)
        w[name] = chg if chg is not None else 0.0
    return w

def get_session():
    h = _now().hour
    if 0 <= h < 7:
        return "ASIA"
    elif 7 <= h < 13:
        return "LONDON"
    elif 13 <= h < 21:
        return "NEW_YORK"
    else:
        return "LATE_NY"

def get_minutes_to_next_session():
    mins = _now().hour*60 + _now().minute
    opens = [0, 420, 810]
    return min([(o - mins) % 1440 for o in opens])

# ------------------------------------------------------------
# 4. FUNDING, FEAR, DOMINANCE, ETF
# ------------------------------------------------------------
def get_funding():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1")
        if j and j["result"].get("list"):
            return float(j["result"]["list"][0].get("fundingRate", 0))*100, "Bybit-LIVE"
    except: pass
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1")
        if j:
            return float(j[0].get("fundingRate", 0))*100, "Binance-LIVE"
    except: pass
    return 0.0, "LIVE-FAIL"

def get_fear():
    try:
        j = _safe_get("https://api.alternative.me/fng/?limit=1")
        if j:
            return int(j["data"][0]["value"]), j["data"][0].get("value_classification",""), "Alternative-LIVE"
    except: pass
    return 50, "Neutral", "LIVE-FAIL"

def get_dominance():
    try:
        j = _safe_get("https://api.coingecko.com/api/v3/global")
        if j:
            d = j["data"]["market_cap_percentage"]
            return {"btc": round(float(d.get("btc", 0)), 2), "usdt": round(float(d.get("usdt", 0)), 2), "eth": round(float(d.get("eth", 0)), 2), "src": "CoinGecko-LIVE"}
    except: pass
    return {"btc": 0.0, "usdt": 0.0, "eth": 0.0, "src": "LIVE-FAIL"}

# ------------------------------------------------------------
# 5. OPEN INTEREST, LONG/SHORT RATIO, ORDERBOOK, CVD
# ------------------------------------------------------------
def get_open_interest():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=6")
        if j:
            lst = j["result"]["list"]
            if len(lst) >= 2:
                first = float(lst[0]["openInterest"]); last = float(lst[-1]["openInterest"])
                chg = (last-first)/first*100 if first else 0
                return {"oi": last, "chg_5m": round(chg, 3), "src": "Bybit-LIVE"}
    except: pass
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
        if j:
            return {"oi": float(j["openInterest"]), "chg_5m": 0.0, "src": "Binance-LIVE"}
    except: pass
    return {"oi": 0.0, "chg_5m": 0.0, "src": "LIVE-FAIL"}

def get_long_short_ratio():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=5min&limit=1")
        if j and j["result"].get("list"):
            d = j["result"]["list"][0]
            return {"buy_ratio": float(d.get("buyRatio", 0))*100, "sell_ratio": float(d.get("sellRatio", 0))*100, "src": "Bybit-LIVE"}
    except: pass
    try:
        j = _safe_get("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1")
        if j:
            return {"buy_ratio": float(j[0]["longAccount"])*100, "sell_ratio": float(j[0]["shortAccount"])*100, "src": "Binance-LIVE"}
    except: pass
    return {"buy_ratio": 50.0, "sell_ratio": 50.0, "src": "LIVE-FAIL"}

def get_orderbook():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=25")
        if j:
            bids = j["result"]["b"]; asks = j["result"]["a"]
            bid_vol = sum(float(x[1])*float(x[0]) for x in bids)
            ask_vol = sum(float(x[1])*float(x[0]) for x in asks)
            best_bid = float(bids[0][0]); best_ask = float(asks[0][0])
            spread = best_ask - best_bid
            total = bid_vol + ask_vol
            buy_pressure = (bid_vol/total*100) if total else 50.0
            return {"bid_vol": round(bid_vol,0), "ask_vol": round(ask_vol,0), "buy_pressure": round(buy_pressure,1), "spread": round(spread,1), "best_bid": best_bid, "best_ask": best_ask, "src": "Bybit-LIVE"}
    except: pass
    return {"bid_vol": 0, "ask_vol": 0, "buy_pressure": 50.0, "spread": 0, "best_bid": 0, "best_ask": 0, "src": "LIVE-FAIL"}

def get_cvd(k1):
    if not k1 or len(k1) < 10:
        return {"cvd": 0.0, "aggressive": "NEUTRAL", "src": "LIVE-FAIL"}
    score = 0.0
    for k in k1[-10:]:
        rng = k["high"] - k["low"]
        if rng > 0:
            pos = (k["close"] - k["low"]) / rng
            score += (pos - 0.5) * k["volume"]
    agg = "BUY" if score > 0 else "SELL" if score < 0 else "NEUTRAL"
    return {"cvd": round(score, 2), "aggressive": agg, "src": "Kline-Proxy"}

# ------------------------------------------------------------
# 6. LIQUIDATION MAP - REAL ONLY
# ------------------------------------------------------------
def get_liq(price, k1):
    ll, sl = 0.0, 0.0
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100")
        if isinstance(j, list) and len(j) > 0:
            for x in j:
                sz = float(x.get("origQty", 0)) * float(x.get("price", price))
                if x.get("side") == "SELL": ll += sz
                elif x.get("side") == "BUY": sl += sz
            if ll + sl > 0:
                return ll, sl, "Binance-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50")
        if j:
            lst = j.get("result", {}).get("list", [])
            for x in lst:
                sz = float(x.get("size", 0)) * float(x.get("price", price))
                if x.get("side") == "Sell": ll += sz
                elif x.get("side") == "Buy": sl += sz
            if ll + sl > 0:
                return ll, sl, "Bybit-LIVE"
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT-SWAP&limit=100")
        if j:
            d = j.get("data", [])
            ll2, sl2 = 0.0, 0.0
            for grp in d:
                for x in grp.get("details", []):
                    try:
                        sz = float(x.get("sz", 0)) * float(x.get("bkPx", price))
                        if x.get("side") == "sell": ll2 += sz
                        elif x.get("side") == "buy": sl2 += sz
                    except: pass
            if ll2 + sl2 > 0:
                return ll2, sl2, "OKX-LIVE"
    except: pass
    try:
        if k1 and len(k1) >= 20:
            total_range = sum(abs(k["high"]-k["low"]) for k in k1[-20:])
            est_total = total_range * price * 0.05
            if est_total < 500000: est_total = 500000.0
            pc = (k1[-1]["close"]-k1[-20]["close"])/k1[-20]["close"]*100 if k1[-20]["close"] else 0
            if pc < 0: ll, sl = est_total*0.65, est_total*0.35
            elif pc > 0: ll, sl = est_total*0.35, est_total*0.65
            else: ll, sl = est_total*0.5, est_total*0.5
            return ll, sl, "Proxy-VOID"
    except: pass
    return 0.0, 0.0, "LIVE-FAIL"

# ------------------------------------------------------------
# 7. ASIA RANGE + SWEEP + HUNT
# ------------------------------------------------------------
def get_asia_range(k15):
    lows, highs = [], []
    for k in k15:
        try:
            dt = datetime.fromtimestamp(k["time"]/1000, tz=timezone.utc)
            if dt.date() == _now().date() and 0 <= dt.hour < 8:
                lows.append(k["low"]); highs.append(k["high"])
        except: pass
    if lows:
        return min(lows), max(highs)
    if len(k15) >= 32:
        return min(x["low"] for x in k15[-32:]), max(x["high"] for x in k15[-32:])
    return 0.0, 0.0

def get_sweep(price, k15, k1):
    a_low, a_high = get_asia_range(k15)
    ll, sl, src = get_liq(price, k1)
    hunt = "NEUTRAL"
    if a_low and a_high and k1:
        last = k1[-1]
        if last["low"] < a_low and last["close"] > a_low and ll > sl:
            hunt = "LONG"
        elif last["high"] > a_high and last["close"] < a_high and sl > ll:
            hunt = "SHORT"
    return hunt, a_low, a_high, ll, sl, src

def is_sweep_done(dest, k1, a_low, a_high):
    if not k1: return False
    last = k1[-1]
    if dest == "LONG" and a_low: return last["low"] < a_low and last["close"] > a_low
    if dest == "SHORT" and a_high: return last["high"] > a_high and last["close"] < a_high
    return False

# ------------------------------------------------------------
# 8. NEWS / VOL SPIKE + MACRO BRAIN
# ------------------------------------------------------------
def get_news(k1=None):
    if k1 is None:
        k1 = get_klines("1", 15)
    if len(k1) >= 15:
        mv = (k1[-1]["close"]-k1[0]["close"])/k1[0]["close"]*100
        if abs(mv) >= 0.8:
            return True, f"VOL SPIKE {mv:.2f}% 15m"
    return False, ""

def get_macro_brain(price, k1, k15):
    try:
        dxy_p, dxy_d, dxy_1h = yahoo_price_1h("DX-Y.NYB")
        jpy_p, jpy_d, jpy_1h = yahoo_price_1h("USDJPY=X")
        tnx_p, tnx_d, tnx_1h = yahoo_price_1h("^TNX")
        funding, fsrc = get_funding()
        fng, fng_txt, _ = get_fear()
        rsi = calc_rsi(k15[-60:] if k15 else [], 14)
        vol_spike = False; vol_mult = 1.0
        if k1 and len(k1) >= 15:
            rec = sum(abs(k["high"]-k["low"]) for k in k1[-5:])
            avg = sum(abs(k["high"]-k["low"]) for k in k1[-15:-5])/10
            if avg > 0:
                vol_mult = rec/max(avg, 1)
                vol_spike = vol_mult >= 2.0
        score = 0.0; det = []
        if dxy_1h is not None:
            if dxy_1h > 0.2: score -= 2; det.append(f"DXY 1h +{dxy_1h:.2f}% SHORT+2")
            elif dxy_1h < -0.5: score += 2; det.append(f"DXY 1h {dxy_1h:.2f}% LONG+2")
            if dxy_p and dxy_p > 102.5: score -= 1; det.append("DXY>102.5 SHORT+1")
        if jpy_1h is not None:
            if jpy_1h < -1.5: score += 2; det.append("USDJPY -1.5% LONG+2")
            elif jpy_1h < -0.8: score += 1; det.append("USDJPY dropping LONG+1")
        if tnx_d is not None and tnx_d > 0.5: score -= 1; det.append("US10Y up SHORT+1")
        if funding < -0.01: score += 1; det.append("Funding shorts crowded LONG+1")
        elif funding > 0.02: score -= 1; det.append("Funding high SHORT+1")
        if rsi < 25: score += 1; det.append(f"RSI {rsi} oversold LONG+1")
        elif rsi > 70: score -= 1; det.append("RSI overbought SHORT+1")
        if fng <= 10: score += 0.5; det.append(f"Fear {fng} bounce risk")
        bias = "SHORT" if score <= -1.5 else "LONG" if score >= 1.5 else "NEUTRAL"
        alert = "PAUSE_SHORT" if (dxy_1h is not None and dxy_1h <= -0.5) or (jpy_1h is not None and jpy_1h <= -0.8) else None
        flip = None
        if dxy_1h is not None and dxy_1h >= 1.0 and price < 62978 and vol_spike:
            flip = {"dir": "SHORT", "reasons": ["DXY +1%", "BTC break 62978", "Vol spike"]}
        return {"score": score, "bias": bias, "alert": alert, "flip": flip, "dxy_1h": dxy_1h, "jpy_1h": jpy_1h, "funding": funding, "fng": fng, "rsi": rsi, "vol_mult": vol_mult, "details": det}
    except Exception as e:
        return {"score": 0.0, "bias": "NEUTRAL", "alert": None, "flip": None, "error": str(e)}

def get_macro_live(world):
    oi = get_open_interest()
    return {"DXY_CHG": world.get("DXY",0), "NQ_CHG": world.get("NQ",0), "SPX_CHG": world.get("SPX",0), "GOLD_CHG": world.get("GOLD",0), "OI_CHG": oi.get("chg_5m",0), "OI": oi.get("oi",0), "OI_SRC": oi.get("src","LIVE-FAIL")}

# ------------------------------------------------------------
# 9. MASTER - ONE CALL FOR BOT CORE
# ------------------------------------------------------------
def get_all_data():
    price, psrc = get_price_live()
    k1 = get_klines("1", 20)
    k15 = get_klines("15", 200)
    world = get_world()
    macro_brain = get_macro_brain(price, k1, k15)
    macro = get_macro_live(world)
    hunt, a_low, a_high, ll, sl, liq_src = get_sweep(price, k15, k1)
    is_news, news_reason = get_news(k1)
    funding, funding_src = get_funding()
    fng, fng_txt, fng_src = get_fear()
    dom = get_dominance()
    oi = get_open_interest()
    ls = get_long_short_ratio()
    ob = get_orderbook()
    cvd = get_cvd(k1)
    session = get_session()
    mins_to_session = get_minutes_to_next_session()
    return {
        "price": price, "price_src": psrc,
        "k1": k1, "k15": k15,
        "world": world,
        "macro_brain": macro_brain, "macro": macro,
        "hunt": hunt, "asia_low": a_low, "asia_high": a_high,
        "liq_long": ll, "liq_short": sl, "liq_src": liq_src,
        "is_news": is_news, "news_reason": news_reason,
        "funding": funding, "funding_src": funding_src,
        "fear": fng, "fear_txt": fng_txt, "fear_src": fng_src,
        "dominance": dom,
        "oi": oi, "long_short": ls, "orderbook": ob, "cvd": cvd,
        "session": session, "mins_to_next_session": mins_to_session,
        "rsi_15m": calc_rsi(k15, 14) if k15 else 50.0,
        "timestamp": _now().isoformat(),
    }

# ------------------------------------------------------------
# 10. V15 BRIDGE - main.py CALLS THIS EVERY LOOP
# get_signal(price, atr, candles) -> cert / direction / hunt / news
# This na the ONLY function main.py need. E dey vote with 8 voters.
# ------------------------------------------------------------
# Cache to avoid hammering Yahoo every 2 seconds - main.py calls every 2-5s
_last_signal = {"time": 0, "data": None}

def get_signal(price, atr=None, candles=None):
    """
    Called by main.py: get_votes(price, atr, candles) -> DE.get_signal(price, atr, candles)
    Returns normalized dict main.py understands:
    {cert, direction, agree, hunt_soon, hunt_cert, cvd_buy_pct, news_critical, news_wait, pause_long, pause_short}
    """
    global _last_signal
    # Use cache for 10s - Yahoo / Bybit no need fetch every 2s
    if _last_signal["data"] is not None and (time.time() - _last_signal["time"]) < 10:
        cached = _last_signal["data"]
        # Still update price for freshness
        cached = dict(cached)
        cached["price"] = price
        return cached

    try:
        # Use price passed by main.py if valid, else fetch fresh
        if not price or price == 0:
            price, _ = get_price_live()
            if price == 0:
                return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False, "price": 0}

        # Get klines - use candles passed by main.py for k1 if available, else fetch
        k1 = candles if candles and len(candles) >= 5 else get_klines("1", 20)
        # Normalize candles from main.py (main.py candles no get volume/time) -> add defaults
        k1_norm = []
        for k in k1:
            k1_norm.append({"open": float(k.get("open", 0)), "high": float(k.get("high", 0)), "low": float(k.get("low", 0)), "close": float(k.get("close", 0)), "volume": float(k.get("volume", 1)), "time": int(k.get("time", 0))})
        k15 = get_klines("15", 200)
        world = get_world()
        macro_brain = get_macro_brain(price, k1_norm, k15)
        hunt, a_low, a_high, ll, sl, liq_src = get_sweep(price, k15, k1_norm)
        is_news, news_reason = get_news(k1_norm)
        funding, _ = get_funding()
        oi = get_open_interest()
        ls = get_long_short_ratio()
        ob = get_orderbook()
        cvd = get_cvd(k1_norm)

        # --- VOTING: 8 VOTERS - DXY, NQ, SPX, GOLD, OI, SWEEP/HUNT, CVD, ORDERBOOK ---
        long_votes = 0
        short_votes = 0
        total_voters = 8
        reasons = []

        # 1. DXY - DXY up = BTC down, DXY down = BTC up
        dxy = world.get("DXY", 0)
        if dxy < -0.05:
            long_votes += 1; reasons.append("DXY down LONG")
        elif dxy > 0.05:
            short_votes += 1; reasons.append("DXY up SHORT")

        # 2. NQ
        nq = world.get("NQ", 0)
        if nq > 0.05:
            long_votes += 1; reasons.append("NQ up LONG")
        elif nq < -0.05:
            short_votes += 1; reasons.append("NQ down SHORT")

        # 3. SPX
        spx = world.get("SPX", 0)
        if spx > 0.05:
            long_votes += 1; reasons.append("SPX up LONG")
        elif spx < -0.05:
            short_votes += 1; reasons.append("SPX down SHORT")

        # 4. GOLD - GOLD up = risk-off sometimes, but for our system GOLD up + BTC up = risk-on
        gold = world.get("GOLD", 0)
        if gold > 0.05:
            long_votes += 1; reasons.append("GOLD up LONG")
        elif gold < -0.05:
            short_votes += 1; reasons.append("GOLD down SHORT")

        # 5. OI - OI rising + price falling = new shorts = bounce LONG, OI rising + price rising = new longs = trend LONG
        oi_chg = oi.get("chg_5m", 0)
        price_chg_5 = 0
        if len(k1_norm) >= 6:
            price_chg_5 = (k1_norm[-1]["close"] - k1_norm[-6]["close"]) / k1_norm[-6]["close"] * 100 if k1_norm[-6]["close"] else 0
        if oi_chg > 0.1 and price_chg_5 < 0:
            long_votes += 1; reasons.append("OI up + price down = shorts crowded LONG")
        elif oi_chg > 0.1 and price_chg_5 > 0:
            long_votes += 1; reasons.append("OI up + price up LONG")
        elif oi_chg < -0.1 and price_chg_5 < 0:
            short_votes += 1; reasons.append("OI down + price down SHORT")
        else:
            # Neutral OI - give to macro bias
            if macro_brain.get("bias") == "LONG":
                long_votes += 1
            elif macro_brain.get("bias") == "SHORT":
                short_votes += 1

        # 6. SWEEP / HUNT - sweep of asia low + reclaim = LONG, sweep of asia high + reject = SHORT
        if hunt == "LONG":
            long_votes += 1; reasons.append("Sweep LONG")
        elif hunt == "SHORT":
            short_votes += 1; reasons.append("Sweep SHORT")
        else:
            if macro_brain.get("bias") == "LONG":
                long_votes += 1
            elif macro_brain.get("bias") == "SHORT":
                short_votes += 1

        # 7. CVD - aggressive buyers = LONG
        cvd_agg = cvd.get("aggressive", "NEUTRAL")
        cvd_buy_pct = 50.0
        if cvd_agg == "BUY":
            long_votes += 1; reasons.append("CVD BUY LONG")
            cvd_buy_pct = 65.0
        elif cvd_agg == "SELL":
            short_votes += 1; reasons.append("CVD SELL SHORT")
            cvd_buy_pct = 35.0
        else:
            # Use orderbook as tie-breaker
            if ob.get("buy_pressure", 50) > 55:
                long_votes += 1
            elif ob.get("buy_pressure", 50) < 45:
                short_votes += 1

        # 8. ORDERBOOK - bid walls = LONG
        if ob.get("buy_pressure", 50) > 55:
            long_votes += 1; reasons.append("Orderbook bids LONG")
        elif ob.get("buy_pressure", 50) < 45:
            short_votes += 1; reasons.append("Orderbook asks SHORT")

        # Decide direction + cert
        if long_votes > short_votes:
            direction = "LONG"
            agree = long_votes
        elif short_votes > long_votes:
            direction = "SHORT"
            agree = short_votes
        else:
            direction = "NONE"
            agree = long_votes

        cert = round((agree / total_voters) * 100, 1) if total_voters else 0

        # Macro brain can boost cert if e agree
        if macro_brain.get("bias") == direction and direction != "NONE":
            cert = min(100, cert + 5)

        # --- HUNT SOON? - liq pool > $2M + session near = hunt soon ---
        total_liq = ll + sl
        mins_to_session = get_minutes_to_next_session()
        hunt_soon = False
        hunt_cert = 0
        if total_liq > 2000000 and mins_to_session < 30:
            hunt_soon = True
            hunt_cert = 75
        elif total_liq > 5000000:
            hunt_soon = True
            hunt_cert = 85

        # --- NEWS: Critical = vol spike >=0.8% in 15m + all agree ---
        # Critical if: vol spike + cert >=90 + all voters agree (agree >=7)
        news_critical = False
        news_wait = 0
        if is_news:
            if cert >= 90 and agree >= 7:
                news_critical = True
            else:
                # Not critical - wait 5 mins confirm (300s)
                news_wait = 300

        # --- PAUSE: GOLD extreme + macro alert ---
        pause_long = False
        pause_short = False
        if macro_brain.get("alert") == "PAUSE_SHORT":
            pause_short = True
        # GOLD +/-0.12 rule: if GOLD move too fast, pause both
        if abs(gold) > 0.12 and cert < 85:
            pause_long = True
            pause_short = True

        result = {
            "cert": cert,
            "direction": direction,
            "agree": agree,
            "hunt_soon": hunt_soon,
            "hunt_cert": hunt_cert,
            "cvd_buy_pct": cvd_buy_pct,
            "news_critical": news_critical,
            "news_wait": news_wait,
            "pause_long": pause_long,
            "pause_short": pause_short,
            "price": price,
            "reasons": reasons,
            "news_reason": news_reason,
            "macro_bias": macro_brain.get("bias"),
            "session": get_session(),
            "liq_long": ll,
            "liq_short": sl,
        }
        _last_signal = {"time": time.time(), "data": result}
        return result
    except Exception as e:
        print(f"get_signal Error: {e}", flush=True)
        return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False, "price": price}

# Aliases so main.py fit call any name - no crash
def get_votes(price, atr=None, candles=None):
    return get_signal(price, atr, candles)

def analyze(price, atr=None, candles=None):
    return get_signal(price, atr, candles)

def check_market(price, atr=None, candles=None):
    return get_signal(price, atr, candles)

def get_decision(price, atr=None, candles=None):
    return get_signal(price, atr, candles)

if __name__ == "__main__":
    d = get_all_data()
    print(f"Price ${d['price']:.0f} [{d['price_src']}] Session {d['session']} Hunt {d['hunt']}")
    print(f"Macro {d['macro_brain']['bias']} Score {d['macro_brain']['score']}")
    print(f"Liq Long ${d['liq_long']:,.0f} Short ${d['liq_short']:,.0f} [{d['liq_src']}]")
    print(f"OI {d['oi']} LS {d['long_short']} OB BuyPressure {d['orderbook']['buy_pressure']}%")
    print(f"Fear {d['fear']} Funding {d['funding']:.4f}% Dom BTC {d['dominance']['btc']}%")
    # Test get_signal + JSON
    sig = get_signal(d['price'], 200, d['k1'])
    print(f"Signal: {sig['direction']} Cert {sig['cert']}% Agree {sig['agree']} HuntSoon {sig['hunt_soon']} NewsCritical {sig['news_critical']}")
    print(f"Today summary: {get_daily_summary()}")
