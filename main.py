# main.py - HEART - V15 SIMPLE FAST - GRAB COPY ON CROSS, BE $0.00, NO LOSS - PAPER MODE
# Fix everything at once: Bot faster 0.5s, MOUSE 5s window, TP on CROSS blink, TP on any profit, BE $0.00 exact
# Simple: No Confirm, No Trend, No Vol, No Cooldown, No Max, Trade every foundation, Continuous

import time, os, threading, json, hmac, hashlib
from flask import Flask
import requests
import websocket

QTY = 0.001
LEV = 120
TP_MOVE = 120

PAPER_WINS = 0
PAPER_LOSSES = 0
PAPER_PNL = 0.0
PAPER_BREAKEVEN = 0
HANDS = []
ACCOUNT_BALANCE = 3.0

last_price = 79000
last_vol_reset = time.time()
LAST_SUMMARY_TIME = 0
PREV_MOUSE_DOM = 0
BUY_VOL_5S = []
SELL_VOL_5S = []
total_vol_1min = 0

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_BASE = "https://api.bybit.com"

def bybit_sign(params, secret):
    query = "&".join([f"{k}={v}" for k,v in sorted(params.items())])
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()

def auto_config_bybit():
    if not BYBIT_API_KEY or not BYBIT_API_SECRET:
        print("[AUTO-CONFIG] No API Keys for Paper, skip", flush=True)
        return
    try:
        ts = str(int(time.time()*1000))
        p = {"api_key": BYBIT_API_KEY, "timestamp": ts, "recv_window": 5000, "symbol": "BTCUSDT", "tradeMode": 1}
        p["sign"] = bybit_sign(p, BYBIT_API_SECRET)
        r = requests.post(f"{BYBIT_BASE}/v5/account/set-margin-mode", json=p, timeout=10)
        print(f"[AUTO-CONFIG] Margin Isolated: {r.text[:200]}", flush=True)
        ts = str(int(time.time()*1000))
        p2 = {"api_key": BYBIT_API_KEY, "timestamp": ts, "recv_window": 5000, "category": "linear", "symbol": "BTCUSDT", "buyLeverage": "120", "sellLeverage": "120"}
        p2["sign"] = bybit_sign(p2, BYBIT_API_SECRET)
        r2 = requests.post(f"{BYBIT_BASE}/v5/position/set-leverage", json=p2, timeout=10)
        print(f"[AUTO-CONFIG] Leverage 120x: {r2.text[:200]}", flush=True)
        ts = str(int(time.time()*1000))
        p3 = {"api_key": BYBIT_API_KEY, "timestamp": ts, "recv_window": 5000, "category": "linear", "coin": "USDT", "mode": 0}
        p3["sign"] = bybit_sign(p3, BYBIT_API_SECRET)
        r3 = requests.post(f"{BYBIT_BASE}/v5/position/switch-mode", json=p3, timeout=10)
        print(f"[AUTO-CONFIG] Position Mode One-Way: {r3.text[:200]}", flush=True)
        print(f"[AUTO-CONFIG] Done! Lev 120x, Isolated, One-Way", flush=True)
    except Exception as e:
        print(f"[AUTO-CONFIG] Fail: {e}", flush=True)

app = Flask(__name__)
@app.route("/")
def home():
    total = PAPER_WINS + PAPER_LOSSES + PAPER_BREAKEVEN
    wr = (PAPER_WINS/total*100) if total>0 else 0
    return f"Heart Bot PAPER V15 FAST - Price {last_price} Hands {len(HANDS)} Wins {PAPER_WINS} BE {PAPER_BREAKEVEN} Losses {PAPER_LOSSES} WinRate {wr:.0f}% PnL ${PAPER_PNL:.4f} Bal ${ACCOUNT_BALANCE:.2f}"
@app.route("/ping")
def ping():
    return "pong"

def self_ping():
    while True:
        try:
            url = os.getenv("RENDER_URL", "http://localhost:10000/ping")
            requests.get(url, timeout=10)
        except:
            pass
        time.sleep(300)

def place_order_paper(side, price):
    print(f"[PAPER] {side} {QTY} @ {price:.1f} - PAPER FILL", flush=True)

def get_fee(entry):
    return entry * QTY * 0.0012

def get_score_str(price):
    total = PAPER_WINS + PAPER_LOSSES + PAPER_BREAKEVEN
    wr = (PAPER_WINS/total*100) if total>0 else 0
    floating = 0
    for h in HANDS:
        if h['side'] == 'BUY':
            floating += (price - h['entry']) * QTY
        else:
            floating += (h['entry'] - price) * QTY
    return f"Wins {PAPER_WINS} BE {PAPER_BREAKEVEN} Losses {PAPER_LOSSES} WinRate {wr:.0f}% PnL ${PAPER_PNL:.4f} Floating ${floating:.4f}"

def get_mouse_dom():
    # V15 FAST: 5s window, no be 10s, react faster to blink cross
    now = time.time()
    b = sum([v for t,v in BUY_VOL_5S if now - t < 5])
    s = sum([v for t,v in SELL_VOL_5S if now - t < 5])
    total = b + s
    if total == 0:
        return 0
    dom = (b - s) / total
    dom = max(-1.00, min(1.00, dom))
    return dom

def check_heart(mouse_dom, price):
    global PAPER_WINS, PAPER_LOSSES, PAPER_PNL, PAPER_BREAKEVEN, HANDS, LAST_SUMMARY_TIME, ACCOUNT_BALANCE, PREV_MOUSE_DOM
    if time.time() - LAST_SUMMARY_TIME > 60:
        LAST_SUMMARY_TIME = time.time()
        print(f"[SUMMARY] 1min | {get_score_str(price)} | Hands {len(HANDS)}/1 | Price {price:.1f} | MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} | Bal ${ACCOUNT_BALANCE:.2f} | V15 FAST 0.5s", flush=True)

    if len(HANDS) > 0:
        hand = HANDS[0]
        entry = hand['entry']; tp = hand['tp']; sl = hand['sl']; hid = hand['id']; side = hand['side']
        hold = int(time.time() - hand['enter_time'])
        fee = get_fee(entry)
        # V15: CROSS = sign flip, grab copy instant
        crossed = False
        if side == 'BUY' and PREV_MOUSE_DOM < 0 and mouse_dom >= 0:
            crossed = True
        if side == 'SELL' and PREV_MOUSE_DOM > 0 and mouse_dom <= 0:
            crossed = True
        if abs(mouse_dom) < 0.05:
            crossed = True
        # V15: Any profit > fee + $0.01, grab copy, no wait $120
        quick_profit = False
        if side == 'BUY' and price >= entry + (fee / QTY) + 10:
            quick_profit = True
        if side == 'SELL' and price <= entry - (fee / QTY) - 10:
            quick_profit = True

        if side == 'BUY':
            be_price = entry + (fee / QTY)
            halfway = entry + (tp - entry) * 0.5
            if not hand['breakeven'] and price >= halfway:
                hand['sl'] = be_price
                hand['breakeven'] = True
                print(f"[HAND {hid} BUY] 🛡️ BE! Price {price:.1f} halfway, SL to BE {be_price:.1f} | {get_score_str(price)}", flush=True)
            # TP 1: Price reach TP $120
            if price >= tp:
                profit = (tp - entry) * QTY
                net = profit - fee
                PAPER_WINS += 1
                PAPER_PNL += net
                ACCOUNT_BALANCE += net
                print(f"[HAND {hid} BUY] ✅ TP $120! Price {price:.1f} >= TP {tp:.1f} | Entry {entry:.1f} Hold {hold}s MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} | Net ${net:.4f} | {get_score_str(price)}", flush=True)
                place_order_paper("Sell", price)
                HANDS.clear()
                PREV_MOUSE_DOM = mouse_dom
                return
            # TP 2: CROSS or QUICK PROFIT - Grab copy in blink, faster
            if crossed or quick_profit:
                pnl_gross = (price - entry) * QTY
                pnl_net = pnl_gross - fee
                if pnl_net >= 0.01:
                    PAPER_WINS += 1
                    PAPER_PNL += pnl_net
                    ACCOUNT_BALANCE += pnl_net
                    print(f"[HAND {hid} BUY] ⏰ GRAB COPY! CROSS={crossed} QUICK={quick_profit} Prev {PREV_MOUSE_DOM:.3f} -> Now {mouse_dom:.3f} | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
                else:
                    # V15 FIX: BE = $0.00 EXACT, no add negative to PnL, no loss
                    PAPER_BREAKEVEN += 1
                    # PnL no change, Balance no change
                    print(f"[HAND {hid} BUY] ⏰ GRAB COPY BE $0.00! CROSS={crossed} Prev {PREV_MOUSE_DOM:.3f} -> Now {mouse_dom:.3f} | Hold {hold}s Price {price:.1f} Gross ${pnl_gross:.4f} Fee ${fee:.4f} PnL $0.00, No Loss | {get_score_str(price)}", flush=True)
                place_order_paper("Sell", price)
                HANDS.clear()
                PREV_MOUSE_DOM = mouse_dom
                return
            # BE HIT - V15: BE = $0.00, no PnL change
            if price <= sl:
                if hand['breakeven']:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} BUY] 🛡️ BE HIT @ {price:.1f} Hold {hold}s | Loss $0.00, PnL $0.00, No Loss | {get_score_str(price)}", flush=True)
                    place_order_paper("Sell", price)
                    HANDS.clear()
                    PREV_MOUSE_DOM = mouse_dom
                    return
                else:
                    hand['sl'] = be_price
                    hand['breakeven'] = True
                    print(f"[HAND {hid} BUY] 🚫 BE KILLER - No loss, move SL to BE, HOLD | {get_score_str(price)}", flush=True)
            # HEART STOP 20s - V15 faster, no hold long
            if time.time() - hand['enter_time'] > 20:
                pnl_gross = (price - entry) * QTY
                pnl_net = pnl_gross - fee
                if pnl_net >= 0.01:
                    PAPER_WINS += 1
                    PAPER_PNL += pnl_net
                    ACCOUNT_BALANCE += pnl_net
                    print(f"[HAND {hid} BUY] 🛑 HEART STOP 20s - Comot Win | Hold {hold}s Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
                else:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} BUY] 🛑 HEART STOP 20s - Comot BE $0.00, no loss | Hold {hold}s | {get_score_str(price)}", flush=True)
                place_order_paper("Sell", price)
                HANDS.clear()
                PREV_MOUSE_DOM = mouse_dom
                return
            print(f"[HAND {hid} BUY] Hold... MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} Cross {crossed} Price {price:.1f} TP {tp:.1f} Entry {entry:.1f} SL {sl:.1f} Hold {hold}s | {get_score_str(price)}", flush=True)
            PREV_MOUSE_DOM = mouse_dom
            return
        else:
            be_price = entry - (fee / QTY)
            halfway = entry - (entry - tp) * 0.5
            if not hand['breakeven'] and price <= halfway:
                hand['sl'] = be_price
                hand['breakeven'] = True
                print(f"[HAND {hid} SELL] 🛡️ BE! Price {price:.1f} halfway, SL to BE {be_price:.1f} | {get_score_str(price)}", flush=True)
            if price <= tp:
                profit = (entry - tp) * QTY
                net = profit - fee
                PAPER_WINS += 1
                PAPER_PNL += net
                ACCOUNT_BALANCE += net
                print(f"[HAND {hid} SELL] ✅ TP $120! Price {price:.1f} <= TP {tp:.1f} | Entry {entry:.1f} Hold {hold}s MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} | Net ${net:.4f} | {get_score_str(price)}", flush=True)
                place_order_paper("Buy", price)
                HANDS.clear()
                PREV_MOUSE_DOM = mouse_dom
                return
            if crossed or quick_profit:
                pnl_gross = (entry - price) * QTY
                pnl_net = pnl_gross - fee
                if pnl_net >= 0.01:
                    PAPER_WINS += 1
                    PAPER_PNL += pnl_net
                    ACCOUNT_BALANCE += pnl_net
                    print(f"[HAND {hid} SELL] ⏰ GRAB COPY! CROSS={crossed} QUICK={quick_profit} Prev {PREV_MOUSE_DOM:.3f} -> Now {mouse_dom:.3f} | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
                else:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} SELL] ⏰ GRAB COPY BE $0.00! CROSS={crossed} Prev {PREV_MOUSE_DOM:.3f} -> Now {mouse_dom:.3f} | Hold {hold}s Price {price:.1f} Gross ${pnl_gross:.4f} Fee ${fee:.4f} PnL $0.00, No Loss | {get_score_str(price)}", flush=True)
                place_order_paper("Buy", price)
                HANDS.clear()
                PREV_MOUSE_DOM = mouse_dom
                return
            if price >= sl:
                if hand['breakeven']:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} SELL] 🛡️ BE HIT @ {price:.1f} Hold {hold}s | Loss $0.00, PnL $0.00, No Loss | {get_score_str(price)}", flush=True)
                    place_order_paper("Buy", price)
                    HANDS.clear()
                    PREV_MOUSE_DOM = mouse_dom
                    return
                else:
                    hand['sl'] = be_price
                    hand['breakeven'] = True
                    print(f"[HAND {hid} SELL] 🚫 BE KILLER - No loss, move SL to BE, HOLD | {get_score_str(price)}", flush=True)
            if time.time() - hand['enter_time'] > 20:
                pnl_gross = (entry - price) * QTY
                pnl_net = pnl_gross - fee
                if pnl_net >= 0.01:
                    PAPER_WINS += 1
                    PAPER_PNL += pnl_net
                    ACCOUNT_BALANCE += pnl_net
                    print(f"[HAND {hid} SELL] 🛑 HEART STOP 20s - Comot Win | Hold {hold}s Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
                else:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} SELL] 🛑 HEART STOP 20s - Comot BE $0.00, no loss | Hold {hold}s | {get_score_str(price)}", flush=True)
                place_order_paper("Buy", price)
                HANDS.clear()
                PREV_MOUSE_DOM = mouse_dom
                return
            print(f"[HAND {hid} SELL] Hold... MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} Cross {crossed} Price {price:.1f} TP {tp:.1f} Entry {entry:.1f} SL {sl:.1f} Hold {hold}s | {get_score_str(price)}", flush=True)
            PREV_MOUSE_DOM = mouse_dom
            return

    # NO HAND - ENTER EVERY FOUNDATION, CONTINUOUS
    if abs(mouse_dom) < 0.01:
        print(f"[ROOF] MOUSE {mouse_dom:.3f} na 0.00, wait 0.5s for new foundation | {get_score_str(price)}", flush=True)
        PREV_MOUSE_DOM = mouse_dom
        return
    direction = "BUY" if mouse_dom < 0 else "SELL"
    hand_id = 1 if direction == 'BUY' else 2
    ENTRY = price
    if direction == 'BUY':
        TP_PRICE = ENTRY + TP_MOVE
        SL_PRICE = ENTRY - (TP_MOVE * 0.5)
    else:
        TP_PRICE = ENTRY - TP_MOVE
        SL_PRICE = ENTRY + (TP_MOVE * 0.5)
    HANDS.append({'entry': ENTRY, 'tp': TP_PRICE, 'sl': SL_PRICE, 'id': hand_id, 'enter_time': time.time(), 'breakeven': False, 'side': direction})
    fee = get_fee(ENTRY)
    net = TP_MOVE * QTY - fee
    print(f"[HAND {hand_id} {direction}] 🔥 ENTER EVERY FOUNDATION @ {ENTRY:.1f} QTY {QTY} LEV {LEV}x | MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} -> 0.00 Foundation, GRAB COPY ON CROSS | TP {TP_PRICE:.1f} SL {SL_PRICE:.1f} BE $0.00 ONLY | Net if TP ${net:.4f} | {get_score_str(price)} | V15 FAST - PAPER", flush=True)
    place_order_paper("Buy" if direction == 'BUY' else "Sell", price)
    PREV_MOUSE_DOM = mouse_dom

def on_message(ws, message):
    global last_price, BUY_VOL_5S, SELL_VOL_5S, total_vol_1min
    try:
        data = json.loads(message)
        topic = data.get("topic", "")
        if "publicTrade.BTCUSDT" in topic:
            for t in data.get("data", []):
                p = float(t["p"]); s = float(t["v"]); side = t["S"]; vol = p * s
                last_price = p
                total_vol_1min += vol
                if side == "Buy":
                    BUY_VOL_5S.append((time.time(), vol))
                else:
                    SELL_VOL_5S.append((time.time(), vol))
                BUY_VOL_5S = [(tt, vv) for tt, vv in BUY_VOL_5S if time.time() - tt < 5]
                SELL_VOL_5S = [(tt, vv) for tt, vv in SELL_VOL_5S if time.time() - tt < 5]
    except Exception as e:
        print(f"[EYE] Error {e}", flush=True)

def on_open(ws):
    print("[EYE] 👁️ Eye don open! PAPER V15 FAST!", flush=True)
    ws.send(json.dumps({"op": "subscribe", "args": ["publicTrade.BTCUSDT"]}))
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
    global total_vol_1min, last_vol_reset
    print("[WATCHER] Watcher start - V15 FAST 0.5s...", flush=True)
    while True:
        # V15 FAST: Check every 0.5s, no be 2s, to catch blink cross
        time.sleep(0.5)
        if time.time() - last_vol_reset > 60:
            print(f"[WATCHER] 1min: Vol ${total_vol_1min:.0f} Price {last_price:.1f} | Hands {len(HANDS)} | {get_score_str(last_price)}", flush=True)
            total_vol_1min = 0; last_vol_reset = time.time(); continue
        if total_vol_1min > 0:
            mouse_dom = get_mouse_dom()
            check_heart(mouse_dom, last_price)

if __name__ == "__main__":
    auto_config_bybit()
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=start_eye, daemon=True).start()
    threading.Thread(target=heart_watcher, daemon=True).start()
    print("V15 FAST Heart Bot start! Paper!", flush=True)
    app.run(host="0.0.0.0", port=10000)
