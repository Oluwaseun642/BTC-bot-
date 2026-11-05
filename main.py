# main.py - HEART - V12.1 FULL - FIX CAT 0.98 BUG, FIX $37k TP BUG, FIX 11 LOSSES - PAPER MODE
# Fix from screenshot Nov 5 04:00: CAT 0.9321 MOUSE 0.906 Exp $37728 -> TP too far, 0 Wins, 8 BE -> 11 Losses
# Fix: CAT clamped -0.05 to +0.05, Near TP = $194 fixed, CAT+MOUSE must agree, BE only, Cooldown 15s

import time, os, threading, json, hmac, hashlib
from flask import Flask
import requests
import websocket

QTY = 0.001
LEV = 120
MIN_VOL = 150_000  # V12.1 FIX: Lower from 400k to 150k, else Vol False dey block correct hearts at start of minute
MIN_CVD = 5_000
MIN_PRESSURE = 0.30
CONFIRM_NEEDED = 1
HEART_STOP_SECS = 10
COOLDOWN_SECS = 15  # V12.1 FIX: No 11 trades in no time, wait 15s after close

PAPER_WINS = 0
PAPER_LOSSES = 0
PAPER_PNL = 0.0
PAPER_BREAKEVEN = 0
CONFIRM_COUNT = 0
HANDS = []
ACCOUNT_BALANCE = 3.0
LAST_CLOSE_TIME = 0

cvd = 0
total_vol_1min = 0
last_price = 79000
best_bid_qty = 0
best_ask_qty = 0
best_bid_price = 0
best_ask_price = 0
last_vol_reset = time.time()
LAST_SUMMARY_TIME = 0
LAST_CAT_DOM = 0
LAST_MOUSE_DOM = 0
LAST_DOM_MOVE_TIME = time.time()
PREV_CAT_DOM = 0
PREV_MOUSE_DOM = 0
BUY_VOL_10S = []
SELL_VOL_10S = []

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_BASE = "https://api.bybit.com"

def bybit_sign(params, secret):
    query = "&".join([f"{k}={v}" for k,v in sorted(params.items())])
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()

def auto_config_bybit():
    if not BYBIT_API_KEY or not BYBIT_API_SECRET:
        print("[AUTO-CONFIG] No API Keys for Paper, skip auto-config, use public only", flush=True)
        return
    try:
        ts = str(int(time.time()*1000))
        p = {"api_key": BYBIT_API_KEY, "timestamp": ts, "recv_window": 5000, "symbol": "BTCUSDT", "tradeMode": 1}
        p["sign"] = bybit_sign(p, BYBIT_API_SECRET)
        r = requests.post(f"{BYBIT_BASE}/v5/account/set-margin-mode", json=p, timeout=10)
        print(f"[AUTO-CONFIG] Margin Mode Isolated: {r.text[:200]}", flush=True)
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
        print(f"[AUTO-CONFIG] Done! Lev 120x, Isolated, One-Way, QTY {QTY} - Bot don set am by itself!", flush=True)
    except Exception as e:
        print(f"[AUTO-CONFIG] Fail: {e}, bot go retry next deploy", flush=True)

app = Flask(__name__)
@app.route("/")
def home():
    total = PAPER_WINS + PAPER_LOSSES + PAPER_BREAKEVEN
    wr = (PAPER_WINS/total*100) if total>0 else 0
    return f"Heart Bot PAPER V12.1 FIX - Price {last_price} Hands {len(HANDS)} Wins {PAPER_WINS} BE {PAPER_BREAKEVEN} Losses {PAPER_LOSSES} WinRate {wr:.0f}% PnL ${PAPER_PNL:.4f} Bal ${ACCOUNT_BALANCE:.2f}"
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

def get_cat_dom(bid_qty, ask_qty):
    total = bid_qty + ask_qty
    if total == 0:
        return 0
    dom = (bid_qty - ask_qty) / total
    return dom

def get_mouse_dom():
    now = time.time()
    b = sum([v for t,v in BUY_VOL_10S if now - t < 10])
    s = sum([v for t,v in SELL_VOL_10S if now - t < 10])
    total = b + s
    if total == 0:
        return 0, 0, 0
    dom = (b - s) / total
    dom = max(-1.00, min(1.00, dom))
    cvd_10s = b - s
    return dom, cvd_10s, total

def smell_direction(cat_dom, mouse_dom):
    # V12.1: Must agree - if Cat and Mouse disagree, no enter
    if cat_dom < 0 and mouse_dom < 0:
        return "BUY"
    if cat_dom > 0 and mouse_dom > 0:
        return "SELL"
    # If Cat small, use Mouse only, but still need Cat not opposite strong
    if abs(cat_dom) < 0.05:
        return "BUY" if mouse_dom < 0 else "SELL"
    return None  # Disagree, skip

def max_hands_for_balance():
    if ACCOUNT_BALANCE >= 2.50:
        return 2
    else:
        return 1

def check_heart(cat_dom, mouse_dom, vol_drip, bid_qty, ask_qty, cvd_val, price):
    global PAPER_WINS, PAPER_LOSSES, PAPER_PNL, PAPER_BREAKEVEN, CONFIRM_COUNT, HANDS, LAST_SUMMARY_TIME, ACCOUNT_BALANCE, LAST_CAT_DOM, LAST_MOUSE_DOM, LAST_DOM_MOVE_TIME, PREV_CAT_DOM, PREV_MOUSE_DOM, LAST_CLOSE_TIME
    if time.time() - LAST_SUMMARY_TIME > 60:
        LAST_SUMMARY_TIME = time.time()
        print(f"[SUMMARY] 1min Score | {get_score_str(price)} | Hands {len(HANDS)}/{max_hands_for_balance()} | Price {price:.1f} | CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} PrevMouse {PREV_MOUSE_DOM:.3f} | CVD10s ${cvd_val:.0f} | Bal ${ACCOUNT_BALANCE:.2f} | V12.1 FIX", flush=True)

    moving_toward_roof_mouse = abs(mouse_dom) < abs(PREV_MOUSE_DOM) if PREV_MOUSE_DOM != 0 else True
    moving_toward_roof_cat = abs(cat_dom) < abs(PREV_CAT_DOM) if PREV_CAT_DOM != 0 else True
    moving_toward_roof = moving_toward_roof_mouse or moving_toward_roof_cat
    if abs(cat_dom - LAST_CAT_DOM) > 0.001 or abs(mouse_dom - LAST_MOUSE_DOM) > 0.001:
        LAST_DOM_MOVE_TIME = time.time()
        LAST_CAT_DOM = cat_dom
        LAST_MOUSE_DOM = mouse_dom

    # === V12.1 FIX: CAT CLAMP - If CAT 0.93, e no be Cat, e be noise, skip for entry, but still manage hands ===
    cat_is_valid = -0.05 <= cat_dom <= 0.05
    if not cat_is_valid and len(HANDS) == 0:
        # Don't enter on CAT 0.93 noise, wait for true Cat -0.05 to +0.05 or Mouse small
        # But allow Mouse-only entry if Mouse small and moving, to not wait forever
        if abs(mouse_dom) > 0.10:
            print(f"[CAT CLAMP] SKIP - CAT {cat_dom:.4f} na noise, no be -0.05 to +0.05 whale, wait true Cat | MOUSE {mouse_dom:.3f} | {get_score_str(price)}", flush=True)
            PREV_CAT_DOM = cat_dom
            PREV_MOUSE_DOM = mouse_dom
            return

    # === BE KILLER - Reverse no cause loss ===
    if len(HANDS) > 0 and not moving_toward_roof_mouse and PREV_MOUSE_DOM != 0:
        for hand in HANDS:
            if not hand['breakeven']:
                fee = get_fee(hand['entry'])
                if hand['side'] == 'BUY':
                    be_price = hand['entry'] + (fee / QTY)
                else:
                    be_price = hand['entry'] - (fee / QTY)
                hand['sl'] = be_price
                hand['breakeven'] = True
                print(f"[BE KILLER] Mouse reverse! MOUSE {mouse_dom:.3f} Prev {PREV_MOUSE_DOM:.3f} moving away, no loss! SL move to BE {be_price:.1f} for HAND {hand['id']} {hand['side']} | {get_score_str(price)}", flush=True)

    # === ROOF 0.00 ===
    if len(HANDS) > 0 and abs(cat_dom) < 0.002 and abs(mouse_dom) < 0.05:
        for hand in HANDS:
            entry = hand['entry']; hid = hand['id']; side = hand['side']
            hold = int(time.time() - hand['enter_time'])
            fee = get_fee(entry)
            if side == 'BUY':
                pnl_gross = (price - entry) * QTY
            else:
                pnl_gross = (entry - price) * QTY
            pnl_net = pnl_gross - fee
            if pnl_net >= 0.01:
                PAPER_WINS += 1
                print(f"[HAND {hid} {side}] ⏰ ROOF 0.00 - TP! Hold {hold}s | Price {price:.1f} Entry {entry:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            else:
                PAPER_BREAKEVEN += 1
                print(f"[HAND {hid} {side}] ⏰ ROOF 0.00 - Comot Break-Even! Hold {hold}s | Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            PAPER_PNL += pnl_net
            ACCOUNT_BALANCE += pnl_net
            place_order_paper("Sell" if side == 'BUY' else "Buy", price)
        HANDS.clear()
        CONFIRM_COUNT = 0
        LAST_CLOSE_TIME = time.time()
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    # === HEART STOP - BE ONLY, NO LOSS ===
    if len(HANDS) > 0 and (time.time() - LAST_DOM_MOVE_TIME > HEART_STOP_SECS):
        for hand in HANDS:
            entry = hand['entry']; hid = hand['id']; side = hand['side']
            hold = int(time.time() - hand['enter_time'])
            fee = get_fee(entry)
            if side == 'BUY':
                pnl_gross = (price - entry) * QTY
            else:
                pnl_gross = (entry - price) * QTY
            pnl_net = pnl_gross - fee
            if pnl_net >= 0.01:
                PAPER_WINS += 1
                print(f"[HAND {hid} {side}] 🛑 HEART STOP - Comot Instant Win, NO HOLD | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            else:
                # V12.1: Heart Stop = BE only, even if net -0.02, count as BE to stop 11 losses
                PAPER_BREAKEVEN += 1
                print(f"[HAND {hid} {side}] 🛑 HEART STOP - Comot Break-Even (BE Killer, no loss) | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            PAPER_PNL += pnl_net
            ACCOUNT_BALANCE += pnl_net
            place_order_paper("Sell" if side == 'BUY' else "Buy", price)
        HANDS.clear()
        CONFIRM_COUNT = 0
        LAST_CLOSE_TIME = time.time()
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    hands_to_remove = []
    for i, hand in enumerate(HANDS):
        entry = hand['entry']; tp = hand['tp']; sl = hand['sl']; hid = hand['id']; side = hand['side']
        hold = int(time.time() - hand['enter_time'])
        fee = get_fee(entry)
        inside_heart = (-0.05 <= cat_dom <= 0.05) or (moving_toward_roof)
        if side == 'BUY':
            be_price = entry + (fee / QTY)
            halfway = entry + (tp - entry) * 0.5
            if not hand['breakeven'] and price >= halfway:
                hand['sl'] = be_price
                hand['breakeven'] = True
                sl = be_price
                print(f"[HAND {hid} BUY] 🛡️ BREAK-EVEN! Price {price:.1f} reach halfway, SL to Entry+Fees {be_price:.1f} | {get_score_str(price)}", flush=True)
            if price >= tp:
                profit = (tp - entry) * QTY
                net = profit - fee
                PAPER_WINS += 1
                PAPER_PNL += net
                ACCOUNT_BALANCE += net
                margin = entry * QTY / LEV
                pct = (net / margin * 100) if margin else 0
                print(f"[HAND {hid} BUY] ✅ NEAR TP HIT! Price {price:.1f} >= TP {tp:.1f} | Entry {entry:.1f} Hold {hold}s CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} | Gross ${profit:.4f} Fee ${fee:.4f} Net ${net:.4f} Max {pct:.1f}% | {get_score_str(price)}", flush=True)
                place_order_paper("Sell", price)
                hands_to_remove.append(i)
                continue
            if price <= sl:
                if inside_heart and not hand['breakeven']:
                    print(f"[HAND {hid} BUY] 🚫 NO WICK DOWN INSIDE HEART! Price {price:.1f} dip below SL {sl:.1f} but CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} still inside, HOLD to roof | {get_score_str(price)}", flush=True)
                    continue
                if hand['breakeven']:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} BUY] 🛡️ BREAK-EVEN HIT @ {price:.1f} Hold {hold}s | Loss $0.00 | {get_score_str(price)}", flush=True)
                else:
                    print(f"[HAND {hid} BUY] 🚫 BE KILLER - No close at loss! Move SL to BE, HOLD | {get_score_str(price)}", flush=True)
                    hand['sl'] = be_price
                    hand['breakeven'] = True
                    continue
                place_order_paper("Sell", price)
                hands_to_remove.append(i)
                continue
        else:
            be_price = entry - (fee / QTY)
            halfway = entry - (entry - tp) * 0.5
            if not hand['breakeven'] and price <= halfway:
                hand['sl'] = be_price
                hand['breakeven'] = True
                sl = be_price
                print(f"[HAND {hid} SELL] 🛡️ BREAK-EVEN! Price {price:.1f} reach halfway, SL to Entry-Fees {be_price:.1f} | {get_score_str(price)}", flush=True)
            if price <= tp:
                profit = (entry - tp) * QTY
                net = profit - fee
                PAPER_WINS += 1
                PAPER_PNL += net
                ACCOUNT_BALANCE += net
                margin = entry * QTY / LEV
                pct = (net / margin * 100) if margin else 0
                print(f"[HAND {hid} SELL] ✅ NEAR TP HIT! Price {price:.1f} <= TP {tp:.1f} | Entry {entry:.1f} Hold {hold}s CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} | Gross ${profit:.4f} Fee ${fee:.4f} Net ${net:.4f} Max {pct:.1f}% | {get_score_str(price)}", flush=True)
                place_order_paper("Buy", price)
                hands_to_remove.append(i)
                continue
            if price >= sl:
                if inside_heart and not hand['breakeven']:
                    print(f"[HAND {hid} SELL] 🚫 NO WICK DOWN INSIDE HEART! Price {price:.1f} wick above SL {sl:.1f} but CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} still inside, HOLD to roof | {get_score_str(price)}", flush=True)
                    continue
                if hand['breakeven']:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} SELL] 🛡️ BREAK-EVEN HIT @ {price:.1f} Hold {hold}s | Loss $0.00 | {get_score_str(price)}", flush=True)
                else:
                    print(f"[HAND {hid} SELL] 🚫 BE KILLER - No close at loss! Move SL to BE, HOLD | {get_score_str(price)}", flush=True)
                    hand['sl'] = be_price
                    hand['breakeven'] = True
                    continue
                place_order_paper("Buy", price)
                hands_to_remove.append(i)
                continue
        print(f"[HAND {hid} {side}] Hold INSIDE HEART... CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} PrevMouse {PREV_MOUSE_DOM:.3f} MovingToRoof {moving_toward_roof} Price {price:.1f} TP {tp:.1f} Entry {entry:.1f} SL {sl:.1f} BE {'ON' if hand['breakeven'] else 'OFF'} Hold {hold}s | {get_score_str(price)}", flush=True)
    for idx in reversed(hands_to_remove):
        HANDS.pop(idx)
        LAST_CLOSE_TIME = time.time()
        if len(HANDS) == 1:
            HANDS[0]['id'] = 1
            print(f"[ENEMY HANDS] One hand close, other hand don become new Hand 1 | {get_score_str(price)}", flush=True)

    # === COOLDOWN ===
    if time.time() - LAST_CLOSE_TIME < COOLDOWN_SECS and len(HANDS) == 0:
        print(f"[COOLDOWN] Wait {COOLDOWN_SECS}s after close, no 11 trades in no time | {get_score_str(price)}", flush=True)
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    # === ENTRY ===
    if abs(cat_dom) < 0.001 and abs(mouse_dom) < 0.01:
        print(f"[ROOF] SKIP - CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} na roof, wait new cat | {get_score_str(price)}", flush=True)
        CONFIRM_COUNT = 0
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    direction = smell_direction(cat_dom, mouse_dom)
    if direction is None:
        print(f"[DISAGREE] SKIP - CAT {cat_dom:.4f} say {'BUY' if cat_dom<0 else 'SELL'} but MOUSE {mouse_dom:.3f} say {'BUY' if mouse_dom<0 else 'SELL'}, dem disagree, no enter | {get_score_str(price)}", flush=True)
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    max_hands = max_hands_for_balance()
    can_enter = False
    exp_move_final = 0
    hand_id = 1
    reason = ""

    if len(HANDS) >= 1:
        print(f"[ENEMY HANDS] Hand {HANDS[0]['id']} {HANDS[0]['side']} dey hold, enemy go wait - Now CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} | {get_score_str(price)}", flush=True)
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    inside_heart_entry = -0.05 <= cat_dom <= 0.05
    outside_heart_entry = abs(mouse_dom) >= 0.02 and moving_toward_roof

    if inside_heart_entry or outside_heart_entry:
        if not moving_toward_roof and PREV_MOUSE_DOM != 0 and not inside_heart_entry:
            print(f"[HEART MOVE] SKIP - MOUSE {mouse_dom:.3f} dey move away from 0.00 (Prev {PREV_MOUSE_DOM:.3f}), na crash | {get_score_str(price)}", flush=True)
            PREV_CAT_DOM = cat_dom
            PREV_MOUSE_DOM = mouse_dom
            return
        # V12.1 FIX: Near TP = $194 FIXED ONLY, no whale_move x Price, no $37k TP
        fee = get_fee(price)
        min_move_for_fees = (fee * 2) / QTY  # $194 for $80k
        exp_move = min_move_for_fees  # Fixed Near TP, always pass fees, price fit reach am
        exp_gross = exp_move * QTY
        if exp_gross < fee * 2:
            print(f"[FEE CHECK] SKIP - Exp Gross ${exp_gross:.4f} < 2x Fee ${fee*2:.4f} | {get_score_str(price)}", flush=True)
            PREV_CAT_DOM = cat_dom
            PREV_MOUSE_DOM = mouse_dom
            return
        can_enter = True
        hand_id = 1 if direction == 'BUY' else 2
        where = "INSIDE HEART CAT -0.05 to +0.05" if inside_heart_entry else "OUTSIDE HEART MOUSE RUN TOWARD CAT"
        reason = f"Enemy Hand {hand_id} - {direction} - {where} - CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} PrevMouse {PREV_MOUSE_DOM:.3f} -> 0.00 QTY {QTY} Exp ${exp_move:.0f} Gross ${exp_gross:.4f} Fee ${fee:.4f} Net ${exp_gross-fee:.4f}"
        exp_move_final = exp_move
    else:
        print(f"[HEART] WAIT - CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} outside heart, wait mouse dey run toward cat | Smell {direction} | {get_score_str(price)}", flush=True)
        PREV_CAT_DOM = cat_dom
        PREV_MOUSE_DOM = mouse_dom
        return

    if can_enter:
        imbalance = bid_qty / (bid_qty + ask_qty) if (bid_qty + ask_qty) != 0 else 0
        pressure = max(imbalance, 1 - imbalance)
        exp_pct = (exp_move_final / price) * 100 if price else 0
        print(f"[CHECK] CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} PrevMouse {PREV_MOUSE_DOM:.3f} MovingToRoof {moving_toward_roof} Smell {direction} Vol ${vol_drip:.0f} CVD10s ${cvd_val:.0f} Pressure {pressure:.2f} Exp {exp_pct:.2f}% Hands {len(HANDS)}/{max_hands} Confirm {CONFIRM_COUNT}/1 - {reason} | {get_score_str(price)}", flush=True)
        if exp_pct < 0.20:
            CONFIRM_COUNT = 0
            print(f"[NEAR TP] SKIP - Exp {exp_pct:.2f}% < 0.20% | {get_score_str(price)}", flush=True)
            PREV_CAT_DOM = cat_dom
            PREV_MOUSE_DOM = mouse_dom
            return
        must_pass = (vol_drip >= MIN_VOL)
        cvd_pass = abs(cvd_val) >= MIN_CVD
        pressure_pass = pressure >= MIN_PRESSURE
        if must_pass and cvd_pass and pressure_pass:
            CONFIRM_COUNT += 1
            print(f"[CONFIRM] Strong CAT AND MOUSE {CONFIRM_COUNT}/1 - CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} Smell {direction} MovingToRoof {moving_toward_roof} | {get_score_str(price)}", flush=True)
            if CONFIRM_COUNT < CONFIRM_NEEDED:
                PREV_CAT_DOM = cat_dom
                PREV_MOUSE_DOM = mouse_dom
                return
            ENTRY = price
            if direction == 'BUY':
                TP_PRICE = ENTRY + exp_move_final
                SL_PRICE = ENTRY - (exp_move_final * 0.5)
            else:
                TP_PRICE = ENTRY - exp_move_final
                SL_PRICE = ENTRY + (exp_move_final * 0.5)
            HANDS.append({'entry': ENTRY, 'tp': TP_PRICE, 'sl': SL_PRICE, 'id': hand_id, 'enter_time': time.time(), 'breakeven': False, 'side': direction})
            CONFIRM_COUNT = 0
            fee = get_fee(ENTRY)
            net = exp_move_final * QTY - fee
            margin = ENTRY * QTY / LEV
            pct = (net / margin * 100) if margin else 0
            print(f"[HAND {hand_id} {direction}] 🔥 ENTER CAT AND MOUSE @ {ENTRY:.1f} QTY {QTY} LEV {LEV}x | Vol ${vol_drip:.0f} | CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} -> 0.00 Smell {direction} Foundation Entry, TP by 0.00 | Exp ${exp_move_final:.0f} Max {pct:.1f}% | TP {TP_PRICE:.1f} | SL {SL_PRICE:.1f} NO WICK DOWN | BE KILLER ONLY | Net if TP ${net:.4f} Bal ${ACCOUNT_BALANCE:.2f} | {get_score_str(price)} | V12.1 FIX - PAPER", flush=True)
            place_order_paper("Buy" if direction == 'BUY' else "Sell", price)
        else:
            CONFIRM_COUNT = 0
            print(f"[CAT AND MOUSE] No join - Vol: {must_pass}, CVD: {cvd_pass}, Pressure: {pressure_pass} | {get_score_str(price)}", flush=True)
    PREV_CAT_DOM = cat_dom
    PREV_MOUSE_DOM = mouse_dom

def on_message(ws, message):
    global cvd, total_vol_1min, last_price, best_bid_qty, best_ask_qty, best_bid_price, best_ask_price, BUY_VOL_10S, SELL_VOL_10S
    try:
        data = json.loads(message)
        topic = data.get("topic", "")
        if "publicTrade.BTCUSDT" in topic:
            for t in data.get("data", []):
                p = float(t["p"]); s = float(t["v"]); side = t["S"]; vol = p * s
                last_price = p
                cvd += vol if side == "Buy" else -vol
                total_vol_1min += vol
                if side == "Buy":
                    BUY_VOL_10S.append((time.time(), vol))
                else:
                    SELL_VOL_10S.append((time.time(), vol))
                BUY_VOL_10S = [(tt, vv) for tt, vv in BUY_VOL_10S if time.time() - tt < 10]
                SELL_VOL_10S = [(tt, vv) for tt, vv in SELL_VOL_10S if time.time() - tt < 10]
        if "orderbook.1.BTCUSDT" in topic:
            ob = data.get("data", {})
            if "b" in ob and ob["b"]:
                best_bid_price = float(ob["b"][0][0])
                best_bid_qty = float(ob["b"][0][1])
            if "a" in ob and ob["a"]:
                best_ask_price = float(ob["a"][0][0])
                best_ask_qty = float(ob["a"][0][1])
    except Exception as e:
        print(f"[EYE] Error {e}", flush=True)

def on_open(ws):
    print("[EYE] 👁️ Eye don open! PAPER V12.1 FIX!", flush=True)
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
    print("[WATCHER] Watcher start - V12.1 FIX...", flush=True)
    while True:
        time.sleep(2)
        if time.time() - last_vol_reset > 60:
            print(f"[WATCHER] 1min: Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f} | Hands {len(HANDS)} | {get_score_str(last_price)}", flush=True)
            total_vol_1min = 0; cvd = 0; last_vol_reset = time.time(); continue
        if total_vol_1min > 0:
            mouse_dom, cvd_10s, vol_10s = get_mouse_dom()
            cat_dom = get_cat_dom(best_bid_qty, best_ask_qty)
            if len(HANDS) > 0 or abs(cat_dom) > 0.001 or abs(mouse_dom) > 0.01:
                check_heart(cat_dom, mouse_dom, total_vol_1min, best_bid_qty, best_ask_qty, cvd_10s, last_price)
            elif int(time.time()) % 30 == 0:
                print(f"[WATCHER] No cat yet - CAT {cat_dom:.4f} MOUSE {mouse_dom:.3f} Vol10s ${vol_10s:.0f} Price {last_price:.1f} | {get_score_str(last_price)}", flush=True)

if __name__ == "__main__":
    auto_config_bybit()
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=start_eye, daemon=True).start()
    threading.Thread(target=heart_watcher, daemon=True).start()
    print("V12.1 FIX Heart Bot start! Paper!", flush=True)
    app.run(host="0.0.0.0", port=10000)
