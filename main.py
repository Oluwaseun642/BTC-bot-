# === V4.4.12 FINAL - 3 GLOBAL BANKS + HIDDEN FRIENDS + 5MIN + LOT IMPROVISE + KEEP-ALIVE ===
import requests, time, os, hmac, hashlib, json, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

def keep_alive():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"V4.4.12 ALIVE - 3 BANKS")
        def log_message(self, *a): return
    port = int(os.getenv("PORT", "10000"))
    try: HTTPServer(("0.0.0.0", port), Handler).serve_forever()
    except Exception as e: print(f"[KEEP-ALIVE FAIL] {e}", flush=True)

threading.Thread(target=keep_alive, daemon=True).start()
print("[KEEP-ALIVE] Web server started", flush=True)

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")

ENV_PROXY = os.getenv("HTTPS_PROXY", os.getenv("HTTP_PROXY", "")).strip().rstrip("/")
if ENV_PROXY and not ENV_PROXY.startswith("http"): ENV_PROXY = "http://" + ENV_PROXY
if ENV_PROXY and "@" in ENV_PROXY:
    order_proxies = {"http": ENV_PROXY, "https": ENV_PROXY}
    print(f"[V4.4.12 SHIELD ACTIVE] {ENV_PROXY[:50]}... 3 BANKS", flush=True)
else:
    order_proxies = None
    print(f"[SHIELD WARNING] Proxy not set!", flush=True)

STATE = {"balance":10.0,"real_bybit_balance":10.0,"median":78756,"live_price":78756,"trading":False,"price_history":[]}

def get_btc():
    prices=[]
    apis={"Binance":"https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT","Coinbase":"https://api.exchange.coinbase.com/products/BTC-USD/ticker","OKX":"https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"}
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
    print(f"[LIVE] ${live:.0f} MEDIAN {len(prices)}/3 FAST",flush=True)
    return live

def get_real_bank_api():
    # 3 GLOBAL BANKS CHECK - WORLD WIDE
    votes=[]; details=[]
    # 1. Binance global flow
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",timeout=5,proxies=None)
        chg=float(r.json()['priceChangePercent']); votes.append(chg>0); details.append(f"Binance {chg:.2f}%")
    except: pass
    # 2. Coinbase US institutions
    try:
        r=requests.get("https://api.exchange.coinbase.com/products/BTC-USD/stats",timeout=5,proxies=None)
        d=r.json(); open_p=float(d['open']); last_p=float(d['last'])
        chg2=((last_p-open_p)/open_p*100) if open_p else 0; votes.append(chg2>0); details.append(f"Coinbase {chg2:.2f}%")
    except: pass
    # 3. OKX Asia banks
    try:
        r=requests.get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",timeout=5,proxies=None)
        data=r.json()['data'][0]; open_p=float(data['open24h']); last_p=float(data['last'])
        chg3=((last_p-open_p)/open_p*100) if open_p else 0; votes.append(chg3>0); details.append(f"OKX {chg3:.2f}%")
    except: pass
    
    if not votes: return {"banks_buying":False,"predicted_wick":700,"info":"BANK FAIL"}
    banks_buying = votes.count(True) >= 2  # majority of 3 banks
    avg_chg = sum([1 if v else -1 for v in votes])
    print(f"[REAL BANK WORLD] {' | '.join(details)} => Banks {'BUY' if banks_buying else 'SELL'} ({votes.count(True)}/3)",flush=True)
    return {"banks_buying":banks_buying,"predicted_wick":1200 if abs(avg_chg)>=2 else 700}

def get_lot():
    bal=STATE.get("real_bybit_balance",10)
    if bal<=12: return 0.002
    elif bal<=50: return 0.005
    elif bal<=100: return 0.010
    elif bal<=500: return 0.020
    else: return 0.030

def should_trade(live,bank):
    if STATE["trading"]:
        print(f"[ONE TRADE] Active! Waiting close...",flush=True)
        return False,None,None
    STATE["price_history"].append(live)
    if len(STATE["price_history"])>10: STATE["price_history"].pop(0)
    old_price=STATE["price_history"][0] if len(STATE["price_history"])>1 else live
    wick=live-old_price
    print(f"[WICK 5MIN] {wick:.0f} ({old_price:.0f}->{live:.0f})",flush=True)
    if abs(wick)<5:
        print(f"[WAIT] Wick ${wick:.0f} <5 wait",flush=True)
        return False,None,None
    banks_buying=bank["banks_buying"]; dest=abs(bank["predicted_wick"])
    if wick>0:
        if not banks_buying:
            print(f"[SKIP] Pump but Banks SELL (2/3) - fake, we hide",flush=True)
            return False,None,None
        side="Buy"
    else:
        if banks_buying:
            print(f"[SKIP] Dump but Banks BUY (2/3) - fake, we hide",flush=True)
            return False,None,None
        side="Sell"
    hunt=dest-300; 
    if hunt<366: hunt=366
    tp=hunt; sl=183
    print(f"[ROLLING HIDDEN FRIEND WORLD] {side} Hunt ${hunt} TP {tp} SL {sl}",flush=True)
    return True,side,(tp,sl,live)

def check_closed():
    try:
        ts=str(int(time.time()*1000)); recv="5000"; params=f"category=linear&symbol=BTCUSDT"
        sign=hmac.new(API_SECRET.encode(),(ts+API_KEY+recv+params).encode(),hashlib.sha256).hexdigest()
        h={"X-BAPI-API-KEY":API_KEY,"X-BAPI-SIGN":sign,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recv}
        r=requests.get(f"https://api.bybit.com/v5/position/list?{params}",headers=h,proxies=order_proxies,timeout=10)
        js=r.json(); size=float(js['result']['list'][0]['size']) if js.get('result') else 0
        if size==0 and STATE["trading"]:
            STATE["trading"]=False; print(f"[RESET] Position closed! Ready!",flush=True)
    except Exception as e: print(f"[CHECK FAIL] {e}",flush=True)

def place_order(side,tp,sl,live):
    try:
        lot=get_lot(); tp_p=live+tp if side=="Buy" else live-tp; sl_p=live-sl if side=="Buy" else live+sl
        ts=str(int(time.time()*1000)); recv="5000"
        params={"category":"linear","symbol":"BTCUSDT","side":side,"orderType":"Market","qty":str(lot),"takeProfit":str(tp_p),"stopLoss":str(sl_p),"tpTriggerBy":"LastPrice","slTriggerBy":"LastPrice","tpslMode":"Full"}
        param_str=ts+API_KEY+recv+json.dumps(params)
        sign=hmac.new(API_SECRET.encode(),param_str.encode(),hashlib.sha256).hexdigest()
        headers={"X-BAPI-API-KEY":API_KEY,"X-BAPI-SIGN":sign,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recv,"Content-Type":"application/json"}
        print(f"[ORDER TRY] {side} {lot} SHIELD {'ON' if order_proxies else 'OFF'} 3BANKS",flush=True)
        r=requests.post("https://api.bybit.com/v5/order/create",headers=headers,json=params,proxies=order_proxies,timeout=15)
        print(f"[ORDER RESP] {r.text[:600]}",flush=True)
        if r.status_code==200 and r.json().get("retCode")==0:
            print(f"[ORDER OK] {side} SUCCESS WORLD",flush=True); STATE["trading"]=True
    except Exception as e: print(f"[ORDER FAIL] {e}",flush=True)

def main():
    print(f"[V4.4.12 START] {datetime.now()} - 3 GLOBAL BANKS",flush=True)
    try:
        r=requests.get("https://api.ipify.org?format=json",proxies=order_proxies,timeout=8)
        print(f"[PROXY TEST OK] {r.text}",flush=True)
    except Exception as e: print(f"[PROXY TEST FAIL] {e}",flush=True)
    while True:
        live=get_btc(); bank=get_real_bank_api(); check_closed()
        if not STATE["trading"]:
            can,side,data=should_trade(live,bank)
            if can: tp,sl,entry=data; place_order(side,tp,sl,entry)
        time.sleep(30)

if __name__=="__main__": main()
