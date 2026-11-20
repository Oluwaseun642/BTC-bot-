# ============================================================
# DATA ENGINE V15.9 - HUNTER VETO POWER / HUNT RIDE
# BE = CLOSE: Normal $800, Hunt $600 | TP Backup $1200
# News = BOOSTER ONLY, NEVER VETO / NEVER BLOCK
# Hunter = RIDE, NO BLOCK - Hunt Ride -> Hunt Done -> Normal
# KEEP: GOLD Boss Booster, Spread Booster, Dominance, Flip
# No duplicates, No dead code, Pure Live Worldwide Checks
# ============================================================
import requests, time, json, re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

def _now(): return datetime.now(timezone.utc)

def _safe_get(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        txt = r.text.strip() if r.text else ""
        if not txt: return None
        try: return r.json()
        except: return txt
    except Exception: return None

def _safe_get_text(url, timeout=5):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        return r.text if r.text else ""
    except Exception: return ""

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
        if day not in daily: daily[day] = {"trades":0,"wins":0,"losses":0,"total_pnl":0.0,"be_tp_hits":0,"sl_hits":0,"tp_hits":0,"hunt_rides":0,"first_aid_hits":0}
        d = daily[day]; d["trades"] += 1
        d["total_pnl"] = round(d["total_pnl"] + float(trade.get("net_pnl",0)), 2)
        if float(trade.get("net_pnl",0)) > 0: d["wins"] += 1
        else: d["losses"] += 1
        res = str(trade.get("result","")).upper()
        if res in ("BE","BE_TP","BE_CLOSE"): d["be_tp_hits"] += 1
        elif res in ("SL","STOP_LOSS"): d["sl_hits"] += 1
        elif res == "TP": d["tp_hits"] += 1
        if str(trade.get("mode","")).upper() == "HUNT_RIDE": d["hunt_rides"] += 1
        if str(trade.get("result","")).upper() == "FIRST_AID": d["first_aid_hits"] += 1
        with open(DAILY_FILE, "w") as f: json.dump(daily, f, indent=2)
        print(f"[{_now().strftime('%H:%M:%S')}] Saved | {day} PNL ${d['total_pnl']:.2f} | Trades {d['trades']}", flush=True)
        return daily
    except Exception as e: print(f"JSON Save Error: {e}", flush=True); return {}

# ---------- PRICE ----------
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
            return [{"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"time":int(x[0])} for x in kl]
    except: pass
    try:
        bi = {"1":"1m","5":"5m","15":"15m","60":"1h"}.get(interval,"1m")
        j = _safe_get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={bi}&limit={limit}")
        if isinstance(j, list):
            return [{"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"time":int(x[0])} for x in j]
    except: pass
    try:
        bar = {"1":"1m","5":"5m","15":"15m","60":"1H"}.get(interval,"1m")
        j = _safe_get(f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT-SWAP&bar={bar}&limit={limit}")
        if j and j.get("data"):
            kl = list(reversed(j["data"]))
            return [{"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"time":int(x[0])} for x in kl]
    except: pass
    return []

def calc_rsi(klines, period=14):
    if not klines or len(klines) < period+1: return 50.0
    closes = [k["close"] for k in klines]
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i]-closes[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag = sum(gains[-period:])/period; al = sum(losses[-period:])/period
    if al == 0: return 100.0
    return round(100-(100/(1+ag/al)),1)

def yahoo_chg(sym):
    try:
        for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
            j = _safe_get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=1m")
            if j:
                meta = j["chart"]["result"][0]["meta"]
                price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0)
                prev = float(meta.get("previousClose") or price)
                if price and prev and price != prev:
                    return round((price-prev)/prev*100,3), price, prev
    except: pass
    try:
        stooq = {"GC=F":"gc.f.us","DX-Y.NYB":"dx.f.us","CL=F":"cl.f.us"}.get(sym)
        if stooq:
            j = _safe_get(f"https://stooq.com/q/l/?s={stooq}&f=sd2t2ohlcv&h&e=json")
            if j and j.get("symbols"):
                d = j["symbols"][0]; price = float(d.get("close",0)); prev = float(d.get("open",0))
                if price and prev: return round((price-prev)/prev*100,3), price, prev
    except: pass
    return None, None, None

def yahoo_price_1h(sym):
    try:
        for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
            j = _safe_get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=5m")
            if j:
                res = j["chart"]["result"][0]
                closes = [c for c in res["indicators"]["quote"][0].get("close",[]) if c is not None]
                if closes:
                    cur = float(closes[-1]); prev = float(res["meta"].get("previousClose") or closes[0])
                    chg_day = (cur-prev)/prev*100 if prev else 0
                    chg_1h = (cur-closes[-13])/closes[-13]*100 if len(closes)>=13 and closes[-13] else 0
                    return cur, chg_day, chg_1h
    except: pass
    return None, None, None

_world_cache = {"time":0,"data":{}}
def get_world():
    if time.time()-_world_cache["time"] < 60 and _world_cache["data"]: return _world_cache["data"]
    w = {}
    for name, sym in [("NIKKEI","^N225"),("HANG_SENG","^HSI"),("FTSE","^FTSE"),("DAX","^GDAXI"),("NQ","NQ=F"),("SPX","ES=F"),("GOLD","GC=F"),("DXY","DX-Y.NYB"),("US10Y","^TNX"),("USDJPY","USDJPY=X"),("OIL","CL=F"),("VIX","^VIX")]:
        chg,_,_ = yahoo_chg(sym); w[name] = chg if chg is not None else 0.0
    _world_cache["time"]=time.time(); _world_cache["data"]=w; return w

def get_session():
    h = _now().hour
    if 0 <= h < 7: return "ASIA"
    elif 7 <= h < 13: return "LONDON"
    elif 13 <= h < 21: return "NEW_YORK"
    else: return "LATE_NY"

def get_hunt_window():
    mins = _now().hour*60+_now().minute
    if mins >= 23*60+30 or mins <= 0*60+15: return True, "ASIA"
    if 6*60+30 <= mins <= 7*60+15: return True, "LONDON"
    if 12*60+30 <= mins <= 13*60+15: return True, "NEW_YORK"
    return False, get_session()

def get_funding():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1")
        if j and j["result"].get("list"): return float(j["result"]["list"][0].get("fundingRate",0))*100, "Bybit-LIVE"
    except: pass
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1")
        if j: return float(j[0].get("fundingRate",0))*100, "Binance-LIVE"
    except: pass
    try:
        j = _safe_get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
        if j and j.get("data"): return float(j["data"][0].get("fundingRate",0))*100, "OKX-LIVE"
    except: pass
    return 0.0, "LIVE-FAIL"

def get_fear():
    try:
        j = _safe_get("https://api.alternative.me/fng/?limit=1")
        if j: return int(j["data"][0]["value"]), j["data"][0].get("value_classification","")
    except: pass
    return 50, "Neutral"

def get_open_interest():
    try:
        j = _safe_get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=6")
        if j:
            lst = j["result"]["list"]
            if len(lst) >= 2:
                first=float(lst[0]["openInterest"]); last=float(lst[-1]["openInterest"])
                chg=(last-first)/first*100 if first else 0
                return {"oi":last,"chg_5m":round(chg,3),"src":"Bybit-LIVE"}
    except: pass
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
        if j: return {"oi":float(j["openInterest"]),"chg_5m":0.0,"src":"Binance-LIVE"}
    except: pass
    return {"oi":0.0,"chg_5m":0.0,"src":"LIVE-FAIL"}

def get_liq_clusters(price, k1=None):
    if not price: return {"long_liq":0,"short_liq":0,"total":0,"dominant":"UNKNOWN","hunt_dir":"NONE","imbalance_pct":0.0,"src":"NO-PRICE"}
    long_liq=0.0; short_liq=0.0; src="LIVE-FAIL"
    try:
        j = _safe_get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100")
        if isinstance(j,list) and len(j)>0:
            for x in j:
                try:
                    sz=float(x.get("origQty",0))*float(x.get("price",price))
                    if x.get("side")=="SELL": long_liq+=sz
                    elif x.get("side")=="BUY": short_liq+=sz
                except: pass
            if long_liq+short_liq>0: src="Binance-LIVE"
    except: pass
    if src=="LIVE-FAIL":
        try:
            j = _safe_get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50")
            if j:
                lst=j.get("result",{}).get("list",[])
                for x in lst:
                    try:
                        sz=float(x.get("size",0))*float(x.get("price",price))
                        if x.get("side")=="Sell": long_liq+=sz
                        elif x.get("side")=="Buy": short_liq+=sz
                    except: pass
                if long_liq+short_liq>0: src="Bybit-LIVE"
        except: pass
    if src=="LIVE-FAIL" and k1 and len(k1)>=20:
        total_range=sum(abs(k["high"]-k["low"]) for k in k1[-20:])
        est_total=max(total_range*price*0.05, 500000.0)
        pc=(k1[-1]["close"]-k1[-20]["close"])/k1[-20]["close"]*100 if k1[-20]["close"] else 0
        if pc<0: long_liq, short_liq = est_total*0.65, est_total*0.35
        elif pc>0: long_liq, short_liq = est_total*0.35, est_total*0.65
        else: long_liq, short_liq = est_total*0.5, est_total*0.5
        src="Proxy-Kline"
    total=long_liq+short_liq
    if total>0:
        if long_liq>short_liq*1.5: dominant="HUNT_LONGS_FIRST"; hunt_dir="DOWN_FIRST"
        elif short_liq>long_liq*1.5: dominant="HUNT_SHORTS_FIRST"; hunt_dir="UP_FIRST"
        else: dominant="BALANCED"; hunt_dir="NONE"
        imb=round((long_liq-short_liq)/total*100,1)
    else: dominant="UNKNOWN"; hunt_dir="NONE"; imb=0.0
    return {"long_liq":round(long_liq,0),"short_liq":round(short_liq,0),"total":round(total,0),"dominant":dominant,"hunt_dir":hunt_dir,"imbalance_pct":imb,"src":src}

def _parse_ob(bids, asks, src):
    biggest_bid=max(bids, key=lambda x: float(x[1])*float(x[0])) if bids else [0,0]
    biggest_ask=max(asks, key=lambda x: float(x[1])*float(x[0])) if asks else [0,0]
    bid_wall_price=float(biggest_bid[0]); bid_wall_usd=float(biggest_bid[1])*bid_wall_price
    ask_wall_price=float(biggest_ask[0]); ask_wall_usd=float(biggest_ask[1])*ask_wall_price
    bid_vol=sum(float(x[1])*float(x[0]) for x in bids); ask_vol=sum(float(x[1])*float(x[0]) for x in asks)
    total=bid_vol+ask_vol; buy_pressure=(bid_vol/total*100) if total else 50.0
    if bid_wall_usd>ask_wall_usd*1.8: cluster_bias="BID_WALL_STRONG"
    elif ask_wall_usd>bid_wall_usd*1.8: cluster_bias="ASK_WALL_STRONG"
    else: cluster_bias="BALANCED"
    return {"bid_wall_price":bid_wall_price,"bid_wall_usd":round(bid_wall_usd,0),"ask_wall_price":ask_wall_price,"ask_wall_usd":round(ask_wall_usd,0),"bid_vol":round(bid_vol,0),"ask_vol":round(ask_vol,0),"buy_pressure":round(buy_pressure,1),"cluster_bias":cluster_bias,"src":src}

def get_ob_clusters(price):
    try:
        j=_safe_get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=50")
        if j: return _parse_ob(j["result"]["b"], j["result"]["a"], "Bybit-LIVE")
    except: pass
    try:
        j=_safe_get("https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=50")
        if j: return _parse_ob(j["bids"], j["asks"], "Binance-LIVE")
    except: pass
    try:
        j=_safe_get("https://www.okx.com/api/v5/market/books?instId=BTC-USDT-SWAP&sz=50")
        if j and j.get("data"):
            d=j["data"][0]; return _parse_ob(d["bids"], d["asks"], "OKX-LIVE")
    except: pass
    return {"bid_wall_price":0,"bid_wall_usd":0,"ask_wall_price":0,"ask_wall_usd":0,"bid_vol":0,"ask_vol":0,"buy_pressure":50.0,"cluster_bias":"UNKNOWN","src":"LIVE-FAIL"}

def get_cvd_live():
    try:
        j=_safe_get("https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=200")
        if j:
            lst=j["result"]["list"]
            buy_vol=sum(float(x.get("size",0)) for x in lst if x.get("side")=="Buy")
            sell_vol=sum(float(x.get("size",0)) for x in lst if x.get("side")=="Sell")
            if buy_vol+sell_vol>0:
                buy_pct=buy_vol/(buy_vol+sell_vol)*100; agg="BUY" if buy_pct>55 else "SELL" if buy_pct<45 else "NEUTRAL"
                return {"cvd":round(buy_vol-sell_vol,3),"buy_vol":round(buy_vol,3),"sell_vol":round(sell_vol,3),"buy_pct":round(buy_pct,1),"aggressive":agg,"src":"Bybit-Trades-LIVE"}
    except: pass
    try:
        j=_safe_get("https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=200")
        if isinstance(j,list) and len(j)>0:
            buy_vol=sum(float(x.get("qty",0)) for x in j if not x.get("isBuyerMaker"))
            sell_vol=sum(float(x.get("qty",0)) for x in j if x.get("isBuyerMaker"))
            if buy_vol+sell_vol>0:
                buy_pct=buy_vol/(buy_vol+sell_vol)*100; agg="BUY" if buy_pct>55 else "SELL" if buy_pct<45 else "NEUTRAL"
                return {"cvd":round(buy_vol-sell_vol,3),"buy_vol":round(buy_vol,3),"sell_vol":round(sell_vol,3),"buy_pct":round(buy_pct,1),"aggressive":agg,"src":"Binance-Trades-LIVE"}
    except: pass
    return {"cvd":0.0,"buy_vol":0,"sell_vol":0,"buy_pct":50.0,"aggressive":"NEUTRAL","src":"LIVE-FAIL"}

def get_spot_premium():
    try:
        cb=_safe_get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        if cb:
            cb_p=float(cb["price"])
            for url, name, parse in [("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT","Binance",lambda j: float(j["price"])),("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP","OKX",lambda j: float(j["data"][0]["last"]))]:
                try:
                    j=_safe_get(url)
                    if not j: continue
                    bn_p=parse(j); prem=cb_p-bn_p; bias="SPOT_BUYING" if prem>50 else "SPOT_SELLING" if prem<-50 else "NEUTRAL"
                    return {"coinbase":cb_p,"binance":bn_p,"premium_usd":round(prem,1),"premium_pct":round(prem/bn_p*100,4) if bn_p else 0,"bias":bias,"src":f"Coinbase+{name}-LIVE"}
                except: pass
    except: pass
    return {"coinbase":0,"binance":0,"premium_usd":0,"premium_pct":0,"bias":"UNKNOWN","src":"LIVE-FAIL"}

def get_spread_score(price, spot, funding):
    spot_prem=spot.get("premium_usd",0) if spot else 0; cb_price=spot.get("coinbase",0) if spot else 0
    cb_bybit=(cb_price-price) if cb_price and price else 0
    score=0; reasons=[]
    if spot_prem>=100: score+=2; reasons.append(f"Spot prem +${spot_prem:.0f} +2")
    elif spot_prem>=50: score+=1; reasons.append(f"Spot prem +${spot_prem:.0f} +1")
    elif spot_prem<=-100: score-=2; reasons.append(f"Spot prem ${spot_prem:.0f} -2")
    elif spot_prem<=-50: score-=1; reasons.append(f"Spot prem ${spot_prem:.0f} -1")
    if cb_bybit>=150: score+=2; reasons.append(f"Coinbase-Bybit +${cb_bybit:.0f} +2")
    elif cb_bybit>=80: score+=1; reasons.append(f"Coinbase-Bybit +${cb_bybit:.0f} +1")
    elif cb_bybit<=-150: score-=2; reasons.append(f"Coinbase-Bybit ${cb_bybit:.0f} -2")
    elif cb_bybit<=-80: score-=1; reasons.append(f"Coinbase-Bybit ${cb_bybit:.0f} -1")
    crowded=False
    if funding is not None and funding>0.05 and score>0: score-=1; crowded=True; reasons.append("Funding crowded LONG, spread boost cut -1")
    if funding is not None and funding<-0.03 and score<0: score+=1; crowded=True; reasons.append("Funding crowded SHORT, spread boost cut +1")
    if score>=3: bias="LONG"
    elif score<=-3: bias="SHORT"
    elif score>0: bias="LONG_WEAK"
    elif score<0: bias="SHORT_WEAK"
    else: bias="NEUTRAL"
    return {"score":score,"bias":bias,"spot_premium_usd":round(spot_prem,1),"coinbase":round(cb_price,1),"coinbase_bybit_spread":round(cb_bybit,1),"crowded":crowded,"reasons":reasons}

# ---------- GOLD BOSS (Booster Only, Never Block) ----------
_gold_boss_state={"break_active":False,"resolve_since":0,"break_candles":0,"last_break_ts":0}
def get_gold_5m_series():
    try:
        for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
            j=_safe_get(f"{base}/v8/finance/chart/GC=F?range=1d&interval=5m")
            if j:
                res=j["chart"]["result"][0]; q=res["indicators"]["quote"][0]
                closes=[c for c in q.get("close",[]) if c is not None]; highs=[h for h in q.get("high",[]) if h is not None]; lows=[l for l in q.get("low",[]) if l is not None]
                if len(closes)>=4: return closes, highs, lows
    except: pass
    return [],[],[]

def get_gold_boss(gold_day_chg, btc_chg_15m, funding, oi_chg_5m):
    closes, highs, lows = get_gold_5m_series()
    gold_15m=0.0; gold_1h=0.0; wick_pct=0.0; wick_active=False
    if len(closes)>=4:
        if closes[-4]: gold_15m=round((closes[-1]-closes[-4])/closes[-4]*100,3)
        if len(closes)>=13 and closes[-13]: gold_1h=round((closes[-1]-closes[-13])/closes[-13]*100,3)
    if highs and lows and closes and closes[-1]:
        wick_pct=round((highs[-1]-lows[-1])/closes[-1]*100,3); wick_active=wick_pct>0.5
    is_break=False; divergence=0.0; break_dir="NONE"; break_tier="NONE"
    if gold_15m!=0 and btc_chg_15m!=0:
        if (gold_15m>0 and btc_chg_15m<0) or (gold_15m<0 and btc_chg_15m>0):
            divergence=round(abs(gold_15m-btc_chg_15m),3)
            if divergence<=0.3: break_tier="TIER1_IGNORE"; is_break=False
            elif divergence<=0.8: break_tier="TIER2_HOLD_WATCH"; is_break=True
            else: break_tier="TIER3_BIG_BREAK"; is_break=True
            if is_break: break_dir="BTC_UP_GOLD_DOWN" if btc_chg_15m>0 else "BTC_DOWN_GOLD_UP"
    now_ts=time.time()
    if is_break:
        if not _gold_boss_state["break_active"]: _gold_boss_state["break_active"]=True; _gold_boss_state["break_candles"]=1; _gold_boss_state["last_break_ts"]=now_ts
        elif now_ts-_gold_boss_state["last_break_ts"]>=240: _gold_boss_state["break_candles"]+=1; _gold_boss_state["last_break_ts"]=now_ts
        _gold_boss_state["resolve_since"]=0
    elif _gold_boss_state["break_active"]: _gold_boss_state["break_active"]=False; _gold_boss_state["resolve_since"]=now_ts; _gold_boss_state["break_candles"]=0
    confirm_ok=False; confirm_wait=0
    if not is_break and _gold_boss_state["resolve_since"]>0:
        elapsed=now_ts-_gold_boss_state["resolve_since"]
        if elapsed>=120 and not wick_active: confirm_ok=True
        else: confirm_wait=max(0,int(120-elapsed))
    elif not is_break: confirm_ok=True
    flip_to="NONE"
    if _gold_boss_state["break_candles"]>=3 and is_break: flip_to="LONG" if break_dir=="BTC_UP_GOLD_DOWN" else "SHORT"
    boss_boost=0; boss_dir="NONE"; boss_reasons=[]
    if not is_break:
        if gold_15m<-0.05 and btc_chg_15m<-0.05:
            boss_dir="SHORT"
            if abs(gold_day_chg)>=2.0: boss_boost=15; boss_reasons.append(f"GOLD BOSS SHORT +15% | GOLD day {gold_day_chg:.2f}% + GOLD 15m {gold_15m:.2f}% + BTC 15m {btc_chg_15m:.2f}% aligned")
            elif abs(gold_day_chg)>=1.0: boss_boost=10; boss_reasons.append(f"GOLD BOSS SHORT +10% | GOLD {gold_day_chg:.2f}% aligned")
            else: boss_boost=5; boss_reasons.append(f"GOLD BOSS SHORT +5% | GOLD 15m {gold_15m:.2f}% aligned")
        elif gold_15m>0.05 and btc_chg_15m>0.05:
            boss_dir="LONG"
            if abs(gold_day_chg)>=2.0: boss_boost=15; boss_reasons.append(f"GOLD BOSS LONG +15% | GOLD day {gold_day_chg:.2f}% + GOLD 15m {gold_15m:.2f}% + BTC 15m {btc_chg_15m:.2f}% aligned")
            elif abs(gold_day_chg)>=1.0: boss_boost=10; boss_reasons.append(f"GOLD BOSS LONG +10% | GOLD {gold_day_chg:.2f}% aligned")
            else: boss_boost=5; boss_reasons.append(f"GOLD BOSS LONG +5% | GOLD 15m {gold_15m:.2f}% aligned")
    dom_boost=0; dom_dir="NONE"; dom_reasons=[]
    if gold_day_chg<-1.0 and oi_chg_5m>0.1 and funding is not None and funding>0.02: dom_dir="SHORT"; dom_boost=10; dom_reasons.append(f"DOMINANCE SHORT +10% | GOLD {gold_day_chg:.2f}% + OI +{oi_chg_5m:.2f}% + Funding +{funding:.4f}% = LONG CROWDED")
    elif gold_day_chg>1.0 and oi_chg_5m>0.1 and funding is not None and funding<-0.01: dom_dir="LONG"; dom_boost=10; dom_reasons.append(f"DOMINANCE LONG +10% | GOLD +{gold_day_chg:.2f}% + OI +{oi_chg_5m:.2f}% + Funding {funding:.4f}% = SHORT CROWDED")
    return {"gold_15m":gold_15m,"gold_1h":gold_1h,"gold_day":gold_day_chg,"btc_15m":round(btc_chg_15m,3),"wick_pct":wick_pct,"wick_active":wick_active,"is_break":is_break,"divergence":divergence,"break_dir":break_dir,"break_tier":break_tier,"break_candles":_gold_boss_state["break_candles"],"confirm_ok":confirm_ok,"confirm_wait":confirm_wait,"resolve_since":_gold_boss_state["resolve_since"],"flip_to":flip_to,"boss_boost":boss_boost,"boss_dir":boss_dir,"boss_reasons":boss_reasons,"dom_boost":dom_boost,"dom_dir":dom_dir,"dom_reasons":dom_reasons}

def get_funding_cascade(funding, oi_chg_5m=0.0, price_chg_5m=0.0):
    risk="NONE"; reason=""
    if funding>0.02 and oi_chg_5m>0.1 and price_chg_5m<0: risk="CASCADE_DOWN"; reason=f"Funding +{funding:.4f}% crowded LONG + OI up + price down"
    elif funding>0.05: risk="CASCADE_DOWN"; reason=f"Funding +{funding:.4f}% extreme crowded LONG"
    elif funding<-0.01 and oi_chg_5m>0.1 and price_chg_5m>0: risk="CASCADE_UP"; reason=f"Funding {funding:.4f}% crowded SHORT + OI up + price up"
    elif funding<-0.03: risk="CASCADE_UP"; reason=f"Funding {funding:.4f}% extreme crowded SHORT"
    return {"funding":funding,"risk":risk,"reason":reason,"oi_chg_5m":oi_chg_5m,"price_chg_5m":round(price_chg_5m,3)}

# ---------- V15.9 NEWS ENGINE - 4 TYPES LIVE, BOOSTER ONLY ----------
_news_cache={"time":0,"data":None}
_BEAR_WORDS=["hike","hawkish","outflow","sue","lawsuit","tariff","ban","hack","selloff","sell-off","dump","crash","recession","inflation","probe","fraud","liquidat","bearish","fear","war","sanction","default"]
_BULL_WORDS=["cut","dovish","inflow","approve","approval","etf","adopt","bullish","rally","surge","accumulat","buy","partnership","launch","upgrade","record","boom"]

def _score_headlines(headlines):
    bear=bull=0; reasons=[]
    for h in headlines[:25]:
        t=h.lower()
        b=sum(1 for w in _BEAR_WORDS if w in t); u=sum(1 for w in _BULL_WORDS if w in t)
        if b>u: bear+=1
        elif u>b: bull+=1
    if bear>=4 and bear>bull*2: return -2, f"News bearish {bear} vs bullish {bull}", bear, bull
    if bull>=4 and bull>bear*2: return 2, f"News bullish {bull} vs bearish {bear}", bear, bull
    if bear>bull: return -1, f"News bearish {bear} vs bullish {bull}", bear, bull
    if bull>bear: return 1, f"News bullish {bull} vs bearish {bear}", bear, bull
    return 0, "News neutral", bear, bull

def _fetch_headlines():
    heads=[]
    # Yahoo Finance search - BTC, SPX, DXY, GOLD
    for q in ["bitcoin","BTC","Federal Reserve","ETF","tariff"]:
        try:
            j=_safe_get(f"https://query1.finance.yahoo.com/v1/finance/search?q={q}&newsCount=5")
            if isinstance(j,dict) and j.get("news"):
                for n in j["news"]: heads.append(str(n.get("title","")))
        except: pass
    # CoinDesk RSS
    try:
        txt=_safe_get_text("https://www.coindesk.com/arc/outboundfeeds/rss/", timeout=5)
        if txt:
            root=ET.fromstring(txt)
            for it in root.findall(".//item")[:15]:
                t=it.findtext("title",""); heads.append(t)
    except: pass
    # Binance public news via CoinTelegraph RSS fallback
    try:
        txt=_safe_get_text("https://cointelegraph.com/rss", timeout=5)
        if txt:
            root=ET.fromstring(txt)
            for it in root.findall(".//item")[:15]:
                t=it.findtext("title",""); heads.append(t)
    except: pass
    return [h for h in heads if h][:40]

def get_news_live(world, price_chg_1h=0.0, cvd_aggressive="NEUTRAL", btc_price_move_1h=0.0):
    # Cache 60s - live, no hardcoded date
    if _news_cache["data"] is not None and time.time()-_news_cache["time"] < 60:
        base=dict(_news_cache["data"])
    else:
        heads=_fetch_headlines()
        h_score, h_reason, bear, bull = _score_headlines(heads)
        base={"headline_score":h_score,"headline_reason":h_reason,"bear_count":bear,"bull_count":bull,"headlines":heads[:8]}
        _news_cache["time"]=time.time(); _news_cache["data"]=base
    # Type 4: Market-Data News - numbers, fastest, never lies
    spx=world.get("SPX",0); nq=world.get("NQ",0); dxy=world.get("DXY",0); gold=world.get("GOLD",0); oil=world.get("OIL",0)
    num_score=0; num_reasons=[]
    if spx<=-1.0: num_score-=1; num_reasons.append(f"SPX day {spx:.2f}% = risk-off -1")
    elif spx>=1.0: num_score+=1; num_reasons.append(f"SPX day +{spx:.2f}% = risk-on +1")
    if nq<=-1.5: num_score-=1; num_reasons.append(f"NQ day {nq:.2f}% -1")
    elif nq>=1.5: num_score+=1; num_reasons.append(f"NQ day +{nq:.2f}% +1")
    if dxy>=0.5: num_score-=1; num_reasons.append(f"DXY day +{dxy:.2f}% = BTC headwind -1")
    elif dxy<=-0.5: num_score+=1; num_reasons.append(f"DXY day {dxy:.2f}% = BTC tailwind +1")
    if gold>=1.0 and spx<0: num_score-=1; num_reasons.append(f"GOLD +{gold:.2f}% + SPX down = risk-off -1")
    if oil>=2.0 and spx<0: num_score-=1; num_reasons.append(f"OIL +{oil:.2f}% + SPX down = war/oil shock -1")
    # Fear check: headline must agree with price+CVD, else ignore headline (fake/slow news protection)
    price_agree = (btc_price_move_1h>0 and cvd_aggressive=="BUY") or (btc_price_move_1h<0 and cvd_aggressive=="SELL") or abs(btc_price_move_1h)<0.1
    h_score = base["headline_score"]
    if h_score!=0 and not price_agree:
        h_score_eff=0; h_note="Headline ignored - price/CVD disagree (fake/slow news protection)"
    else:
        h_score_eff=h_score; h_note=base["headline_reason"]
    # Combine: headline + numbers, clamp -2..+2
    total = max(-2, min(2, h_score_eff + (1 if num_score>=2 else -1 if num_score<=-2 else 0)))
    # If numbers strongly disagree with headline, trust numbers
    if num_score>=2 and total<0: total=0
    if num_score<=-2 and total>0: total=0
    if total<0: direction="SHORT"
    elif total>0: direction="LONG"
    else: direction="NEUTRAL"
    return {"score":total,"direction":direction,"headline_score":h_score,"headline_score_eff":h_score_eff,"headline_note":h_note,"numbers_score":num_score,"numbers_reasons":num_reasons,"bear_count":base["bear_count"],"bull_count":base["bull_count"],"headlines":base["headlines"],"src":"Yahoo+CoinDesk+CoinTelegraph+LiveNumbers"}

def news_booster(news, direction, base_cert, price_agree=True):
    # BOOSTER ONLY: Never block, never penalize. Max +10% Cert, only if base >=65%
    if direction=="NONE" or base_cert<65: return 0, "No news boost - base cert <65% or no direction"
    if news.get("direction")==direction and news.get("score",0)!=0:
        return 10, f"NEWS BOOSTER +10% | News {news['direction']} {news['score']} backs {direction} | {news.get('headline_note','')}"
    return 0, "News no boost - disagree or neutral, ignored (no block)"

# ---------- HUNT V15.9 ----------
def get_hunt_certainty(price, liq, obc, cvd, fc, a_low, a_high):
    score=0; reasons=[]; hunt_dir="NONE"; target=0.0
    if liq["dominant"]=="HUNT_LONGS_FIRST": hunt_dir="DOWN_FIRST"; target=a_low if a_low else price-800; score+=2; reasons.append("Liq Longs > Shorts 1.5x +2")
    elif liq["dominant"]=="HUNT_SHORTS_FIRST": hunt_dir="UP_FIRST"; target=a_high if a_high else price+800; score+=2; reasons.append("Liq Shorts > Longs 1.5x +2")
    if liq.get("total",0)>5000000: score+=2; reasons.append(f"Liq total ${liq['total']:,.0f} > $5M +2")
    elif liq.get("total",0)>2000000: score+=1; reasons.append(f"Liq total ${liq['total']:,.0f} > $2M +1")
    if hunt_dir=="DOWN_FIRST" and obc.get("cluster_bias")=="ASK_WALL_STRONG": score+=1; reasons.append("Ask wall + hunt down +1")
    elif hunt_dir=="UP_FIRST" and obc.get("cluster_bias")=="BID_WALL_STRONG": score+=1; reasons.append("Bid wall + hunt up +1")
    if hunt_dir=="DOWN_FIRST" and cvd.get("aggressive")=="SELL": score+=1; reasons.append("CVD SELL + hunt down +1")
    elif hunt_dir=="UP_FIRST" and cvd.get("aggressive")=="BUY": score+=1; reasons.append("CVD BUY + hunt up +1")
    if target:
        dist=abs(price-target)
        if dist<=300: score+=2; reasons.append(f"Price ${dist:.0f} from target +2")
        elif dist<=800: score+=1; reasons.append(f"Price ${dist:.0f} from target +1")
    if hunt_dir=="DOWN_FIRST" and fc.get("risk")=="CASCADE_DOWN": score+=1; reasons.append("Funding cascade DOWN +1")
    elif hunt_dir=="UP_FIRST" and fc.get("risk")=="CASCADE_UP": score+=1; reasons.append("Funding cascade UP +1")
    label="CERTAIN" if score>=6 else "MAYBE" if score>=3 else "NO_HUNT"
    dist=abs(price-target) if target else 9999
    size_label="TOO_SMALL" if dist<300 else "GOOD" if dist<=1200 else "SL_DANGER"
    return {"score":score,"label":label,"hunt_dir":hunt_dir,"target":target,"distance":round(dist,0),"size_label":size_label,"reasons":reasons}

def get_hunt_state(hunt_cert, price, a_low, a_high, k1_norm, world):
    # Sessional vs Normal Day Hunt - live, no hardcoded date
    session=get_session(); hunt_active,_=get_hunt_window()
    is_session_open = hunt_active
    countries_align = (world.get("DXY",0)!=0 and world.get("NQ",0)!=0 and world.get("SPX",0)!=0)
    if is_session_open and countries_align: hunt_type="SESSIONAL"
    else: hunt_type="NORMAL_DAY"
    score=hunt_cert.get("score",0)
    if score>=6: state="CERTAINLY_VITAL"
    elif score>=4: state="COMING"
    elif score>=3: state="MAYBE_LOW"
    else: state="NOT_VITAL"
    # Hunt Done: 2 of 3 - close back inside + score drop + CVD flip / OB wall
    hunt_done=False; done_reasons=[]
    if k1_norm and len(k1_norm)>=2 and a_low and a_high:
        last=k1_norm[-1]
        if hunt_cert.get("hunt_dir")=="UP_FIRST" and last["high"]>a_high and last["close"]<a_high: done_reasons.append("Price wick above Asia High, close back inside")
        if hunt_cert.get("hunt_dir")=="DOWN_FIRST" and last["low"]<a_low and last["close"]>a_low: done_reasons.append("Price wick below Asia Low, close back inside")
    if score<3: done_reasons.append(f"Hunter score drop to {score}/9")
    if len(done_reasons)>=1 and score<3: hunt_done=True
    return {"state":state,"hunt_type":hunt_type,"session":session,"hunt_active":hunt_active,"hunt_done":hunt_done,"done_reasons":done_reasons}

def get_fake_hunt(hunt_cert, price, entry_price, hunt_direction, k1_norm):
    # Fake if: never reach BE $600 AND score drop <3 AND close back inside within 3 candles
    if hunt_direction=="NONE" or entry_price==0: return False, ""
    move = (price-entry_price) if hunt_direction=="LONG" else (entry_price-price)
    if move>=600: return False, "Real hunt - reached BE $600"
    if hunt_cert.get("score",0)<3:
        if k1_norm and len(k1_norm)>=2:
            return True, f"FAKE HUNT: Score drop {hunt_cert.get('score')}/9, move ${move:.0f} < $600 BE, no real hunt"
        return True, f"FAKE HUNT: Score drop {hunt_cert.get('score')}/9"
    return False, ""

def get_first_aid_v159(price, hunt_cert, direction, cert, sweep_done, k1_norm, hunt_ride_open=False, hunt_ride_entry=0):
    # V15.9 First Aid: Hunt Ride open, never reach BE $600, Hunter drop <3, Normal Cert opposite 75%+ -> close Hunt Ride, enter Normal
    if sweep_done: return False, "", "NONE", direction
    if hunt_ride_open:
        hunt_dir=hunt_cert.get("hunt_dir","NONE")
        # Hunt fail: score drop + cert takeover
        if hunt_cert.get("score",0)<3 and cert>=75:
            return True, f"FIRST AID V15.9: Hunt failed score {hunt_cert.get('score')}/9, Cert {cert}% {direction} takeover - close Hunt Ride, enter Normal {direction}", "FIRST_AID_CLOSE_HUNT_ENTER_NORMAL", direction
        # Hunt target broken through without sweep = hunt failed
        target=hunt_cert.get("target",0)
        if target and k1_norm:
            last=k1_norm[-1]
            if hunt_dir=="DOWN_FIRST" and last["close"]<target-200: return True, f"FIRST AID: Price break through hunt target ${target:,.0f} without sweep - HUNT FAILED", "RELEASE_TREND", direction
            if hunt_dir=="UP_FIRST" and last["close"]>target+200: return True, f"FIRST AID: Price break through hunt target ${target:,.0f} without sweep - HUNT FAILED", "RELEASE_TREND", direction
        if target and abs(price-target)>1500: return True, f"FIRST AID: Price run away ${abs(price-target):.0f} from hunt target ${target:,.0f} - HUNT INVALID", "RELEASE_TREND", direction
    # Old first-aid for non-hunt-ride path (kept, no duplicate)
    if hunt_cert.get("label")=="CERTAIN":
        hunt_dir=hunt_cert.get("hunt_dir","NONE"); target=hunt_cert.get("target",0)
        if hunt_dir=="DOWN_FIRST" and direction=="SHORT" and cert>=85: return True, f"FIRST AID: Hunt DOWN to ${target:,.0f} then LONG, but worldwide flip SHORT {cert}% - hunt CANCELLED", "RELEASE_FLIP_SHORT", "SHORT"
        if hunt_dir=="UP_FIRST" and direction=="LONG" and cert>=85: return True, f"FIRST AID: Hunt UP to ${target:,.0f} then SHORT, but worldwide flip LONG {cert}% - hunt CANCELLED", "RELEASE_FLIP_LONG", "LONG"
    return False, "", "NONE", direction

def get_hunter_live(price, k1_norm, funding, spot, oi, oi_chg, price_chg_5, a_low=0, a_high=0, world=None):
    try:
        liq=get_liq_clusters(price, k1_norm); obc=get_ob_clusters(price); cvd=get_cvd_live()
        fc=get_funding_cascade(funding, oi_chg, price_chg_5)
        hunt_cert=get_hunt_certainty(price, liq, obc, cvd, fc, a_low, a_high)
        hunt_active, hunt_session=get_hunt_window()
        score=0.0; reasons=[]
        if liq["dominant"]=="HUNT_LONGS_FIRST": score-=1.5; reasons.append(f"Liq Longs ${liq['long_liq']:,.0f} > Shorts ${liq['short_liq']:,.0f}")
        elif liq["dominant"]=="HUNT_SHORTS_FIRST": score+=1.5; reasons.append(f"Liq Shorts ${liq['short_liq']:,.0f} > Longs ${liq['long_liq']:,.0f}")
        if fc["risk"]=="CASCADE_DOWN": score-=2; reasons.append(f"Funding cascade DOWN: {fc['reason']}")
        elif fc["risk"]=="CASCADE_UP": score+=2; reasons.append(f"Funding cascade UP: {fc['reason']}")
        if obc["cluster_bias"]=="BID_WALL_STRONG": score+=1; reasons.append(f"OB Bid wall ${obc['bid_wall_usd']:,.0f}")
        elif obc["cluster_bias"]=="ASK_WALL_STRONG": score-=1; reasons.append(f"OB Ask wall ${obc['ask_wall_usd']:,.0f}")
        if cvd["aggressive"]=="BUY" and cvd["buy_pct"]>60: score+=1; reasons.append(f"CVD BUY {cvd['buy_pct']}%")
        elif cvd["aggressive"]=="SELL" and cvd["buy_pct"]<40: score-=1; reasons.append(f"CVD SELL {cvd['buy_pct']}%")
        if spot["bias"]=="SPOT_BUYING": score+=1; reasons.append(f"Spot +${spot['premium_usd']:.0f}")
        elif spot["bias"]=="SPOT_SELLING": score-=1; reasons.append(f"Spot ${spot['premium_usd']:.0f}")
        if oi_chg>0.1 and price_chg_5>0: score+=0.5; reasons.append("OI up + price up")
        elif oi_chg>0.1 and price_chg_5<0: score-=0.5; reasons.append("OI up + price down")
        elif oi_chg<-0.1 and price_chg_5>0: score+=0.5; reasons.append("OI down + price up")
        elif oi_chg<-0.1 and price_chg_5<0: score-=0.5; reasons.append("OI down + price down")
        hunter_bias="LONG" if score>=1.5 else "SHORT" if score<=-1.5 else "NEUTRAL"
        # V15.9: hunter_wait REMOVED as block - now hunt_ride signal
        hunt_ride = hunt_cert["label"]=="CERTAIN" and hunt_cert["size_label"]=="GOOD" and hunter_bias!="NEUTRAL"
        hunt_state = get_hunt_state(hunt_cert, price, a_low, a_high, k1_norm, world or {})
        return {"hunter_score":round(score,2),"hunter_bias":hunter_bias,"hunt_ride":hunt_ride,"hunt_state":hunt_state,"reasons":reasons,"liq":liq,"ob_clusters":obc,"cvd_live":cvd,"spot":spot,"funding_cascade":fc,"oi":oi,"hunt_certainty":hunt_cert,"hunt_active":hunt_active,"hunt_session":hunt_session}
    except Exception as e:
        return {"hunter_score":0.0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_state":{"state":"NOT_VITAL","hunt_type":"NORMAL_DAY","hunt_done":False,"done_reasons":[]},"reasons":[f"Hunter error {e}"],"liq":{},"ob_clusters":{},"cvd_live":{},"spot":spot,"funding_cascade":{},"oi":oi,"hunt_certainty":{"score":0,"label":"NO_HUNT","hunt_dir":"NONE","target":0,"distance":9999,"size_label":"TOO_SMALL","reasons":[]},"hunt_active":False,"hunt_session":get_session()}

def get_asia_range(k15):
    lows, highs = [], []
    for k in k15:
        try:
            dt=datetime.fromtimestamp(k["time"]/1000, tz=timezone.utc)
            if dt.date()==_now().date() and 0<=dt.hour<8: lows.append(k["low"]); highs.append(k["high"])
        except: pass
    if lows: return min(lows), max(highs)
    if len(k15)>=32: return min(x["low"] for x in k15[-32:]), max(x["high"] for x in k15[-32:])
    return 0.0, 0.0

def get_sweep(price, k15, k1, liq_clusters=None):
    a_low, a_high = get_asia_range(k15)
    if liq_clusters: ll=liq_clusters.get("long_liq",0); sl=liq_clusters.get("short_liq",0)
    else:
        c=get_liq_clusters(price, k1); ll=c["long_liq"]; sl=c["short_liq"]
    sweep_done=False; sweep_dir="NONE"; hunt="NEUTRAL"
    if a_low and a_high and k1:
        last=k1[-1]
        if last["low"]<a_low and last["close"]>a_low: hunt="LONG"; sweep_done=True; sweep_dir="LONG"
        elif last["high"]>a_high and last["close"]<a_high: hunt="SHORT"; sweep_done=True; sweep_dir="SHORT"
    return hunt, a_low, a_high, ll, sl, sweep_done, sweep_dir

def get_macro_brain(price, k1, k15, funding=0.0):
    try:
        dxy_p, dxy_d, dxy_1h = yahoo_price_1h("DX-Y.NYB")
        _,_, jpy_1h = yahoo_price_1h("USDJPY=X")
        _, tnx_d, _ = yahoo_price_1h("^TNX")
        fng,_ = get_fear(); rsi=calc_rsi(k15[-60:] if k15 else [],14)
        score=0.0; det=[]
        if dxy_1h is not None:
            if dxy_1h>0.2: score-=2; det.append(f"DXY 1h +{dxy_1h:.2f}% SHORT+2")
            elif dxy_1h<-0.5: score+=2; det.append(f"DXY 1h {dxy_1h:.2f}% LONG+2")
            if dxy_p and dxy_p>102.5: score-=1; det.append("DXY>102.5 SHORT+1")
        if jpy_1h is not None:
            if jpy_1h<-1.5: score+=2; det.append("USDJPY -1.5% LONG+2")
            elif jpy_1h<-0.8: score+=1; det.append("USDJPY dropping LONG+1")
        if tnx_d is not None and tnx_d>0.5: score-=1; det.append("US10Y up SHORT+1")
        if funding<-0.01: score+=1; det.append("Funding shorts crowded LONG+1")
        elif funding>0.02: score-=1; det.append("Funding high SHORT+1")
        if rsi<25: score+=1; det.append(f"RSI {rsi} oversold LONG+1")
        elif rsi>70: score-=1; det.append("RSI overbought SHORT+1")
        if fng<=10: score+=0.5; det.append(f"Fear {fng} bounce risk")
        bias="SHORT" if score<=-1.5 else "LONG" if score>=1.5 else "NEUTRAL"
        alert="PAUSE_SHORT" if (dxy_1h is not None and dxy_1h<=-0.5) or (jpy_1h is not None and jpy_1h<=-0.8) else None
        return {"score":score,"bias":bias,"alert":alert,"dxy_1h":dxy_1h,"jpy_1h":jpy_1h,"funding":funding,"fng":fng,"rsi":rsi,"details":det}
    except Exception as e: return {"score":0.0,"bias":"NEUTRAL","alert":None,"error":str(e)}

_last_signal={"time":0,"data":None}
def _macro_vote(bias):
    if bias=="LONG": return 1,0
    if bias=="SHORT": return 0,1
    return 0,0
def _ob_vote(obc):
    bp=obc.get("buy_pressure",50)
    if obc.get("cluster_bias")=="BID_WALL_STRONG": return 1,0,"OB Bid Wall LONG"
    if obc.get("cluster_bias")=="ASK_WALL_STRONG": return 0,1,"OB Ask Wall SHORT"
    if bp>55: return 1,0,"Orderbook bids LONG"
    if bp<45: return 0,1,"Orderbook asks SHORT"
    return 0,0,""

def get_signal(price, atr=None, candles=None):
    global _last_signal
    if _last_signal["data"] is not None and (time.time()-_last_signal["time"])<15:
        cached=dict(_last_signal["data"]); cached["price"]=price; return cached
    try:
        if not price or price==0:
            price,_ = get_price_live()
            if price==0:
                return {"cert":0,"direction":"NONE","agree":0,"hunt_soon":False,"hunt_cert":0,"cvd_buy_pct":50,"news_critical":False,"news_wait":0,"pause_long":False,"pause_short":False,"price":0,"hunter_score":0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_done":False,"sweep_done":False,"sweep_dir":"NONE","first_aid":False,"first_aid_action":"NONE","first_aid_reason":"","hunt_certainty":{"score":0,"label":"NO_HUNT"},"spread":{"score":0,"bias":"NEUTRAL","spot_premium_usd":0,"coinbase_bybit_spread":0,"reasons":[]},"gold_boss":{},"gold_boss_boost":0,"news":{},"news_boost":0}
        k1=candles if candles and len(candles)>=5 else get_klines("1",20)
        k1_norm=[{"open":float(k.get("open",0)),"high":float(k.get("high",0)),"low":float(k.get("low",0)),"close":float(k.get("close",0)),"volume":float(k.get("volume",1)),"time":int(k.get("time",0))} for k in k1]
        k15=get_klines("15",200)
        world=get_world(); funding,_=get_funding(); spot=get_spot_premium(); oi=get_open_interest()
        price_chg_5=(k1_norm[-1]["close"]-k1_norm[-6]["close"])/k1_norm[-6]["close"]*100 if len(k1_norm)>=6 and k1_norm[-6]["close"] else 0
        price_chg_1h=(k1_norm[-1]["close"]-k1_norm[0]["close"])/k1_norm[0]["close"]*100 if k1_norm and k1_norm[0]["close"] else 0
        macro_brain=get_macro_brain(price, k1_norm, k15, funding)
        a_low_tmp, a_high_tmp=get_asia_range(k15)
        hunter=get_hunter_live(price, k1_norm, funding, spot, oi, oi.get("chg_5m",0), price_chg_5, a_low_tmp, a_high_tmp, world)
        hunt, a_low, a_high, ll, sl, sweep_done, sweep_dir=get_sweep(price, k15, k1_norm, hunter.get("liq"))
        obc=hunter.get("ob_clusters",{}); cvd_live=hunter.get("cvd_live",{}); fc=hunter.get("funding_cascade",{})
        hunt_cert=hunter.get("hunt_certainty",{"score":0,"label":"NO_HUNT","hunt_dir":"NONE","target":0,"distance":9999,"size_label":"TOO_SMALL","reasons":[]})
        hunt_active=hunter.get("hunt_active",False); spread=get_spread_score(price, spot, funding)
        # V15.9 NEWS - Booster Only
        news=get_news_live(world, price_chg_1h, cvd_live.get("aggressive","NEUTRAL"), price_chg_1h)
        long_votes=0; short_votes=0; total_voters=8; reasons=[]
        for key in ["DXY","NQ","SPX"]:
            v=world.get(key,0)
            if key=="DXY":
                if v<-0.05: long_votes+=1; reasons.append("DXY down LONG")
                elif v>0.05: short_votes+=1; reasons.append("DXY up SHORT")
            else:
                if v>0.05: long_votes+=1; reasons.append(f"{key} up LONG")
                elif v<-0.05: short_votes+=1; reasons.append(f"{key} down SHORT")
        gold=world.get("GOLD",0)
        if gold>0.05: long_votes+=1; reasons.append("GOLD up LONG")
        elif gold<-0.05: short_votes+=1; reasons.append("GOLD down SHORT")
        oi_chg=oi.get("chg_5m",0); macro_l, macro_s=_macro_vote(macro_brain.get("bias"))
        if oi_chg>0.1 and price_chg_5<0: long_votes+=1; reasons.append("OI up + price down LONG")
        elif oi_chg>0.1 and price_chg_5>0: long_votes+=1; reasons.append("OI up + price up LONG")
        elif oi_chg<-0.1 and price_chg_5<0: short_votes+=1; reasons.append("OI down + price down SHORT")
        else: long_votes+=macro_l; short_votes+=macro_s
        if hunt=="LONG": long_votes+=1; reasons.append("Sweep LONG")
        elif hunt=="SHORT": short_votes+=1; reasons.append("Sweep SHORT")
        cvd_agg=cvd_live.get("aggressive","NEUTRAL"); cvd_buy_pct=cvd_live.get("buy_pct",50.0)
        if cvd_agg=="BUY": long_votes+=1; reasons.append(f"CVD BUY {cvd_buy_pct}% LONG")
        elif cvd_agg=="SELL": short_votes+=1; reasons.append(f"CVD SELL {cvd_buy_pct}% SHORT")
        ob_l, ob_s, ob_r=_ob_vote(obc)
        long_votes+=ob_l; short_votes+=ob_s
        if ob_r and ob_r not in reasons: reasons.append(ob_r)
        if long_votes>short_votes: direction="LONG"; agree=long_votes
        elif short_votes>long_votes: direction="SHORT"; agree=short_votes
        else: direction="NONE"; agree=long_votes
        cert=round((agree/total_voters)*100,1) if total_voters else 0
        if macro_brain.get("bias")==direction and direction!="NONE": cert=min(100,cert+5)
        hunter_bias=hunter.get("hunter_bias","NEUTRAL"); hunter_score=hunter.get("hunter_score",0)
        if hunter_bias==direction and direction!="NONE": cert=min(100,cert+5); reasons.append(f"Hunter agrees {hunter_bias} +5")
        elif hunter_bias!="NEUTRAL" and hunter_bias!=direction and direction!="NONE": cert=max(0,cert-10); reasons.append(f"Hunter disagrees {hunter_bias} vs {direction} -10")
        spread_boost=0
        if direction!="NONE" and spread.get("bias") in ("LONG","SHORT"):
            spread_dir=spread["bias"]
            if spread_dir==direction and (hunter_bias==direction or macro_brain.get("bias")==direction):
                spread_boost=10; cert=min(100,cert+10); reasons.append(f"SPREAD BOOSTER +10% | Spread {spread_dir} {spread['score']} | Spot +${spread['spot_premium_usd']:.0f} | Coinbase-Bybit +${spread['coinbase_bybit_spread']:.0f}")
            elif spread_dir!=direction and spread.get("score",0)!=0:
                spread_boost=-5; cert=max(0,cert-5); reasons.append(f"SPREAD WARNING -5% | Spread {spread_dir} vs {direction} | Spot ${spread['spot_premium_usd']:.0f}")
        # V15.9 NEWS BOOSTER - Never block, never penalize
        news_boost, news_boost_reason = news_booster(news, direction, cert)
        if news_boost>0:
            cert=min(100,cert+news_boost); reasons.append(news_boost_reason)
        else:
            reasons.append(f"News {news.get('direction')} {news.get('score')} - {news_boost_reason} (ignored, no block)")
        # Hunt Ride boost from News: +1 hunt score if news backs hunt direction
        hunt_boost=0
        hunt_dir_map={"UP_FIRST":"LONG","DOWN_FIRST":"SHORT"}
        hunt_trade_dir=hunt_dir_map.get(hunt_cert.get("hunt_dir","NONE"),"NONE")
        if hunt_trade_dir!="NONE" and news.get("direction")==hunt_trade_dir and news.get("score",0)!=0:
            hunt_boost=1; reasons.append(f"NEWS BOOST HUNT +1 | News {news['direction']} backs hunt {hunt_trade_dir}")
        if sweep_done:
            direction=sweep_dir; agree=max(agree,7); cert=85.0; reasons.append(f"SWEEP DONE {sweep_dir} @ ${price:,.0f} - ENTER IMMEDIATELY")
        first_aid, first_aid_reason, first_aid_action, fa_dir=get_first_aid_v159(price, hunt_cert, direction, cert, sweep_done, k1_norm)
        if first_aid: direction=fa_dir; reasons.append(first_aid_reason)
        hunt_soon=False; hunt_cert_score=hunt_cert.get("score",0)
        if hunt_cert["label"]=="CERTAIN" and hunt_active and not sweep_done and not first_aid: hunt_soon=True
        # V15.9 Hunt Ride: opposite to normal direction, follow hunters
        hunt_ride_active=False; hunt_ride_dir="NONE"
        if hunter.get("hunt_ride") and not sweep_done and not first_aid:
            if hunt_cert.get("hunt_dir")=="UP_FIRST": hunt_ride_dir="LONG"
            elif hunt_cert.get("hunt_dir")=="DOWN_FIRST": hunt_ride_dir="SHORT"
            if hunt_ride_dir!="NONE": hunt_ride_active=True; reasons.append(f"HUNT RIDE {hunt_ride_dir} | Hunter {hunt_cert['score']}/9 {hunter.get('hunt_state',{}).get('hunt_type')} {hunt_cert['hunt_dir']} target ${hunt_cert['target']:,.0f} BE $600 close SL $1000 TP $1200")
        hunt_state=hunter.get("hunt_state",{})
        hunt_done=bool(hunt_state.get("hunt_done",False))
        if hunt_done: reasons.append(f"HUNT DONE: {'; '.join(hunt_state.get('done_reasons',[]))} -> Enter Normal {direction} immediately")
        # News critical / wait - V15.9: news never blocks, only info
        news_critical=False; news_wait=0
        if abs(price_chg_1h)>=0.8:
            news_critical=(cert>=90 and agree>=7)
        pause_long=False; pause_short=False; pause_reason=""
        if macro_brain.get("alert")=="PAUSE_SHORT": pause_short=True; pause_reason="Macro PAUSE_SHORT DXY/JPY"
        btc_chg_15m_calc=(k1_norm[-1]["close"]-k1_norm[-16]["close"])/k1_norm[-16]["close"]*100 if len(k1_norm)>=16 and k1_norm[-16]["close"] else price_chg_5
        gold_boss=get_gold_boss(gold, btc_chg_15m_calc, funding, oi_chg)
        gold_boss_boost=0
        if gold_boss["boss_dir"]==direction and direction!="NONE": gold_boss_boost+=gold_boss["boss_boost"]; cert=min(100,cert+gold_boss["boss_boost"]); reasons.extend(gold_boss["boss_reasons"])
        if gold_boss["dom_dir"]==direction and direction!="NONE": gold_boss_boost+=gold_boss["dom_boost"]; cert=min(100,cert+gold_boss["dom_boost"]); reasons.extend(gold_boss["dom_reasons"])
        if gold_boss["boss_dir"]!="NONE" and gold_boss["boss_dir"]!=direction and direction!="NONE": cert=max(0,cert-5); reasons.append(f"GOLD BOSS WARNING -5% | GOLD BOSS {gold_boss['boss_dir']} vs {direction}")
        if gold_boss["is_break"]:
            reasons.append(f"GOLD {gold_boss['break_tier']} WARNING - No Block, Cert Decides | GOLD 15m {gold_boss['gold_15m']:.2f}% vs BTC 15m {gold_boss['btc_15m']:.2f}% div {gold_boss['divergence']:.2f}%")
            if gold_boss["flip_to"]!="NONE": reasons.append(f"GOLD BREAK FLIP {gold_boss['break_candles']} candles -> Follow BTC {gold_boss['flip_to']} (Info only)")
        else:
            if gold_boss["resolve_since"]>0 and not gold_boss["confirm_ok"]:
                reasons.append(f"GOLD BREAK RESOLVED, 2min confirm {gold_boss['confirm_wait']}s left - Warning only, No Block")
            elif gold_boss["wick_active"] and direction!="NONE":
                reasons.append(f"GOLD WICK WARNING {gold_boss['wick_pct']:.2f}% - No Block, trade if cert strong")
        # V15.9: NO hunter_wait block, NO funding cascade block - Hunt Ride replaces block
        if sweep_done or first_aid: pause_long=False; pause_short=False; pause_reason=""
        result={"cert":cert,"direction":direction,"agree":agree,"hunt_soon":hunt_soon,"hunt_cert":hunt_cert_score,"cvd_buy_pct":cvd_buy_pct,"news_critical":news_critical,"news_wait":news_wait,"pause_long":pause_long,"pause_short":pause_short,"pause_reason":pause_reason,"price":price,"reasons":reasons,"news_reason":news.get("headline_note",""),"macro_bias":macro_brain.get("bias"),"session":get_session(),"liq_long":ll,"liq_short":sl,"hunter_score":hunter_score,"hunter_bias":hunter_bias,"hunt_ride":hunt_ride_active,"hunt_ride_dir":hunt_ride_dir,"hunt_ride_boost":hunt_boost,"hunt_state":hunt_state,"hunt_done":hunt_done,"hunter_reasons":hunter.get("reasons",[]),"liq_clusters":hunter.get("liq",{}),"ob_clusters":obc,"cvd_live":cvd_live,"spot_premium":spot,"spot_premium_usd":spot.get("premium_usd",0),"funding_cascade":fc,"oi":oi,"sweep_done":sweep_done,"sweep_dir":sweep_dir,"first_aid":first_aid,"first_aid_action":first_aid_action,"first_aid_reason":first_aid_reason,"hunt_certainty":hunt_cert,"hunt_active":hunt_active,"hunt_session":hunter.get("hunt_session",get_session()),"asia_low":a_low,"asia_high":a_high,"spread":spread,"spread_score":spread.get("score",0),"spread_bias":spread.get("bias","NEUTRAL"),"spread_boost":spread_boost,"gold_boss":gold_boss,"gold_boss_boost":gold_boss_boost,"news":news,"news_boost":news_boost,"price_chg_1h":round(price_chg_1h,3)}
        _last_signal={"time":time.time(),"data":result}
        return result
    except Exception as e:
        print(f"get_signal Error: {e}", flush=True)
        return {"cert":0,"direction":"NONE","agree":0,"hunt_soon":False,"hunt_cert":0,"cvd_buy_pct":50,"news_critical":False,"news_wait":0,"pause_long":False,"pause_short":False,"price":price,"hunter_score":0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_ride_dir":"NONE","hunt_done":False,"sweep_done":False,"sweep_dir":"NONE","first_aid":False,"first_aid_action":"NONE","first_aid_reason":"","spread":{"score":0,"bias":"NEUTRAL","spot_premium_usd":0,"coinbase_bybit_spread":0,"reasons":[]},"spread_boost":0,"gold_boss":{},"gold_boss_boost":0,"news":{"score":0,"direction":"NEUTRAL"},"news_boost":0}

if __name__=="__main__":
    price, src=get_price_live()
    sig=get_signal(price, 200, get_klines("1",20))
    print(f"Price ${price:.0f} [{src}] Signal: {sig['direction']} Cert {sig['cert']}% Hunter {sig['hunter_bias']} {sig['hunter_score']} HuntRide {sig.get('hunt_ride')} {sig.get('hunt_ride_dir')} HuntDone {sig.get('hunt_done')} Sweep {sig.get('sweep_done')} Hunt {sig.get('hunt_certainty',{}).get('label')} FirstAid {sig.get('first_aid')} News {sig.get('news',{}).get('direction')} {sig.get('news',{}).get('score')} Boost {sig.get('news_boost')} Spread {sig.get('spread',{}).get('bias')} {sig.get('spread',{}).get('score')} GOLD_BOSS {sig.get('gold_boss',{}).get('boss_dir')} {sig.get('gold_boss_boost')}")
