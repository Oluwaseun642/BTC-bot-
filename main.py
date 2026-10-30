# V4.4.18 FINAL - FIXED BRACKET + IMPROVISED - BALANCE GROWS
import os, time, threading, requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from pybit.unified_trading import HTTP

print("=== V4.4.18 FINAL IMPROVISED - READY ===")

SYMBOL = "BTCUSDT"
CATEGORY = "linear"
LEVERAGE = 20
LEVERAGE_STR = "20"
INITIAL_BAL = 10.0

STATE = {
    "trading": False,
    "neural_mode": False,
    "entry_price": 0,
    "side": None,
    "tp1_done": False,
    "friend": None,
    "last_random_wick_time": 0,
    "last_premium": 0,
    "last_premium_time": 0
}

client = HTTP(api_key=os.getenv("BYBIT_API_KEY"), api_secret=os.getenv("BYBIT_API_SECRET"), testnet=False)

try:
    client.set_leverage(category=CATEGORY, symbol=SYMBOL, buyLeverage=LEVERAGE_STR, sellLeverage=LEVERAGE_STR)
    print(f"[LEVERAGE] {LEVERAGE_STR}x")
except Exception as e:
    print(f"[LEVERAGE] {e}")

def keep_alive():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type","text/plain")
            self.end_headers()
            self.wfile.write(b"V4.4.18 FINAL IMPROVISED ALIVE - BALANCE BASED")
        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-type","text/plain")
            self.end_headers()
        def log_message(self,*a): return
    def run():
        port = int(os.getenv("PORT", 10000))
        HTTPServer(("0.0.0.0", port), H).serve_forever()  # FIXED BRACKET HERE!
    threading.Thread(target=run, daemon=True).start()
keep_alive()

def get_balance():
    try:
        bal = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        data = bal["result"]["list"][0]
        coins = data.get("coin", [])
        if coins:
            usdt = coins[0]
            total = float(usdt.get("walletBalance") or usdt.get("equity") or usdt.get("availableToWithdraw") or 10)
        else:
            total = float(data.get("totalWalletBalance") or 10)
        total = max(total, 1.0)
        growth = ((total - INITIAL_BAL)/INITIAL_BAL*100) if INITIAL_BAL>0 else 0
        print(f"[BALANCE] ${total:.2f} | Growth: {growth:+.1f}% from $10")
        return total
    except Exception as e:
        print(f"[BALANCE ERR] {e} -> $10 fallback")
        return 10.0

def get_coinbase_premium_cached():
    # IMPROVISED: Cache premium 10s to avoid rate limit
    now = time.time()
    if now - STATE["last_premium_time"] < 10:
        return None, None, STATE["last_premium"]
    try:
        cb = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=3).json()
        cb_price = float(cb["data"]["amount"])
        bybit_price = float(client.get_tickers(category=CATEGORY, symbol=SYMBOL)["result"]["list"][0]["lastPrice"])
        premium = cb_price - bybit_price
        STATE["last_premium"] = premium
        STATE["last_premium_time"] = now
        return cb_price, bybit_price, premium
    except:
        return None, None, STATE["last_premium"]

def scan_world():
    try:
        klines = client.get_kline(category=CATEGORY, symbol=SYMBOL, interval="5", limit=200)
        closes = [float(c[4]) for c in klines["result"]["list"]][::-1]
        vols = [float(c[5]) for c in klines["result"]["list"]][::-1]
        ema50 = sum(closes[-50:])/50
        ema200 = sum(closes[-200:])/200 if len(closes)>=200 else sum(closes)/len(closes)
        current = closes[-1]
        vol_now = vols[-1]
        vol_avg = sum(vols[-20:])/20 if sum(vols[-20:])>0 else 1
        if current > ema50 > ema200 and current > closes[-2]: real_dir="LONG"
        elif current < ema50 < ema200 and current < closes[-2]: real_dir="SHORT"
        else: real_dir="NEUTRAL"
        last = klines["result"]["list"][0]
        high,low,open_p,close_p = float(last[2]),float(last[3]),float(last[1]),float(last[4])
        wick_up = high-max(open_p,close_p); wick_down=min(open_p,close_p)-low; body=abs(close_p-open_p)+0.1
        is_hunt=False; hunt_type=None; is_real=False
        if wick_up>body*1.8 and vol_now>vol_avg*1.3: is_hunt=True; hunt_type="HUNT_UP"
        elif wick_down>body*1.8 and vol_now>vol_avg*1.3: is_hunt=True; hunt_type="HUNT_DOWN"
        elif body>wick_up and body>wick_down and vol_now>vol_avg*1.2: is_real=True
        _,_,premium = get_coinbase_premium_cached()
        if real_dir=="LONG" and premium>5: driver="USA_COINBASE_STRONG_LONG"
        elif real_dir=="LONG": driver="USA_COINBASE_LONG"
        elif real_dir=="SHORT" and premium<-5: driver="USA_COINBASE_STRONG_SHORT"
        elif real_dir=="SHORT": driver="ASIA_BANKS_SHORT"
        else: driver="NONE"
        dynamic_sl = 800 if is_hunt else 450
        return {"real_direction":real_dir,"current_price":current,"driver":driver,"is_hunt":is_hunt,"hunt_type":hunt_type,"is_real":is_real,"wick_up":wick_up,"wick_down":wick_down,"dynamic_sl":dynamic_sl,"premium":premium,"vol_ratio":vol_now/vol_avg}
    except Exception as e:
        print(f"[SCAN ERR] {e}"); return {"real_direction":"NEUTRAL","current_price":78000,"is_hunt":False,"is_real":False,"dynamic_sl":800,"premium":STATE["last_premium"],"driver":"NONE"}

def soldier_decision():
    if STATE["trading"]:
        print(f"[LOYAL] In trade {STATE['friend']} {STATE['side']} - Staying!")
        return False,None,None
    scan=scan_world()
    print(f"[SCAN] Real:{scan['real_direction']} Driver:{scan['driver']} Price:{scan['current_price']:.1f} Premium:{scan['premium']:.2f} Vol:{scan['vol_ratio']:.1f}x")
    if scan["real_direction"]=="NEUTRAL":
        if not STATE["neural_mode"]: print("[NEURAL ON] No driver - Sitting vigilant..."); STATE["neural_mode"]=True
        return False,None,scan
    else:
        if STATE["neural_mode"]: print(f"[NEURAL OFF] {scan['driver']} JOINING!"); STATE["neural_mode"]=False
    if not scan["is_hunt"] and not scan["is_real"] and (scan["wick_up"]>150 or scan["wick_down"]>150):
        now=time.time()
        if STATE["last_random_wick_time"]==0: STATE["last_random_wick_time"]=now
        if now-STATE["last_random_wick_time"]<60: return False,None,scan
        else: STATE["last_random_wick_time"]=0
    else: STATE["last_random_wick_time"]=0
    return True, scan["real_direction"], scan

def place_order(direction, scan):
    try:
        price=scan["current_price"]; sl_dist=scan["dynamic_sl"]
        if direction=="LONG": sl=price-sl_dist; tp1=price+(sl_dist*0.8); tp2=price+(sl_dist*1.8); side="Buy"
        else: sl=price+sl_dist; tp1=price-(sl_dist*0.8); tp2=price-(sl_dist*1.8); side="Sell"
        balance = get_balance()
        # IMPROVISED: If balance > $100, use 80% not 95% to stay safe
        pct = 0.80 if balance >= 100 else 0.95
        usable = balance * pct
        position_usdt = usable * LEVERAGE
        qty_raw = position_usdt / price
        qty = str(round(max(qty_raw, 0.001), 4))
        print(f"[ORDER] Bal ${balance:.2f} ({pct*100:.0f}%) -> ${position_usdt:.2f} Qty {qty} | {direction} | {scan['driver']} | SL {sl} TP1 {tp1} TP2 {tp2}")
        client.place_order(category=CATEGORY, symbol=SYMBOL, side=side, orderType="Market", qty=qty,
                           takeProfit=str(tp2), stopLoss=str(sl), tpTriggerBy="LastPrice", slTriggerBy="LastPrice", positionIdx=0)
        STATE.update({"trading":True,"entry_price":price,"side":direction,"tp1_done":False,"tp1_price":tp1,"friend":scan["driver"],"sl_dist":sl_dist})
    except Exception as e: print(f"[ORDER ERR] {e}")

def check_partial():
    if not STATE["trading"] or STATE["tp1_done"]: return
    try:
        current=float(client.get_tickers(category=CATEGORY, symbol=SYMBOL)["result"]["list"][0]["lastPrice"])
        tp1,entry,side=STATE["tp1_price"],STATE["entry_price"],STATE["side"]
        hit=(side=="LONG" and current>=tp1) or (side=="SHORT" and current<=tp1)
        if hit:
            pos=client.get_positions(category=CATEGORY, symbol=SYMBOL); size=float(pos["result"]["list"][0]["size"])
            if size>0:
                close_qty=str(round(size*0.5,4))
                client.place_order(category=CATEGORY, symbol=SYMBOL, side="Sell" if side=="LONG" else "Buy", orderType="Market", qty=close_qty, reduceOnly=True, positionIdx=0)
            client.set_trading_stop(category=CATEGORY, symbol=SYMBOL, stopLoss=str(entry), slTriggerBy="LastPrice", positionIdx=0)
            print(f"[BREAKEVEN] SL->{entry}"); STATE["tp1_done"]=True
    except Exception as e: print(f"[TP ERR] {e}")

def check_closed():
    if not STATE["trading"]: return
    try:
        if float(client.get_positions(category=CATEGORY, symbol=SYMBOL)["result"]["list"][0]["size"])==0:
            print("[RESET] Closed! Vigilant!"); STATE.update({"trading":False,"tp1_done":False,"side":None})
    except: pass

def main():
    print("[V4.4.18 FINAL IMPROVISED] Fixed bracket, cached premium, safe pct, balance growth log")
    while True:
        try:
            should,direction,scan=soldier_decision()
            if should: place_order(direction,scan)
            check_partial(); check_closed(); time.sleep(5)
        except Exception as e: print(f"[MAIN ERR] {e}"); time.sleep(5)

if __name__=="__main__": main()
