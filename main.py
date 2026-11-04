# main.py - HEART - V8 TWO HANDS + SEAMLESS - PAPER MODE
# Previous agreement Vol 400k, No daily loss stop, Unlimited trades, Hold till TP, 2 Hands
# Hand1 hold till TP even over roof 0.00, Hand2 enter new -0.02 while Hand1 still dey

import time, os, threading, json
from flask import Flask
import requests
import websocket

QTY = 0.001
LEV = 120  # PAPER simulation for 120x as you want, Real we go talk later
MIN_VOL = 400_000          # PREVIOUS AGREEMENT - back to 400k
MIN_CVD = 5_000            # PREVIOUS AGREEMENT
MIN_PRESSURE = 0.30        # PREVIOUS AGREEMENT
MIN_EXP_PCT = 0.15         # PREVIOUS AGREEMENT
CONFIRM_NEEDED = 2

# SEAMLESS - NO LIMITS FOR DEMO
# No MAX_DAILY_LOSS stop, No MAX_TRADES_PER_HOUR, No SL cooldown
# Unlimited trades till eternity

PAPER_WINS = 0
PAPER_LOSSES = 0
PAPER_PNL = 0.0
CONFIRM_COUNT = 0

# TWO HANDS - List of open positions
# Each hand: {entry, tp, sl, id}
HANDS = []

cvd = 0
total_vol_1min = 0
last_price = 79000
best_bid_qty = 0
best_ask_qty = 0
last_vol_reset = time.time()

app = Flask(__name__)
@app.route("/")
def home():
    return f"Heart Bot PAPER V8 TWO HANDS SEAMLESS - Price {last_price} CVD {cvd} Vol ${total_vol_1min:.0f} Hands {len(HANDS)} Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}"
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
    print(f"[PAPER] {side} {QTY} @ {price:.1f} - PAPER FILL", flush=True)

def check_heart(dominance, vol_drip, bid_qty, ask_qty, cvd_val, price):
    global PAPER_WINS, PAPER_LOSSES, PAPER_PNL, CONFIRM_COUNT, HANDS
    # 1. CHECK HANDS FIRST - Hold till TP, even over roof
    # SEAMLESS: No daily loss stop, no trade limit
    hands_to_remove = []
    for i, hand in enumerate(HANDS):
        entry = hand['entry']; tp = hand['tp']; sl = hand['sl']; hid = hand['id']
        if price >= tp:
            profit = (tp - entry) * QTY
            fee = entry * QTY * 0.0011
            net = profit - fee
            PAPER_WINS += 1
            PAPER_PNL += net
            print(f"[HAND {hid}] ✅ TP HIT! Price {price:.1f} >= TP {tp:.1f} | Entry {entry:.1f} | Net ${net:.4f} | Hands left {len(HANDS)-1} | Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}", flush=True)
            place_order_paper("Sell", price)
            hands_to_remove.append(i)
            continue
        if price <= sl:
            loss = (entry - sl) * QTY
            PAPER_LOSSES += 1
            PAPER_PNL -= loss
            print(f"[HAND {hid}] ❌ SL HIT @ {price:.1f} | Loss ${loss:.4f} | Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}", flush=True)
            place_order_paper("Sell", price)
            hands_to_remove.append(i)
            continue
        # HOLD TILL TP - Even if Dom over roof 0.00, NO close
        # Only close if Dom go too far +0.20 - heart don die finish
        if dominance >= 0.20:
            pnl = (price - entry) * QTY
            pnl_net = pnl - (entry * QTY * 0.0011) if pnl > 0 else pnl
            PAPER_PNL += pnl_net
            if pnl_net >= 0:
                PAPER_WINS += 1
            else:
                PAPER_LOSSES += 1
            print(f"[HAND {hid}] ⏰ Heart die finish Dom {dominance:.3f} >= 0.20, comot PnL ${pnl_net:.4f} | Total PnL ${PAPER_PNL:.4f}", flush=True)
            place_order_paper("Sell", price)
            hands_to_remove.append(i)
            continue
        print(f"[HAND {hid}] Hold... Dom {dominance:.3f} Price {price:.1f} TP {tp:.1f} Entry {entry:.1f} - Hold till TP, no comot for 0.00", flush=True)
    # Remove closed hands (reverse to keep index correct)
    for idx in reversed(hands_to_remove):
        HANDS.pop(idx)

    # 2. CHECK NEW ENTRY - For Hand 1 or Hand 2
    if len(HANDS) >= 2:
        print(f"[SEAMLESS] 2 Hands already open, no Hand 3, wait make one close", flush=True)
        return
    imbalance = bid_qty / (bid_qty + ask_qty) if (bid_qty + ask_qty) != 0 else 0
    pressure = max(imbalance, 1 - imbalance)
    exp_move = vol_drip * 0.00035
    exp_pct = (exp_move / price) * 100 if price else 0
    print(f"[CHECK] Dom {dominance:.3f} Vol ${vol_drip:.0f} CVD ${cvd_val:.0f} Imb {imbalance:.2f} Pressure {pressure:.2f} Exp {exp_pct:.2f}% Hands {len(HANDS)}/2 Confirm {CONFIRM_COUNT}/2", flush=True)
    if exp_pct < MIN_EXP_PCT:
        CONFIRM_COUNT = 0
        print(f"[-0.02] SKIP - Exp {exp_pct:.2f}% too small", flush=True)
        return
    must_pass = (vol_drip >= MIN_VOL) and (-0.50 < dominance < -0.005)
    cvd_pass = abs(cvd_val) >= MIN_CVD
    pressure_pass = pressure >= MIN_PRESSURE
    if must_pass and cvd_pass and pressure_pass:
        CONFIRM_COUNT += 1
        print(f"[CONFIRM] Strong heart {CONFIRM_COUNT}/2 - Dom {dominance:.3f} Vol ${vol_drip:.0f}", flush=True)
        if CONFIRM_COUNT < CONFIRM_NEEDED:
            return
        # ENTER NEW HAND - Hand 1 or Hand 2
        ENTRY = price
        TP_PRICE = ENTRY + exp_move
        SL_PRICE = ENTRY - (exp_move * 0.5)
        hand_id = len(HANDS) + 1 if len(HANDS) == 0 else 2
        # If Hand 1 still dey, this na Hand 2 - Follow-up
        if len(HANDS) == 1:
            hand_id = 2
            print(f"[TWO HANDS] 🔥 Hand 1 still dey hold, Hand 2 dey enter follow-up!", flush=True)
        else:
            hand_id = 1
        HANDS.append({'entry': ENTRY, 'tp': TP_PRICE, 'sl': SL_PRICE, 'id': hand_id})
        CONFIRM_COUNT = 0
        fee = ENTRY * QTY * 0.0011
        net = exp_move * QTY - fee
        print(f"[HAND {hand_id}] 🔥 ENTER @ {ENTRY:.1f} QTY {QTY} LEV {LEV}x | Vol ${vol_drip:.0f} | Dom {dominance:.3f} | CVD ${cvd_val:.0f} | Pressure {pressure:.2f} | Exp ${exp_move:.0f} ({exp_pct:.2f}%) | TP {TP_PRICE:.1f} HOLD TILL TP | SL {SL_PRICE:.1f} | Net if TP ${net:.4f} | V8 TWO HANDS SEAMLESS - PAPER", flush=True)
        place_order_paper("Buy", price)
    else:
        CONFIRM_COUNT = 0
        print(f"[-0.02] No join - Vol+Dom: {must_pass}, CVD>=5k: {cvd_pass}, Pressure>=0.30: {pressure_pass}", flush=True)

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
    print("[EYE] 👁️ Eye don open! PAPER V8 TWO HANDS SEAMLESS - Unlimited, No stop!", flush=True)
    ws.send(json.dumps({"op": "subscribe", "args": ["publicTrade.BTCUSDT", "orderbook.1.BTCUSDT"]}))
def on_error(ws, e): print(f"[EYE] Error {e}", flush=True)
def on_close(ws, a, b): print("[EYE] Eye close, go reconnect...", flush=True)

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
    print("[WATCHER] Watcher start - V8 TWO HANDS SEAMLESS - dey check every 2s...", flush=True)
    while True:
        time.sleep(2)
        if time.time() - last_vol_reset > 60:
            print(f"[WATCHER] 1min: Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f} | Hands {len(HANDS)} | PAPER Wins {PAPER_WINS} Losses {PAPER_LOSSES} PnL ${PAPER_PNL:.4f}", flush=True)
            total_vol_1min = 0; cvd = 0; last_vol_reset = time.time(); continue
        if total_vol_1min > 0:
            dominance = cvd / total_vol_1min
            # SEAMLESS: Always check, even if hands open (for Hand 2) or no hands
            # Check if in trade (hands) OR new signal -0.02
            if len(HANDS) > 0 or (-0.50 < dominance < -0.005):
                check_heart(dominance, total_vol_1min, best_bid_qty, best_ask_qty, cvd, last_price)
            elif int(time.time()) % 30 == 0:
                print(f"[WATCHER] No heart yet - Dom {dominance:.3f} Vol ${total_vol_1min:.0f} Price {last_price:.1f}", flush=True)

if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=start_eye, daemon=True).start()
    threading.Thread(target=heart_watcher, daemon=True).start()
    print("V8 TWO HANDS SEAMLESS Heart Bot start! Unlimited, No stop, Paper!", flush=True)
    app.run(host="0.0.0.0", port=10000)
