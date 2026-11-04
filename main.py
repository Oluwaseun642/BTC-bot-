# main.py - HEART DEMO - TINY + TP INSIDE HEART - FINAL
# DEMO ONLY - Demo Account + Current API - Money for Earn, no real money
# Tiny bot to pierce heart: -0.02 enter, TP inside, comot before 0.00

import time, os, threading
from flask import Flask
import requests

# ===== TINY CONFIG =====
DEMO_TRADING = True
QTY = 0.001  # TINY - fit pierce heart, no slippage, no move market
BALANCE = 100.0  # Demo balance
SL_HITS = 0
LAST_SL_TIME = 0
IN_TRADE = False
ENTRY = 0
TP_PRICE = 0
SL_PRICE = 0

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

# ===== SELF PING - Render no sleep =====
app = Flask(__name__)

@app.route("/")
def home():
    return "Heart Tiny Bot Alive - DEMO -0.02 to 0.00"

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
        time.sleep(300)  # 5 mins

# ===== HEART LOGIC =====
def check_heart(dominance, vol_drip, bid, ask, cvd, timestamp, price):
    global IN_TRADE, ENTRY, TP_PRICE, SL_PRICE, SL_HITS, LAST_SL_TIME

    # 2 SL = sleep 1 min only for DEMO
    if SL_HITS >= 2:
        if time.time() - LAST_SL_TIME < 60:
            print("DEMO: 2 SL hit, sleep 1 min...")
            return
        else:
            SL_HITS = 0
            print("DEMO: 1 min don pass, back to heart!")

    # === IF WE DEY INSIDE HEART ALREADY - MONITOR TP INSIDE ===
    if IN_TRADE:
        # TP HIT INSIDE HEART - BEFORE 0.00!
        if price >= TP_PRICE:
            profit = (TP_PRICE - ENTRY) * QTY
            print(f"[HEART] ✅ TP HIT INSIDE HEART! Price {price:.1f} >= TP {TP_PRICE:.1f} | Dom {dominance} (no reach 0.00 yet) | Profit ${profit:.4f} | COMOT FAST!")
            print(f"[HEART] Back to -0.02, dey wait next heart...")
            IN_TRADE = False
            return
        # WIDE SL HIT
        if price <= SL_PRICE:
            print(f"[HEART] ❌ WIDE SL HIT inside heart @ {price:.1f} | Dom {dominance}")
            SL_HITS += 1
            LAST_SL_TIME = time.time()
            IN_TRADE = False
            return
        # HEART CLOSE - 0.00 reach, TP never hit
        if dominance >= 0.00:
            pnl = (price - ENTRY) * QTY
            print(f"[HEART] ⏰ Heart close 0.00, TP never hit, comot with ${pnl:.4f}, go back -0.02")
            IN_TRADE = False
            return
        # Still inside, dey wait
        print(f"[HEART] Inside... Dom {dominance} Price {price:.1f} TP {TP_PRICE:.1f} | Waiting TP inside...")
        return

    # === IF WE NO DEY TRADE - WAIT FOR -0.02 ===
    if timestamp == -0.02:
        imbalance = bid / (bid + ask) if (bid + ask) != 0 else 0
        total_vol = vol_drip

        # TP FROM VOLUME - Profit Over Percentage
        exp_move = total_vol * 0.00035  # $1M = $350
        exp_move_pct = (exp_move / price) * 100 if price else 0

        # FEE CHECK - Must be >= 0.15% else skip
        if exp_move_pct < 0.15:
            print(f"[-0.02] SKIP - Exp {exp_move_pct:.2f}% too small, fee go chop am")
            return

        if dominance >= 0.08 and cvd >= 300_000 and imbalance >= 0.65 and total_vol >= 1_000_000:
            ENTRY = price
            TP_PRICE = ENTRY + exp_move  # TP INSIDE HEART, go show before 0.00
            SL_PRICE = ENTRY - (exp_move * 0.5)  # Wide SL
            IN_TRADE = True
            fee = ENTRY * QTY * 0.0011
            net = exp_move * QTY - fee
            print(f"[HEART] 🔥 ENTER TINY @ {ENTRY:.1f} QTY {QTY} | Vol ${total_vol} | Exp ${exp_move:.0f} ({exp_move_pct:.2f}%)")
            print(f"[HEART] TP @ {TP_PRICE:.1f} INSIDE HEART | SL @ {SL_PRICE:.1f} | Net if TP ${net:.4f} | DEMO ONLY")
            print(f"[HEART] Now dey monitor inside heart... TP go show before 0.00")
        else:
            print(f"[-0.02] No join - dom {dominance} cvd {cvd} imb {imbalance:.2f} vol ${total_vol}")

# ===== TEST LOOP - For Render logs, remove when you connect real feed =====
def test_loop():
    # This na demo loop to show logs dey work, replace with your real Bybit feed
    import random
    price = 79000.0
    while True:
        # Simulate heart: -0.02 signal comes
        dominance = 0.08
        # Call check_heart with fake data to test
        # In real bot, you go call this from your websocket feed
        time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()
    print("Tiny Heart Bot don start! -0.02 enter, TP inside, comot before 0.00 - DEMO ONLY")
    print("QTY 0.001 tiny - fit pierce heart, no slippage")
    app.run(host="0.0.0.0", port=10000)
