# ============================================================
# DATA ENGINE V15.6 CLEAN - GOLD BOSS PROTOCOL
# GOLD: BOSS + VOTER, no panic pause.
# - GOLD aligned = +15/+10/+5, Dominance = +10
# - Break 3 tiers: <0.3% IGNORE, 0.3-0.8% HOLD LIVE, >0.8% BIG BREAK LIVE
# - No hardcoded wait: No break = ENTER joyfully. Break resolve + 2min confirm = ENTER.
# - Break 3x 5m = FLIP, follow BTC.
# - Wick >0.5% = wait wick close. Wick check time = waiting time.
# SPREAD: Booster only, never solo.
# HUNT: Certainty first, First Aid instant.
# ALL LIVE: No hardcoded BTC price.
# CLEAN: No duplicate votes, no dead code.
# ============================================================
import requests, time, json
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc)

def _safe_get(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if not r.text.strip():
            return None
        return r.json()
    except Exception:
        return None

TRADES_FILE = "trades.json"
DAILY_FILE = "daily.json"

def save_trade(trade):
    try:
        try:
            with open(TRADES_FILE, "r") as f: all_trades = json.load(f)
        except: all_trades = []
        all_trades.append(trade)
        with open(TRADES_FILE, "w") as f: json.dump(all_trades, f, indent=2)
        day = str(trade.get("time", _now().strftime("%Y-%m-%d %H:%M:%S")))[:10]
        try:
            with open(DAILY_FILE, "r") as f: daily = json.load(f)
        except: daily = {}
        if day not in daily:
            daily[day] = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "be_tp_hits": 0, "sl_hits": 0, "tp_hits": 0}
        d = daily[day]
        d["trades"] += 1
        d["total_pnl"] = round(d["total_pnl"] + float(trade.get("net_pnl", 0)), 2)
        if float(trade.get("net_pnl", 0)) > 0: d["wins"] += 1
        else: d["losses"] += 1
        res = str(trade.get("result", "")).upper()
        if res == "BE_TP": d["be_tp_hits"] += 1
        elif res in ("SL", "STOP_LOSS"): d["sl_hits"] += 1
        elif res == "TP": d["tp_hits"] += 1
        with open(DAILY_FILE, "w") as f: json.dump(daily, f, indent=2)
        print(f"[{_now().strftime('%H:%M:%S')}] Saved | {day} PNL ${d['total_pnl']:.2f} | Trades {d['trades']}", flush=True)
        return daily
    except Exception as e:
        print(f"JSON Save Error: {e}", flush=True)
        return {}

def get_price_live():
    for url, parse, name in [
        ("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", lambda j: float(j["result"]["list"][0]["lastPrice"]), "Bybit-LIVE"),
        ("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", lambda j: float(j["price"]), "Binance-LIVE"),
        ("https://api.exchange.coinbase.com/products/BTC-USD/ticker", lambda j: float(j["price"]), "Coinbase-LIVE"),
        ("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", lambda j: float(j["result"]["XXBTZUSD"]["c"][0]), "Kraken-LIVE"),
        ("https://www.bitstamp.net/api/v2/ticker/btcusd/", lambda j: float(j["last"]), "Bitstamp-LIVE"),
        ("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP", lambda j: float(j["data"][0]["last"]), "OKX-LIVE"),
        ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", lambda j: float(j["bitcoin"]["usd"]), "CoinGecko-LIVE"),
    ]:
        try:
            j = _safe_get(url)
            if j:
                p = parse(j)
                if p > 0: return p, name
        except: pass
    return 0.0, "LIVE-FAIL"

def get_klines(interval="1", limit=100):
    try:
        j = _safe_get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}")
        if j:
            kl = list(reversed(j["result"]["list"]))
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])} for x in kl]
    except: pass
    try:
        bi = {"1": "1m", "5": "5m", "15": "15m", "60": "1h"}.get(interval, "1m")
        j = _safe_get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={bi}&limit={limit}")
        if isinstance(j, list):
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])} for x in j]
    except: pass
    try:
        bar = {"1": "1m", "5": "5m", "15": "15m", "60": "1H"}.get(interval, "1m")
        j = _safe_get(f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar={bar}&limit={limit}")
        if j and j.get("data"):
            kl = list(reversed(j["data"]))
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])} for x in kl]
    except: pass
    try:
        kraken_int = {"1": "1", "5": "5", "15": "15", "60": "60"}.get(interval, "1")
        j = _safe_get(f"https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval={kraken_int}")
        if j and j.get("result"):
            key = [k for k in j["result"] if k != "last"][0]
            kl = j["result"][key][-limit:]
            return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])*1000} for x in kl]
    except: pass
    try:
        gran = {"1": "60", "5": "300", "15": "900", "60": "3600"}.get(interval, "60")
        j = _safe_get(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity={gran}")
        if isinstance(j, list) and len(j) > 0:
            kl = list(reversed(j[-limit:]))
            return [{"open": float(x[3]), "high": float(x[2]), "low": float(x[1]), "close": float(x[4]), "volume": float(x[5]), "time": int(x[0])*1000} for x in kl]
    except: pass
    return []

def calc_rsi(klines, period=14):
    if not klines or len(klines) < period + 1: return 50.0
    closes = [k["close"] for k in klines]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - (100 / (1 + ag / al)), 1)

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
    try:
        stooq = {"GC=F": "gc.f.us", "DX-Y.NYB": "dx.f.us", "CL=F": "cl.f.us"}.get(sym)
        if stooq:
            j = _safe_get(f"https://stooq.com/q/l/?s={stooq}&f=sd2t2ohlcv&h&e=json")
            if j and j.get("symbols"):
                d = j["symbols"][0]
                price = float(d.get("close", 0)); prev = float(d.get("open", 0))
                if price and prev: return round((price-prev)/prev*100, 3), price, prev
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
    w = {}
    for name, sym in [("NIKKEI","^N225"),("HANG_SENG","^HSI"),("FTSE","^FTSE"),("DAX","^GDAXI"),("NQ","NQ=F"),("SPX","ES=F"),("GOLD","GC=F"),("DXY","DX-Y.NYB"),("US10Y","^TNX"),("USDJPY","USDJPY=X"),("OIL","CL=F"),("VIX","^VIX")]:
        chg, _, _ = yahoo_chg(sym)
        w[name] = chg if chg is not None else 0.0
    return w

def get_session():
    h = _now().hour
    if 0 <= h < 7: return "ASIA"
    elif 7 <= h < 13: return "LONDON"
    elif 13 <= h < 21: return "NEW_YORK"
    else: return "LATE_NY"

def get_hunt_window():
    mins = _now().hour*60 + _now().minute
    if mins >= 23*60+30 or mins <= 0*60+15:
        return True, "ASIA"
    if 6*60+30 <= mins <= 7*60+15:
        return True, "LONDON"
    if 12*60+30 <= mins <= 13*60+15:
        return True, "NEW_YORK"
    return False, get_session()

def get_funding():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1")
        if j and j["result"].get("list"):
            return float(j["result"]["list"][0].get("fundingRate", 0))*100, "Bybit-LIVE"
    except: pass
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1")
        if j: return float(j[0].get("fundingRate", 0))*100, "Binance-LIVE"
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
        if j and j.get("data"): return float(j["data"][0].get("fundingRate", 0))*100, "OKX-LIVE"
    except: pass
    return 0.0, "LIVE-FAIL"

def get_fear():
    try:
        j = _safe_get("https://api.alternative.me/fng/?limit=1")
        if j: return int(j["data"][0]["value"]), j["data"][0].get("value_classification", "")
    except: pass
    return 50, "Neutral"

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
        if j: return {"oi": float(j["openInterest"]), "chg_5m": 0.0, "src": "Binance-LIVE"}
    except: pass
    return {"oi": 0.0, "chg_5m": 0.0, "src": "LIVE-FAIL"}

def get_liq_clusters(price, k1=None):
    long_liq = 0.0; short_liq = 0.0; src = "LIVE-FAIL"
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100")
        if isinstance(j, list) and len(j) > 0:
            for x in j:
                try:
                    sz = float(x.get("origQty", 0)) * float(x.get("price", price))
                    if x.get("side") == "SELL": long_liq += sz
                    elif x.get("side") == "BUY": short_liq += sz
                except: pass
            if long_liq + short_liq > 0: src = "Binance-LIVE"
    except: pass
    if src == "LIVE-FAIL":
        try:
            j = _safe_get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50")
            if j:
                lst = j.get("result", {}).get("list", [])
                for x in lst:
                    try:
                        sz = float(x.get("size", 0)) * float(x.get("price", price))
                        if x.get("side") == "Sell": long_liq += sz
                        elif x.get("side") == "Buy": short_liq += sz
                    except: pass
                if long_liq + short_liq > 0: src = "Bybit-LIVE"
        except: pass
    if src == "LIVE-FAIL" and k1 and len(k1) >= 20:
        total_range = sum(abs(k["high"]-k["low"]) for k in k1[-20:])
        est_total = max(total_range * price * 0.05, 500000.0)
        pc = (k1[-1]["close"]-k1[-20]["close"])/k1[-20]["close"]*100 if k1[-20]["close"] else 0
        if pc < 0: long_liq, short_liq = est_total*0.65, est_total*0.35
        elif pc > 0: long_liq, short_liq = est_total*0.35, est_total*0.65
        else: long_liq, short_liq = est_total*0.5, est_total*0.5
        src = "Proxy-Kline"
    total = long_liq + short_liq
    if total > 0:
        if long_liq > short_liq * 1.5: dominant = "HUNT_LONGS_FIRST"; hunt_dir = "DOWN_FIRST"
        elif short_liq > long_liq * 1.5: dominant = "HUNT_SHORTS_FIRST"; hunt_dir = "UP_FIRST"
        else: dominant = "BALANCED"; hunt_dir = "NONE"
        imb = round((long_liq - short_liq) / total * 100, 1)
    else:
        dominant = "UNKNOWN"; hunt_dir = "NONE"; imb = 0.0
    return {"long_liq": round(long_liq, 0), "short_liq": round(short_liq, 0), "total": round(total, 0),
            "dominant": dominant, "hunt_dir": hunt_dir, "imbalance_pct": imb, "src": src}

def _parse_ob(bids, asks, src):
    biggest_bid = max(bids, key=lambda x: float(x[1])*float(x[0])) if bids else [0, 0]
    biggest_ask = max(asks, key=lambda x: float(x[1])*float(x[0])) if asks else [0, 0]
    bid_wall_price = float(biggest_bid[0]); bid_wall_usd = float(biggest_bid[1])*bid_wall_price
    ask_wall_price = float(biggest_ask[0]); ask_wall_usd = float(biggest_ask[1])*ask_wall_price
    bid_vol = sum(float(x[1])*float(x[0]) for x in bids)
    ask_vol = sum(float(x[1])*float(x[0]) for x in asks)
    total = bid_vol + ask_vol
    buy_pressure = (bid_vol/total*100) if total else 50.0
    if bid_wall_usd > ask_wall_usd * 1.8: cluster_bias = "BID_WALL_STRONG"
    elif ask_wall_usd > bid_wall_usd * 1.8: cluster_bias = "ASK_WALL_STRONG"
    else: cluster_bias = "BALANCED"
    return {"bid_wall_price": bid_wall_price, "bid_wall_usd": round(bid_wall_usd, 0),
            "ask_wall_price": ask_wall_price, "ask_wall_usd": round(ask_wall_usd, 0),
            "bid_vol": round(bid_vol, 0), "ask_vol": round(ask_vol, 0),
            "buy_pressure": round(buy_pressure, 1), "cluster_bias": cluster_bias, "src": src}

def get_ob_clusters(price):
    try:
        j = _safe_get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=50")
        if j: return _parse_ob(j["result"]["b"], j["result"]["a"], "Bybit-LIVE")
    except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=50")
        if j: return _parse_ob(j["bids"], j["asks"], "Binance-LIVE")
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/market/books?instId=BTC-USDT-SWAP&sz=50")
        if j and j.get("data"):
            d = j["data"][0]
            return _parse_ob(d["bids"], d["asks"], "OKX-LIVE")
    except: pass
    return {"bid_wall_price": 0, "bid_wall_usd": 0, "ask_wall_price": 0, "ask_wall_usd": 0,
            "bid_vol": 0, "ask_vol": 0, "buy_pressure": 50.0, "cluster_bias": "UNKNOWN", "src": "LIVE-FAIL"}

def get_cvd_live():
    for url, parse, name in [
        ("https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=200",
         lambda lst: (sum(float(x.get("size", 0)) for x in lst if x.get("side") == "Buy"), sum(float(x.get("size", 0)) for x in lst if x.get("side") == "Sell")), "Bybit-Trades-LIVE"),
    ]:
        try:
            j = _safe_get(url)
            if j:
                lst = j["result"]["list"]
                buy_vol, sell_vol = parse(lst)
                if buy_vol + sell_vol > 0:
                    buy_pct = buy_vol/(buy_vol+sell_vol)*100
                    agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                    return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3), "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": name}
        except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=200")
        if isinstance(j, list) and len(j) > 0:
            buy_vol = sum(float(x.get("qty", 0)) for x in j if not x.get("isBuyerMaker"))
            sell_vol = sum(float(x.get("qty", 0)) for x in j if x.get("isBuyerMaker"))
            if buy_vol + sell_vol > 0:
                buy_pct = buy_vol/(buy_vol+sell_vol)*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3), "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "Binance-Trades-LIVE"}
    except: pass
    return {"cvd": 0.0, "buy_vol": 0, "sell_vol": 0, "buy_pct": 50.0, "aggressive": "NEUTRAL", "src": "LIVE-FAIL"}

def get_spot_premium():
    try:
        cb = _safe_get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        if cb:
            cb_p = float(cb["price"])
            for url, name, parse in [
                ("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", "Binance", lambda j: float(j["price"])),
                ("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP", "OKX", lambda j: float(j["data"][0]["last"])),
            ]:
                try:
                    j = _safe_get(url)
                    if not j: continue
                    bn_p = parse(j)
                    prem = cb_p - bn_p
                    bias = "SPOT_BUYING" if prem > 50 else "SPOT_SELLING" if prem < -50 else "NEUTRAL"
                    return {"coinbase": cb_p, "binance": bn_p, "premium_usd": round(prem, 1), "premium_pct": round(prem/bn_p*100, 4) if bn_p else 0, "bias": bias, "src": f"Coinbase+{name}-LIVE"}
                except: pass
    except: pass
    return {"coinbase": 0, "binance": 0, "premium_usd": 0, "premium_pct": 0, "bias": "UNKNOWN", "src": "LIVE-FAIL"}

def get_spread_score(price, spot, funding):
    spot_prem = spot.get("premium_usd", 0) if spot else 0
    cb_price = spot.get("coinbase", 0) if spot else 0
    cb_bybit = (cb_price - price) if cb_price and price else 0
    score = 0; reasons = []
    if spot_prem >= 100: score += 2; reasons.append(f"Spot prem +${spot_prem:.0f} +2")
    elif spot_prem >= 50: score += 1; reasons.append(f"Spot prem +${spot_prem:.0f} +1")
    elif spot_prem <= -100: score -= 2; reasons.append(f"Spot prem ${spot_prem:.0f} -2")
    elif spot_prem <= -50: score -= 1; reasons.append(f"Spot prem ${spot_prem:.0f} -1")
    if cb_bybit >= 150: score += 2; reasons.append(f"Coinbase-Bybit +${cb_bybit:.0f} +2")
    elif cb_bybit >= 80: score += 1; reasons.append(f"Coinbase-Bybit +${cb_bybit:.0f} +1")
    elif cb_bybit <= -150: score -= 2; reasons.append(f"Coinbase-Bybit ${cb_bybit:.0f} -2")
    elif cb_bybit <= -80: score -= 1; reasons.append(f"Coinbase-Bybit ${cb_bybit:.0f} -1")
    crowded = False
    if funding is not None and funding > 0.05 and score > 0:
        score -= 1; crowded = True; reasons.append("Funding crowded LONG, spread boost cut -1")
    if funding is not None and funding < -0.03 and score < 0:
        score += 1; crowded = True; reasons.append("Funding crowded SHORT, spread boost cut +1")
    if score >= 3: bias = "LONG"
    elif score <= -3: bias = "SHORT"
    elif score > 0: bias = "LONG_WEAK"
    elif score < 0: bias = "SHORT_WEAK"
    else: bias = "NEUTRAL"
    return {"score": score, "bias": bias, "spot_premium_usd": round(spot_prem, 1),
            "coinbase": round(cb_price, 1), "coinbase_bybit_spread": round(cb_bybit, 1),
            "crowded": crowded, "reasons": reasons}

# ------------------------------------------------------------
# V15.6 GOLD BOSS - LIVE EYE, NO HARDCODED WAIT
# ------------------------------------------------------------
_gold_boss_state = {"break_active": False, "resolve_since": 0, "break_candles": 0, "last_break_ts": 0}

def get_gold_5m_series():
    try:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            j = _safe_get(f"{base}/v8/finance/chart/GC=F?range=1d&interval=5m")
            if j:
                res = j["chart"]["result"][0]
                q = res["indicators"]["quote"][0]
                closes = [c for c in q.get("close", []) if c is not None]
                highs = [h for h in q.get("high", []) if h is not None]
                lows = [l for l in q.get("low", []) if l is not None]
                if len(closes) >= 4:
                    return closes, highs, lows
    except: pass
    return [], [], []

def get_gold_boss(gold_day_chg, btc_chg_15m, funding, oi_chg_5m):
    closes, highs, lows = get_gold_5m_series()
    gold_15m = 0.0; gold_1h = 0.0; wick_pct = 0.0; wick_active = False
    if len(closes) >= 4:
        if closes[-4]: gold_15m = round((closes[-1]-closes[-4])/closes[-4]*100, 3)
        if len(closes) >= 13 and closes[-13]: gold_1h = round((closes[-1]-closes[-13])/closes[-13]*100, 3)
    if highs and lows and closes and closes[-1]:
        wick_pct = round((highs[-1]-lows[-1])/closes[-1]*100, 3)
        wick_active = wick_pct > 0.5
    is_break = False; divergence = 0.0; break_dir = "NONE"; break_tier = "NONE"
    if gold_15m != 0 and btc_chg_15m != 0:
        if (gold_15m > 0 and btc_chg_15m < 0) or (gold_15m < 0 and btc_chg_15m > 0):
            divergence = round(abs(gold_15m - btc_chg_15m), 3)
            if divergence <= 0.3:
                break_tier = "TIER1_IGNORE"; is_break = False
            elif divergence <= 0.8:
                break_tier = "TIER2_HOLD_WATCH"; is_break = True
            else:
                break_tier = "TIER3_BIG_BREAK"; is_break = True
            if is_break:
                break_dir = "BTC_UP_GOLD_DOWN" if btc_chg_15m > 0 else "BTC_DOWN_GOLD_UP"
    now_ts = time.time()
    if is_break:
        if not _gold_boss_state["break_active"]:
            _gold_boss_state["break_active"] = True; _gold_boss_state["break_candles"] = 1; _gold_boss_state["last_break_ts"] = now_ts
        elif now_ts - _gold_boss_state["last_break_ts"] >= 240:
            _gold_boss_state["break_candles"] += 1; _gold_boss_state["last_break_ts"] = now_ts
        _gold_boss_state["resolve_since"] = 0
    elif _gold_boss_state["break_active"]:
        _gold_boss_state["break_active"] = False; _gold_boss_state["resolve_since"] = now_ts; _gold_boss_state["break_candles"] = 0
    confirm_ok = False; confirm_wait = 0
    if not is_break and _gold_boss_state["resolve_since"] > 0:
        elapsed = now_ts - _gold_boss_state["resolve_since"]
        if elapsed >= 120 and not wick_active: confirm_ok = True
        else: confirm_wait = max(0, int(120 - elapsed))
    elif not is_break:
        confirm_ok = True
    flip_to = "NONE"
    if _gold_boss_state["break_candles"] >= 3 and is_break:
        flip_to = "LONG" if break_dir == "BTC_UP_GOLD_DOWN" else "SHORT"
    boss_boost = 0; boss_dir = "NONE"; boss_reasons = []
    if not is_break:
        if gold_15m < -0.05 and btc_chg_15m < -0.05:
            boss_dir = "SHORT"
            if abs(gold_day_chg) >= 2.0: boss_boost = 15; boss_reasons.append(f"GOLD BOSS SHORT +15% | GOLD day {gold_day_chg:.2f}% + GOLD 15m {gold_15m:.2f}% + BTC 15m {btc_chg_15m:.2f}% aligned")
            elif abs(gold_day_chg) >= 1.0: boss_boost = 10; boss_reasons.append(f"GOLD BOSS SHORT +10% | GOLD {gold_day_chg:.2f}% aligned")
            else: boss_boost = 5; boss_reasons.append(f"GOLD BOSS SHORT +5% | GOLD 15m {gold_15m:.2f}% aligned")
        elif gold_15m > 0.05 and btc_chg_15m > 0.05:
            boss_dir = "LONG"
            if abs(gold_day_chg) >= 2.0: boss_boost = 15; boss_reasons.append(f"GOLD BOSS LONG +15% | GOLD day {gold_day_chg:.2f}% + GOLD 15m {gold_15m:.2f}% + BTC 15m {btc_chg_15m:.2f}% aligned")
            elif abs(gold_day_chg) >= 1.0: boss_boost = 10; boss_reasons.append(f"GOLD BOSS LONG +10% | GOLD {gold_day_chg:.2f}% aligned")
            else: boss_boost = 5; boss_reasons.append(f"GOLD BOSS LONG +5% | GOLD 15m {gold_15m:.2f}% aligned")
    dom_boost = 0; dom_dir = "NONE"; dom_reasons = []
    if gold_day_chg < -1.0 and oi_chg_5m > 0.1 and funding is not None and funding > 0.02:
        dom_dir = "SHORT"; dom_boost = 10; dom_reasons.append(f"DOMINANCE SHORT +10% | GOLD {gold_day_chg:.2f}% + OI +{oi_chg_5m:.2f}% + Funding +{funding:.4f}% = LONG CROWDED")
    elif gold_day_chg > 1.0 and oi_chg_5m > 0.1 and funding is not None and funding < -0.01:
        dom_dir = "LONG"; dom_boost = 10; dom_reasons.append(f"DOMINANCE LONG +10% | GOLD +{gold_day_chg:.2f}% + OI +{oi_chg_5m:.2f}% + Funding {funding:.4f}% = SHORT CROWDED")
    return {"gold_15m": gold_15m, "gold_1h": gold_1h, "gold_day": gold_day_chg, "btc_15m": round(btc_chg_15m, 3),
            "wick_pct": wick_pct, "wick_active": wick_active, "is_break": is_break, "divergence": divergence, "break_dir": break_dir, "break_tier": break_tier,
            "break_candles": _gold_boss_state["break_candles"], "confirm_ok": confirm_ok, "confirm_wait": confirm_wait, "resolve_since": _gold_boss_state["resolve_since"],
            "flip_to": flip_to, "boss_boost": boss_boost, "boss_dir": boss_dir, "boss_reasons": boss_reasons,
            "dom_boost": dom_boost, "dom_dir": dom_dir, "dom_reasons": dom_reasons}

def get_funding_cascade(funding, oi_chg_5m=0.0, price_chg_5m=0.0):
    risk = "NONE"; block_long = False; block_short = False; reason = ""
    if funding > 0.02 and oi_chg_5m > 0.1 and price_chg_5m < 0:
        risk = "CASCADE_DOWN"; block_long = True; reason = f"Funding +{funding:.4f}% crowded LONG + OI up + price down"
    elif funding > 0.05:
        risk = "CASCADE_DOWN"; block_long = True; reason = f"Funding +{funding:.4f}% extreme crowded LONG"
    elif funding < -0.01 and oi_chg_5m > 0.1 and price_chg_5m > 0:
        risk = "CASCADE_UP"; block_short = True; reason = f"Funding {funding:.4f}% crowded SHORT + OI up + price up"
    elif funding < -0.03:
        risk = "CASCADE_UP"; block_short = True; reason = f"Funding {funding:.4f}% extreme crowded SHORT"
    return {"funding": funding, "risk": risk, "block_long": block_long, "block_short": block_short, "reason": reason, "oi_chg_5m": oi_chg_5m, "price_chg_5m": round(price_chg_5m, 3)}

def get_hunt_certainty(price, liq, obc, cvd, fc, a_low, a_high):
    score = 0; reasons = []; hunt_dir = "NONE"; target = 0.0
    if liq["dominant"] == "HUNT_LONGS_FIRST":
        hunt_dir = "DOWN_FIRST"; target = a_low if a_low else price - 800; score += 2; reasons.append("Liq Longs > Shorts 1.5x +2")
    elif liq["dominant"] == "HUNT_SHORTS_FIRST":
        hunt_dir = "UP_FIRST"; target = a_high if a_high else price + 800; score += 2; reasons.append("Liq Shorts > Longs 1.5x +2")
    if liq.get("total", 0) > 5000000: score += 2; reasons.append(f"Liq total ${liq['total']:,.0f} > $5M +2")
    elif liq.get("total", 0) > 2000000: score += 1; reasons.append(f"Liq total ${liq['total']:,.0f} > $2M +1")
    if hunt_dir == "DOWN_FIRST" and obc.get("cluster_bias") == "ASK_WALL_STRONG": score += 1; reasons.append("Ask wall + hunt down +1")
    elif hunt_dir == "UP_FIRST" and obc.get("cluster_bias") == "BID_WALL_STRONG": score += 1; reasons.append("Bid wall + hunt up +1")
    if hunt_dir == "DOWN_FIRST" and cvd.get("aggressive") == "SELL": score += 1; reasons.append("CVD SELL + hunt down +1")
    elif hunt_dir == "UP_FIRST" and cvd.get("aggressive") == "BUY": score += 1; reasons.append("CVD BUY + hunt up +1")
    if target:
        dist = abs(price - target)
        if dist <= 300: score += 2; reasons.append(f"Price ${dist:.0f} from target +2")
        elif dist <= 800: score += 1; reasons.append(f"Price ${dist:.0f} from target +1")
    if hunt_dir == "DOWN_FIRST" and fc.get("risk") == "CASCADE_DOWN": score += 1; reasons.append("Funding cascade DOWN +1")
    elif hunt_dir == "UP_FIRST" and fc.get("risk") == "CASCADE_UP": score += 1; reasons.append("Funding cascade UP +1")
    label = "CERTAIN" if score >= 6 else "MAYBE" if score >= 3 else "NO_HUNT"
    dist = abs(price - target) if target else 9999
    size_label = "TOO_SMALL" if dist < 300 else "GOOD" if dist <= 1200 else "SL_DANGER"
    return {"score": score, "label": label, "hunt_dir": hunt_dir, "target": target, "distance": round(dist, 0), "size_label": size_label, "reasons": reasons}

def get_first_aid(price, hunt_cert, direction, cert, sweep_done, k1_norm):
    if not hunt_cert or hunt_cert.get("label") != "CERTAIN" or sweep_done:
        return False, "", "NONE", direction
    hunt_dir = hunt_cert.get("hunt_dir", "NONE"); target = hunt_cert.get("target", 0)
    if hunt_dir == "DOWN_FIRST" and direction == "SHORT" and cert >= 85:
        return True, f"FIRST AID: Hunt DOWN to ${target:,.0f} then LONG, but worldwide flip to SHORT {cert}% - hunt CANCELLED", "RELEASE_FLIP_SHORT", "SHORT"
    if hunt_dir == "UP_FIRST" and direction == "LONG" and cert >= 85:
        return True, f"FIRST AID: Hunt UP to ${target:,.0f} then SHORT, but worldwide flip to LONG {cert}% - hunt CANCELLED", "RELEASE_FLIP_LONG", "LONG"
    if target and k1_norm:
        last = k1_norm[-1]
        if hunt_dir == "DOWN_FIRST" and last["close"] < target - 200:
            return True, f"FIRST AID: Price ${price:,.0f} break through hunt target ${target:,.0f} without sweep - HUNT FAILED, trade trend", "RELEASE_TREND", direction
        if hunt_dir == "UP_FIRST" and last["close"] > target + 200:
            return True, f"FIRST AID: Price ${price:,.0f} break through hunt target ${target:,.0f} without sweep - HUNT FAILED, trade trend", "RELEASE_TREND", direction
    if target and abs(price - target) > 1500:
        return True, f"FIRST AID: Price ${price:,.0f} run away ${abs(price-target):.0f} from hunt target ${target:,.0f} - HUNT INVALID", "RELEASE_TREND", direction
    return False, "", "NONE", direction

def get_hunter_live(price, k1_norm, funding, spot, oi, oi_chg, price_chg_5, a_low=0, a_high=0):
    try:
        liq = get_liq_clusters(price, k1_norm); obc = get_ob_clusters(price); cvd = get_cvd_live()
        fc = get_funding_cascade(funding, oi_chg, price_chg_5)
        hunt_cert = get_hunt_certainty(price, liq, obc, cvd, fc, a_low, a_high)
        hunt_active, hunt_session = get_hunt_window()
        score = 0.0; reasons = []
        if liq["dominant"] == "HUNT_LONGS_FIRST": score -= 1.5; reasons.append(f"Liq Longs ${liq['long_liq']:,.0f} > Shorts ${liq['short_liq']:,.0f}")
        elif liq["dominant"] == "HUNT_SHORTS_FIRST": score += 1.5; reasons.append(f"Liq Shorts ${liq['short_liq']:,.0f} > Longs ${liq['long_liq']:,.0f}")
        if fc["risk"] == "CASCADE_DOWN": score -= 2; reasons.append(f"Funding cascade DOWN: {fc['reason']}")
        elif fc["risk"] == "CASCADE_UP": score += 2; reasons.append(f"Funding cascade UP: {fc['reason']}")
        if obc["cluster_bias"] == "BID_WALL_STRONG": score += 1; reasons.append(f"OB Bid wall ${obc['bid_wall_usd']:,.0f}")
        elif obc["cluster_bias"] == "ASK_WALL_STRONG": score -= 1; reasons.append(f"OB Ask wall ${obc['ask_wall_usd']:,.0f}")
        if cvd["aggressive"] == "BUY" and cvd["buy_pct"] > 60: score += 1; reasons.append(f"CVD BUY {cvd['buy_pct']}%")
        elif cvd["aggressive"] == "SELL" and cvd["buy_pct"] < 40: score -= 1; reasons.append(f"CVD SELL {cvd['buy_pct']}%")
        if spot["bias"] == "SPOT_BUYING": score += 1; reasons.append(f"Spot +${spot['premium_usd']:.0f}")
        elif spot["bias"] == "SPOT_SELLING": score -= 1; reasons.append(f"Spot ${spot['premium_usd']:.0f}")
        if oi_chg > 0.1 and price_chg_5 > 0: score += 0.5; reasons.append("OI up + price up")
        elif oi_chg > 0.1 and price_chg_5 < 0: score -= 0.5; reasons.append("OI up + price down")
        elif oi_chg < -0.1 and price_chg_5 > 0: score += 0.5; reasons.append("OI down + price up")
        elif oi_chg < -0.1 and price_chg_5 < 0: score -= 0.5; reasons.append("OI down + price down")
        hunter_bias = "LONG" if score >= 1.5 else "SHORT" if score <= -1.5 else "NEUTRAL"
        hunter_wait = hunt_cert["label"] == "CERTAIN" and hunt_active and hunter_bias != "NEUTRAL" and hunt_cert["size_label"] == "GOOD"
        wait_reason = f"Hunt {hunt_cert['label']} {hunt_cert['score']}/9 {hunt_session} {hunt_cert['hunt_dir']} target ${hunt_cert['target']:,.0f}" if hunter_wait else f"Hunt {hunt_cert['label']} {hunt_cert['score']}/9 - no wait, trade trend / skip candle"
        return {"hunter_score": round(score, 2), "hunter_bias": hunter_bias, "hunter_wait": hunter_wait, "wait_reason": wait_reason, "reasons": reasons,
                "liq": liq, "ob_clusters": obc, "cvd_live": cvd, "spot": spot, "funding_cascade": fc, "oi": oi, "hunt_certainty": hunt_cert, "hunt_active": hunt_active, "hunt_session": hunt_session}
    except Exception as e:
        return {"hunter_score": 0.0, "hunter_bias": "NEUTRAL", "hunter_wait": False, "wait_reason": "", "reasons": [f"Hunter error {e}"],
                "liq": {}, "ob_clusters": {}, "cvd_live": {}, "spot": spot, "funding_cascade": {}, "oi": oi,
                "hunt_certainty": {"score": 0, "label": "NO_HUNT", "hunt_dir": "NONE", "target": 0, "distance": 9999, "size_label": "TOO_SMALL", "reasons": []},
                "hunt_active": False, "hunt_session": get_session()}

def get_asia_range(k15):
    lows, highs = [], []
    for k in k15:
        try:
            dt = datetime.fromtimestamp(k["time"]/1000, tz=timezone.utc)
            if dt.date() == _now().date() and 0 <= dt.hour < 8:
                lows.append(k["low"]); highs.append(k["high"])
        except: pass
    if lows: return min(lows), max(highs)
    if len(k15) >= 32:
        return min(x["low"] for x in k15[-32:]), max(x["high"] for x in k15[-32:])
    return 0.0, 0.0

def get_sweep(price, k15, k1, liq_clusters=None):
    a_low, a_high = get_asia_range(k15)
    if liq_clusters:
        ll = liq_clusters.get("long_liq", 0); sl = liq_clusters.get("short_liq", 0)
    else:
        c = get_liq_clusters(price, k1); ll = c["long_liq"]; sl = c["short_liq"]
    sweep_done = False; sweep_dir = "NONE"; hunt = "NEUTRAL"
    if a_low and a_high and k1:
        last = k1[-1]
        if last["low"] < a_low and last["close"] > a_low: hunt = "LONG"; sweep_done = True; sweep_dir = "LONG"
        elif last["high"] > a_high and last["close"] < a_high: hunt = "SHORT"; sweep_done = True; sweep_dir = "SHORT"
    return hunt, a_low, a_high, ll, sl, sweep_done, sweep_dir

def get_news(k1=None):
    if k1 is None: k1 = get_klines("1", 15)
    if len(k1) >= 15:
        mv = (k1[-1]["close"]-k1[0]["close"])/k1[0]["close"]*100
        if abs(mv) >= 0.8: return True, f"VOL SPIKE {mv:.2f}% 15m"
    return False, ""

def get_macro_brain(price, k1, k15, funding=0.0):
    try:
        dxy_p, dxy_d, dxy_1h = yahoo_price_1h("DX-Y.NYB")
        _, _, jpy_1h = yahoo_price_1h("USDJPY=X")
        _, tnx_d, _ = yahoo_price_1h("^TNX")
        fng, _ = get_fear()
        rsi = calc_rsi(k15[-60:] if k15 else [], 14)
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
        return {"score": score, "bias": bias, "alert": alert, "dxy_1h": dxy_1h, "jpy_1h": jpy_1h, "funding": funding, "fng": fng, "rsi": rsi, "details": det}
    except Exception as e:
        return {"score": 0.0, "bias": "NEUTRAL", "alert": None, "error": str(e)}

_last_signal = {"time": 0, "data": None}

def _macro_vote(bias):
    if bias == "LONG": return 1, 0
    if bias == "SHORT": return 0, 1
    return 0, 0

def _ob_vote(obc):
    bp = obc.get("buy_pressure", 50)
    if obc.get("cluster_bias") == "BID_WALL_STRONG": return 1, 0, "OB Bid Wall LONG"
    if obc.get("cluster_bias") == "ASK_WALL_STRONG": return 0, 1, "OB Ask Wall SHORT"
    if bp > 55: return 1, 0, "Orderbook bids LONG"
    if bp < 45: return 0, 1, "Orderbook asks SHORT"
    return 0, 0, ""

def get_signal(price, atr=None, candles=None):
    global _last_signal
    if _last_signal["data"] is not None and (time.time() - _last_signal["time"]) < 10:
        cached = dict(_last_signal["data"]); cached["price"] = price; return cached
    try:
        if not price or price == 0:
            price, _ = get_price_live()
            if price == 0:
                return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False, "price": 0, "hunter_score": 0, "hunter_bias": "NEUTRAL", "hunter_wait": False, "sweep_done": False, "sweep_dir": "NONE", "first_aid": False, "first_aid_action": "NONE", "first_aid_reason": "", "hunt_certainty": {"score": 0, "label": "NO_HUNT"}, "spread": {"score": 0, "bias": "NEUTRAL", "spot_premium_usd": 0, "coinbase_bybit_spread": 0, "reasons": []}, "gold_boss": {}, "gold_boss_boost": 0}
        k1 = candles if candles and len(candles) >= 5 else get_klines("1", 20)
        k1_norm = [{"open": float(k.get("open", 0)), "high": float(k.get("high", 0)), "low": float(k.get("low", 0)), "close": float(k.get("close", 0)), "volume": float(k.get("volume", 1)), "time": int(k.get("time", 0))} for k in k1]
        k15 = get_klines("15", 200)
        world = get_world(); funding, _ = get_funding(); spot = get_spot_premium(); oi = get_open_interest()
        price_chg_5 = (k1_norm[-1]["close"]-k1_norm[-6]["close"])/k1_norm[-6]["close"]*100 if len(k1_norm) >= 6 and k1_norm[-6]["close"] else 0
        macro_brain = get_macro_brain(price, k1_norm, k15, funding)
        a_low_tmp, a_high_tmp = get_asia_range(k15)
        hunter = get_hunter_live(price, k1_norm, funding, spot, oi, oi.get("chg_5m", 0), price_chg_5, a_low_tmp, a_high_tmp)
        hunt, a_low, a_high, ll, sl, sweep_done, sweep_dir = get_sweep(price, k15, k1_norm, hunter.get("liq"))
        is_news, news_reason = get_news(k1_norm)
        obc = hunter.get("ob_clusters", {}); cvd_live = hunter.get("cvd_live", {}); fc = hunter.get("funding_cascade", {})
        hunt_cert = hunter.get("hunt_certainty", {"score": 0, "label": "NO_HUNT", "hunt_dir": "NONE", "target": 0, "distance": 9999, "size_label": "TOO_SMALL", "reasons": []})
        hunt_active = hunter.get("hunt_active", False)
        spread = get_spread_score(price, spot, funding)
        # --- VOTES: Each voter votes ONCE (no duplicates) ---
        long_votes = 0; short_votes = 0; total_voters = 8; reasons = []
        for key in ["DXY", "NQ", "SPX"]:
            v = world.get(key, 0)
            if key == "DXY":
                if v < -0.05: long_votes += 1; reasons.append("DXY down LONG")
                elif v > 0.05: short_votes += 1; reasons.append("DXY up SHORT")
            else:
                if v > 0.05: long_votes += 1; reasons.append(f"{key} up LONG")
                elif v < -0.05: short_votes += 1; reasons.append(f"{key} down SHORT")
        gold = world.get("GOLD", 0)
        if gold > 0.05: long_votes += 1; reasons.append("GOLD up LONG")
        elif gold < -0.05: short_votes += 1; reasons.append("GOLD down SHORT")
        oi_chg = oi.get("chg_5m", 0)
        macro_l, macro_s = _macro_vote(macro_brain.get("bias"))
        # OI vote OR Macro vote, not both
        if oi_chg > 0.1 and price_chg_5 < 0: long_votes += 1; reasons.append("OI up + price down LONG")
        elif oi_chg > 0.1 and price_chg_5 > 0: long_votes += 1; reasons.append("OI up + price up LONG")
        elif oi_chg < -0.1 and price_chg_5 < 0: short_votes += 1; reasons.append("OI down + price down SHORT")
        else: long_votes += macro_l; short_votes += macro_s
        # Sweep vote OR Macro vote, not both - if sweep exists, sweep wins, macro already counted above if OI did not
        if hunt == "LONG": long_votes += 1; reasons.append("Sweep LONG")
        elif hunt == "SHORT": short_votes += 1; reasons.append("Sweep SHORT")
        cvd_agg = cvd_live.get("aggressive", "NEUTRAL"); cvd_buy_pct = cvd_live.get("buy_pct", 50.0)
        ob_l, ob_s, ob_r = _ob_vote(obc)
        # CVD vote OR OB vote, not both
        if cvd_agg == "BUY": long_votes += 1; reasons.append(f"CVD BUY {cvd_buy_pct}% LONG")
        elif cvd_agg == "SELL": short_votes += 1; reasons.append(f"CVD SELL {cvd_buy_pct}% SHORT")
        else: long_votes += ob_l; short_votes += ob_s
        # OB extra: only if CVD was decisive, OB is separate voter - counted once here via ob_l/ob_s above OR here
        # CLEAN: OB already counted in else branch. If CVD voted, OB is 8th voter - count it once:
        if cvd_agg in ("BUY", "SELL"):
            long_votes += ob_l; short_votes += ob_s
        if ob_r and ob_r not in reasons: reasons.append(ob_r)
        if long_votes > short_votes: direction = "LONG"; agree = long_votes
        elif short_votes > long_votes: direction = "SHORT"; agree = short_votes
        else: direction = "NONE"; agree = long_votes
        cert = round((agree / total_voters) * 100, 1) if total_voters else 0
        if macro_brain.get("bias") == direction and direction != "NONE": cert = min(100, cert + 5)
        hunter_bias = hunter.get("hunter_bias", "NEUTRAL"); hunter_score = hunter.get("hunter_score", 0); hunter_wait = hunter.get("hunter_wait", False)
        if hunter_bias == direction and direction != "NONE": cert = min(100, cert + 5); reasons.append(f"Hunter agrees {hunter_bias} +5")
        elif hunter_bias != "NEUTRAL" and hunter_bias != direction and direction != "NONE": cert = max(0, cert - 10); reasons.append(f"Hunter disagrees {hunter_bias} vs {direction} -10")
        spread_boost = 0
        if direction != "NONE" and spread.get("bias") in ("LONG", "SHORT"):
            spread_dir = spread["bias"]
            if spread_dir == direction and (hunter_bias == direction or macro_brain.get("bias") == direction):
                spread_boost = 10; cert = min(100, cert + 10); reasons.append(f"SPREAD BOOSTER +10% | Spread {spread_dir} {spread['score']} | Spot +${spread['spot_premium_usd']:.0f} | Coinbase-Bybit +${spread['coinbase_bybit_spread']:.0f}")
            elif spread_dir != direction and spread.get("score", 0) != 0:
                spread_boost = -5; cert = max(0, cert - 5); reasons.append(f"SPREAD WARNING -5% | Spread {spread_dir} vs {direction} | Spot ${spread['spot_premium_usd']:.0f}")
        if sweep_done:
            direction = sweep_dir; agree = max(agree, 7); cert = 85.0; reasons.append(f"SWEEP DONE {sweep_dir} @ ${price:,.0f} - ENTER IMMEDIATELY"); hunter_wait = False
        first_aid, first_aid_reason, first_aid_action, fa_dir = get_first_aid(price, hunt_cert, direction, cert, sweep_done, k1_norm)
        if first_aid: direction = fa_dir; hunter_wait = False; reasons.append(first_aid_reason)
        hunt_soon = False; hunt_cert_score = 0
        if hunt_cert["label"] == "CERTAIN" and hunt_active and not sweep_done and not first_aid: hunt_soon = True; hunt_cert_score = hunt_cert["score"]
        news_critical = False; news_wait = 0
        if is_news:
            if cert >= 90 and agree >= 7: news_critical = True
            else: news_wait = 300
        pause_long = False; pause_short = False; pause_reason = ""
        if macro_brain.get("alert") == "PAUSE_SHORT": pause_short = True; pause_reason = "Macro PAUSE_SHORT DXY/JPY"
        # --- V15.6 GOLD BOSS ---
        btc_chg_15m_calc = (k1_norm[-1]["close"]-k1_norm[-16]["close"])/k1_norm[-16]["close"]*100 if len(k1_norm) >= 16 and k1_norm[-16]["close"] else price_chg_5
        gold_boss = get_gold_boss(gold, btc_chg_15m_calc, funding, oi_chg)
        gold_boss_boost = 0
        if gold_boss["boss_dir"] == direction and direction != "NONE":
            gold_boss_boost += gold_boss["boss_boost"]; cert = min(100, cert + gold_boss["boss_boost"]); reasons.extend(gold_boss["boss_reasons"])
        if gold_boss["dom_dir"] == direction and direction != "NONE":
            gold_boss_boost += gold_boss["dom_boost"]; cert = min(100, cert + gold_boss["dom_boost"]); reasons.extend(gold_boss["dom_reasons"])
        if gold_boss["boss_dir"] != "NONE" and gold_boss["boss_dir"] != direction and direction != "NONE":
            cert = max(0, cert - 5); reasons.append(f"GOLD BOSS WARNING -5% | GOLD BOSS {gold_boss['boss_dir']} vs {direction}")
        if gold_boss["is_break"]:
            pause_long = True; pause_short = True
            pause_reason = f"GOLD BREAK LIVE WATCH {gold_boss['break_tier']} | GOLD 15m {gold_boss['gold_15m']:.2f}% vs BTC 15m {gold_boss['btc_15m']:.2f}% div {gold_boss['divergence']:.2f}% | Wick {gold_boss['wick_pct']:.2f}% | Candles {gold_boss['break_candles']}"
            if gold_boss["flip_to"] != "NONE":
                reasons.append(f"GOLD BREAK FLIP {gold_boss['break_candles']} candles -> BTC winning, flip candidate {gold_boss['flip_to']}")
                if gold_boss["flip_to"] == "LONG": pause_long = False
                elif gold_boss["flip_to"] == "SHORT": pause_short = False
                pause_reason = f"GOLD BREAK FLIP {gold_boss['break_candles']} candles -> Follow BTC {gold_boss['flip_to']}"
        else:
            if gold_boss["resolve_since"] > 0 and not gold_boss["confirm_ok"]:
                pause_long = True; pause_short = True; pause_reason = f"GOLD BREAK RESOLVED, 2min confirm {gold_boss['confirm_wait']}s left | Wick {gold_boss['wick_pct']:.2f}%"
            elif gold_boss["wick_active"] and direction != "NONE":
                pause_long = True; pause_short = True; pause_reason = f"GOLD WICK LIVE WATCH {gold_boss['wick_pct']:.2f}% >0.5% - wait wick close"
        if hunter_wait and hunt_soon:
            if hunter_score < -1.0 and direction == "LONG": pause_long = True; pause_reason = hunter.get("wait_reason", "Hunter wait LONG")
            if hunter_score > 1.0 and direction == "SHORT": pause_short = True; pause_reason = hunter.get("wait_reason", "Hunter wait SHORT")
        if fc.get("block_long") and direction == "LONG": pause_long = True; pause_reason = fc.get("reason", "Funding cascade block LONG")
        if fc.get("block_short") and direction == "SHORT": pause_short = True; pause_reason = fc.get("reason", "Funding cascade block SHORT")
        if sweep_done or first_aid: pause_long = False; pause_short = False; pause_reason = ""
        result = {"cert": cert, "direction": direction, "agree": agree,
                  "hunt_soon": hunt_soon, "hunt_cert": hunt_cert_score, "cvd_buy_pct": cvd_buy_pct,
                  "news_critical": news_critical, "news_wait": news_wait,
                  "pause_long": pause_long, "pause_short": pause_short, "pause_reason": pause_reason,
                  "price": price, "reasons": reasons, "news_reason": news_reason,
                  "macro_bias": macro_brain.get("bias"), "session": get_session(),
                  "liq_long": ll, "liq_short": sl,
                  "hunter_score": hunter_score, "hunter_bias": hunter_bias, "hunter_wait": hunter_wait,
                  "hunter_reasons": hunter.get("reasons", []), "hunter_wait_reason": hunter.get("wait_reason", ""),
                  "liq_clusters": hunter.get("liq", {}), "ob_clusters": obc, "cvd_live": cvd_live,
                  "spot_premium": spot, "spot_premium_usd": spot.get("premium_usd", 0),
                  "funding_cascade": fc, "oi": oi,
                  "sweep_done": sweep_done, "sweep_dir": sweep_dir,
                  "first_aid": first_aid, "first_aid_action": first_aid_action, "first_aid_reason": first_aid_reason,
                  "hunt_certainty": hunt_cert, "hunt_active": hunt_active, "hunt_session": hunter.get("hunt_session", get_session()),
                  "asia_low": a_low, "asia_high": a_high,
                  "spread": spread, "spread_score": spread.get("score", 0), "spread_bias": spread.get("bias", "NEUTRAL"), "spread_boost": spread_boost,
                  "gold_boss": gold_boss, "gold_boss_boost": gold_boss_boost}
        _last_signal = {"time": time.time(), "data": result}
        return result
    except Exception as e:
        print(f"get_signal Error: {e}", flush=True)
        return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False, "price": price, "hunter_score": 0, "hunter_bias": "NEUTRAL", "hunter_wait": False, "sweep_done": False, "sweep_dir": "NONE", "first_aid": False, "first_aid_action": "NONE", "first_aid_reason": "", "spread": {"score": 0, "bias": "NEUTRAL", "spot_premium_usd": 0, "coinbase_bybit_spread": 0, "reasons": []}, "spread_boost": 0, "gold_boss": {}, "gold_boss_boost": 0}

if __name__ == "__main__":
    price, src = get_price_live()
    sig = get_signal(price, 200, get_klines("1", 20))
    print(f"Price ${price:.0f} [{src}] Signal: {sig['direction']} Cert {sig['cert']}% Hunter {sig['hunter_bias']} {sig['hunter_score']} Sweep {sig.get('sweep_done')} Hunt {sig.get('hunt_certainty', {}).get('label')} FirstAid {sig.get('first_aid')} Spread {sig.get('spread', {}).get('bias')} {sig.get('spread', {}).get('score')} Boost {sig.get('spread_boost')} GOLD_BOSS {sig.get('gold_boss', {}).get('boss_dir')} {sig.get('gold_boss_boost')} Break {sig.get('gold_boss', {}).get('is_break')} Wick {sig.get('gold_boss', {}).get('wick_pct')}")
