import os,time,hmac,hashlib,requests,json
from urllib.parse import urlencode
BASE="https://api.bybit.com"
KEY=os.getenv("BYBIT_API_KEY","").strip(); SEC=os.getenv("BYBIT_API_SECRET","").strip()
SYMBOL="BTCUSDT"; MARGIN="USDT"
def _sign(payload,ts): return hmac.new(SEC.encode(),f"{ts}{KEY}{payload}".encode(),hashlib.sha256).hexdigest() if SEC else "MISSING"
def bybit_post(path,params):
    if not KEY or not SEC: return {"retCode":-1,"retMsg":"API key not set","result":{}}
    ts=int(time.time()*1000); payload=json.dumps(params,separators=(",",":")) if params else ""
    h={"X-BAPI-API-KEY":KEY,"X-BAPI-SIGN":_sign(payload,ts),"X-BAPI-TIMESTAMP":str(ts),"X-BAPI-RECV-WINDOW":"5000","Content-Type":"application/json"}
    try: return requests.post(BASE+path,headers=h,data=payload,timeout=30).json()
    except Exception as e: return {"retCode":-1,"retMsg":str(e),"result":{}}
def bybit_get(path,params):
    if not KEY or not SEC: return {"retCode":-1,"retMsg":"API key not set","result":{}}
    ts=int(time.time()*1000); q=urlencode(params or {})
    h={"X-BAPI-API-KEY":KEY,"X-BAPI-SIGN":_sign(q,ts),"X-BAPI-TIMESTAMP":str(ts),"X-BAPI-RECV-WINDOW":"5000"}
    try: return requests.get(BASE+path,headers=h,params=params or {},timeout=30).json()
    except Exception as e: return {"retCode":-1,"retMsg":str(e),"result":{}}
def get_balance():
    j=bybit_get("/v5/account/wallet-balance",{"accountType":"UNIFIED"})
    try:
        for c in j.get("result",{}).get("list",[])[0].get("coin",[]):
            if c.get("coin")==MARGIN: return float(c.get("walletBalance",0))
    except Exception: pass
    return None
def get_position():
    try:
        j=bybit_get("/v5/position/list",{"category":"linear","symbol":SYMBOL}); lst=j.get("result",{}).get("list",[])
        if lst and float(lst[0].get("size",0))>0:
            p=lst[0]; return ("LONG" if p.get("side")=="Buy" else "SHORT"),float(p.get("size",0)),float(p.get("entryPrice",0))
    except Exception as e: print(f"[POS] {e}",flush=True)
    return None,0.0,0.0
def get_dynamic_leverage(price,bal,risk=30.0):
    if not price or not bal: return 1
    return max(1,min(20,int(round((risk*20)/(bal*price)))))
def get_dynamic_qty(price,bal,risk=30.0):
    if not price or not bal: return 0.0,1
    lev=get_dynamic_leverage(price,bal,risk); return max(0.0,round((bal*lev)/price,3)),lev
def set_isolated_margin(sym,lev,side):
    return bybit_post("/v5/position/switch-isolated",{"category":"linear","symbol":sym,"tradeMode":1,"buyLeverage":str(lev),"sellLeverage":str(lev)})
def place_order(side,qty,sl,tp,price,lev):
    if qty<=0 or not price or sl<=0 or tp<=0: return {"retCode":-1,"retMsg":"Bad SL/TP/Qty","result":{}}
    if abs(price-sl)<50 or abs(tp-price)<50: return {"retCode":-1,"retMsg":"SL/TP too close","result":{}}
    return bybit_post("/v5/order/create",{"category":"linear","symbol":SYMBOL,"side":"Buy" if side=="LONG" else "Sell","orderType":"Market","qty":str(qty),"timeInForce":"GTC","positionIdx":0,"takeProfit":str(round(tp,1)),"stopLoss":str(round(sl,1)),"tpTriggerBy":"LastPrice","slTriggerBy":"LastPrice","tpOrderType":"Market","slOrderType":"Market"})
def close_position_market(side,qty):
    return bybit_post("/v5/order/create",{"category":"linear","symbol":SYMBOL,"side":"Sell" if side=="LONG" else "Buy","orderType":"Market","qty":str(qty),"timeInForce":"GTC","positionIdx":0,"reduceOnly":True})
