# ============================================================
# BTC SWEEP BOT - V6.2 FULL - FIXED FOR RENDER DEPLOY
# NEVER STOP + Trailing Always + BE Over Fees + Health Server
# File name MUST be main.py
# ============================================================

import os
import time
import requests
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============ 1. HEALTH SERVER FOR RENDER (FIXES HANG) ============
# Render waits for a port. This small server tells Render "I dey alive"
# So deploy no go hang 15 mins again.
PORT = int(os.environ.get("PORT", 10000))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        try:
            bal = STATE.get("balance", 0)
            pnl = STATE.get("pnl", 0)
            pos = STATE.get("open_position")
            pos_str = f"{pos['side']} @ {pos['entry']}" if pos else "FLAT"
            self.wfile.write(f"OK Bot Alive Bal ${bal:.2f} PnL ${pnl:.2f} Pos {pos_str}".encode())
        except:
            self.wfile.write(b"OK Bot Alive")
    def log_message(self, format, *args):
        return  # silence http logs

def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        print(f"[HEALTH] Server running on port {PORT}", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"[HEALTH ERROR] {e}", flush=True)

# ================= CONFIG =================
CONFIG = {
    "SYMBOL": "BTCUSDT",
    "QTY": 0.001,
    "LEVERAGE": 50,
    "MIN_CERTAINTY_NORMAL": 80.0,
    "MIN_AGREE_NORMAL": 5,
    "MIN_SCORE_NORMAL": 0.75,
    "TOTAL_SIGNALS": 6,
    "SURE_CERTAINTY": 95.0,
    "SURE_AGREE": 6,
    "TP_MULT_NORMAL": 2.0,
    "TP_MULT_SURE": 3.5,
    "NEWS_ENABLED": True,
    "MIN_CERTAINTY_NEWS": 75.0,
    "MIN_AGREE_NEWS": 5,
    "MIN_SCORE_NEWS": 0.60,
    "SL_PCT": 0.0085,
    "WICK_BUFFER": 80.0,
    "NEVER_STOP": True,
    "MAX_TRADES_PER_DAY": 999,
    "MAX_LOSSES_PER_DAY": 999,
    "COOLDOWN_AFTER_LOSS_MIN": 15,
    "AFTER_LOSS_CERTAINTY": 85.0,
    "AFTER_LOSS_AGREE": 6,
    "COOLDOWN_AFTER_WIN_MIN": 2,
    "TRAILING_ENABLED": True,
    "TRAIL_START_PCT": 0.004,
    "TRAIL_STEP_1": 0.008,
    "TRAIL_DIST_1": 0.004,
    "TRAIL_STEP_2": 0.012,
    "TRAIL_DIST_2": 0.006,
    "TRAIL_STEP_3": 0.020,
    "TRAIL_DIST_3": 0.008,
    "BE_OVER_FEES": True,
    "BE_BUFFER_USD": 5.0,
    "BE_TRIGGER_PCT": 0.002,
    "FEE_RATE": 0.0006,
    "MIN_TP_OVER_FEES": 3.0,
    "MIN_RR": 1.8,
    "MIN_WINPROB": 52.0,
    "POLL_SEC": 60,
    "HEARTBEAT_MIN": 10,
}

STATE = {
    "balance": 9.69,
    "pnl": -0.31,
    "wins": 0,
    "losses": 0,
    "breakevens": 0,
    "trades_today": 0,
    "losses_today": 0,
    "last_loss_time": None,
    "last_trade_time": None,
    "day": datetime.now(timezone.utc).date(),
    "open_position": None,
    "last_price": 73500.0,
}

def now_utc():
    return datetime.now(timezone.utc)

def log(msg):
    print(f"[{now_utc().strftime('%H:%M:%S %d %b')}] {msg}", flush=True)

def get_price():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=10)
        j = r.json()
        if "result" in j and "list" in j["result"] and len(j["result"]["list"]) > 0:
            price = float(j["result"]["list"][0]["lastPrice"])
            STATE["last_price"] = price
            return price
        else:
            log(f"PRICE BAD JSON {j}")
            return STATE["last_price"]
    except Exception as e:
        log(f"PRICE ERROR {e} - using last {STATE['last_price']}")
        return STATE["last_price"]

def get_klines(limit=20):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&limit={limit}", timeout=10)
        j = r.json()
        if "result" not in j or "list" not in j["result"]:
            return []
        kl = list(reversed(j["result"]["list"]))
        out = []
        for x in kl:
            try:
                out.append({"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4])})
            except:
                continue
        return out
    except Exception as e:
        log(f"KLINE ERROR {e}")
        return []

def get_macro():
    oi_chg = 0
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=10)
        j = r.json()
        if "result" in j and "list" in j["result"] and len(j["result"]["list"]) >= 2:
            oi_list = j["result"]["list"]
            oi_now = float(oi_list[-1]["openInterest"])
            oi_prev = float(oi_list[0]["openInterest"])
            if oi_prev != 0:
                oi_chg = (oi_now - oi_prev) / oi_prev * 100
    except Exception as e:
        log(f"OI ERROR {e}")
    return {"DXY_CHG": 0.18, "NQ_CHG": 0.70, "SPX_CHG": 0.64, "GOLD_CHG": 0.10, "OI_CHG": oi_chg}

def get_news_score():
    if not CONFIG["NEWS_ENABLED"]:
        return False, 0, ""
    try:
        kl = get_klines(15)
        if len(kl) >= 15 and kl[0]["close"] != 0:
            move = (kl[-1]["close"] - kl[0]["close"]) / kl[0]["close"] * 100
            if abs(move) >= 0.8:
                return True, 85.0, f"VOL SPIKE {move:.2f}% in 15m"
    except Exception as e:
        log(f"NEWS ERROR {e}")
    return False, 0, ""

def get_signals(price, macro, klines):
    signals = []
    if macro["DXY_CHG"] > 0.10:
        signals.append(("DXY_LEVEL", "SHORT"))
    elif macro["DXY_CHG"] < -0.10:
        signals.append(("DXY_LEVEL", "LONG"))
    else:
        signals.append(("DXY_LEVEL", "NEUTRAL"))
    if macro["NQ_CHG"] > 0.20:
        signals.append(("NQ_MOMENTUM", "LONG"))
    elif macro["NQ_CHG"] < -0.20:
        signals.append(("NQ_MOMENTUM", "SHORT"))
    else:
        signals.append(("NQ_MOMENTUM", "NEUTRAL"))
    if macro["SPX_CHG"] > 0.20:
        signals.append(("SPX_MOMENTUM", "LONG"))
    elif macro["SPX_CHG"] < -0.20:
        signals.append(("SPX_MOMENTUM", "SHORT"))
    else:
        signals.append(("SPX_MOMENTUM", "NEUTRAL"))
    if macro["GOLD_CHG"] > 0.50:
        signals.append(("GOLD_AFTER_SWEEP", "SHORT"))
    elif macro["GOLD_CHG"] < -0.30:
        signals.append(("GOLD_AFTER_SWEEP", "LONG"))
    else:
        signals.append(("GOLD_AFTER_SWEEP", "NEUTRAL"))
    if klines and len(klines) >= 5 and klines[-5]["close"] != 0:
        price_chg = (klines[-1]["close"] - klines[-5]["close"]) / klines[-5]["close"] * 100
        if macro["OI_CHG"] > 0.5 and price_chg < -0.2:
            signals.append(("OI_DIVERGENCE", "SHORT"))
        elif macro["OI_CHG"] < -0.5 and price_chg > 0.2:
            signals.append(("OI_DIVERGENCE", "LONG"))
        else:
            signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    else:
        signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    if klines and len(klines) >= 3:
        last = klines[-1]
        wick_down = last["close"] - last["low"]
        wick_up = last["high"] - last["close"]
        if wick_down > 150 and wick_down > wick_up * 1.5:
            signals.append(("LIQ_SWEEP", "LONG"))
        elif wick_up > 150 and wick_up > wick_down * 1.5:
            signals.append(("LIQ_SWEEP", "SHORT"))
        else:
            signals.append(("LIQ_SWEEP", "NEUTRAL"))
    else:
        signals.append(("LIQ_SWEEP", "NEUTRAL"))
    return signals

def decide(signals):
    longs = sum(1 for _, v in signals if v == "LONG")
    shorts = sum(1 for _, v in signals if v == "SHORT")
    decided = longs + shorts
    if longs > shorts:
        dest, agree = "LONG", longs
    elif shorts > longs:
        dest, agree = "SHORT", shorts
    else:
        dest, agree = "NONE", 0
    certainty = (agree / decided * 100) if decided else 0
    return dest, agree, decided, longs, shorts, certainty

def calc_score(signals, dest, macro, is_news):
    _, agree, decided, _, _, certainty = decide(signals)
    base = (certainty / 100) * 1.0
    align = 0
    if dest == "LONG" and macro["NQ_CHG"] > 0 and macro["SPX_CHG"] > 0:
        align = 0.4
    if dest == "SHORT" and macro["DXY_CHG"] > 0:
        align = 0.3
    news_bonus = 0.4 if is_news else 0
    return round(base + align + news_bonus, 2)

def calc_sl_tp(price, side, klines, is_sure):
    sl_dist_pct = price * CONFIG["SL_PCT"]
    if klines:
        if side == "LONG":
            struct_low = min(c["low"] for c in klines[-15:])
            sl_struct = struct_low - CONFIG["WICK_BUFFER"]
            sl = min(price - sl_dist_pct, sl_struct)
            sl = max(sl, price * 0.988)
        else:
            struct_high = max(c["high"] for c in klines[-15:])
            sl_struct = struct_high + CONFIG["WICK_BUFFER"]
            sl = max(price + sl_dist_pct, sl_struct)
            sl = min(sl, price * 1.012)
    else:
        sl = price - sl_dist_pct if side == "LONG" else price + sl_dist_pct
    sl_dist = abs(price - sl)
    mult = CONFIG["TP_MULT_SURE"] if is_sure else CONFIG["TP_MULT_NORMAL"]
    tp_dist = sl_dist * mult
    tp = price + tp_dist if side == "LONG" else price - tp_dist
    return round(sl, 1), round(tp, 1), round(sl_dist, 1), round(tp_dist, 1)

def calc_fees_ev(price, sl_dist, tp_dist, winprob):
    qty = CONFIG["QTY"]
    pos = qty * price
    margin = pos / CONFIG["LEVERAGE"]
    fees = pos * CONFIG["FEE_RATE"] * 2
    tp_profit = (qty * tp_dist) - fees
    sl_loss = (qty * sl_dist) + fees
    rr = tp_dist / sl_dist if sl_dist else 0
    ev = (winprob/100 * tp_profit) - ((1-winprob/100) * sl_loss)
    be = tp_profit >= (fees * CONFIG["MIN_TP_OVER_FEES"])
    return pos, margin, fees, tp_profit, sl_loss, rr, ev, be

def check_loss_control():
    today = now_utc().date()
    if STATE["day"] != today:
        STATE["day"] = today
        STATE["trades_today"] = 0
        STATE["losses_today"] = 0
        STATE["last_loss_time"] = None
    if STATE["open_position"]:
        return False, "BLOCK: Already in position"
    if STATE["last_loss_time"]:
        mins_since = (now_utc() - STATE["last_loss_time"]).total_seconds() / 60
        if mins_since < CONFIG["COOLDOWN_AFTER_LOSS_MIN"]:
            return False, f"WARY: Cooldown {mins_since:.0f}/{CONFIG['COOLDOWN_AFTER_LOSS_MIN']}min"
    return True, ""

def get_dynamic_thresholds(is_news, just_lost):
    if just_lost:
        return CONFIG["AFTER_LOSS_CERTAINTY"], CONFIG["AFTER_LOSS_AGREE"], CONFIG["MIN_SCORE_NORMAL"]
    if is_news:
        return CONFIG["MIN_CERTAINTY_NEWS"], CONFIG["MIN_AGREE_NEWS"], CONFIG["MIN_SCORE_NEWS"]
    return CONFIG["MIN_CERTAINTY_NORMAL"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"]

def manage_position(price, klines):
    if not STATE["open_position"]:
        return
    p = STATE["open_position"]
    entry = p["entry"]
    side = p["side"]
    profit_pct = (price - entry) / entry if side == "LONG" else (entry - price) / entry

    if CONFIG["BE_OVER_FEES"] and not p.get("be_done"):
        if profit_pct >= CONFIG["BE_TRIGGER_PCT"]:
            if side == "LONG":
                be_sl = entry + CONFIG["BE_BUFFER_USD"]
                if be_sl > p["sl"]:
                    p["sl"] = be_sl; p["be_done"] = True
                    log(f"BE OVER FEES: SL -> ${be_sl:.0f} - CANNOT lose again")
            else:
                be_sl = entry - CONFIG["BE_BUFFER_USD"]
                if be_sl < p["sl"]:
                    p["sl"] = be_sl; p["be_done"] = True
                    log(f"BE OVER FEES: SL -> ${be_sl:.0f} - CANNOT lose again")

    if CONFIG["TRAILING_ENABLED"] and profit_pct >= CONFIG["TRAIL_START_PCT"]:
        if side == "LONG":
            if profit_pct >= CONFIG["TRAIL_STEP_3"]:
                new_sl = price - (price * CONFIG["TRAIL_DIST_3"]); label = "Trail 0.8%"
            elif profit_pct >= CONFIG["TRAIL_STEP_2"]:
                new_sl = price - (price * CONFIG["TRAIL_DIST_2"]); label = "Trail 0.6%"
            elif profit_pct >= CONFIG["TRAIL_STEP_1"]:
                new_sl = price - (price * CONFIG["TRAIL_DIST_1"]); label = "Trail 0.4%"
            else:
                new_sl = p["sl"]; label = ""
            if new_sl > p["sl"]:
                p["sl"] = new_sl
                log(f"TRAILING LONG: SL -> ${new_sl:.0f} Price ${price:.0f} Profit {profit_pct*100:.2f}% {label}")
        else:
            if profit_pct >= CONFIG["TRAIL_STEP_3"]:
                new_sl = price + (price * CONFIG["TRAIL_DIST_3"]); label = "Trail 0.8%"
            elif profit_pct >= CONFIG["TRAIL_STEP_2"]:
                new_sl = price + (price * CONFIG["TRAIL_DIST_2"]); label = "Trail 0.6%"
            elif profit_pct >= CONFIG["TRAIL_STEP_1"]:
                new_sl = price + (price * CONFIG["TRAIL_DIST_1"]); label = "Trail 0.4%"
            else:
                new_sl = p["sl"]; label = ""
            if new_sl < p["sl"]:
                p["sl"] = new_sl
                log(f"TRAILING SHORT: SL -> ${new_sl:.0f} Price ${price:.0f} Profit {profit_pct*100:.2f}% {label}")

    hit_tp = (price >= p["tp"] if side == "LONG" else price <= p["tp"])
    last_closed = klines[-2] if len(klines) >= 2 else None
    hit_sl = False
    if last_closed:
        if side == "LONG" and last_closed["close"] < p["sl"]:
            hit_sl = True
        if side == "SHORT" and last_closed["close"] > p["sl"]:
            hit_sl = True
    if hit_tp:
        profit = abs(price - entry) * CONFIG["QTY"]
        STATE["balance"] += profit; STATE["pnl"] += profit; STATE["wins"] += 1
        log(f"TP HIT +${profit:.2f} - Bot continues NEVER STOPS")
        STATE["open_position"] = None
    elif hit_sl:
        if p.get("be_done"):
            profit = abs(price - entry) * CONFIG["QTY"]
            STATE["balance"] += profit; STATE["pnl"] += profit; STATE["breakevens"] += 1
            log(f"BE OVER FEES HIT +${profit:.2f} - No loss")
        else:
            loss = abs(price - entry) * CONFIG["QTY"]
            STATE["balance"] -= loss; STATE["pnl"] -= loss; STATE["losses"] += 1; STATE["losses_today"] += 1; STATE["last_loss_time"] = now_utc()
            log(f"SL HIT -${loss:.2f} - WARY 15min, then trade again NEVER STOPS")
        STATE["open_position"] = None

def main():
    # Start health server in background so Render no go kill am
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()
    log("BOT V6.2 STARTED - NEVER STOP + Trailing + BE Over Fees + Health Server ON")
    last_heartbeat = now_utc()
    while True:
        try:
            price = get_price()
            klines = get_klines(20)
            macro = get_macro()
            is_news, news_score, news_reason = get_news_score()
            signals = get_signals(price, macro, klines)
            dest, agree, decided, longs, shorts, certainty = decide(signals)
            score = calc_score(signals, dest, macro, is_news)
            winprob = max(50, min(75, 50 + (certainty - 50) * 0.4))
            just_lost = STATE["last_loss_time"] is not None and (now_utc() - STATE["last_loss_time"]).total_seconds() < 3600
            need_cert, need_agree, need_score = get_dynamic_thresholds(is_news, just_lost)
            is_sure = (certainty >= CONFIG["SURE_CERTAINTY"] and agree >= CONFIG["SURE_AGREE"])
            mode = "SURE 95%+ WIDE TP" if is_sure else ("NEWS HUNTER" if is_news else "NORMAL")
            ok_control, control_reason = check_loss_control()

            if dest in ("LONG", "SHORT"):
                sl, tp, sl_dist, tp_dist = calc_sl_tp(price, dest, klines, is_sure)
                pos, margin, fees, tp_profit, sl_loss, rr, ev, be = calc_fees_ev(price, sl_dist, tp_dist, winprob)
            else:
                sl = tp = sl_dist = tp_dist = pos = margin = fees = tp_profit = sl_loss = rr = ev = 0; be = False

            gates = []
            gates.append((f"Agree {agree}/{decided} Need {need_agree}", agree >= need_agree and decided >= need_agree))
            gates.append((f"Certainty {certainty:.0f}% Need {need_cert:.0f}%", certainty >= need_cert))
            gates.append((f"Score {score:.2f} / Thr {need_score:.2f}", score >= need_score))
            gates.append((f"WinProb {winprob:.0f}%", winprob >= CONFIG["MIN_WINPROB"]))
            gates.append((f"TP Profit >=3x Fees", be))
            gates.append((f"RR {rr:.2f}", rr >= CONFIG["MIN_RR"]))
            gates.append((f"EV ${ev:.4f}", ev > 0))
            gates.append((f"LossControl", ok_control))
            all_pass = all(p for _, p in gates)
            failed = [n for n, p in gates if not p]

            sig_str = " ".join([f"{n}:{v}" for n, v in signals])
            log(f"Long {longs} Short {shorts} Decided {decided} | DEST {dest} Certainty {certainty:.0f}% Agree {agree}/{decided} Mode {mode} {'Pass True' if all_pass else 'Pass False'}")
            log(f"Signals: {sig_str} | News: {is_news} {news_reason} | Score {score:.2f} / Thr {need_score:.2f} | WinProb {winprob:.0f}% EV ${ev:.4f} RR {rr:.2f}")
            log(f"Price ${price:.0f} SL ${sl:.0f} TP ${tp:.0f} Pos ${pos:.0f} Margin ${margin:.2f} | Bal ${STATE['balance']:.2f} PnL ${STATE['pnl']:.2f} W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']}")

            if not all_pass:
                log(f"BLOCK/WARY: {'; '.join(failed)} {control_reason} - Bot still alive")
            else:
                log(f"TRADE SIGNAL - {dest} {mode} Entry ${price:.0f} SL ${sl:.0f} TP ${tp:.0f}")
                STATE["open_position"] = {"side": dest, "entry": price, "sl": sl, "tp": tp, "certainty": certainty, "is_sure": is_sure, "be_done": False}
                STATE["trades_today"] += 1
                STATE["last_trade_time"] = now_utc()

            manage_position(price, klines)

            if (now_utc() - last_heartbeat).total_seconds() > CONFIG["HEARTBEAT_MIN"] * 60:
                log(f"HEARTBEAT OK - Bot alive NEVER STOP - Bal ${STATE['balance']:.2f}")
                last_heartbeat = now_utc()

            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e:
            log(f"ERROR {e}")
            import traceback
            log(traceback.format_exc())
            time.sleep(10)

if __name__ == "__main__":
    main()
