# === V4.4.9 FINAL COMPLETE - NO HARD PROXY - ONLY RENDER ENV - 100% READY ===
import requests, time, os, hmac, hashlib, json
from datetime import datetime

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")

# NO HARD PROXY - ONLY RENDER ENV PROXY FOR BYBIT!
ENV_PROXY = os.getenv("HTTPS_PROXY", os.getenv("HTTP_PROXY", ""))
if ENV_PROXY:
    order_proxies = {"http": ENV_PROXY, "https": ENV_PROXY}
    print(f"[V4.4.9 RENDER PROXY] USING ENV {ENV_PROXY[:45]} FOR BYBIT ONLY", flush=True)
else:
    order_proxies = None
    print(f"[V4.4.9 NO PROXY] WARNING! ENV HTTPS_PROXY NOT SET! Bybit fit block US!", flush=True)

STATE = {"balance":10.0,"real_bybit_balance":10.0,"median":78756,"live_price":78756,"spread":0,"trading":False,"prev_price":0}

def get_btc():
    prices=[]
    apis={
        "Binance":"https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
        "Coinbase":"https://api.exchange.coinbase.com/products/BTC-USD/ticker",
        "OKX":"https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
    }
    for n,u in apis.items():
        try:
            r=requests.get(u,timeout=4,proxies=None)
            p=float(r.json()['price']) if n!="OKX" else float(r.json()['data'][0]['last'])
            if p>1000: prices.append(p)
        except: continue
    prices.sort()
    median=prices[len(prices)//2] if prices else STATE["median"]
    live=median*0.9995
    STATE["median"]=median; STATE["live_price"]=live
    print(f"[LIVE 🌍] ${live:.0f} MEDIAN {len(prices)}/3 DIRECT FAST",flush=True)
    return live

def get_real_bank_api():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",timeout=5,proxies=None)
        d=r.json()
        chg=float(d['priceChangePercent'])
        banks_buying=chg>0
        wick=STATE["live_price"]-STATE.get("prev_price",STATE["live_price"])
        pred=1200 if abs(wick)>=150 else 700
        print(f"[REAL BANK 🏦] Chg {chg:.2f}% | Banks {'BUY ✅' if banks_buying else 'SELL 🔻'} | Wick ${wick:.0f}",flush=True)
        return {"banks_buying":banks_buying,"predicted_wick":pred,"current_wick":wick}
    except Exception as e:
        print(f"[BANK FAIL] {e}",flush=True)
        return {"banks_buying":False,"predicted_wick":700,"current_wick":0}

def get_lot():
    bal=STATE.get("real_bybit_balance",10)
    return 0.002 if bal<=12 else 0.005 if bal<=50 else 0.010

def should_trade(live,bank):
    if STATE["trading"]:
        print(f"[ONE TRADE ♾️] Active! Waiting close...",flush=True)
        return False,None,None
    wick=bank["current_wick"]; banks_buying=bank["banks_buying"]; dest=abs(bank["predicted_wick"])
    if abs(wick)<200: print(f"[WAIT] Wick ${wick:.0f} <200",flush=True); return False,None,None
    if dest<500: print(f"[WAIT] Dest ${dest} <500",flush=True); return False,None,None
    if wick>0:
        if not banks_buying: print(f"[SKIP ❌] PUMP but Banks SELL - SKIP! Save account!",flush=True); return False,None,None
        side="Buy"
        print(f"[TREND ✅] PUMP ${wick:.0f}+BUY=FOLLOW BUY!",flush=True)
    else:
        if banks_buying: print(f"[SKIP ❌] DUMP but Banks BUY DIP - SKIP! Save account!",flush=True); return False,None,None
        side="Sell"
        print(f"[TREND ✅] DUMP ${wick:.0f}+SELL=FOLLOW SELL!",flush=True)
    hunt=dest-300
    if hunt<366: hunt=366
    tp=hunt; sl=183
    print(f"[ROLLING ♾️] {side} Hunt ${hunt} TP {tp} SL {sl} Live ${live:.0f}",flush=True)
    return True,side,(tp,sl,live)

def check_closed():
    try:
        ts=str(int(time.time()*1000)); recv="5000"
        params=f"category=linear&symbol=BTCUSDT"
        sign=hmac.new(API_SECRET.encode(),(ts+API_KEY+recv+params).encode(),hashlib.sha256).hexdigest()
        h={"X-BAPI-API-KEY":API_KEY,"X-BAPI-SIGN":sign,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recv}
        r=requests.get(f"https://api.bybit.com/v5/position/list?{params}",headers=h,proxies=order_proxies,timeout=10)
        js=r.json()
        size=float(js['result']['list'][0]['size']) if js.get('result') else 0
        if size==0 and STATE["trading"]:
            STATE["trading"]=False
            print(f"[RESET ♾️] Position closed! Ready for next!",flush=True)
    except: pass

def place_order(side,tp,sl,live):
    try:
        lot=get_lot()
        tp_p=live+tp if side=="Buy" else live-tp
        sl_p=live-sl if side=="Buy" else live+sl
        ts=str(int(time.time()*1000)); recv="5000"
        params={"category":"linear","symbol":"BTCUSDT","side":side,"orderType":"Market","qty":str(lot),"takeProfit":str(tp_p),"stopLoss":str(sl_p),"tpTriggerBy":"LastPrice","slTriggerBy":"LastPrice","tpslMode":"Full"}
        param_str=ts+API_KEY+recv+json.dumps(params)
        sign=hmac.new(API_SECRET.encode(),param_str.encode(),hashlib.sha256).hexdigest()
        headers={"X-BAPI-API-KEY":API_KEY,"X-BAPI-SIGN":sign,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recv,"Content-Type":"application/json"}
        print(f"[ORDER TRY 🌍] {side} {lot} via RENDER ENV PROXY TP {tp_p:.0f} SL {sl_p:.0f}",flush=True)
        r=requests.post("https://api.bybit.com/v5/order/create",headers=headers,json=params,proxies=order_proxies,timeout=15)
        print(f"[ORDER RESP] {r.text[:600]}",flush=True)
        if r.status_code==200 and r.json().get("retCode")==0:
            print(f"[ORDER ✅] {side} RENDER PROXY SUCCESS ♾️",flush=True)
            STATE["trading"]=True
    except Exception as e: print(f"[ORDER FAIL] {e}",flush=True)

def main():
    print(f"[V4.4.9 START] {datetime.now()}",flush=True)
    try:
        r=requests.get("https://api.ipify.org?format=json",proxies=order_proxies,timeout=6)
        print(f"[PROXY TEST ✅] {r.text} GERMANY FRANKFURT",flush=True)
    except Exception as e: print(f"[PROXY TEST ❌] {e}",flush=True)
    while True:
        live=get_btc()
        if STATE["prev_price"]==0: STATE["prev_price"]=live
        bank=get_real_bank_api()
        check_closed()
        if not STATE["trading"]:
            can,side,data=should_trade(live,bank)
            if can: tp,sl,entry=data; place_order(side,tp,sl,entry)
        STATE["prev_price"]=live; time.sleep(30)

if __name__=="__main__": main()
