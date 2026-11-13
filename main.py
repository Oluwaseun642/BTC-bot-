# ============================================================
# BTC SWEEP BOT - V12.4 FULL - Option 2 Web Service + Flask Keep-Alive
# Paper till Sun 8:30pm WAT (19:30 UTC 15 Nov) -> Auto REAL
# Fees+Slippage + BE+Trailing Real SL + Dynamic Balance/Qty + NEVER STOP
# ============================================================

import time, requests, hmac, hashlib, os, json, threading
from datetime import datetime, timezone

# ================= FLASK KEEP-ALIVE - FOR RENDER WEB SERVICE ONLY =================
# This no touch trading. E just open port so Render no go say "No open ports" and restart bot.
# Bot still dey run for main thread, Flask dey run for background thread.
try:
    from flask import Flask
    _flask_app = Flask(__name__)
    @_flask_app.route("/")
    def _health():
        return "BOT ALIVE - PAPER till Sun 8:30pm WAT, then REAL", 200
    @_flask_app.route("/health")
    def _health2():
        return "OK", 200
    def _run_flask():
        try:
            port = int(os.getenv("PORT", 10000))
            _flask_app.run(host="0.0.0.0", port=port, use_reloader=False)
        except Exception as e:
            print(f"Flask error {e}", flush=True)
    threading.Thread(target=_run_flask, daemon=True).start()
    print("Flask keep-alive ON - port open for Render Web Service", flush=True)
except Exception as e:
    print(f"Flask keep-alive OFF {e}", flush=True)

# ================= CONFIG - DYNAMIC, NO FIXED PRICE / BALANCE =================
CONFIG = {
    "SYMBOL": "BTCUSDT",
    "LEVERAGE": 50,
    "PAPER_QTY": 0.002,
    "REAL_RISK_MARGIN_PCT": 0.10,
    "REAL_MIN_QTY": 0.001,
    "REAL_MAX_QTY": 0.010,

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
    "WICK_BUFFER_PCT": 0.0011,
    "SL_CLOSE_CONFIRM": True,

    "NEVER_STOP": True,
    "MAX_TRADES_PER_DAY": 999,
    "MAX_LOSSES_PER_DAY": 999,
    "COOLDOWN_AFTER_LOSS_MIN": 15,
    "AFTER_LOSS_CERTAINTY": 85.0,
    "AFTER_LOSS_AGREE": 6,
    "COOLDOWN_AFTER_WIN_MIN": 2,

    "TRAILING_ENABLED": True,
    "TRAIL_START_PCT": 0.004,
    "TRAIL_STEP_1": 0.008, "TRAIL_DIST_1": 0.004,
    "TRAIL_STEP_2": 0.012, "TRAIL_DIST_2": 0.006,
    "TRAIL_STEP_3": 0.020, "TRAIL_DIST_3": 0.008,

    "BE_OVER_FEES": True,
    "BE_TRIGGER_PCT": 0.0035,
    "FEE_RATE": 0.0006,
    "SLIPPAGE_PCT": 0.0005,
    "BE_BUFFER_PCT": 0.0024,  # 0.24% = fees 0.12% + slippage 0.10% + 0.02% profit

    "MIN_TP_OVER_FEES": 3.0,
    "MIN_RR": 1.8,
    "MIN_WINPROB": 52.0,
    "POLL_SEC": 5,
    "HEARTBEAT_MIN": 10,

    "AUTO_SWITCH_UTC": datetime(2026, 11, 15, 19, 30, tzinfo=timezone.utc),  # Sun 8:30pm WAT
    "BYBIT_BASE": "https://api.bybit.com",
}

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")

STATE = {
    "mode": "PAPER",
    "balance": 4.75, "real_balance": 0.0,
    "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0,
    "trades_today": 0, "losses_today": 0,
    "last_loss_time": None, "last_trade_time": None,
    "day": datetime.now(timezone.utc).date(),
    "open_position": None, "last_price": 0.0,
}

def now_utc(): return datetime.now(timezone.utc)
def log(msg): print(f"[{now_utc().strftime('%H:%M:%S %d %b')}] {msg}", flush=True)
def get_mode():
    if now_utc() >= CONFIG["AUTO_SWITCH_UTC"]:
        return "REAL"
    return "PAPER"

# ================= BYBIT SIGNED HELPERS =================
def bybit_sign(params):
    qs = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()

def bybit_post(path, params):
    params["api_key"] = API_KEY
    params["timestamp"] = str(int(time.time()*1000))
    params["recv_window"] = "5000"
    params["sign"] = bybit_sign(params)
    r = requests.post(CONFIG["BYBIT_BASE"]+path, data=params, timeout=10)
    return r.json()

def bybit_get(path, params):
    params["api_key"] = API_KEY
    params["timestamp"] = str(int(time.time()*1000))
    params["recv_window"] = "5000"
    params["sign"] = bybit_sign(params)
    r = requests.get(CONFIG["BYBIT_BASE"]+path, params=params, timeout=10)
    return r.json()

def get_real_balance():
    try:
        res = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
        bal = float(res["result"]["list"][0]["coin"][0]["walletBalance"])
        STATE["real_balance"] = bal
        return bal
    except Exception as e:
        log(f"REAL BALANCE ERROR {e} - using last {STATE['real_balance']}")
        return STATE["real_balance"] or 0.0

def get_dynamic_qty(price, mode):
    if mode == "PAPER":
        return CONFIG["PAPER_QTY"]
    bal = get_real_balance()
    if bal <= 0:
        return CONFIG["REAL_MIN_QTY"]
    margin = bal * CONFIG["REAL_RISK_MARGIN_PCT"]
    pos = margin * CONFIG["LEVERAGE"]
    qty = pos / price if price else CONFIG["REAL_MIN_QTY"]
    qty = max(CONFIG["REAL_MIN_QTY"], min(qty, CONFIG["REAL_MAX_QTY"]))
    return round(qty, 3)

# ================= 1. PLACE REAL ORDER =================
def place_real_order(side, price, sl, tp, qty):
    if not API_KEY or not API_SECRET:
        log("REAL ORDER BLOCKED: No API keys in env - add BYBIT_API_KEY / SECRET for Render")
        return False
    try:
        bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": CONFIG["SYMBOL"], "buyLeverage": str(CONFIG["LEVERAGE"]), "sellLeverage": str(CONFIG["LEVERAGE"])})
        res = bybit_post("/v5/order/create", {
            "category": "linear", "symbol": CONFIG["SYMBOL"],
            "side": "Buy" if side == "LONG" else "Sell",
            "orderType": "Market", "qty": str(qty),
            "takeProfit": str(round(tp, 1)), "stopLoss": str(round(sl, 1)),
            "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice",
            "timeInForce": "GTC",
        })
        log(f"REAL ORDER PLACED {side} Qty {qty} Entry ~${price:.0f} SL ${sl:.0f} TP ${tp:.0f} Bybit: {res}")
        return res.get("retCode") == 0
    except Exception as e:
        log(f"REAL ORDER ERROR {e}")
        return False

# ================= 2. UPDATE REAL SL - BE / TRAILING =================
def update_real_sl(new_sl, side):
    if STATE["mode"] != "REAL":
        return True
    if not API_KEY:
        return False
    try:
        res = bybit_post("/v5/position/trading-stop", {
            "category": "linear", "symbol": CONFIG["SYMBOL"],
            "stopLoss": str(round(new_sl, 1)),
            "slTriggerBy": "LastPrice",
            "positionIdx": 0,
        })
        log(f"REAL SL UPDATED -> ${new_sl:.0f} Bybit: {res.get('retMsg')}")
        return res.get("retCode") == 0
    except Exception as e:
        log(f"REAL SL UPDATE ERROR {e}")
        return False

# ================= PRICE / KLINES / MACRO =================
def get_price():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=5)
        price = float(r.json()["result"]["list"][0]["lastPrice"])
        STATE["last_price"] = price
        return price
    except:
        return STATE["last_price"] or 68000.0

def get_klines(limit=20):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&limit={limit}", timeout=5)
        kl = list(reversed(r.json()["result"]["list"]))
        return [{"open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4])} for x in kl]
    except: return []

def get_macro():
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5)
        oi_list = r.json()["result"]["list"]
        oi_chg = (float(oi_list[-1]["openInterest"]) - float(oi_list[0]["openInterest"])) / float(oi_list[0]["openInterest"]) * 100
    except: oi_chg = 0
    return {"DXY_CHG": 0.18, "NQ_CHG": 0.70, "SPX_CHG": 0.64, "GOLD_CHG": 0.10, "OI_CHG": oi_chg}

def get_news_score():
    if not CONFIG["NEWS_ENABLED"]: return False, 0, ""
    kl = get_klines(15)
    if len(kl) >= 15:
        move = (kl[-1]["close"] - kl[0]["close"]) / kl[0]["close"] * 100
        if abs(move) >= 0.8: return True, 85.0, f"VOL SPIKE {move:.2f}% in 15m"
    return False, 0, ""

def get_signals(price, macro, klines):
    signals = []
    if macro["DXY_CHG"] > 0.10: signals.append(("DXY_LEVEL", "SHORT"))
    elif macro["DXY_CHG"] < -0.10: signals.append(("DXY_LEVEL", "LONG"))
    else: signals.append(("DXY_LEVEL", "NEUTRAL"))
    if macro["NQ_CHG"] > 0.20: signals.append(("NQ_MOMENTUM", "LONG"))
    elif macro["NQ_CHG"] < -0.20: signals.append(("NQ_MOMENTUM", "SHORT"))
    else: signals.append(("NQ_MOMENTUM", "NEUTRAL"))
    if macro["SPX_CHG"] > 0.20: signals.append(("SPX_MOMENTUM", "LONG"))
    elif macro["SPX_CHG"] < -0.20: signals.append(("SPX_MOMENTUM", "SHORT"))
    else: signals.append(("SPX_MOMENTUM", "NEUTRAL"))
    if macro["GOLD_CHG"] > 0.50: signals.append(("GOLD_AFTER_SWEEP", "SHORT"))
    elif macro["GOLD_CHG"] < -0.30: signals.append(("GOLD_AFTER_SWEEP", "LONG"))
    else: signals.append(("GOLD_AFTER_SWEEP", "NEUTRAL"))
    if klines and len(klines) >= 5:
        pc = (klines[-1]["close"] - klines[-5]["close"]) / klines[-5]["close"] * 100
        if macro["OI_CHG"] > 0.5 and pc < -0.2: signals.append(("OI_DIVERGENCE", "SHORT"))
        elif macro["OI_CHG"] < -0.5 and pc > 0.2: signals.append(("OI_DIVERGENCE", "LONG"))
        else: signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    else: signals.append(("OI_DIVERGENCE", "NEUTRAL"))
    if klines and len(klines) >= 3:
        last = klines[-1]; wd = last["close"] - last["low"]; wu = last["high"] - last["close"]
        thr = price * 0.002
        if wd > thr and wd > wu * 1.5: signals.append(("LIQ_SWEEP", "LONG"))
        elif wu > thr and wu > wd * 1.5: signals.append(("LIQ_SWEEP", "SHORT"))
        else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
    else: signals.append(("LIQ_SWEEP", "NEUTRAL"))
    return signals

def decide(signals):
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT")
    decided = longs + shorts
    if longs > shorts: dest, agree = "LONG", longs
    elif shorts > longs: dest, agree = "SHORT", shorts
    else: dest, agree = "NONE", 0
    return dest, agree, decided, longs, shorts, (agree / decided * 100) if decided else 0

def calc_score(signals, dest, macro, is_news):
    _, agree, decided, _, _, certainty = decide(signals)
    base = (certainty / 100) * 1.0; align = 0
    if dest == "LONG" and macro["NQ_CHG"] > 0 and macro["SPX_CHG"] > 0: align = 0.4
    if dest == "SHORT" and macro["DXY_CHG"] > 0: align = 0.3
    return round(base + align + (0.4 if is_news else 0), 2)

def calc_sl_tp(price, side, klines, is_sure):
    sl_dist = price * CONFIG["SL_PCT"]; wick_buf = price * CONFIG["WICK_BUFFER_PCT"]
    if klines:
        if side == "LONG":
            sl = min(price - sl_dist, min(c["low"] for c in klines[-15:]) - wick_buf); sl = max(sl, price * 0.988)
        else:
            sl = max(price + sl_dist, max(c["high"] for c in klines[-15:]) + wick_buf); sl = min(sl, price * 1.012)
    else:
        sl = price - sl_dist if side == "LONG" else price + sl_dist
    sl_f = abs(price - sl); mult = CONFIG["TP_MULT_SURE"] if is_sure else CONFIG["TP_MULT_NORMAL"]
    tp_dist = sl_f * mult; tp = price + tp_dist if side == "LONG" else price - tp_dist
    return round(sl, 1), round(tp, 1), round(sl_f, 1), round(tp_dist, 1)

def calc_fees_ev(price, sl_dist, tp_dist, winprob, qty):
    pos = qty * price; margin = pos / CONFIG["LEVERAGE"]
    fees = pos * CONFIG["FEE_RATE"] * 2
    slippage_cost = pos * CONFIG["SLIPPAGE_PCT"] * 2
    total_cost = fees + slippage_cost
    tp_profit = (qty * tp_dist) - total_cost
    sl_loss = (qty * sl_dist) + total_cost
    rr = tp_dist / sl_dist if sl_dist else 0
    ev = (winprob/100 * tp_profit) - ((1-winprob/100) * sl_loss)
    be = tp_profit >= (total_cost * CONFIG["MIN_TP_OVER_FEES"])
    return pos, margin, fees, slippage_cost, total_cost, tp_profit, sl_loss, rr, ev, be

def check_loss_control():
    today = now_utc().date()
    if STATE["day"] != today:
        STATE["day"] = today; STATE["trades_today"] = 0; STATE["losses_today"] = 0; STATE["last_loss_time"] = None
    if STATE["open_position"]: return False, "BLOCK: Already in position"
    if STATE["last_loss_time"]:
        mins = (now_utc() - STATE["last_loss_time"]).total_seconds() / 60
        if mins < CONFIG["COOLDOWN_AFTER_LOSS_MIN"]: return False, f"WARY: Cooldown {mins:.0f}/{CONFIG['COOLDOWN_AFTER_LOSS_MIN']}min"
    return True, ""

def get_dynamic_thresholds(is_news, just_lost):
    if just_lost: return CONFIG["AFTER_LOSS_CERTAINTY"], CONFIG["AFTER_LOSS_AGREE"], CONFIG["MIN_SCORE_NORMAL"]
    if is_news: return CONFIG["MIN_CERTAINTY_NEWS"], CONFIG["MIN_AGREE_NEWS"], CONFIG["MIN_SCORE_NEWS"]
    return CONFIG["MIN_CERTAINTY_NORMAL"], CONFIG["MIN_AGREE_NORMAL"], CONFIG["MIN_SCORE_NORMAL"]

# ================= MANAGE - BE + TRAILING FIRST =================
def manage_position(price, klines, qty):
    if not STATE["open_position"]: return
    p = STATE["open_position"]; entry = float(p["entry"]); side = p["side"]
    profit_pct = (price - entry) / entry if side == "LONG" else (entry - price) / entry

    # 1. BE OVER FEES+SLIPPAGE - FIRST
    if CONFIG["BE_OVER_FEES"] and not p.get("be_done"):
        if profit_pct >= CONFIG["BE_TRIGGER_PCT"]:
            be_buffer = entry * CONFIG["BE_BUFFER_PCT"]
            be_sl = entry + be_buffer if side == "LONG" else entry - be_buffer
            if (side == "LONG" and be_sl > p["sl"]) or (side == "SHORT" and be_sl < p["sl"]):
                p["sl"] = be_sl; p["be_done"] = True
                log(f"REAL BE OVER FEES+SLIPPAGE: SL -> ${be_sl:.0f} (Entry ${entry:.0f} +/- 0.24% = ${be_buffer:.2f} covers fees+slippage)")
                update_real_sl(be_sl, side)

    # 2. TRAILING - DYNAMIC
    if CONFIG["TRAILING_ENABLED"] and profit_pct >= CONFIG["TRAIL_START_PCT"]:
        if profit_pct >= CONFIG["TRAIL_STEP_3"]: td = CONFIG["TRAIL_DIST_3"]; label = "Trail 0.80% behind"
        elif profit_pct >= CONFIG["TRAIL_STEP_2"]: td = CONFIG["TRAIL_DIST_2"]; label = "Trail 0.60% behind"
        elif profit_pct >= CONFIG["TRAIL_STEP_1"]: td = CONFIG["TRAIL_DIST_1"]; label = "Trail 0.40% behind"
        else: td = None; label = ""
        if td is not None:
            new_sl = price - (price * td) if side == "LONG" else price + (price * td)
            if (side == "LONG" and new_sl > p["sl"]) or (side == "SHORT" and new_sl < p["sl"]):
                p["sl"] = new_sl
                log(f"REAL TRAILING {side}: SL -> ${new_sl:.0f} | Price ${price:.0f} Profit {profit_pct*100:.2f}% - {label}")
                update_real_sl(new_sl, side)

    # 3. TP / SL
    hit_tp = (price >= p["tp"] if side == "LONG" else price <= p["tp"])
    last_closed = klines[-2] if len(klines) >= 2 else None
    hit_sl = False
    if last_closed:
        if side == "LONG" and last_closed["close"] < p["sl"]: hit_sl = True
        if side == "SHORT" and last_closed["close"] > p["sl"]: hit_sl = True
    if hit_tp:
        profit = abs(price - entry) * qty
        STATE["balance"] += profit; STATE["pnl"] += profit; STATE["wins"] += 1
        log(f"TP HIT +${profit:.2f} - Closed {side} at ${price:.0f} - Bot continues, NEVER STOPS")
        STATE["open_position"] = None
    elif hit_sl:
        if p.get("be_done"):
            profit = abs(price - entry) * qty
            STATE["balance"] += profit; STATE["pnl"] += profit; STATE["breakevens"] += 1
            log(f"BE OVER FEES+SLIPPAGE HIT +${profit:.2f} - No loss, fees+slippage covered")
        else:
            loss = abs(price - entry) * qty
            STATE["balance"] -= loss; STATE["pnl"] -= loss; STATE["losses"] += 1; STATE["losses_today"] += 1; STATE["last_loss_time"] = now_utc()
            log(f"SL HIT -${loss:.2f} - WARY: Next need 85% + 6/6, 15min cooldown - NEVER STOPS")
        STATE["open_position"] = None

# ================= MAIN =================
def main():
    log("BOT V12.4 STARTED - Web Service + Flask Keep-Alive + Paper till Sun 8:30pm WAT -> Auto REAL")
    last_heartbeat = now_utc()
    while True:
        try:
            new_mode = get_mode()
            if new_mode != STATE["mode"]:
                STATE["mode"] = new_mode
                if new_mode == "REAL":
                    bal = get_real_balance()
                    log(f"*** AUTO SWITCH TO REAL *** Sun 8:30pm WAT reached - Real Balance met: ${bal:.2f} USDT - Bot go trade real now, Asia opening, good boy mode ON ***")
                    if STATE["open_position"]:
                        log("Closing paper position before REAL switch")
                        STATE["open_position"] = None
            mode = STATE["mode"]
            price = get_price(); klines = get_klines(20); macro = get_macro()
            is_news, _, news_reason = get_news_score()
            signals = get_signals(price, macro, klines)
            dest, agree, decided, longs, shorts, certainty = decide(signals)
            score = calc_score(signals, dest, macro, is_news)
            winprob = max(50, min(75, 50 + (certainty - 50) * 0.4))
            just_lost = STATE["last_loss_time"] is not None and (now_utc() - STATE["last_loss_time"]).total_seconds() < 3600
            need_cert, need_agree, need_score = get_dynamic_thresholds(is_news, just_lost)
            is_sure = (certainty >= CONFIG["SURE_CERTAINTY"] and agree >= CONFIG["SURE_AGREE"])
            mode_str = "SURE 95%+ WIDE TP" if is_sure else ("NEWS HUNTER" if is_news else "NORMAL")
            ok_control, control_reason = check_loss_control()
            qty = get_dynamic_qty(price, mode)

            if dest in ("LONG", "SHORT"):
                sl, tp, sl_dist, tp_dist = calc_sl_tp(price, dest, klines, is_sure)
                pos, margin, fees, slip, total_cost, tp_profit, sl_loss, rr, ev, be = calc_fees_ev(price, sl_dist, tp_dist, winprob, qty)
            else:
                sl = tp = sl_dist = tp_dist = pos = margin = fees = slip = total_cost = tp_profit = sl_loss = rr = ev = 0; be = False

            gates = []
            gates.append((f"Agree {agree}/{decided} Need {need_agree}", agree >= need_agree and decided >= need_agree))
            gates.append((f"Certainty {certainty:.0f}% Need {need_cert:.0f}%", certainty >= need_cert))
            gates.append((f"Score {score:.2f} / Thr {need_score:.2f}", score >= need_score))
            gates.append((f"WinProb {winprob:.0f}% Need {CONFIG['MIN_WINPROB']:.0f}%", winprob >= CONFIG["MIN_WINPROB"]))
            gates.append((f"TP Profit ${tp_profit:.4f} >= 3x TotalCost ${total_cost:.4f} (Fees ${fees:.4f}+Slip ${slip:.4f})", be))
            gates.append((f"RR {rr:.2f} Need {CONFIG['MIN_RR']}", rr >= CONFIG["MIN_RR"]))
            gates.append((f"EV ${ev:.4f} > 0", ev > 0))
            gates.append((f"LossControl", ok_control))
            all_pass = all(p for _, p in gates); failed = [n for n, p in gates if not p]

            bal_show = STATE["real_balance"] if mode == "REAL" else STATE["balance"]
            log(f"MODE {mode} | Long {longs} Short {shorts} DEST {dest} Cert {certainty:.0f}% Agree {agree}/{decided} {mode_str} {'Pass True' if all_pass else 'Pass False'}")
            log(f"Qty {qty} Bal ${bal_show:.2f} Pos ${pos:.0f} Margin ${margin:.2f} Lev {CONFIG['LEVERAGE']}x | Price ${price:.0f} SL ${sl:.0f} TP ${tp:.0f}")
            log(f"FEES ${fees:.4f} + SLIPPAGE ${slip:.4f} = Total ${total_cost:.4f} TP Profit ${tp_profit:.4f} >=3x {be} | W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']} NEVER_STOP True")

            if not all_pass:
                log(f"BLOCK/WARY: {'; '.join(failed)} {control_reason} - Bot still alive, will trade next cycle")
            else:
                log(f"TRADE SIGNAL - {mode} {dest} {mode_str} Entry ${price:.0f} SL ${sl:.0f} TP ${tp:.0f} Qty {qty}")
                if mode == "REAL":
                    ok = place_real_order(dest, price, sl, tp, qty)
                    if not ok:
                        log("REAL ORDER FAILED - No trade opened, will retry next cycle")
                        time.sleep(CONFIG["POLL_SEC"]); continue
                STATE["open_position"] = {"side": dest, "entry": price, "sl": sl, "tp": tp, "certainty": certainty, "is_sure": is_sure, "be_done": False}
                STATE["trades_today"] += 1; STATE["last_trade_time"] = now_utc()
                log(f"ORDER PLACED ({mode}) - Real SL on Bybit + BE/Trailing ACTIVE")

            manage_position(price, klines, qty)

            if (now_utc() - last_heartbeat).total_seconds() > CONFIG["HEARTBEAT_MIN"] * 60:
                log(f"HEARTBEAT OK - MODE {mode} - Bal ${bal_show:.2f} PnL ${STATE['pnl']:.2f}")
                last_heartbeat = now_utc()
            time.sleep(CONFIG["POLL_SEC"])
        except Exception as e:
            log(f"ERROR {e}"); time.sleep(10)

if __name__ == "__main__":
    main()
