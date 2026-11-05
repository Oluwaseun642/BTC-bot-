# main.py - HEART - V11.5 FULL - NO FLOATING + PROFIT COVER FEES - PAPER MODE
# Combine all: V11.3 + V11.4 + V11.4.1 + V11.5 Floating Killer
# - Inside heart only -0.02 to 0.00, Thrice steps, No Wick Down, No Hold
# - Bybit Min QTY 0.001, Dynamic Hands for $3, Smell BUY/SELL Follow to TP
# - Auto-Config: Bot set Lev 120x, Isolated, One-Way by itself
# - Floating Killer: Dom comot from heart = comot instantly, no floating
# - Profit must cover Fees + Lev Fees: Exp Gross >= 2x Fee, else skip
# - Heart pump = Stay, Heart stop 10s = Comot, Heart reach 0.00 = Comot Instant Win

import time, os, threading, json, hmac, hashlib
from flask import Flask
import requests
import websocket

QTY = 0.001  # Bybit Min, no below this, no 0.0006 again
LEV = 120
MIN_VOL = 400_000
MIN_CVD = 5_000
MIN_PRESSURE = 0.30
MIN_EXP_PCT = 0.15
CONFIRM_NEEDED = 1
DOM_ROOF = 0.00
DOM_CRASH = -0.20
DOM_FOUNDATION_BUY = -0.025
DOM_FOUNDATION_SELL = 0.025
MAX_CVD_CRASH = -1_000_000
HEART_STOP_SECS = 10  # If Dom no move toward 0.00 for 10 secs, heart don stop, comot instantly
FLOATING_KILLER_DOM = 0.03  # If Dom > 0.03, heart don break, kill floating instantly

PAPER_WINS = 0
PAPER_LOSSES = 0
PAPER_PNL = 0.0
PAPER_BREAKEVEN = 0
CONFIRM_COUNT = 0
HANDS = []
CVD_HISTORY = []
ACCOUNT_BALANCE = 3.0  # $3

cvd = 0
total_vol_1min = 0
last_price = 79000
best_bid_qty = 0
best_ask_qty = 0
last_vol_reset = time.time()
LAST_SUMMARY_TIME = 0
LAST_DOM = 0
LAST_DOM_MOVE_TIME = time.time()

# V11.4.1 AUTO-CONFIG
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
    return f"Heart Bot PAPER V11.5 NO FLOATING - Price {last_price} Hands {len(HANDS)} Wins {PAPER_WINS} BE {PAPER_BREAKEVEN} Losses {PAPER_LOSSES} WinRate {wr:.0f}% PnL ${PAPER_PNL:.4f} Bal ${ACCOUNT_BALANCE:.2f}"
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
    # Fee = 0.12% = Taker 0.055% x2 + Funding 0.01% - Cover Lev Fees + Trading Fees
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

def smell_direction():
    if len(CVD_HISTORY) < 2:
        return "BUY"
    old_cvd = CVD_HISTORY[0][1]
    new_cvd = CVD_HISTORY[-1][1]
    if new_cvd > old_cvd:
        return "BUY"
    elif new_cvd < old_cvd:
        return "SELL"
    else:
        return "BUY"

def max_hands_for_balance():
    # Dynamic for $3: If balance >= 2.50, 2 Hands fit (Margin $1.32). If < 2.50, 1 Hand only to protect $3.
    if ACCOUNT_BALANCE >= 2.50:
        return 2
    else:
        return 1

def check_heart(dominance, vol_drip, bid_qty, ask_qty, cvd_val, price):
    global PAPER_WINS, PAPER_LOSSES, PAPER_PNL, PAPER_BREAKEVEN, CONFIRM_COUNT, HANDS, LAST_SUMMARY_TIME, ACCOUNT_BALANCE, LAST_DOM, LAST_DOM_MOVE_TIME
    if time.time() - LAST_SUMMARY_TIME > 60:
        LAST_SUMMARY_TIME = time.time()
        print(f"[SUMMARY] 1min Score | {get_score_str(price)} | Hands {len(HANDS)}/{max_hands_for_balance()} | Price {price:.1f} | Dom {dominance:.3f} | CVD ${cvd_val:.0f} | Smell {smell_direction()} | Bal ${ACCOUNT_BALANCE:.2f}", flush=True)

    # Track Dom movement for Heart Stop check
    if abs(dominance - LAST_DOM) > 0.001:
        LAST_DOM_MOVE_TIME = time.time()
        LAST_DOM = dominance

    # V11.5 FIX: FLOATING KILLER - If Dom don comot from heart > 0.03, kill floating instantly, no hold
    if len(HANDS) > 0 and abs(dominance) > FLOATING_KILLER_DOM:
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
                print(f"[HAND {hid} {side}] 💥 FLOATING KILLER! Dom {dominance:.3f} don comot from heart, comot Instant Win, NO FLOATING | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            elif pnl_net >= -0.005:
                PAPER_BREAKEVEN += 1
                print(f"[HAND {hid} {side}] 💥 FLOATING KILLER! Dom {dominance:.3f} don comot, comot Break-Even, NO FLOATING | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            else:
                PAPER_LOSSES += 1
                print(f"[HAND {hid} {side}] 💥 FLOATING KILLER! Dom {dominance:.3f} don comot, comot Small Loss, NO FLOATING | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            PAPER_PNL += pnl_net
            ACCOUNT_BALANCE += pnl_net
            place_order_paper("Sell" if side == 'BUY' else "Buy", price)
        HANDS.clear()
        CONFIRM_COUNT = 0
        return

    # NO HOLD: Roof = Instant TP, comot, no hold
    if len(HANDS) > 0 and abs(dominance) < 0.002:
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
                print(f"[HAND {hid} {side}] ⏰ ROOF 0.00 - NO HOLD, Comot Instant Win! Hold {hold}s ONLY, Heart pump finish | Price {price:.1f} Entry {entry:.1f} Gross ${pnl_gross:.4f} Fee ${fee:.4f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            elif pnl_net >= -0.005:
                PAPER_BREAKEVEN += 1
                print(f"[HAND {hid} {side}] ⏰ ROOF 0.00 - NO HOLD, Comot Break-Even! Hold {hold}s ONLY | Price {price:.1f} Entry {entry:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            else:
                PAPER_LOSSES += 1
                print(f"[HAND {hid} {side}] ⏰ ROOF 0.00 - NO HOLD, Comot Small Loss | Hold {hold}s Price {price:.1f} Entry {entry:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            PAPER_PNL += pnl_net
            ACCOUNT_BALANCE += pnl_net
            place_order_paper("Sell" if side == 'BUY' else "Buy", price)
        HANDS.clear()
        CONFIRM_COUNT = 0
        return

    # NO HOLD: Heart Stop - If Dom no move toward 0.00 for 10 secs, heart don stop pumping, comot instantly, no hold 3 mins
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
                print(f"[HAND {hid} {side}] 🛑 HEART STOP - Dom no move for {HEART_STOP_SECS}s, heart don stop pumping, comot Instant Win, NO HOLD | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            elif pnl_net >= -0.005:
                PAPER_BREAKEVEN += 1
                print(f"[HAND {hid} {side}] 🛑 HEART STOP - Dom no move for {HEART_STOP_SECS}s, comot Break-Even, NO HOLD | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            else:
                PAPER_LOSSES += 1
                print(f"[HAND {hid} {side}] 🛑 HEART STOP - Dom no move for {HEART_STOP_SECS}s, comot Small Loss, NO HOLD | Hold {hold}s Price {price:.1f} Net ${pnl_net:.4f} | {get_score_str(price)}", flush=True)
            PAPER_PNL += pnl_net
            ACCOUNT_BALANCE += pnl_net
            place_order_paper("Sell" if side == 'BUY' else "Buy", price)
        HANDS.clear()
        CONFIRM_COUNT = 0
        return

    hands_to_remove = []
    for i, hand in enumerate(HANDS):
        entry = hand['entry']; tp = hand['tp']; sl = hand['sl']; hid = hand['id']; side = hand['side']
        hold = int(time.time() - hand['enter_time'])
        fee = get_fee(entry)
        inside_heart = 0.002 <= abs(dominance) <= 0.025
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
                print(f"[HAND {hid} BUY] ✅ TP HIT INSIDE HEART! NO HOLD! Price {price:.1f} >= TP {tp:.1f} | Entry {entry:.1f} Hold {hold}s Dom {dominance:.3f} | Gross ${profit:.4f} Fee ${fee:.4f} Net ${net:.4f} Max {pct:.1f}% | {get_score_str(price)}", flush=True)
                place_order_paper("Sell", price)
                hands_to_remove.append(i)
                continue
            if price <= sl:
                if inside_heart and not hand['breakeven']:
                    print(f"[HAND {hid} BUY] 🚫 NO WICK DOWN INSIDE HEART! Price {price:.1f} dip below SL {sl:.1f} but Dom {dominance:.3f} still inside, fake noise, HOLD to roof, heart still dey pump | {get_score_str(price)}", flush=True)
                    continue
                if hand['breakeven']:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} BUY] 🛡️ BREAK-EVEN HIT @ {price:.1f} Hold {hold}s | Loss $0.00 | {get_score_str(price)}", flush=True)
                else:
                    if dominance < DOM_FOUNDATION_BUY:
                        loss = (entry - sl) * QTY
                        PAPER_LOSSES += 1
                        PAPER_PNL -= loss
                        ACCOUNT_BALANCE -= loss
                        print(f"[HAND {hid} BUY] ❌ FOUNDATION BREAK! Dom {dominance:.3f} < -0.025, heart fake | Price {price:.1f} Loss ${loss:.4f} | {get_score_str(price)}", flush=True)
                    else:
                        print(f"[HAND {hid} BUY] 🚫 NO WICK DOWN - HOLD | {get_score_str(price)}", flush=True)
                        continue
                place_order_paper("Sell", price)
                hands_to_remove.append(i)
                continue
        else:  # SELL - Fixed: Foundation for SELL na +0.025, no be -0.025
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
                print(f"[HAND {hid} SELL] ✅ TP HIT INSIDE HEART! NO HOLD! Price {price:.1f} <= TP {tp:.1f} | Entry {entry:.1f} Hold {hold}s Dom {dominance:.3f} | Gross ${profit:.4f} Fee ${fee:.4f} Net ${net:.4f} Max {pct:.1f}% | {get_score_str(price)}", flush=True)
                place_order_paper("Buy", price)
                hands_to_remove.append(i)
                continue
            if price >= sl:
                if inside_heart and not hand['breakeven']:
                    print(f"[HAND {hid} SELL] 🚫 NO WICK DOWN INSIDE HEART! Price {price:.1f} wick above SL {sl:.1f} but Dom {dominance:.3f} still inside, fake noise, HOLD to roof | {get_score_str(price)}", flush=True)
                    continue
                if hand['breakeven']:
                    PAPER_BREAKEVEN += 1
                    print(f"[HAND {hid} SELL] 🛡️ BREAK-EVEN HIT @ {price:.1f} Hold {hold}s | Loss $0.00 | {get_score_str(price)}", flush=True)
                else:
                    if dominance > DOM_FOUNDATION_SELL:
                        loss = (sl - entry) * QTY
                        PAPER_LOSSES += 1
                        PAPER_PNL -= loss
                        ACCOUNT_BALANCE -= loss
                        print(f"[HAND {hid} SELL] ❌ FOUNDATION BREAK! Dom {dominance:.3f} > +0.025, heart fake | Price {price:.1f} Loss ${loss:.4f} | {get_score_str(price)}", flush=True)
                    else:
                        print(f"[HAND {hid} SELL] 🚫 NO WICK DOWN - HOLD | {get_score_str(price)}", flush=True)
                        continue
                place_order_paper("Buy", price)
                hands_to_remove.append(i)
                continue
        # V11.5 FIX: No lie again - If Dom don comot, no print Inside Heart
        if abs(dominance) > 0.025:
            print(f"[HAND {hid} {side}] Dom {dominance:.3f} don comot from heart, go comot next check, NO FLOATING | {get_score_str(price)}", flush=True)
        else:
            print(f"[HAND {hid} {side}] Hold INSIDE heart... Dom {dominance:.3f} Price {price:.1f} TP {tp:.1f} Entry {entry:.1f} SL {sl:.1f} BE {'ON' if hand['breakeven'] else 'OFF'} Hold {hold}s - Heart dey pump, NO HOLD beyond roof, NO WICK DOWN | {get_score_str(price)}", flush=True)
    for idx in reversed(hands_to_remove):
        HANDS.pop(idx)
        if len(HANDS) == 1:
            HANDS[0]['id'] = 1
            print(f"[TWO HANDS] Hand 1 close, Hand 2 don become new Hand 1, still inside heart | {get_score_str(price)}", flush=True)

    if cvd_val < MAX_CVD_CRASH:
        print(f"[CRASH FILTER] SKIP - CVD ${cvd_val:.0f} < -$1M | {get_score_str(price)}", flush=True)
        CONFIRM_COUNT = 0
        return
    if dominance < DOM_CRASH:
        print(f"[CRASH FILTER] SKIP - Dom {dominance:.3f} < -0.20 | {get_score_str(price)}", flush=True)
        CONFIRM_COUNT = 0
        return
    if abs(dominance) < 0.002:
        print(f"[ROOF] SKIP - Dom {dominance:.3f} na roof, wait new foundation | {get_score_str(price)}", flush=True)
        CONFIRM_COUNT = 0
        return

    direction = smell_direction()
    # V11.5 FIX: Smell must match Dom sign, no mixed hand, no floating
    # If Dom negative (-0.02), na BUY heart. If Dom positive (+0.02), na SELL heart.
    if dominance < 0 and direction == "SELL":
        print(f"[SMELL FIX] SKIP - Smell SELL but Dom {dominance:.3f} na negative (BUY side), mixed hand go cause floating, skip | {get_score_str(price)}", flush=True)
        return
    if dominance > 0 and direction == "BUY":
        print(f"[SMELL FIX] SKIP - Smell BUY but Dom {dominance:.3f} na positive (SELL side), mixed hand go cause floating, skip | {get_score_str(price)}", flush=True)
        return
    # Force direction = Dom sign, to avoid floating
    direction = "BUY" if dominance < 0 else "SELL"
    abs_dom = abs(dominance)
    max_hands = max_hands_for_balance()
    can_enter = False
    exp_move_final = 0
    hand_id = 1
    reason = ""
    if len(HANDS) == 0:
        if 0.015 < abs_dom < 0.025:
            exp_move = vol_drip * abs_dom * 0.01
            exp_gross = exp_move * QTY
            fee = get_fee(price)
            # PROFIT COVER FEES: Exp Gross must be >= 2x Fee, else skip, no 0.00 loss
            if exp_gross < fee * 2:
                print(f"[FEE CHECK] SKIP Hand 1 - Exp Gross ${exp_gross:.4f} < 2x Fee ${fee*2:.4f} - Profit no go cover fees, skip | {get_score_str(price)}", flush=True)
                return
            can_enter = True
            hand_id = 1
            reason = f"Hand 1 - Foundation Smell {direction} - Dom {dominance:.3f} QTY {QTY} (Bybit Min) Exp ${exp_move:.0f} Gross ${exp_gross:.4f} Fee ${fee:.4f} Net ${exp_gross-fee:.4f}"
            exp_move_final = exp_move
        else:
            if 0.002 <= abs_dom <= 0.015:
                print(f"[THRICE STEPS] SKIP - Dom {dominance:.3f} don pass foundation, wait new foundation | Smell {direction} | {get_score_str(price)}", flush=True)
            return
    elif len(HANDS) == 1 and max_hands >= 2:
        if 0.002 < abs_dom < 0.015:
            # Smell Follow to TP: Hand 2 must follow Hand 1 direction, no flip inside same heart
            direction = HANDS[0]['side']
            exp_move = vol_drip * abs_dom * 0.01
            exp_gross = exp_move * QTY
            fee = get_fee(price)
            if exp_gross < fee * 2:
                print(f"[FEE CHECK] SKIP Hand 2 - Remaining Exp Gross ${exp_gross:.4f} < 2x Fee ${fee*2:.4f}, Hand2 go cause 0.00 loss, skip | {get_score_str(price)}", flush=True)
                return
            can_enter = True
            hand_id = 2
            reason = f"Hand 2 - Halfway Smell {direction} (Follow Hand 1 to TP) - Dom {dominance:.3f} QTY {QTY} (Bybit Min) Exp ${exp_move:.0f} Gross ${exp_gross:.4f} Fee ${fee:.4f} Net ${exp_gross-fee:.4f} - Dynamic $3, 2 Hands fit!"
            exp_move_final = exp_move
        else:
            print(f"[ONE AFTER THE OTHER] Hand 1 dey hold, Hand 2 go wait for Halfway - Now Dom {dominance:.3f} | {get_score_str(price)}", flush=True)
            return
    elif len(HANDS) == 1 and max_hands == 1:
        print(f"[DYNAMIC $3] Bal ${ACCOUNT_BALANCE:.2f} < $2.50, 1 Hand only to protect $3, Hand 2 go wait till balance grow | {get_score_str(price)}", flush=True)
        return
    else:
        print(f"[SEAMLESS] {max_hands} Hands already open, no Hand 3 | {get_score_str(price)}", flush=True)
        return

    if can_enter:
        imbalance = bid_qty / (bid_qty + ask_qty) if (bid_qty + ask_qty) != 0 else 0
        pressure = max(imbalance, 1 - imbalance)
        exp_pct = (exp_move_final / price) * 100 if price else 0
        print(f"[CHECK] Dom {dominance:.3f} Abs {abs_dom:.3f} Smell {direction} Vol ${vol_drip:.0f} CVD ${cvd_val:.0f} Pressure {pressure:.2f} Exp {exp_pct:.2f}% Hands {len(HANDS)}/{max_hands} Confirm {CONFIRM_COUNT}/1 - {reason} | {get_score_str(price)}", flush=True)
        if exp_pct < MIN_EXP_PCT:
            CONFIRM_COUNT = 0
            print(f"[-0.02] SKIP - Exp {exp_pct:.2f}% too small, profit no go cover fees | {get_score_str(price)}", flush=True)
            return
        must_pass = (vol_drip >= MIN_VOL)
        cvd_pass = abs(cvd_val) >= MIN_CVD
        pressure_pass = pressure >= MIN_PRESSURE
        if must_pass and cvd_pass and pressure_pass:
            CONFIRM_COUNT += 1
            print(f"[CONFIRM] Strong heart {CONFIRM_COUNT}/1 - Dom {dominance:.3f} Smell {direction} | {get_score_str(price)}", flush=True)
            if CONFIRM_COUNT < CONFIRM_NEEDED:
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
            print(f"[HAND {hand_id} {direction}] 🔥 ENTER INSIDE HEART @ {ENTRY:.1f} QTY {QTY} (Bybit Min) LEV {LEV}x | Vol ${vol_drip:.0f} | Dom {dominance:.3f} Smell {direction} Follow to TP | Exp ${exp_move_final:.0f} Max {pct:.1f}% | TP {TP_PRICE:.1f} | SL {SL_PRICE:.1f} Only foundation break, NO WICK DOWN | NO HOLD, Heart pump = Stay, Heart stop = Comot, NO FLOATING | Net if TP ${net:.4f} Bal ${ACCOUNT_BALANCE:.2f} | {get_score_str(price)} | V11.5 NO FLOATING - PAPER", flush=True)
            place_order_paper("Buy" if direction == 'BUY' else "Sell", price)
        else:
            CONFIRM_COUNT = 0
            print(f"[-0.02] No join - Vol: {must_pass}, CVD: {cvd_pass}, Pressure: {pressure_pass} | {get_score_str(price)}", flush=True)

def on_message(ws, message):
    global cvd, total_vol_1min, last_price, best_bid_qty, best_ask_qty, CVD_HISTORY
    try:
        data = json.loads(message)
        topic = data.get("topic", "")
        if "publicTrade.BTCUSDT" in topic:
            for t in data.get("data", []):
                p = float(t["p"]); s = float(t["v"]); side = t["S"]; vol = p * s
                last_price = p
                cvd += vol if side == "Buy" else -vol
                total_vol_1min += vol
                CVD_HISTORY.append((time.time(), cvd))
                CVD_HISTORY = [(tt, cc) for tt, cc in CVD_HISTORY if time.time() - tt < 10]
        if "orderbook.1.BTCUSDT" in topic:
            ob = data.get("data", {})
            if "b" in ob and ob["b"]:
                best_bid_qty = float(ob["b"][0][1])
            if "a" in ob and ob["a"]:
                best_ask_qty = float(ob["a"][0][1])
    except Exception as e:
        print(f"[EYE] Error {e}", flush=True)

def on_open(ws):
    print("[EYE] 👁️ Eye don open! PAPER V11.5 NO FLOATING!", flush=True)
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
    print("[WATCHER] Watcher start - V11.5 NO FLOATING...", flush=True)
    while True:
        time.sleep(2)
        if time.time() - last_vol_reset > 60:
            print(f"[WATCHER] 1min: Vol ${total_vol_1min:.0f} CVD ${cvd:.0f} Price {last_price:.1f} | Hands {len(HANDS)} | {get_score_str(last_price)}", flush=True)
            total_vol_1min = 0; cvd = 0; last_vol_reset = time.time(); continue
        if total_vol_1min > 0:
            dominance = cvd / total_vol_1min
            if len(HANDS) > 0 or abs(dominance) > 0.002:
                check_heart(dominance, total_vol_1min, best_bid_qty, best_ask_qty, cvd, last_price)
            elif int(time.time()) % 30 == 0:
                print(f"[WATCHER] No heart yet - Dom {dominance:.3f} Vol ${total_vol_1min:.0f} Price {last_price:.1f} | {get_score_str(last_price)}", flush=True)

if __name__ == "__main__":
    auto_config_bybit()
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=start_eye, daemon=True).start()
    threading.Thread(target=heart_watcher, daemon=True).start()
    print("V11.5 NO FLOATING Heart Bot start! Paper!", flush=True)
    app.run(host="0.0.0.0", port=10000)
