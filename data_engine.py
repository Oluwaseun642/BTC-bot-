# ============================================================
# DATA ENGINE V15.3.0 CLEAN - NO DUPLICATES, NO DEAD CODE
# GOLD FIXED: >1.0% + Hunter confirm only
# MULTI-SOURCE: Bybit/Binance/OKX/Kraken/Coinbase/Bitstamp/CoinGecko/CoinCap
# SPREAD OUT
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

# ------------------------------------------------------------
# 0. JSON RECORD KEEPER - USED by main.py save_trade
# ------------------------------------------------------------
TRADES_FILE = "trades.json"
DAILY_FILE = "daily.json"

def save_trade(trade):
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
        if res == "BE_TP": d["be_tp_hits"] += 1
        elif res in ("SL", "STOP_LOSS"): d["sl_hits"] += 1
        elif res == "TP": d["tp_hits"] += 1
        with open(DAILY_FILE, "w") as f:
            json.dump(daily, f, indent=2)
        print(f"[{_now().strftime('%H:%M:%S')}] 💾 Saved | {day} PNL ${d['total_pnl']:.2f} | Trades {d['trades']}", flush=True)
        return daily
    except Exception as e:
        print(f"JSON Save Error: {e}", flush=True)
        return {}

# ------------------------------------------------------------
# 1. PRICE + KLINES - MULTI-SOURCE
# ------------------------------------------------------------
def get_price_live():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT")
        if j:
            p = float(j["result"]["list"][0]["lastPrice"])
            if p > 0: return p, "Bybit-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
        if j:
            p = float(j["price"])
            if p > 0: return p, "Binance-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        if j:
            p = float(j["price"])
            if p > 0: return p, "Coinbase-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")
        if j:
            p = float(j["result"]["XXBTZUSD"]["c"][0])
            if p > 0: return p, "Kraken-LIVE"
    except: pass
    try:
        j = _safe_get("https://www.bitstamp.net/api/v2/ticker/btcusd/")
        if j:
            p = float(j["last"])
            if p > 0: return p, "Bitstamp-LIVE"
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP")
        if j:
            p = float(j["data"][0]["last"])
            if p > 0: return p, "OKX-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        if j:
            p = float(j["bitcoin"]["usd"])
            if p > 0: return p, "CoinGecko-LIVE"
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
    if not klines or len(klines) < period + 1:
        return 50.0
    closes = [k["close"] for k in klines]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100.0
    return round(100 - (100 / (1 + ag / al)), 1)

# ------------------------------------------------------------
# 2. YAHOO - WORLD MARKETS + STOOQ FALLBACK
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
    try:
        stooq = {"GC=F": "gc.f.us", "DX-Y.NYB": "dx.f.us", "CL=F": "cl.f.us"}.get(sym)
        if stooq:
            j = _safe_get(f"https://stooq.com/q/l/?s={stooq}&f=sd2t2ohlcv&h&e=json")
            if j and j.get("symbols"):
                d = j["symbols"][0]
                price = float(d.get("close", 0)); prev = float(d.get("open", 0))
                if price and prev:
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

def get_minutes_to_next_session():
    mins = _now().hour*60 + _now().minute
    opens = [0, 420, 810]
    return min([(o - mins) % 1440 for o in opens])

# ------------------------------------------------------------
# 3. FUNDING, FEAR, DOMINANCE - MULTI-SOURCE
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
    try:
        j = _safe_get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
        if j and j.get("data"):
            return float(j["data"][0].get("fundingRate", 0))*100, "OKX-LIVE"
    except: pass
    try:
        j = _safe_get("https://api.bitget.com/api/v2/mix/market/current-funding-rate?symbol=BTCUSDT&productType=USDT-FUTURES")
        if j and j.get("data"):
            return float(j["data"][0].get("fundingRate", 0))*100, "Bitget-LIVE"
    except: pass
    return 0.0, "LIVE-FAIL"

def get_fear():
    try:
        j = _safe_get("https://api.alternative.me/fng/?limit=1")
        if j:
            return int(j["data"][0]["value"]), j["data"][0].get("value_classification", ""), "Alternative-LIVE"
    except: pass
    return 50, "Neutral", "LIVE-FAIL"

def get_dominance():
    try:
        j = _safe_get("https://api.coingecko.com/api/v3/global")
        if j:
            d = j["data"]["market_cap_percentage"]
            return {"btc": round(float(d.get("btc", 0)), 2), "usdt": round(float(d.get("usdt", 0)), 2), "eth": round(float(d.get("eth", 0)), 2), "src": "CoinGecko-LIVE"}
    except: pass
    try:
        j = _safe_get("https://api.coincap.io/v2/assets?limit=3")
        if j and j.get("data"):
            caps = {x["symbol"]: float(x["marketCapUsd"]) for x in j["data"]}
            total = sum(caps.values())
            if total > 0:
                return {"btc": round(caps.get("BTC", 0)/total*100, 2), "usdt": 0.0, "eth": round(caps.get("ETH", 0)/total*100, 2), "src": "CoinCap-LIVE"}
    except: pass
    return {"btc": 0.0, "usdt": 0.0, "eth": 0.0, "src": "LIVE-FAIL"}

# ------------------------------------------------------------
# 4. OPEN INTEREST - MULTI-SOURCE
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
    try:
        j = _safe_get("https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP")
        if j and j.get("data"):
            return {"oi": float(j["data"][0]["oi"]), "chg_5m": 0.0, "src": "OKX-LIVE"}
    except: pass
    return {"oi": 0.0, "chg_5m": 0.0, "src": "LIVE-FAIL"}

# ------------------------------------------------------------
# 5. HUNTER LIVE - MULTI-SOURCE
# ------------------------------------------------------------
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
    if src == "LIVE-FAIL":
        try:
            j = _safe_get("https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT-SWAP&limit=100")
            if j:
                for grp in j.get("data", []):
                    for x in grp.get("details", []):
                        try:
                            sz = float(x.get("sz", 0)) * float(x.get("bkPx", price))
                            if x.get("side") == "sell": long_liq += sz
                            elif x.get("side") == "buy": short_liq += sz
                        except: pass
                if long_liq + short_liq > 0: src = "OKX-LIVE"
        except: pass
    if src == "LIVE-FAIL" and k1 and len(k1) >= 20:
        try:
            total_range = sum(abs(k["high"]-k["low"]) for k in k1[-20:])
            est_total = max(total_range * price * 0.05, 500000.0)
            pc = (k1[-1]["close"]-k1[-20]["close"])/k1[-20]["close"]*100 if k1[-20]["close"] else 0
            if pc < 0: long_liq, short_liq = est_total*0.65, est_total*0.35
            elif pc > 0: long_liq, short_liq = est_total*0.35, est_total*0.65
            else: long_liq, short_liq = est_total*0.5, est_total*0.5
            src = "Proxy-Kline"
        except: pass
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
        if j:
            return _parse_ob(j["result"]["b"], j["result"]["a"], "Bybit-LIVE")
    except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=50")
        if j:
            return _parse_ob(j["bids"], j["asks"], "Binance-LIVE")
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/market/books?instId=BTC-USDT-SWAP&sz=50")
        if j and j.get("data"):
            d = j["data"][0]
            return _parse_ob(d["bids"], d["asks"], "OKX-LIVE")
    except: pass
    try:
        j = _safe_get("https://api.kraken.com/0/public/Depth?pair=XBTUSD&count=50")
        if j and j.get("result"):
            key = [k for k in j["result"] if k != "last"][0]
            d = j["result"][key]
            bids = [[x[0], x[1]] for x in d["bids"]]; asks = [[x[0], x[1]] for x in d["asks"]]
            return _parse_ob(bids, asks, "Kraken-LIVE")
    except: pass
    return {"bid_wall_price": 0, "bid_wall_usd": 0, "ask_wall_price": 0, "ask_wall_usd": 0,
            "bid_vol": 0, "ask_vol": 0, "buy_pressure": 50.0, "cluster_bias": "UNKNOWN", "src": "LIVE-FAIL"}

def get_cvd_live():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=200")
        if j:
            lst = j["result"]["list"]
            buy_vol = sum(float(x.get("size", 0)) for x in lst if x.get("side") == "Buy")
            sell_vol = sum(float(x.get("size", 0)) for x in lst if x.get("side") == "Sell")
            if buy_vol + sell_vol > 0:
                buy_pct = buy_vol/(buy_vol+sell_vol)*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3),
                        "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "Bybit-Trades-LIVE"}
    except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=200")
        if isinstance(j, list) and len(j) > 0:
            buy_vol = sum(float(x.get("qty", 0)) for x in j if not x.get("isBuyerMaker"))
            sell_vol = sum(float(x.get("qty", 0)) for x in j if x.get("isBuyerMaker"))
            if buy_vol + sell_vol > 0:
                buy_pct = buy_vol/(buy_vol+sell_vol)*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3),
                        "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "Binance-Trades-LIVE"}
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/market/trades?instId=BTC-USDT-SWAP&limit=100")
        if j and j.get("data"):
            buy_vol = sum(float(x.get("sz", 0)) for x in j["data"] if x.get("side") == "buy")
            sell_vol = sum(float(x.get("sz", 0)) for x in j["data"] if x.get("side") == "sell")
            if buy_vol + sell_vol > 0:
                buy_pct = buy_vol/(buy_vol+sell_vol)*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3),
                        "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "OKX-Trades-LIVE"}
    except: pass
    try:
        j = _safe_get("https://api.kraken.com/0/public/Trades?pair=XBTUSD&count=100")
        if j and j.get("result"):
            key = [k for k in j["result"] if k != "last"][0]
            buy_vol = sum(float(x[1]) for x in j["result"][key] if x[3] == "b")
            sell_vol = sum(float(x[1]) for x in j["result"][key] if x[3] == "s")
            if buy_vol + sell_vol > 0:
                buy_pct = buy_vol/(buy_vol+sell_vol)*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3),
                        "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "Kraken-Trades-LIVE"}
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
                    return {"coinbase": cb_p, "binance": bn_p, "premium_usd": round(prem, 1),
                            "premium_pct": round(prem/bn_p*100, 4) if bn_p else 0, "bias": bias, "src": f"Coinbase+{name}-LIVE"}
                except: pass
            try:
                j = _safe_get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")
                if j:
                    kr_p = float(j["result"]["XXBTZUSD"]["c"][0])
                    prem = cb_p - kr_p
                    bias = "SPOT_BUYING" if prem > 50 else "SPOT_SELLING" if prem < -50 else "NEUTRAL"
                    return {"coinbase": cb_p, "binance": kr_p, "premium_usd": round(prem, 1),
                            "premium_pct": round(prem/kr_p*100, 4) if kr_p else 0, "bias": bias, "src": "Coinbase+Kraken-LIVE"}
            except: pass
    except: pass
    return {"coinbase": 0, "binance": 0, "premium_usd": 0, "premium_pct": 0, "bias": "UNKNOWN", "src": "LIVE-FAIL"}

def get_funding_cascade(funding, oi_chg_5m=0.0, price_chg_5m=0.0):
    risk = "NONE"; block_long = False; block_short = False; reason = ""
    if funding > 0.02 and oi_chg_5m > 0.1 and price_chg_5m < 0:
        risk = "CASCADE_DOWN"; block_long = True
        reason = f"Funding +{funding:.4f}% crowded LONG + OI up + price down = longs go get liquidated"
    elif funding > 0.05:
        risk = "CASCADE_DOWN"; block_long = True
        reason = f"Funding +{funding:.4f}% extreme crowded LONG"
    elif funding < -0.01 and oi_chg_5m > 0.1 and price_chg_5m > 0:
        risk = "CASCADE_UP"; block_short = True
        reason = f"Funding {funding:.4f}% crowded SHORT + OI up + price up = shorts go get squeezed"
    elif funding < -0.03:
        risk = "CASCADE_UP"; block_short = True
        reason = f"Funding {funding:.4f}% extreme crowded SHORT"
    return {"funding": funding, "risk": risk, "block_long": block_long, "block_short": block_short,
            "reason": reason, "oi_chg_5m": oi_chg_5m, "price_chg_5m": round(price_chg_5m, 3)}

def get_hunter_live(price, k1_norm, funding, spot, oi, oi_chg, price_chg_5):
    try:
        liq = get_liq_clusters(price, k1_norm)
        obc = get_ob_clusters(price)
        cvd = get_cvd_live()
        etf_score = 0.0; etf_reasons = []
        if spot.get("premium_usd", 0) > 50:
            etf_score += 1; etf_reasons.append(f"Coinbase premium +${spot['premium_usd']:.0f} ETF/spot buying")
        elif spot.get("premium_usd", 0) < -50:
            etf_score -= 1; etf_reasons.append(f"Coinbase discount ${spot['premium_usd']:.0f} spot selling")
        fc = get_funding_cascade(funding, oi_chg, price_chg_5)
        score = 0.0; reasons = []
        hunter_wait = False; wait_reason = ""
        if liq["dominant"] == "HUNT_LONGS_FIRST":
            score -= 1.5; reasons.append(f"Liq: Longs ${liq['long_liq']:,.0f} > Shorts ${liq['short_liq']:,.0f} -> hunters sweep DOWN first")
            if liq["total"] > 2000000:
                hunter_wait = True; wait_reason = "Long liq pool big, wait sweep down before LONG"
        elif liq["dominant"] == "HUNT_SHORTS_FIRST":
            score += 1.5; reasons.append(f"Liq: Shorts ${liq['short_liq']:,.0f} > Longs ${liq['long_liq']:,.0f} -> hunters sweep UP first")
            if liq["total"] > 2000000:
                hunter_wait = True; wait_reason = "Short liq pool big, wait sweep up before SHORT"
        if fc["risk"] == "CASCADE_DOWN":
            score -= 2; reasons.append(f"Funding cascade DOWN: {fc['reason']}")
            hunter_wait = True; wait_reason = wait_reason or "Funding cascade DOWN, no LONG"
        elif fc["risk"] == "CASCADE_UP":
            score += 2; reasons.append(f"Funding cascade UP: {fc['reason']}")
            hunter_wait = True; wait_reason = wait_reason or "Funding cascade UP, no SHORT"
        if obc["cluster_bias"] == "BID_WALL_STRONG":
            score += 1; reasons.append(f"OB: Bid wall ${obc['bid_wall_usd']:,.0f} @ ${obc['bid_wall_price']:,.0f} support")
        elif obc["cluster_bias"] == "ASK_WALL_STRONG":
            score -= 1; reasons.append(f"OB: Ask wall ${obc['ask_wall_usd']:,.0f} @ ${obc['ask_wall_price']:,.0f} resistance")
        if cvd["aggressive"] == "BUY" and cvd["buy_pct"] > 60:
            score += 1; reasons.append(f"CVD live BUY {cvd['buy_pct']}% aggressive buyers")
        elif cvd["aggressive"] == "SELL" and cvd["buy_pct"] < 40:
            score -= 1; reasons.append(f"CVD live SELL {cvd['buy_pct']}% aggressive sellers")
        if spot["bias"] == "SPOT_BUYING":
            score += 1; reasons.append(f"Spot premium +${spot['premium_usd']:.0f} US spot buying")
        elif spot["bias"] == "SPOT_SELLING":
            score -= 1; reasons.append(f"Spot premium ${spot['premium_usd']:.0f} US spot selling")
        if etf_score > 0:
            score += 0.5
        if oi_chg > 0.1 and price_chg_5 > 0:
            score += 0.5; reasons.append("OI up + price up = new longs")
        elif oi_chg > 0.1 and price_chg_5 < 0:
            score -= 0.5; reasons.append("OI up + price down = new shorts")
        elif oi_chg < -0.1 and price_chg_5 > 0:
            score += 0.5; reasons.append("OI down + price up = shorts closing / squeeze")
        elif oi_chg < -0.1 and price_chg_5 < 0:
            score -= 0.5; reasons.append("OI down + price down = longs closing")
        hunter_bias = "LONG" if score >= 1.5 else "SHORT" if score <= -1.5 else "NEUTRAL"
        return {"hunter_score": round(score, 2), "hunter_bias": hunter_bias,
                "hunter_wait": hunter_wait, "wait_reason": wait_reason, "reasons": reasons,
                "liq": liq, "ob_clusters": obc, "cvd_live": cvd, "spot": spot,
                "etf": {"score": etf_score, "reasons": etf_reasons, "spot_premium": spot.get("premium_usd", 0)},
                "funding_cascade": fc, "oi": oi}
    except Exception as e:
        return {"hunter_score": 0.0, "hunter_bias": "NEUTRAL", "hunter_wait": False, "wait_reason": "",
                "reasons": [f"Hunter error {e}"], "liq": {}, "ob_clusters": {}, "cvd_live": {}, "spot": spot, "etf": {}, "funding_cascade": {}, "oi": oi}

# ------------------------------------------------------------
# 6. ASIA RANGE + SWEEP
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

def get_sweep(price, k15, k1, liq_clusters=None):
    a_low, a_high = get_asia_range(k15)
    if liq_clusters:
        ll = liq_clusters.get("long_liq", 0); sl = liq_clusters.get("short_liq", 0); src = liq_clusters.get("src", "LIVE-FAIL")
    else:
        c = get_liq_clusters(price, k1)
        ll = c["long_liq"]; sl = c["short_liq"]; src = c["src"]
    hunt = "NEUTRAL"
    if a_low and a_high and k1:
        last = k1[-1]
        if last["low"] < a_low and last["close"] > a_low and ll > sl:
            hunt = "LONG"
        elif last["high"] > a_high and last["close"] < a_high and sl > ll:
            hunt = "SHORT"
    return hunt, a_low, a_high, ll, sl, src

# ------------------------------------------------------------
# 7. NEWS / MACRO BRAIN
# ------------------------------------------------------------
def get_news(k1=None):
    if k1 is None:
        k1 = get_klines("1", 15)
    if len(k1) >= 15:
        mv = (k1[-1]["close"]-k1[0]["close"])/k1[0]["close"]*100
        if abs(mv) >= 0.8:
            return True, f"VOL SPIKE {mv:.2f}% 15m"
    return False, ""

def get_macro_brain(price, k1, k15, funding=0.0):
    try:
        dxy_p, dxy_d, dxy_1h = yahoo_price_1h("DX-Y.NYB")
        jpy_p, jpy_d, jpy_1h = yahoo_price_1h("USDJPY=X")
        tnx_p, tnx_d, tnx_1h = yahoo_price_1h("^TNX")
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

# ------------------------------------------------------------
# 8. MASTER - get_signal - GOLD FIXED, NO DUPLICATE VOTES
# ------------------------------------------------------------
_last_signal = {"time": 0, "data": None}

def _macro_vote(bias):
    # Single helper, replaces 3 duplicate if-blocks before
    if bias == "LONG": return 1, 0
    if bias == "SHORT": return 0, 1
    return 0, 0

def _ob_vote(obc):
    # Single helper, replaces 2 duplicate buy_pressure blocks before
    bp = obc.get("buy_pressure", 50)
    if obc.get("cluster_bias") == "BID_WALL_STRONG": return 1, 0, "OB Cluster Bid Wall LONG"
    if obc.get("cluster_bias") == "ASK_WALL_STRONG": return 0, 1, "OB Cluster Ask Wall SHORT"
    if bp > 55: return 1, 0, "Orderbook bids LONG"
    if bp < 45: return 0, 1, "Orderbook asks SHORT"
    return 0, 0, ""

def get_signal(price, atr=None, candles=None):
    global _last_signal
    if _last_signal["data"] is not None and (time.time() - _last_signal["time"]) < 10:
        cached = dict(_last_signal["data"])
        cached["price"] = price
        return cached
    try:
        if not price or price == 0:
            price, _ = get_price_live()
            if price == 0:
                return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False, "price": 0, "hunter_score": 0, "hunter_bias": "NEUTRAL", "hunter_wait": False}
        k1 = candles if candles and len(candles) >= 5 else get_klines("1", 20)
        k1_norm = [{"open": float(k.get("open", 0)), "high": float(k.get("high", 0)), "low": float(k.get("low", 0)), "close": float(k.get("close", 0)), "volume": float(k.get("volume", 1)), "time": int(k.get("time", 0))} for k in k1]
        k15 = get_klines("15", 200)
        world = get_world()
        funding, _ = get_funding()
        spot = get_spot_premium()
        oi = get_open_interest()
        price_chg_5 = (k1_norm[-1]["close"]-k1_norm[-6]["close"])/k1_norm[-6]["close"]*100 if len(k1_norm) >= 6 and k1_norm[-6]["close"] else 0
        macro_brain = get_macro_brain(price, k1_norm, k15, funding)
        hunter = get_hunter_live(price, k1_norm, funding, spot, oi, oi.get("chg_5m", 0), price_chg_5)
        hunt, a_low, a_high, ll, sl, liq_src = get_sweep(price, k15, k1_norm, hunter.get("liq"))
        is_news, news_reason = get_news(k1_norm)
        obc = hunter.get("ob_clusters", {})
        cvd_live = hunter.get("cvd_live", {})
        fc = hunter.get("funding_cascade", {})
        long_votes = 0; short_votes = 0; total_voters = 8; reasons = []
        # Voter 1-4: World
        for key, up_txt, down_txt in [("DXY", "DXY down LONG", "DXY up SHORT"), ("NQ", "NQ up LONG", "NQ down SHORT"), ("SPX", "SPX up LONG", "SPX down SHORT")]:
            v = world.get(key, 0)
            if key == "DXY":
                if v < -0.05: long_votes += 1; reasons.append(up_txt)
                elif v > 0.05: short_votes += 1; reasons.append(down_txt)
            else:
                if v > 0.05: long_votes += 1; reasons.append(up_txt)
                elif v < -0.05: short_votes += 1; reasons.append(down_txt)
        gold = world.get("GOLD", 0)
        if gold > 0.05: long_votes += 1; reasons.append("GOLD up LONG")
        elif gold < -0.05: short_votes += 1; reasons.append("GOLD down SHORT")
        # Voter 5: OI + Price, fallback Macro (once, no duplicate)
        oi_chg = oi.get("chg_5m", 0)
        if oi_chg > 0.1 and price_chg_5 < 0: long_votes += 1; reasons.append("OI up + price down = shorts crowded LONG")
        elif oi_chg > 0.1 and price_chg_5 > 0: long_votes += 1; reasons.append("OI up + price up LONG")
        elif oi_chg < -0.1 and price_chg_5 < 0: short_votes += 1; reasons.append("OI down + price down SHORT")
        else:
            a, b = _macro_vote(macro_brain.get("bias")); long_votes += a; short_votes += b
        # Voter 6: Sweep, fallback Macro (once)
        if hunt == "LONG": long_votes += 1; reasons.append("Sweep LONG")
        elif hunt == "SHORT": short_votes += 1; reasons.append("Sweep SHORT")
        else:
            a, b = _macro_vote(macro_brain.get("bias")); long_votes += a; short_votes += b
        # Voter 7: CVD, fallback OB (once)
        cvd_agg = cvd_live.get("aggressive", "NEUTRAL")
        cvd_buy_pct = cvd_live.get("buy_pct", 50.0)
        if cvd_agg == "BUY": long_votes += 1; reasons.append(f"CVD LIVE BUY {cvd_buy_pct}% LONG")
        elif cvd_agg == "SELL": short_votes += 1; reasons.append(f"CVD LIVE SELL {cvd_buy_pct}% SHORT")
        else:
            a, b, r = _ob_vote(obc); long_votes += a; short_votes += b
            if r: reasons.append(r)
        # Voter 8: OB Cluster (once)
        a, b, r = _ob_vote(obc); long_votes += a; short_votes += b
        if r and r not in reasons: reasons.append(r)
        if long_votes > short_votes: direction = "LONG"; agree = long_votes
        elif short_votes > long_votes: direction = "SHORT"; agree = short_votes
        else: direction = "NONE"; agree = long_votes
        cert = round((agree / total_voters) * 100, 1) if total_voters else 0
        if macro_brain.get("bias") == direction and direction != "NONE":
            cert = min(100, cert + 5)
        hunter_bias = hunter.get("hunter_bias", "NEUTRAL")
        hunter_score = hunter.get("hunter_score", 0)
        hunter_wait = hunter.get("hunter_wait", False)
        if hunter_bias == direction and direction != "NONE":
            cert = min(100, cert + 5); reasons.append(f"Hunter agrees {hunter_bias} +5")
        elif hunter_bias != "NEUTRAL" and hunter_bias != direction and direction != "NONE":
            cert = max(0, cert - 10); reasons.append(f"Hunter disagrees {hunter_bias} vs {direction} -10")
        total_liq = ll + sl
        mins_to_session = get_minutes_to_next_session()
        hunt_soon = False; hunt_cert = 0
        if total_liq > 2000000 and mins_to_session < 30: hunt_soon = True; hunt_cert = 75
        elif total_liq > 5000000: hunt_soon = True; hunt_cert = 85
        if hunter.get("liq", {}).get("total", 0) > 5000000: hunt_soon = True; hunt_cert = max(hunt_cert, 85)
        news_critical = False; news_wait = 0
        if is_news:
            if cert >= 90 and agree >= 7: news_critical = True
            else: news_wait = 300
        pause_long = False; pause_short = False; pause_reason = ""
        if macro_brain.get("alert") == "PAUSE_SHORT":
            pause_short = True; pause_reason = "Macro PAUSE_SHORT DXY/JPY"
        # GOLD FIXED: >1.0% + Hunter confirm, >2% panic only
        if abs(gold) > 1.0 and cert < 85:
            if gold > 1.0 and hunter_bias == "SHORT" and direction == "LONG":
                pause_long = True; pause_reason = f"GOLD +{gold:.3f}% extreme + Hunter SHORT"
            elif gold < -1.0 and hunter_bias == "LONG" and direction == "SHORT":
                pause_short = True; pause_reason = f"GOLD {gold:.3f}% extreme + Hunter LONG"
            elif abs(gold) > 2.0:
                pause_long = True; pause_short = True; pause_reason = f"GOLD {gold:.3f}% panic >2%"
        if hunter_wait:
            if hunter_score < -1.0 and direction == "LONG":
                pause_long = True; pause_reason = hunter.get("wait_reason", "Hunter wait LONG")
            if hunter_score > 1.0 and direction == "SHORT":
                pause_short = True; pause_reason = hunter.get("wait_reason", "Hunter wait SHORT")
        if fc.get("block_long") and direction == "LONG":
            pause_long = True; pause_reason = fc.get("reason", "Funding cascade block LONG")
        if fc.get("block_short") and direction == "SHORT":
            pause_short = True; pause_reason = fc.get("reason", "Funding cascade block SHORT")
        result = {"cert": cert, "direction": direction, "agree": agree,
                  "hunt_soon": hunt_soon, "hunt_cert": hunt_cert, "cvd_buy_pct": cvd_buy_pct,
                  "news_critical": news_critical, "news_wait": news_wait,
                  "pause_long": pause_long, "pause_short": pause_short, "pause_reason": pause_reason,
                  "price": price, "reasons": reasons, "news_reason": news_reason,
                  "macro_bias": macro_brain.get("bias"), "session": get_session(),
                  "liq_long": ll, "liq_short": sl,
                  "hunter_score": hunter_score, "hunter_bias": hunter_bias, "hunter_wait": hunter_wait,
                  "hunter_reasons": hunter.get("reasons", []), "hunter_wait_reason": hunter.get("wait_reason", ""),
                  "liq_clusters": hunter.get("liq", {}), "ob_clusters": obc, "cvd_live": cvd_live,
                  "spot_premium": spot, "spot_premium_usd": spot.get("premium_usd", 0),
                  "funding_cascade": fc, "etf_proxy": hunter.get("etf", {}), "oi": oi}
        _last_signal = {"time": time.time(), "data": result}
        return result
    except Exception as e:
        print(f"get_signal Error: {e}", flush=True)
        return {"cert": 0, "direction": "NONE", "agree": 0, "hunt_soon": False, "hunt_cert": 0, "cvd_buy_pct": 50, "news_critical": False, "news_wait": 0, "pause_long": False, "pause_short": False, "price": price, "hunter_score": 0, "hunter_bias": "NEUTRAL", "hunter_wait": False}

if __name__ == "__main__":
    price, src = get_price_live()
    sig = get_signal(price, 200, get_klines("1", 20))
    print(f"Price ${price:.0f} [{src}] Signal: {sig['direction']} Cert {sig['cert']}% Hunter {sig['hunter_bias']} {sig['hunter_score']}")
