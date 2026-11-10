# ============================================
# V5.13 - BTCUSDT - SAFE KILLER MODE
# Bybit / Binance Compatible | Render Ready
# Qty 0.001 | Lev 50x Isolated | No Pause Logic
# ============================================
import os, time, math, requests, threading
from datetime import datetime, timezone

# ---------- CONFIG - YOUR RULES ----------
PAIR = "BTCUSDT"
QTY = 0.001
LEV = 50
MARGIN_MODE = "ISOLATED"

MIN_CERTAINTY = 95      # Must be 95%+
MIN_AGREE = 6           # 6/6 must agree
MIN_SCORE = 8.0         # Strong score only
REQUIRE_PREFLIP_MATCH = True

TP_FEE_MULTIPLIER = 3.0 # TP must be >= 3x Fees
SL_PCT = 0.007          # 0.7% SL - before liquidation for 50x
TP_PCT = 0.015          # 1.5% TP min - Reward 2x Risk

MAX_OPEN_POS = 1
COOLDOWN_MIN = 5        # 5 mins between trades - your rule
SELF_PING_INTERVAL = 300 # 5 mins - keep Render awake

# Fees - adjust for your exchange
MAKER_FEE = 0.0005
TAKER_FEE = 0.0005
FUNDING_EST = 0.0001

# State
last_trade_time = 0
open_position = None
stats = {"W": 0, "L": 0, "BE": 0, "PnL": 0.0}

# ---------- HELPERS ----------
def log(msg):
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{now}] [V5.13] {msg}", flush=True)

def get_price():
    # Replace with your exchange price fetch
    # Example using Binance public API
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={PAIR}", timeout=5)
        return float(r.json()["price"])
    except:
        return 0

def get_market_checks():
    # THIS IS YOUR BRAIN - Replace with your real indicators
    # Must return dict with 6 checks
    # For now, this is template - plug your DXY, NQ, SPX, Trend, Momentum, PreFlip here
    # Example logic:
    price = get_price()
    # TODO: Connect your real data sources here
    # Returning dummy structure - your existing V5.12.15 checks go here
    return {
        "trend": "SHORT",      # LONG / SHORT
        "dxy": "SHORT",
        "nq": "SHORT",
        "spx": "SHORT",
        "momentum": "SHORT",
        "preflip": "SHORT",
        "certainty": 96,
        "score": -9.5,
        "price": price
    }

def calculate_fees(price):
    pos_value = price * QTY
    entry = pos_value * TAKER_FEE
    exit_fee = pos_value * TAKER_FEE
    funding = pos_value * FUNDING_EST * 3
    total = entry + exit_fee + funding
    return total, entry, exit_fee, funding

def can_trade(checks, price):
    # Rule 1: Certainty
    if checks["certainty"] < MIN_CERTAINTY:
        return False, f"Certainty {checks['certainty']}% < {MIN_CERTAINTY}% - SKIP"
    # Rule 2: Agree 6/6
    votes = [checks["trend"], checks["dxy"], checks["nq"], checks["spx"], checks["momentum"], checks["preflip"]]
    # Count how many agree with trend direction
    agree_count = sum(1 for v in votes if v == checks["trend"])
    if agree_count < MIN_AGREE:
        return False, f"Agree {agree_count}/6 < 6/6 - SKIP"
    # Rule 3: Score
    if abs(checks["score"]) < MIN_SCORE:
        return False, f"Score {checks['score']} weak < {MIN_SCORE} - SKIP"
    # Rule 4: PreFlip must match
    if REQUIRE_PREFLIP_MATCH and checks["preflip"] != checks["trend"]:
        return False, f"PreFlip {checks['preflip']} != {checks['trend']} - SKIP - Nonsense trade blocked"
    # Rule 5: TP >= 3x Fees
    fees, _, _, _ = calculate_fees(price)
    tp_target = fees * TP_FEE_MULTIPLIER
    tp_profit_potential = (price * QTY) * TP_PCT
    if tp_profit_potential < tp_target:
        return False, f"TP profit ${tp_profit_potential:.4f} < 3x Fees ${tp_target:.4f} - SKIP"
    # Rule 6: Max 1 position
    if open_position is not None:
        return False, "Already in position - Max 1 - SKIP"
    # Rule 7: Cooldown 5 mins
    global last_trade_time
    if time.time() - last_trade_time < COOLDOWN_MIN * 60:
        return False, f"Cooldown {COOLDOWN_MIN}min - SKIP"
    return True, "PASS - ALL CHECKS GREEN"

def open_trade(direction, price, checks):
    global open_position, last_trade_time
    fees, entry_f, exit_f, fund = calculate_fees(price)
    tp_target = fees * TP_FEE_MULTIPLIER

    if direction == "LONG":
        tp = price * (1 + TP_PCT)
        sl = price * (1 - SL_PCT)
    else:
        tp = price * (1 - TP_PCT)
        sl = price * (1 + SL_PCT)

    # BE = Entry + Fees
    be_price = price + (fees / QTY) if direction == "LONG" else price - (fees / QTY)

    log(f"OPEN {direction} Entry ${price:.2f} Qty {QTY} Lev {LEV}x | TP ${tp:.2f} SL ${sl:.2f} BE ${be_price:.2f}")
    log(f"FEES: Entry ${entry_f:.4f} + Exit ${exit_f:.4f} + Fund ${fund:.4f} = Total ${fees:.4f} | TP Target ${tp_target:.4f} | Certainty {checks['certainty']}% Agree 6/6 Score {checks['score']}")
    log(f"Reason: I don't want to loss - All 6 agree, Certainty high, TP 3x Fees")

    open_position = {
        "dir": direction,
        "entry": price,
        "tp": tp,
        "sl": sl,
        "be": be_price,
        "time": time.time()
    }
    last_trade_time = time.time()
    # TODO: Place real order here via exchange API
    # exchange.create_order(PAIR, direction, QTY, leverage=LEV)
    return open_position

def check_exit(price):
    global open_position
    if not open_position:
        return
    d = open_position
    pnl = (price - d["entry"]) * QTY if d["dir"] == "LONG" else (d["entry"] - price) * QTY
    # TP hit
    if (d["dir"] == "LONG" and price >= d["tp"]) or (d["dir"] == "SHORT" and price <= d["tp"]):
        log(f"TP HIT ✅ PnL ${pnl:.4f}")
        stats["W"] += 1
        stats["PnL"] += pnl
        open_position = None
    # SL hit
    elif (d["dir"] == "LONG" and price <= d["sl"]) or (d["dir"] == "SHORT" and price >= d["sl"]):
        log(f"SL HIT ❌ PnL ${pnl:.4f} - Cut fast, no bleed")
        stats["L"] += 1
        stats["PnL"] += pnl
        open_position = None
    else:
        log(f"Holding {d['dir']} Entry ${d['entry']:.2f} Now ${price:.2f} PnL ${pnl:.4f} TP ${d['tp']:.2f} SL ${d['sl']:.2f}")

# ---------- SELF PING - KEEP RENDER AWAKE ----------
def self_ping_loop():
    url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not url:
        # Use your Render URL here if env not set
        url = os.getenv("SELF_URL", "")
    while True:
        try:
            if url:
                requests.get(url, timeout=10)
                log(f"Self-ping OK - Keeping alive")
        except Exception as e:
            log(f"Self-ping fail: {e}")
        time.sleep(SELF_PING_INTERVAL)

# ---------- MAIN LOOP ----------
def main():
    log(f"V5.13 STARTED - {PAIR} Qty {QTY} Lev {LEV}x Isolated - No Pause Mode - Brain: Don't Loss")
    # Start self-ping thread
    threading.Thread(target=self_ping_loop, daemon=True).start()

    while True:
        try:
            price = get_price()
            if price == 0:
                log("Price fetch fail - retry")
                time.sleep(10)
                continue

            # If in position, check exit
            if open_position:
                check_exit(price)
                time.sleep(10)
                continue

            # If not in position, check for new trade
            checks = get_market_checks()
            direction = checks["trend"]
            ok, reason = can_trade(checks, price)
            log(f"Check: Price ${price:.2f} Dir {direction} Cert {checks['certainty']}% Score {checks['score']} | {reason} | Stats W {stats['W']} L {stats['L']} PnL ${stats['PnL']:.2f}")
            if ok:
                open_trade(direction, price, checks)
            # No pause, no daily stop - just keep checking with brain
            time.sleep(30)  # Check every 30s, cooldown handles 5min rule
        except Exception as e:
            log(f"Error: {e} - Continuing, no stop")
            time.sleep(10)

if __name__ == "__main__":
    main()o
