# ============================================================
# DATA ENGINE V15.1.0 FINAL CLEAN - BRAIN + JSON + HUNTER LIVE
# ONLY FETCH DATA + VOTE + SAVE RECORDS. NO ORDERS. NO TRADING.
# main.py -> get_signal() -> cert/direction/hunt/news/hunter
# main.py -> save_trade() -> trades.json + daily.json
# If one source fails, returns LIVE-FAIL / 0, never crashes.
# SPREAD IS OUT.
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
# 0. JSON RECORD KEEPER
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
        if res == "BE_TP":
            d["be_tp_hits"] += 1
        elif res in ("SL", "STOP_LOSS"):
            d["sl_hits"] += 1
        elif res == "TP":
            d["tp_hits"] += 1
        with open(DAILY_FILE, "w") as f:
            json.dump(daily, f, indent=2)
        print(f"[{_now().strftime('%H:%M:%S')}] 💾 Saved | {day} PNL ${d['total_pnl']:.2f} | Trades {d['trades']}", flush=True)
        return daily
    except Exception as e:
        print(f"JSON Save Error: {e}", flush=True)
        return {}

def get_daily_summary(day=None):
    if day is None:
        day = _now().strftime("%Y-%m-%d")
    try:
        with open(DAILY_FILE, "r") as f:
            daily = json.load(f)
        return daily.get(day, {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "be_tp_hits": 0, "sl_hits": 0, "tp_hits": 0})
    except:
        return {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "be_tp_hits": 0, "sl_hits": 0, "tp_hits": 0}

# ------------------------------------------------------------
# 1. PRICE + KLINES
# ------------------------------------------------------------
def get_price_live():
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

def calc_atr_from_klines(klines, period=14):
    if not klines or len(klines) < period + 1:
        return 200.0
    trs = []
    for i in range(1, len(klines)):
        c, p = klines[i], klines[i-1]
        trs.append(max(c["high"]-c["low"], abs(c["high"]-p["close"]), abs(c["low"]-p["close"])))
    return sum(trs[-period:]) / period

# ------------------------------------------------------------
# 2. YAHOO - WORLD MARKETS
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
# 3. FUNDING, FEAR, DOMINANCE
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
    return {"btc": 0.0, "usdt": 0.0, "eth": 0.0, "src": "LIVE-FAIL"}

# ------------------------------------------------------------
# 4. OPEN INTEREST
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

# ------------------------------------------------------------
# 5. HUNTER LIVE - SINGLE SOURCE FOR LIQ / OB / CVD / SPOT / FUNDING CASCADE
# ------------------------------------------------------------
def get_liq_clusters(price):
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
    total = long_liq + short_liq
    if total > 0:
        if long_liq > short_liq * 1.5:
            dominant = "HUNT_LONGS_FIRST"; hunt_dir = "DOWN_FIRST"
        elif short_liq > long_liq * 1.5:
            dominant = "HUNT_SHORTS_FIRST"; hunt_dir = "UP_FIRST"
        else:
            dominant = "BALANCED"; hunt_dir = "NONE"
        imb = round((long_liq - short_liq) / total * 100, 1)
    else:
        dominant = "UNKNOWN"; hunt_dir = "NONE"; imb = 0.0
    return {"long_liq": round(long_liq, 0), "short_liq": round(short_liq, 0), "total": round(total, 0),
            "dominant": dominant, "hunt_dir": hunt_dir, "imbalance_pct": imb, "src": src}

def get_ob_clusters(price):
    try:
        j = _safe_get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=50")
        if j:
            bids = j["result"]["b"]; asks = j["result"]["a"]
            biggest_bid = max(bids, key=lambda x: float(x[1])*float(x[0])) if bids else [0, 0]
            biggest_ask = max(asks, key=lambda x: float(x[1])*float(x[0])) if asks else [0, 0]
            bid_wall_price = float(biggest_bid[0]); bid_wall_usd = float(biggest_bid[1])*bid_wall_price
            ask_wall_price = float(biggest_ask[0]); ask_wall_usd = float(biggest_ask[1])*ask_wall_price
            bid_vol = sum(float(x[1])*float(x[0]) for x in bids)
            ask_vol = sum(float(x[1])*float(x[0]) for x in asks)
            total = bid_vol + ask_vol
            buy_pressure = (bid_vol/total*100) if total else 50.0
            if bid_wall_usd > ask_wall_usd * 1.8:
                cluster_bias = "BID_WALL_STRONG"
            elif ask_wall_usd > bid_wall_usd * 1.8:
                cluster_bias = "ASK_WALL_STRONG"
            else:
                cluster_bias = "BALANCED"
            return {"bid_wall_price": bid_wall_price, "bid_wall_usd": round(bid_wall_usd, 0),
                    "ask_wall_price": ask_wall_price, "ask_wall_usd": round(ask_wall_usd, 0),
                    "bid_vol": round(bid_vol, 0), "ask_vol": round(ask_vol, 0),
                    "buy_pressure": round(buy_pressure, 1), "cluster_bias": cluster_bias, "src": "Bybit-LIVE"}
    except: pass
    return {"bid_wall_price": 0, "bid_wall_usd": 0, "ask_wall_price": 0, "ask_wall_usd": 0,
            "bid_vol": 0, "ask_vol": 0, "buy_pressure": 50.0, "cluster_bias": "UNKNOWN", "src": "LIVE-FAIL"}

def get_cvd_live():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=200")
        if j:
            lst = j["result"]["list"]
            buy_vol = 0.0; sell_vol = 0.0
            for x in lst:
                try:
                    sz = float(x.get("size", 0))
                    if x.get("side") == "Buy": buy_vol += sz
                    elif x.get("side") == "Sell": sell_vol += sz
                except: pass
            total = buy_vol + sell_vol
            if total > 0:
                buy_pct = buy_vol/total*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3),
                        "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "Bybit-Trades-LIVE"}
    except: pass
    try:
        j = _safe_get("https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=200")
        if isinstance(j, list) and len(j) > 0:
            buy_vol = 0.0; sell_vol = 0.0
            for x in j:
                sz = float(x.get("qty", 0))
                if x.get("isBuyerMaker"): sell_vol += sz
                else: buy_vol += sz
            total = buy_vol + sell_vol
            if total > 0:
                buy_pct = buy_vol/total*100
                agg = "BUY" if buy_pct > 55 else "SELL" if buy_pct < 45 else "NEUTRAL"
                return {"cvd": round(buy_vol-sell_vol, 3), "buy_vol": round(buy_vol, 3), "sell_vol": round(sell_vol, 3),
                        "buy_pct": round(buy_pct, 1), "aggressive": agg, "src": "Binance-Trades-LIVE"}
    except: pass
    return {"cvd": 0.0, "buy_vol": 0, "sell_vol": 0, "buy_pct": 50.0, "aggressive": "NEUTRAL", "src": "LIVE-FAIL"}

def get_spot_premium():
    try:
        cb = _safe_get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        bn = _safe_get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
        if cb and bn:
            cb_p = float(cb["price"]); bn_p = float(bn["price"])
            prem = cb_p - bn_p
            prem_pct = prem / bn_p * 100 if bn_p else 0
            bias = "SPOT_BUYING" if prem > 50 else "SPOT_SELLING" if prem < -50 else "NEUTRAL"
            return {"coinbase": cb_p, "binance": bn_p, "premium_usd": round(prem, 1),
                    "premium_pct": round(prem_pct, 4), "bias": bias, "src": "Coinbase+Binance-LIVE"}
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
    # FIXED: ETF proxy from spot ONLY, no extra CoinGecko call
    try:
        liq = get_liq_clusters(price)
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
# 6. ASIA RANGE + SWEEP + HUNT
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
        c = get_liq_clusters(price)
        ll = c["long_liq"]; sl = c["short_liq"]; src = c["src"]
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
# 7. NEWS / VOL SPIKE + MACRO BRAIN
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
# 8. MASTER - get_all_data + get_signal
# ------------------------------------------------------------
def get_all_data():
    price, psrc = get_price_live()
    k1 = get_klines("1", 20)
    k15 = get_klines("15", 200)
    world = get_world()
    funding, funding_src = get_funding()
    spot = get_spot_premium()
    oi = get_open_interest()
    price_chg_5 = (k1[-1]["close"]-k1[-6]["close"])/k1[-6]["close"]*100 if len(k1) >= 6 and k1[-6]["close"] else 0
    macro_brain = get_macro_brain(price, k1, k15, funding)
    hunter = get_hunter_live(price, k1, funding, spot, oi, oi.get("chg_5m", 0), price_chg_5)
    hunt, a_low, a_high, ll, sl, liq_src = get_sweep(price, k15, k1, hunter.get("liq"))
    is_news, news_reason = get_news(k1)
    fng, fng_txt, fng_src = get_fear()
    dom = get_dominance()
    return {"price": price, "price_src": psrc, "k1": k1, "k15": k15, "world": world,
            "macro_brain": macro_brain, "hunt": hunt, "asia_low": a_low, "asia_high": a_high,
            "liq_long": ll, "liq_short": sl, "liq_src": liq_src,
            "is_news": is_news, "news_reason": news_reason,
            "funding": funding, "funding_src": funding_src,
            "fear": fng, "fear_txt": fng_txt, "fear_src": fng_src, "dominance": dom,
            "oi": oi, "hunter": hunter, "spot_premium": spot,
            "liq_clusters": hunter.get("liq", {}), "ob_clusters": hunter.get("ob_clusters", {}),
            "cvd_live": hunter.get("cvd_live", {}), "funding_cascade": hunter.get("funding_cascade", {}),
            "session": get_session(), "mins_to_next_session": get_minutes_to_next_session(),
            "rsi_15m": calc_rsi(k15, 14) if k15 else 50.0, "timestamp": _now().isoformat()}

_last_signal = {"time": 0, "data": None}

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
        dxy = world.get("DXY", 0)
        if dxy < -0.05: long_votes += 1; reasons.append("DXY down LONG")
        elif dxy > 0.05: short_votes += 1; reasons.append("DXY up SHORT")
        nq = world.get("NQ", 0)
        if nq > 0.05: long_votes += 1; reasons.append("NQ up LONG")
        elif nq < -0.05: short_votes += 1; reasons.append("NQ down SHORT")
        spx = world.get("SPX", 0)
        if spx > 0.05: long_votes += 1; reasons.append("SPX up LONG")
        elif spx < -0.05: short_votes += 1; reasons.append("SPX down SHORT")
        gold = world.get("GOLD", 0)
        if gold > 0.05: long_votes += 1; reasons.append("GOLD up LONG")
        elif gold < -0.05: short_votes += 1; reasons.append("GOLD down SHORT")
        oi_chg = oi.get("chg_5m", 0)
        if oi_chg > 0.1 and price_chg_5 < 0: long_votes += 1; reasons.append("OI up + price down = shorts crowded LONG")
        elif oi_chg > 0.1 and price_chg_5 > 0: long_votes += 1; reasons.append("OI up + price up LONG")
        elif oi_chg < -0.1 and price_chg_5 < 0: short_votes += 1; reasons.append("OI down + price down SHORT")
        else:
            if macro_brain.get("bias") == "LONG": long_votes += 1
            elif macro_brain.get("bias") == "SHORT": short_votes += 1
        if hunt == "LONG": long_votes += 1; reasons.append("Sweep LONG")
        elif hunt == "SHORT": short_votes += 1; reasons.append("Sweep SHORT")
        else:
            if macro_brain.get("bias") == "LONG": long_votes += 1
            elif macro_brain.get("bias") == "SHORT": short_votes += 1
        cvd_agg = cvd_live.get("aggressive", "NEUTRAL")
        cvd_buy_pct = cvd_live.get("buy_pct", 50.0)
        if cvd_agg == "BUY": long_votes += 1; reasons.append(f"CVD LIVE BUY {cvd_buy_pct}% LONG")
        elif cvd_agg == "SELL": short_votes += 1; reasons.append(f"CVD LIVE SELL {cvd_buy_pct}% SHORT")
        else:
            if obc.get("buy_pressure", 50) > 55: long_votes += 1
            elif obc.get("buy_pressure", 50) < 45: short_votes += 1
        if obc.get("cluster_bias") == "BID_WALL_STRONG": long_votes += 1; reasons.append("OB Cluster Bid Wall LONG")
        elif obc.get("cluster_bias") == "ASK_WALL_STRONG": short_votes += 1; reasons.append("OB Cluster Ask Wall SHORT")
        else:
            if obc.get("buy_pressure", 50) > 55: long_votes += 1; reasons.append("Orderbook bids LONG")
            elif obc.get("buy_pressure", 50) < 45: short_votes += 1; reasons.append("Orderbook asks SHORT")
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
        if abs(gold) > 0.12 and cert < 85:
            pause_long = True; pause_short = True; pause_reason = f"GOLD {gold:.3f}% extreme"
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

def get_votes(price, atr=None, candles=None):
    return get_signal(price, atr, candles)

if __name__ == "__main__":
    d = get_all_data()
    print(f"Price ${d['price']:.0f} [{d['price_src']}] Session {d['session']} Hunt {d['hunt']}")
    print(f"Macro {d['macro_brain']['bias']} Score {d['macro_brain']['score']}")
    print(f"Liq Long ${d['liq_long']:,.0f} Short ${d['liq_short']:,.0f} [{d['liq_src']}]")
    print(f"OI {d['oi']} Hunter {d['hunter']['hunter_bias']} {d['hunter']['hunter_score']} Wait {d['hunter']['hunter_wait']}")
    print(f"Fear {d['fear']} Funding {d['funding']:.4f}% Dom BTC {d['dominance']['btc']}%")
    sig = get_signal(d['price'], 200, d['k1'])
    print(f"Signal: {sig['direction']} Cert {sig['cert']}% Agree {sig['agree']} Hunter {sig['hunter_bias']} {sig['hunter_score']}")
    print(f"Today summary: {get_daily_summary()}")
