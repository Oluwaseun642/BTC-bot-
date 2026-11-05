# main.py - HEART - V23 TWO HANDS SAME DIRECTION DOUBLE WIN - PAPER MODE
# User correct: Earlier 2 hands make losses rapidly, so 2 hands go make profits rapidly too. Let both hands go same direction.
# Flow: Hand 1 smeller enters >=20%, Hand 2 joiner enters if MOUSE grow stronger + price move cover fee, at -0.01 building point. Both hold for 0.00, both TP @ 0.00 together, both go back smell foundation.
# If Hand 2 profit no go over fee, e no trigger. If e go over am, e join. BE $0.00 still dey, losses gone.

import time, os, threading, json, hmac, hashlib
from flask import Flask
import requests
import websocket

QTY = 0.001
LEV = 120
MIN_ORDER_PCT = 0.20
MOUSE_WINDOW = 10
MAKER_FEE_RATE = 0.0001

PAPER_WINS = 0
PAPER_LOSSES = 0
PAPER_PNL = 0.0
PAPER_BREAKEVEN = 0
HANDS = []  # V23: Max 2 hands, same direction
ACCOUNT_BALANCE = 3.0

last_price = 79000
last_vol_reset = time.time()
LAST_SUMMARY_TIME = 0
PREV_MOUSE_DOM = 0
BUY_VOL = []
SELL_VOL = []
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
    return f"Heart Bot PAPER V23 TWO HANDS - Price {last_price} Hands {len(HANDS)} Wins {PAPER_WINS} BE {PAPER_BREAKEVEN} Losses {PAPER_LOSSES} WinRate {wr:.0f}% PnL ${PAPER_PNL:.4f} Bal ${ACCOUNT_BALANCE:.2f}"
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
    print(f"[PAPER] {side} {QTY} @ {price:.1f} - PAPER FILL LIMIT MAKER", flush=True)

def get_fee(entry):
    return entry * QTY * MAKER_FEE_RATE

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
    now = time.time()
    b = sum([v for t,v in BUY_VOL if now - t < MOUSE_WINDOW])
    s = sum([v for t,v in SELL_VOL if now - t < MOUSE_WINDOW])
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
        print(f"[SUMMARY] 1min | {get_score_str(price)} | Hands {len(HANDS)}/2 | Price {price:.1f} | MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} Order% {abs(mouse_dom)*100:.1f}% | Bal ${ACCOUNT_BALANCE:.2f} | V23 TWO HANDS", flush=True)

    # HAVE HANDS - Manage 1 or 2 hands, same direction, TP @ 0.00 together
    if len(HANDS) > 0:
        side = HANDS[0]['side']
        entry_pct_1 = HANDS[0]['entry_pct']
        hold1 = int(time.time() - HANDS[0]['enter_time'])
        fee1 = get_fee(HANDS[0]['entry'])
        # CROSS still dey
        crossed = False
        if side == 'SELL' and PREV_MOUSE_DOM < 0 and mouse_dom >= 0:
            crossed = True
        if side == 'BUY' and PREV_MOUSE_DOM > 0 and mouse_dom <= 0:
            crossed = True
        if abs(mouse_dom) < 0.05:
            crossed = True
        # WEAK - Use Hand 1 Entry% for rule: High % wait big weaken, Low % grab small weaken
        weakening = False
        weaken_amt = 0
        if PREV_MOUSE_DOM != 0:
            weaken_amt = abs(PREV_MOUSE_DOM) - abs(mouse_dom)
            if entry_pct_1 >= 0.80:
                if weaken_amt >= 0.10:
                    weakening = True
            elif entry_pct_1 >= 0.50:
                if weaken_amt >= 0.05:
                    weakening = True
            else:
                if weaken_amt >= 0.01:
                    weakening = True
        max_hold = hold1 >= 40
        # Price stuck if MOUSE no move + price no move
        price_stuck = abs(price - HANDS[0]['entry']) < 3 and hold1 >= 15 and abs(mouse_dom - PREV_MOUSE_DOM) < 0.01

        # V23: HAND 2 JOIN - If we have only 1 hand, and MOUSE don grow stronger in same direction, and price move go cover fee, join!
        if len(HANDS) == 1 and not crossed and not weakening:
            h1 = HANDS[0]
            # Condition 1: MOUSE stronger by 0.15+ from entry, same direction
            stronger = abs(mouse_dom) >= h1['entry_pct'] + 0.15
            # Condition 2: Price don move $5 for our side, so Hand 2 profit go over fee ($8 feeMove, $5 move + stronger MOUSE = e go over am)
            price_cover = False
            if side == 'BUY' and price >= h1['entry'] + 5:
                price_cover = True
            if side == 'SELL' and price <= h1['entry'] - 5:
                price_cover = True
            # Condition 3: MOUSE still >= 40%, still strong, no be weak heart
            still_strong = abs(mouse_dom) >= 0.40
            if stronger and price_cover and still_strong:
                # Hand 2 join same direction at -0.01 building point
                fee2 = get_fee(price)
                HANDS.append({'entry': price, 'id': 2 if side == 'SELL' else 1, 'enter_time': time.time(), 'breakeven': False, 'side': side, 'entry_pct': abs(mouse_dom)})
                print(f"[HAND 2 {side}] 🔥 JOIN! Hand 1 Entry {h1['entry']:.1f} Entry% {h1['entry_pct']*100:.1f}% -> Now MOUSE {mouse_dom:.3f} Order% {abs(mouse_dom)*100:.1f}% Stronger +0.15, Price Move $5+, Fee Cover Yes | Join @ {price:.1f} Same Direction, Both Go To 0.00 | {get_score_str(price)}", flush=True)
                place_order_paper("Buy" if side == 'BUY' else "Sell", price)
                PREV_MOUSE_DOM = mouse_dom
                return
            # If Hand 2 no go cover fee, e no trigger - log am
            # (We no log every time to avoid spam, only when stronger but price no cover)
        
        # EXIT BOTH HANDS TOGETHER @ 0.00
        if crossed or weakening or max_hold or price_stuck:
            total_gross = 0
            total_fee = 0
            for h in HANDS:
                if h['side'] == 'BUY':
                    total_gross += (price - h['entry']) * QTY
                else:
                    total_gross += (h['entry'] - price) * QTY
                total_fee += get_fee(h['entry'])
            total_net = total_gross - total_fee
            if total_net >= 0.002:
                PAPER_WINS += 1
                PAPER_PNL += total_net
                ACCOUNT_BALANCE += total_net
                print(f"[HANDS {len(HANDS)}x {side}] ✅ WIN @ 0.00! CROSS={crossed} WEAK={weakening} Weaken {weaken_amt:.3f} Prev {PREV_MOUSE_DOM:.3f} -> Now {mouse_dom:.3f} | Hold {hold1}s Price {price:.1f} Hands {len(HANDS)} Gross ${total_gross:.4f} Fee ${total_fee:.4f} Net ${total_net:.4f} DOUBLE WIN! | {get_score_str(price)}", flush=True)
            else:
                PAPER_BREAKEVEN += 1
                print(f"[HANDS {len(HANDS)}x {side}] ⏰ BE @ 0.00! CROSS={crossed} WEAK={weakening} MAXHOLD={max_hold} STUCK={price_stuck} Prev {PREV_MOUSE_DOM:.3f} -> Now {mouse_dom:.3f} | Hold {hold1}s Price {price:.1f} Gross ${total_gross:.4f} Fee ${total_fee:.4f} Net ${total_net:.4f} No Loss | {get_score_str(price)}", flush=True)
            place_order_paper("Sell" if side == 'BUY' else "Buy", price)
            HANDS.clear()
            PREV_MOUSE_DOM = mouse_dom
            return
        # BE KILLER for both hands
        if side == 'BUY' and price <= HANDS[0]['entry'] - 40:
            PAPER_BREAKEVEN += 1
            print(f"[HANDS {len(HANDS)}x BUY] 🛑 BE KILLER - Price go against, both comot BE $0.00 | Hold {hold1}s Price {price:.1f} | {get_score_str(price)}", flush=True)
            place_order_paper("Sell", price)
            HANDS.clear()
            PREV_MOUSE_DOM = mouse_dom
            return
        if side == 'SELL' and price >= HANDS[0]['entry'] + 40:
            PAPER_BREAKEVEN += 1
            print(f"[HANDS {len(HANDS)}x SELL] 🛑 BE KILLER - Price go against, both comot BE $0.00 | Hold {hold1}s Price {price:.1f} | {get_score_str(price)}", flush=True)
            place_order_paper("Buy", price)
            HANDS.clear()
            PREV_MOUSE_DOM = mouse_dom
            return
        print(f"[HANDS {len(HANDS)}x {side}] Hold for 0.00... MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} Order% {abs(mouse_dom)*100:.1f}% Entry% {entry_pct_1*100:.1f}% Weak {weakening} Weaken {weaken_amt:.3f} Price {price:.1f} Entry {HANDS[0]['entry']:.1f} TP @ 0.00 Hold {hold1}s | {get_score_str(price)}", flush=True)
        PREV_MOUSE_DOM = mouse_dom
        return

    # NO HAND - Smell foundation, Hand 1 enter
    order_pct = abs(mouse_dom)
    if order_pct < 0.01:
        print(f"[ROOF] MOUSE {mouse_dom:.3f} na 0.00, wait 0.5s | {get_score_str(price)}", flush=True)
        PREV_MOUSE_DOM = mouse_dom
        return
    if order_pct < MIN_ORDER_PCT:
        print(f"[SKIP] Order% {order_pct*100:.1f}% too small, no go cover fee, skip | MOUSE {mouse_dom:.3f} Price {price:.1f} | {get_score_str(price)}", flush=True)
        PREV_MOUSE_DOM = mouse_dom
        return
    direction = "SELL" if mouse_dom < 0 else "BUY"
    ENTRY = price
    fee = get_fee(ENTRY)
    fee_move = fee / QTY
    HANDS.append({'entry': ENTRY, 'id': 2 if direction == 'SELL' else 1, 'enter_time': time.time(), 'breakeven': False, 'side': direction, 'entry_pct': order_pct})
    print(f"[HAND 1 {direction}] 🔥 ENTER %CHECK PASS @ {ENTRY:.1f} QTY {QTY} LEV {LEV}x | MOUSE {mouse_dom:.3f} Order% {order_pct*100:.1f}% >=20% Maker Fee ${fee:.4f} FeeMove ${fee_move:.1f} | TP ALWAYS @ 0.00, Hand 2 go join if stronger | {get_score_str(price)} | V23 TWO HANDS - PAPER", flush=True)
    place_order_paper("Buy" if direction == 'BUY' else "Sell", price)
    PREV_MOUSE_DOM = mouse_dom

def on_message(ws, message):
    global last_price, BUY_VOL, SELL_VOL, total_vol_1min
    try:
        data = json.loads(message)
        topic = data.get("topic", "")
        if "publicTrade.BTCUSDT" in topic:
            for t in data.get("data", []):
                p = float(t["p"]); s = float(t["v"]); side = t["S"]; vol = p * s
                last_price = p
                total_vol_1min += vol
                if side == "Buy":
                    BUY_VOL.append((time.time(), vol))
                else:
                    SELL_VOL.append((time.time(), vol))
                BUY_VOL = [(tt, vv) for tt, vv in BUY_VOL if time.time() - tt < MOUSE_WINDOW]
                SELL_VOL = [(tt, vv) for tt, vv in SELL_VOL if time.time() - tt < MOUSE_WINDOW]
    except Exception as e:
        print(f"[EYE] Error {e}", flush=True)

def on_open(ws):
    print("[EYE] 👁️ Eye don open! PAPER V23 TWO HANDS!", flush=True)
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
    print("[WATCHER] Watcher start - V23 TWO HANDS 0.5s...", flush=True)
    while True:
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
    print("V23 TWO HANDS Heart Bot start! Paper!", flush=True)
    app.run(host="0.0.0.0", port=10000)
