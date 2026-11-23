# DATA ENGINE V16.2 PATCHED - PART 1/3
# BE $800/$600 | TP $1200 | News booster only | Gold Boss booster only
import requests,time,json,re
from datetime import datetime,timezone
from xml.etree import ElementTree as ET
def _now(): return datetime.now(timezone.utc)
def _safe_get(url,timeout=5):
    try:
        r=requests.get(url,timeout=timeout,headers={"User-Agent":"Mozilla/5.0"})
        txt=r.text.strip() if r.text else ""
        if not txt: return None
        try: return r.json()
        except: return txt
    except: return None
def _safe_get_text(url,timeout=5):
    try:
        r=requests.get(url,timeout=timeout,headers={"User-Agent":"Mozilla/5.0"})
        return r.text if r.text else ""
    except: return ""
TRADES_FILE="trades.json"; DAILY_FILE="daily.json"
def save_trade(trade):
    try:
        try:
            with open(TRADES_FILE) as f: a=json.load(f)
        except: a=[]
        a.append(trade)
        with open(TRADES_FILE,"w") as f: json.dump(a,f,indent=2)
        day=str(trade.get("time",_now().strftime("%Y-%m-%d %H:%M:%S")))[:10]
        try:
            with open(DAILY_FILE) as f: d=json.load(f)
        except: d={}
        if day not in d: d[day]={"trades":0,"wins":0,"losses":0,"total_pnl":0.0,"be_tp_hits":0,"sl_hits":0,"tp_hits":0,"hunt_rides":0,"flips":0}
        x=d[day]; x["trades"]+=1; x["total_pnl"]=round(x["total_pnl"]+float(trade.get("net_pnl",0)),2)
        x["wins" if float(trade.get("net_pnl",0))>0 else "losses"]+=1
        with open(DAILY_FILE,"w") as f: json.dump(d,f,indent=2)
        return d
    except Exception as e: print(f"JSON Save Error: {e}",flush=True); return {}
def get_price_live():
    for url,parse in [("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT",lambda j: float(j["result"]["list"][0]["lastPrice"])),("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",lambda j: float(j["price"])),("https://api.exchange.coinbase.com/products/BTC-USD/ticker",lambda j: float(j["price"])),("https://api.kraken.com/0/public/Ticker?pair=XBTUSD",lambda j: float(j["result"]["XXBTZUSD"]["c"][0])),("https://www.bitstamp.net/api/v2/ticker/btcusd/",lambda j: float(j["last"])),("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP",lambda j: float(j["data"][0]["last"])),("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",lambda j: float(j["bitcoin"]["usd"]))]:
        try:
            j=_safe_get(url)
            if j:
                p=parse(j)
                if p>0: return p,"LIVE"
        except: pass
    return 0.0,"LIVE-FAIL"
def get_klines(interval="1",limit=100):
    try:
        j=_safe_get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}")
        if j:
            kl=list(reversed(j["result"]["list"])); return [{"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"time":int(x[0])} for x in kl]
    except: pass
    try:
        bi={"1":"1m","5":"5m","15":"15m","60":"1h"}.get(interval,"1m"); j=_safe_get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={bi}&limit={limit}")
        if isinstance(j,list): return [{"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5]),"time":int(x[0])} for x in j]
    except: pass
    return []
def calc_rsi(klines,period=14):
    if not klines or len(klines)<period+1: return 50.0
    closes=[k["close"] for k in klines]; gains=[]; losses=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[-period:])/period; al=sum(losses[-period:])/period
    if al==0: return 100.0
    return round(100-(100/(1+ag/al)),1)
def yahoo_chg(sym):
    try:
        for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
            j=_safe_get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=1m")
            if j:
                m=j["chart"]["result"][0]["meta"]; price=float(m.get("regularMarketPrice") or m.get("previousClose") or 0); prev=float(m.get("previousClose") or price)
                if price and prev and price!=prev: return round((price-prev)/prev*100,3),price,prev
    except: pass
    return None,None,None
def yahoo_price_1h(sym):
    try:
        for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
            j=_safe_get(f"{base}/v8/finance/chart/{sym}?range=1d&interval=5m")
            if j:
                res=j["chart"]["result"][0]; closes=[c for c in res["indicators"]["quote"][0].get("close",[]) if c is not None]
                if closes:
                    cur=float(closes[-1]); prev=float(res["meta"].get("previousClose") or closes[0]); chg_day=(cur-prev)/prev*100 if prev else 0; chg_1h=(cur-closes[-13])/closes[-13]*100 if len(closes)>=13 and closes[-13] else 0; return cur,chg_day,chg_1h
    except: pass
    return None,None,None
_world_cache={"time":0,"data":{}}
def get_world():
    if time.time()-_world_cache["time"]<60 and _world_cache["data"]: return _world_cache["data"]
    w={}
    for name,sym in [("NIKKEI","^N225"),("HANG_SENG","^HSI"),("FTSE","^FTSE"),("DAX","^GDAXI"),("NQ","NQ=F"),("SPX","ES=F"),("GOLD","GC=F"),("DXY","DX-Y.NYB"),("US10Y","^TNX"),("USDJPY","USDJPY=X"),("OIL","CL=F"),("VIX","^VIX")]:
        chg,_,_=yahoo_chg(sym); w[name]=chg if chg is not None else 0.0
    _world_cache["time"]=time.time(); _world_cache["data"]=w; return w
def get_session():
    h=_now().hour
    return "ASIA" if 0<=h<7 else "LONDON" if 7<=h<13 else "NEW_YORK" if 13<=h<21 else "LATE_NY"
def get_hunt_window():
    mins=_now().hour*60+_now().minute
    if mins>=22*60 or mins<=8*60: return True,"ASIA"
    if 6*60<=mins<=14*60+30: return True,"LONDON"
    if 12*60<=mins<=22*60: return True,"NEW_YORK"
    return False,get_session()
def get_pre_entry():
    mins=_now().hour*60+_now().minute
    if mins>=22*60 or mins<=0: return True,"ASIA_PRE","Asia Pre 22:00-00:00 - watch DXY/GOLD/OI/CVD"
    if 6*60<=mins<=7*60: return True,"LONDON_PRE","London Pre 06:00-07:00 - watch Asia close + DXY + NQ"
    if 12*60<=mins<=13*60+30: return True,"NY_PRE","NY Pre 12:00-13:30 - watch London close + SPX + DXY"
    return False,"NONE",""
def get_funding():
    try:
        j=_safe_get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1")
        if j and j["result"].get("list"): return float(j["result"]["list"][0].get("fundingRate",0))*100,"Bybit-LIVE"
    except: pass
    try:
        j=_safe_get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1")
        if j: return float(j[0].get("fundingRate",0))*100,"Binance-LIVE"
    except: pass
    return 0.0,"LIVE-FAIL"
def get_fear():
    try:
        j=_safe_get("https://api.alternative.me/fng/?limit=1")
        if j: return int(j["data"][0]["value"]),j["data"][0].get("value_classification","")
    except: pass
    return 50,"Neutral"
def get_open_interest():
    try:
        j=_safe_get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=6")
        if j:
            lst=j["result"]["list"]
            if len(lst)>=2:
                first=float(lst[0]["openInterest"]); last=float(lst[-1]["openInterest"]); chg=(last-first)/first*100 if first else 0; return {"oi":last,"chg_5m":round(chg,3),"src":"Bybit-LIVE"}
    except: pass
    return {"oi":0.0,"chg_5m":0.0,"src":"LIVE-FAIL"}
def get_asia_range(k15):
    lows=[]; highs=[]
    for k in k15:
        try:
            dt=datetime.fromtimestamp(k["time"]/1000,tz=timezone.utc)
            if dt.date()==_now().date() and 0<=dt.hour<8: lows.append(k["low"]); highs.append(k["high"])
        except: pass
    if lows: return min(lows),max(highs)
    if len(k15)>=32: return min(x["low"] for x in k15[-32:]),max(x["high"] for x in k15[-32:])
    return 0.0,0.0
