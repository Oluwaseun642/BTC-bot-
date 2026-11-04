# main.py - HEART DEMO - V5.1 PAPER MODE - CHECKED COMPLETE
# Checked: Imports, Flask, Eye, Watcher, Heart -0.02 to 0.00, Paper PnL - ALL COMPLETE
# Real Dominance Heart, No API needed

import time, os, threading, json
from flask import Flask
import requests
import websocket

QTY = 0.001
MIN_VOL = 400_000
MIN_CVD = 5_000
MIN_IMBALANCE = 0.30
MIN_EXP_PCT = 0.15

IN_TRADE = False
ENTRY = 0
TP_PRICE = 0
SL_PRICE = 0
SL_HITS = 0
LAST_SL_TIME = 0
PAPER_WINS = 0
PAPER_LOSSES = 0
PAPER_PNL = 0.0

cvd = 0
total_vol_1min = 0
last_price = 79000
best_bid_qty = 0
best_ask_qty = 0
last_vol_reset = time.time()

app = Flask(__name__)
@app.route("/")
def home():
    return f"Heart Bot PAPER MODE V5.1 - Price {last_price} CVD {cvd} Vol ${total_vol_1min:.0f} InTrade {IN_TRADE} Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}"
@app.route("/ping")
def ping():
    return "pong"

def self_ping():
    while True:
        try:
            url = os.getenv("RENDER_URL", "http://localhost:10000/ping")
            requests.get(url, timeout=10)
            print(f"[SELF-PING] alive {time.strftime('%H:%M:%S')}", flush=True)
        except Exception as e:
            print(f"[SELF-PING] Fail: {e}", flush=True)
        time.sleep(300)

def place_order_paper(side, price):
    print(f"[PAPER] {side} {QTY} @ {price:.1f} - PAPER FILL (Real price, no Bybit order)", flush=True)

def check_heart(dominance, vol_drip, bid_qty, ask_qty, cvd_val, price):
    global IN_TRADE, ENTRY, TP_PRICE, SL_PRICE, SL_HITS, LAST_SL_TIME, PAPER_WINS, PAPER_LOSSES, PAPER_PNL
    # FIXED: 2 SL rest logic - if 60s don pass, reset
    if SL_HITS >= 2:
        if time.time() - LAST_SL_TIME < 60:
            return
        SL_HITS = 0

    if IN_TRADE:
        if price >= TP_PRICE:
            profit = (TP_PRICE - ENTRY) * QTY
            fee = ENTRY * QTY * 0.0011
            net = profit - fee
            PAPER_WINS += 1
            PAPER_PNL += net
            print(f"[HEART] ✅ TP HIT INSIDE HEART! Price {price:.1f} >= TP {TP_PRICE:.1f} | Dom {dominance:.3f} (no reach 0.00 yet) | Net ${net:.4f} | Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f} | COMOT FAST!", flush=True)
            place_order_paper("Sell", price)
            IN_TRADE = False
            return
        if price <= SL_PRICE:
            loss = (ENTRY - SL_PRICE) * QTY
            PAPER_LOSSES += 1
            PAPER_PNL -= loss
            print(f"[HEART] ❌ WIDE SL HIT @ {price:.1f} | Loss ${loss:.4f} | Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}", flush=True)
            place_order_paper("Sell", price)
            SL_HITS += 1
            LAST_SL_TIME = time.time()
            IN_TRADE = False
            return
        if dominance >= 0.00:
            pnl = (price - ENTRY) * QTY
            PAPER_PNL += pnl
            if pnl >= 0:
                PAPER_WINS += 1
            else:
                PAPER_LOSSES += 1
            print(f"[HEART] ⏰ Heart close 0.00, comot PnL ${pnl:.4f}, Total PnL ${PAPER_PNL:.4f}, go back -0.02", flush=True)
            place_order_paper("Sell", price)
            IN_TRADE = False
            return
        print(f"[HEART] Inside... Dom {dominance:.3f} Price {price:.1f} TP {TP_PRICE:.1f}", flush=True)
        return

    imbalance = bid_qty / (bid_qty + ask_qty) if (bid_qty + ask_qty) != 0 else 0
    pressure = max(imbalance, 1 - imbalance)
    exp_move = vol_drip * 0.00035
    exp_pct = (exp_move / price) * 100 if price else 0
    print(f"[CHECK] Dom {dominance:.3f} Vol ${vol_drip:.0f} CVD ${cvd_val:.0f} Imb {imbalance:.2f} Pressure {pressure:.2f} Exp {exp_pct:.2f}%", flush=True)
    if exp_pct < MIN_EXP_PCT:
        print(f"[-0.02] SKIP - Exp {exp_pct:.2f}% too small", flush=True)
        return
    must_pass = (vol_drip >= MIN_VOL) and (-0.50 < dominance < -0.005)
    score_pass = (abs(cvd_val) >= MIN_CVD) or (pressure >= MIN_IMBALANCE)
    if must_pass and score_pass:
        ENTRY = price
        TP_PRICE = ENTRY + exp_move
        SL_PRICE = ENTRY - (exp_move * 0.5)
        IN_TRADE = True
        fee = ENTRY * QTY * 0.0011
        net = exp_move * QTY - fee
        print(f"[HEART] 🔥 ENTER TINY @ {ENTRY:.1f} QTY {QTY} | Vol ${vol_drip:.0f} | Dom {dominance:.3f} | CVD ${cvd_val:.0f} | Pressure {pressure:.2f} | Exp ${exp_move:.0f} ({exp_pct:.2f}%) | TP {TP_PRICE:.1f} INSIDE HEART | SL {SL_PRICE:.1f} | Net if TP ${net:.4f} | PAPER MODE - REAL HEART", flush=True)
        place_order_paper("Buy", price)
    else:
        print(f"[-0.02] No join - Must Vol+Dom: {must_pass}, Score CVD/Pressure: {score_pass}", flush=True)

def on_message(ws, message):
    global cvd, total_vol_1min, last_price, best_bid_qty, best_ask_qty
    try:
        data = json.loads(message)
        topic = data.get("topic", "")
        if "publicTrade.BTCUSDT" in topic:
            for t in data.get("data", []):
                p = float(t["p"]); s = float(t["v"]); side = t["S"]; vol = p * s
                last_price = p
                cvd += vol if side == "Buy" else -vol
                total_vol_1min += vol
        if "orderbook.1.BTCUSDT" in topic:
            ob = data.get("data", {})
            if "b" in ob and ob["b"]:
                best_bid_qty = float(ob["b"][0][1])
            if "a" in ob and ob["a"]:
                best_ask_qty = float(ob["a"][0][1])
    except Exception as e:
        print(f"[EYE] Error {e}", flush=True)

def on_open(ws):
    print("[EYE] 👁️ Eye don open! PAPER MODE V5.1 - Real Heart, No API needed!", flush=True)
    ws.send(json.dumps({"op": "subscribe", "args": ["publicTrade.BTCUSDT", "orderbook.1.BTCUSDT"]}))

def on_error(ws, e):
    print(f"[EYE] Error {e}", flush=True)

def on_close(ws, a, b):
    print("[EYE] Eye close, go reconnect...", flush=True)

# FIXED: Loop reconnect, no recursion pile-up
def start_eye():
    while True:
        try:
            ws = websocket.WebSocketApp("wss://stream.bybit.com/v5/public/linear", on_message=on_message, on_open=on_open, on_error=on_error, on_close=on_close)
            ws.run_forever(ping_interval=20)
        except Exception as e:
            print(f"[EYE] Crash {e}, retry in 3s...", flush=True)
        time.sleep(3)

def heart_watcher():
    global total_vol_1min, last_vol_reset, cvd
    print("[WATCHER] Watcher start - PAPER MODE V5.1 - Real Heart - dey check every 2s...", flush=True)
    while True:
        time.sleep(2)
        if time.time() - last_vol_reset > 60:
            print(f"[WATCHER] 1min: Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f} BidQty {best_bid_qty} AskQty {best_ask_qty} | PAPER Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}", flush=True)
            total_vol_1min = 0
            cvd = 0
            last_vol_reset = time.time()
            continue
        if total_vol_1min > 0:
            dominance = cvd / total_vol_1min
            if IN_TRADE:
                check_heart(dominance, total_vol_1min, best_bid_qty, best_ask_qty, cvd, last_price)
            elif -0.50 < dominance < -0.005:
                print(f"[WATCHER] 👀 -0.02 SIGNAL? Dom {dominance:.3f} Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f}", flush=True)
                check_heart(dominance, total_vol_1min, best_bid_qty, best_ask_qty, cvd, last_price)
            elif int(time.time()) % 30 == 0:
                print(f"[WATCHER] No heart yet - Dom {dominance:.3f} Vol ${total_vol_1min:.0f} Price {last_price:.1f}", flush=True)

if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=start_eye, daemon=True).start()
    threading.Thread(target=heart_watcher, daemon=True).start()
    print("V5.1 PAPER MODE Heart Bot start! Real Heart, No API! CHECKED COMPLETE!", flush=True)
    app.run(host="0.0.0.0", port=10000)
