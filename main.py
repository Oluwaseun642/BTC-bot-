# main.py - HEART DEMO - V4 SCORE SYSTEM - FIXED FILTERS
# Fix from log: Dom -0.012 Vol $401k was rejected, Dom -0.271 Vol $1.5M was ignored
# Now: Vol + Dom must pass, CVD OR Imb must pass - no more 4 locks

import time, os, threading, json, hmac, hashlib
from flask import Flask
import requests
import websocket

QTY = 0.001
MIN_VOL = 400_000
MIN_CVD = 5_000  # Was 50k, too high - log show CVD 4879 for real heart
MIN_IMBALANCE = 0.30  # Was 0.52, too high - real top book na 0.31
MIN_EXP_PCT = 0.15

IN_TRADE = False
ENTRY = 0
TP_PRICE = 0
SL_PRICE = 0
SL_HITS = 0
LAST_SL_TIME = 0

cvd = 0
total_vol_1min = 0
last_price = 79000
best_bid_qty = 0
best_ask_qty = 0
last_vol_reset = time.time()

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
BASE_URL = "https://api-demo.bybit.com"

app = Flask(__name__)
@app.route("/")
def home():
    return f"Heart Bot Alive - V4 Score - Price {last_price} CVD {cvd} Vol ${total_vol_1min:.0f} InTrade {IN_TRADE}"
@app.route("/ping")
def ping():
    return "pong"

def self_ping():
    while True:
        try:
            url = os.getenv("RENDER_URL", "http://localhost:10000/ping")
            requests.get(url, timeout=10)
            print(f"[SELF-PING] alive {time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"[SELF-PING] Fail: {e}")
        time.sleep(300)

def place_order(side, qty):
    if not API_KEY or not API_SECRET:
        print(f"[ORDER] ❌ No API key!")
        return None
    ts = str(int(time.time()*1000))
    recv = "5000"
    params = {"category":"linear","symbol":"BTCUSDT","side":side,"orderType":"Market","qty":str(qty),"timestamp":ts,"recvWindow":recv}
    query = "&".join([f"{k}={v}" for k,v in sorted(params.items())])
    sign = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    headers = {"X-BAPI-API-KEY":API_KEY,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recv,"X-BAPI-SIGN":sign,"Content-Type":"application/json"}
    try:
        r = requests.post(f"{BASE_URL}/v5/order/create", json=params, headers=headers, timeout=10)
        print(f"[ORDER] {side} {qty} -> {r.text[:300]}")
        return r.json()
    except Exception as e:
        print(f"[ORDER] Fail {e}")
        return None

def check_heart(dominance, vol_drip, bid_qty, ask_qty, cvd_val, price):
    global IN_TRADE, ENTRY, TP_PRICE, SL_PRICE, SL_HITS, LAST_SL_TIME
    if SL_HITS >= 2:
        if time.time() - LAST_SL_TIME < 60:
            return
        SL_HITS = 0
    if IN_TRADE:
        if price >= TP_PRICE:
            print(f"[HEART] ✅ TP HIT INSIDE HEART! Price {price:.1f} >= TP {TP_PRICE:.1f} | Dom {dominance:.3f} (no reach 0.00 yet) | COMOT FAST!")
            place_order("Sell", QTY)
            IN_TRADE = False
            return
        if price <= SL_PRICE:
            print(f"[HEART] ❌ WIDE SL HIT @ {price:.1f}")
            place_order("Sell", QTY)
            SL_HITS += 1
            LAST_SL_TIME = time.time()
            IN_TRADE = False
            return
        if dominance >= 0.00:
            print(f"[HEART] ⏰ Heart close 0.00, comot, go back -0.02")
            place_order("Sell", QTY)
            IN_TRADE = False
            return
        print(f"[HEART] Inside... Dom {dominance:.3f} Price {price:.1f} TP {TP_PRICE:.1f}")
        return

    # NOT IN TRADE - SCORE SYSTEM
    imbalance = bid_qty / (bid_qty + ask_qty) if (bid_qty + ask_qty)!=0 else 0
    # If sellers dey for book, imbalance go low - so we check both sides: max(imb, 1-imb)
    # E.g Imb 0.15 means sellers 0.85 strong - that na also pressure!
    pressure = max(imbalance, 1 - imbalance)
    exp_move = vol_drip * 0.00035
    exp_pct = (exp_move / price)*100 if price else 0
    print(f"[CHECK] Dom {dominance:.3f} Vol ${vol_drip:.0f} CVD ${cvd_val:.0f} Imb {imbalance:.2f} Pressure {pressure:.2f} Exp {exp_pct:.2f}%")
    if exp_pct < MIN_EXP_PCT:
        print(f"[-0.02] SKIP - Exp {exp_pct:.2f}% too small")
        return

    # MUST: Vol + Dominance (WIDER: -0.50 to -0.005 to catch -0.271 big move)
    must_pass = (vol_drip >= MIN_VOL) and (-0.50 < dominance < -0.005)
    # SCORE: CVD OR Pressure - only one need pass
    score_pass = (abs(cvd_val) >= MIN_CVD) or (pressure >= MIN_IMBALANCE)

    if must_pass and score_pass:
        ENTRY = price
        TP_PRICE = ENTRY + exp_move
        SL_PRICE = ENTRY - (exp_move*0.5)
        IN_TRADE = True
        fee = ENTRY * QTY * 0.0011
        net = exp_move * QTY - fee
        print(f"[HEART] 🔥 ENTER TINY @ {ENTRY:.1f} QTY {QTY} | Vol ${vol_drip:.0f} | Dom {dominance:.3f} | CVD ${cvd_val:.0f} | Pressure {pressure:.2f} | Exp ${exp_move:.0f} ({exp_pct:.2f}%) | TP {TP_PRICE:.1f} INSIDE HEART | SL {SL_PRICE:.1f} | Net ${net:.4f} | DEMO")
        place_order("Buy", QTY)
    else:
        print(f"[-0.02] No join - Must Vol+Dom: {must_pass}, Score CVD/Pressure: {score_pass}")

def on_message(ws, message):
    global cvd, total_vol_1min, last_price, best_bid_qty, best_ask_qty
    try:
        data = json.loads(message)
        topic = data.get("topic","")
        if "publicTrade.BTCUSDT" in topic:
            for t in data.get("data",[]):
                p=float(t["p"]); s=float(t["v"]); side=t["S"]; vol=p*s
                last_price=p
                cvd += vol if side=="Buy" else -vol
                total_vol_1min += vol
        if "orderbook.1.BTCUSDT" in topic:
            ob=data.get("data",{})
            if "b" in ob and ob["b"]:
                best_bid_qty=float(ob["b"][0][1])
            if "a" in ob and ob["a"]:
                best_ask_qty=float(ob["a"][0][1])
    except Exception as e:
        print(f"[EYE] Error {e}")

def on_open(ws):
    print("[EYE] 👁️ Eye don open! V4 Score System!")
    ws.send(json.dumps({"op":"subscribe","args":["publicTrade.BTCUSDT","orderbook.1.BTCUSDT"]}))
def on_error(ws,e): print(f"[EYE] Error {e}")
def on_close(ws,a,b):
    print("[EYE] Eye close, reconnect...")
    time.sleep(3); start_eye()
def start_eye():
    ws=websocket.WebSocketApp("wss://stream.bybit.com/v5/public/linear", on_message=on_message, on_open=on_open, on_error=on_error, on_close=on_close)
    ws.run_forever(ping_interval=20)

def heart_watcher():
    global total_vol_1min, last_vol_reset, cvd
    print("[WATCHER] Watcher start - V4 - Dom -0.50 to -0.005 - dey check every 2s...")
    while True:
        time.sleep(2)
        if time.time()-last_vol_reset>60:
            print(f"[WATCHER] 1min: Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f} BidQty {best_bid_qty} AskQty {best_ask_qty}")
            total_vol_1min=0; cvd=0; last_vol_reset=time.time(); continue
        if total_vol_1min>0:
            dominance=cvd/total_vol_1min
            if IN_TRADE:
                check_heart(dominance, total_vol_1min, best_bid_qty, best_ask_qty, cvd, last_price)
            elif -0.50 < dominance < -0.005:
                print(f"[WATCHER] 👀 -0.02 SIGNAL? Dom {dominance:.3f} Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f}")
                check_heart(dominance, total_vol_1min, best_bid_qty, best_ask_qty, cvd, last_price)
            elif int(time.time())%30==0:
                print(f"[WATCHER] No heart yet - Dom {dominance:.3f} Vol ${total_vol_1min:.0f} Price {last_price:.1f}")

if __name__=="__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=start_eye, daemon=True).start()
    threading.Thread(target=heart_watcher, daemon=True).start()
    print("V4 Score Heart Bot start! Fixed filters!")
    app.run(host="0.0.0.0", port=10000)
