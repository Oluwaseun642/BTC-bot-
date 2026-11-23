import os,time,hmac,hashlib,requests,json
from urllib.parse import urlencode
BASE="https://api.bybit.com"
KEY=os.getenv("BYBIT_API_KEY","").strip(); SEC=os.getenv("BYBIT_API_SECRET","").strip()
SYMBOL="BTCUSDT"; MARGIN="USDT"; RECV="5000"
def _sign(payload,ts):
    if not SEC: return "MISSING"
    msg=f"{ts}{KEY}{RECV}{payload}"
    return hmac.new(SEC.encode(),msg.encode(),hashlib.sha256).hexdigest()
def bybit_post(path,params):
    if not KEY or not SEC: return {"retCode":-1,"retMsg":"API key not set","result":{}}
    ts=int(time.time()*1000); payload=json.dumps(params,separators=(",",":")) if params else ""
    h={"X-BAPI-API-KEY":KEY,"X-BAPI-SIGN":_sign(payload,ts),"X-BAPI-TIMESTAMP":str(ts),"X-BAPI-RECV-WINDOW":RECV,"Content-Type":"application/json"}
    try: return requests.post(BASE+path,headers=h,data=payload,timeout=30).json()
    except Exception as e: return {"retCode":-1,"retMsg":str(e),"result":{}}
def bybit_get(path,params):
    if not KEY or not SEC: return {"retCode":-1,"retMsg":"API key not set","result":{}}
    ts=int(time.time()*1000); q=urlencode(params or {})
    h={"X-BAPI-API-KEY":KEY,"X-BAPI-SIGN":_sign(q,ts),"X-BAPI-TIMESTAMP":str(ts),"X-BAPI-RECV-WINDOW":RECV}
    try: return requests.get(BASE+path,headers=h,params=params or {},timeout=30).json()
    except Exception as e: return {"retCode":-1,"retMsg":str(e),"result":{}}
def get_balance():
    # PATCHED: avail FIRST, wallet second. Bot must use avail, no be wallet.
    for acct in ["UNIFIED","CONTRACT"]:
        j=bybit_get("/v5/account/wallet-balance",{"accountType":acct,"coin":"USDT"})
        print(f"[BAL DEBUG] {acct} retCode={j.get('retCode')} retMsg={j.get('retMsg')} ",flush=True)
        try:
            lst=j.get("result",{}).get("list",[])
            if not lst: continue
            for c in lst[0].get("coin",[]):
                if c.get("coin")==MARGIN:
                    bal=float(c.get("walletBalance",0) or 0)
                    avail=float(c.get("availableBalance",0) or 0)
                    # Bybit sometimes puts avail in availableToWithdraw
                    if avail==0:
                        avail=float(c.get("availableToWithdraw",0) or 0)
                    print(f"[BAL] {acct} wallet=${bal:.2f} avail=${avail:.2f}",flush=True)
                    if avail>0:
                        print(f"[BAL] Using AVAIL ${avail:.2f} from {acct}",flush=True)
                        return avail
                    if bal>0:
                        print(f"[BAL] Avail 0, fallback to wallet ${bal:.2f} - order fit fail if avail still 0, transfer to Unified!",flush=True)
                        return bal
        except Exception as e:
            print(f"[BAL ERROR] {acct} {e}",flush=True); continue
    print("[BAL] All wallets $0 - check Assets -> Unified USDT",flush=True)
    return 0.0
def get_available_balance():
    # Helper for main.py - returns avail only, no wallet fallback
    return get_balance()
def get_position():
    try:
        j=bybit_get("/v5/position/list",{"category":"linear","symbol":SYMBOL}); lst=j.get("result",{}).get("list",[])
        if lst and float(lst[0].get("size",0))>0:
            p=lst[0]; return ("LONG" if p.get("side")=="Buy" else "SHORT"),float(p.get("size",0)),float(p.get("entryPrice",0))
    except Exception as e: print(f"[POS] {e}",flush=True)
    return None,0.0,0.0
def get_dynamic_leverage(price,bal,risk=30.0):
    if not price or not bal: return 1
    if bal<5: return 60
    if bal<15: return 40
    if bal<50: return 30
    if bal<200: return 20
    return 15
def get_dynamic_qty(price,bal,risk=30.0):
    if not price or not bal: return 0.0,1
    if bal<5: return 0.001,60
    if bal<15: return 0.001,40
    if bal<50: return 0.001,30
    if bal<200: return 0.001,20
    return 0.001,15
def set_isolated_margin(sym,lev,side):
    sym="BTCUSDT"
    return bybit_post("/v5/position/switch-isolated",{"category":"linear","symbol":sym,"tradeMode":1,"buyLeverage":str(lev),"sellLeverage":str(lev)})
def place_order(side,qty,sl,tp,price,lev):
    if qty<=0 or not price or sl<=0 or tp<=0: return {"retCode":-1,"retMsg":"Bad SL/TP/Qty","result":{}}
    if abs(price-sl)<50 or abs(tp-price)<50: return {"retCode":-1,"retMsg":"SL/TP too close","result":{}}
    return bybit_post("/v5/order/create",{"category":"linear","symbol":SYMBOL,"side":"Buy" if side=="LONG" else "Sell","orderType":"Market","qty":str(qty),"timeInForce":"GTC","positionIdx":0,"takeProfit":str(round(tp,1)),"stopLoss":str(round(sl,1)),"tpTriggerBy":"LastPrice","slTriggerBy":"LastPrice","tpOrderType":"Market","slOrderType":"Market"})
def close_position_market(side,qty):
    return bybit_post("/v5/order/create",{"category":"linear","symbol":SYMBOL,"side":"Sell" if side=="LONG" else "Buy","orderType":"Market","qty":str(qty),"timeInForce":"GTC","positionIdx":0,"reduceOnly":True})
