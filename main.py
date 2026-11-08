import time, requests, datetime, threading, os
from flask import Flask
import statistics

# ===== V3.0 DYNAMIC EVERYTHING - PAPER $10 - BE OVER ALL FEES =====
# NO FIXED PRICE. NO FIXED TP/SL. NO BLIND TRADE.
# BE = Trading Fee + Funding Fee + Leverage Fee + Buffer
# If TP no cover BE, SKIP. If trigger no update, TRAIL am.
VIRTUAL_BALANCE = 10.00
SYMBOL = "BTCUSDT"
PORT = int(os.environ.get("PORT", 10000))
app = Flask(__name__)

@app.route("/")
def home(): return "WarshBot V3.0 DYNAMIC EVERYTHING - PAPER $10 - BE OVER ALL FEES"
@app.route("/health")
def health(): return "OK"

def keep_alive():
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT, threaded=True), daemon=True).start()
    def ping():
        while True:
            try: requests.get(f"http://localhost:{PORT}/health", timeout=5)
            except: pass
            time.sleep(600)
    threading.Thread(target=ping, daemon=True).start()

def yahoo(t):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?interval=1m&range=1d", headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        meta = r['chart']['result'][0]['meta']; price = meta['regularMarketPrice']; prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        return price, ((price-prev)/prev*100) if prev else 0
    except: return None, 0

def get_btc():
    try: return float(requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=8).json()['result']['list'][0]['lastPrice'])
    except: return None

def get_klines():
    # For ATR + EMA + RSI - live
    try:
        r = requests.get("https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&limit=50", timeout=8).json()
        closes = [float(x[4]) for x in r['result']['list'][::-1]]
        highs = [float(x[2]) for x in r['result']['list'][::-1]]
        lows = [float(x[3]) for x in r['result']['list'][::-1]]
        return closes, highs, lows
    except: return [], [], []

def calc_ema(prices, period):
    if len(prices) < period: return prices[-1] if prices else 0
    k = 2 / (period + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema

def calc_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains, losses = [], []
    for i in range(1, period+1):
        d = prices[-i] - prices[-i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_g = sum(gains)/period; avg_l = sum(losses)/period
    if avg_l == 0: return 100
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < 2: return 120
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        trs.append(tr)
    atr = sum(trs[-period:]) / min(len(trs), period)
    return max(atr, 60)  # floor so SL no too tight

def dynamic_params(balance, btc, atr):
    # DYNAMIC LEVERAGE - based on volatility, not fixed
    # High ATR = low lev (danger), Low ATR = higher lev (safe)
    if atr > 250: lev = 10
    elif atr > 150: lev = 15
    elif atr > 80: lev = 20
    else: lev = 25
    # DYNAMIC QTY - risk 2% only, qty from ATR distance
    risk_usd = balance * 0.02  # $0.20 for $10
    qty_raw = risk_usd / max(atr, 1)  # risk / SL distance
    qty = max(round(qty_raw, 3), 0.001)
    pos_usd = qty * btc
    # Cap pos to 8x balance max
    if pos_usd > balance * 8:
        qty = round((balance * 8) / btc, 3)
        qty = max(qty, 0.001)
        pos_usd = qty * btc
    return lev, qty, pos_usd

def calc_all_fees(pos_usd, lev, qty):
    trading_fee = pos_usd * 0.0012  # Bybit taker ~0.06% x2 (open+close) + buffer
    funding_fee = pos_usd * 0.0001  # funding prorated
    leverage_fee = pos_usd * (lev * 0.00005)  # borrow / interest
    buffer = 0.08  # extra safety
    total = trading_fee + funding_fee + leverage_fee + buffer
    be_distance = total / max(qty, 0.001)  # price move needed to cover ALL fees
    return trading_fee, funding_fee, leverage_fee, total, be_distance

def bot_loop():
    virtual_bal = VIRTUAL_BALANCE
    pnl_today = 0; wins = 0; losses = 0; be_hits = 0
    hidden = None; open_trade = None
    price_history = []
    print("=== V3.0 DYNAMIC EVERYTHING DEPLOYED - $10 PAPER - BE OVER ALL FEES ===", flush=True)
    while True:
        try:
            now = datetime.datetime.now(); btc = get_btc()
            if not btc: time.sleep(30); continue
            closes, highs, lows = get_klines()
            if closes:
                price_history = closes
            atr = calc_atr(highs, lows, closes) if closes else 120
            ema9 = calc_ema(closes, 9) if closes else btc
            ema21 = calc_ema(closes, 21) if closes else btc
            ema50 = calc_ema(closes, 50) if closes else btc
            rsi = calc_rsi(closes) if closes else 50
            lev, qty, pos_usd = dynamic_params(virtual_bal, btc, atr)
            trading_fee, funding_fee, leverage_fee, total_fees, be_dist = calc_all_fees(pos_usd, lev, qty)

            print(f"\n[{now.strftime('%H:%M WAT')}] PAPER Bal ${virtual_bal:.2f} | PnL ${pnl_today:.4f} | W {wins} L {losses} BE {be_hits} | BTC ${btc} | DYN {lev}x Qty {qty} Pos ${pos_usd:.2f}", flush=True)
            print(f"DYNAMIC: EMA9 ${ema9:.0f} EMA21 ${ema21:.0f} EMA50 ${ema50:.0f} RSI {rsi:.1f} ATR ${atr:.0f} | FEES Trade ${trading_fee:.4f} Fund ${funding_fee:.4f} Lev ${leverage_fee:.4f} TOTAL ${total_fees:.4f} BE Dist ${be_dist:.0f}", flush=True)

            # === OPEN TRADE: DYNAMIC BE + DYNAMIC TRAILING EXIT ===
            if open_trade:
                side = open_trade['side']; entry = open_trade['entry']; tp = open_trade['tp']; sl = open_trade['sl']
                be_dist_trade = open_trade['be_dist']
                move = (btc - entry) if side == "Buy" else (entry - btc)
                # DYNAMIC BE: When move >= BE distance, move SL to Entry + BE distance (covers ALL fees)
                if not open_trade.get('be_done') and move >= be_dist_trade:
                    open_trade['be_done'] = True; be_hits += 1
                    if side == "Buy": open_trade['sl'] = entry + be_dist_trade
                    else: open_trade['sl'] = entry - be_dist_trade
                    print(f"🛡️ DYNAMIC BE ACTIVATED! Move +{move:.0f} >= BE ${be_dist_trade:.0f}, SL -> Entry + BE (${open_trade['sl']:.0f}) - ALL FEES COVERED (Trade+Funding+Leverage).", flush=True)
                # DYNAMIC TRAILING: If move > ATR, trail SL by ATR*0.5 to lock more profit
                if open_trade.get('be_done') and move > atr:
                    trail_sl = (btc - atr*0.5) if side == "Buy" else (btc + atr*0.5)
                    if (side == "Buy" and trail_sl > open_trade['sl']) or (side == "Sell" and trail_sl < open_trade['sl']):
                        open_trade['sl'] = trail_sl
                        print(f"📈 TRAILING SL -> ${trail_sl:.0f} - Locking profit dynamically.", flush=True)
                sl = open_trade['sl']
                hit_tp = (side == "Buy" and btc >= tp) or (side == "Sell" and btc <= tp)
                hit_sl = (side == "Buy" and btc <= sl) or (side == "Sell" and btc >= sl)
                # DYNAMIC TIME EXIT: If trade don stay > 120 mins and no move, close to free capital
                age_mins = (now - open_trade['opened_at']).total_seconds() / 60
                if age_mins > 120 and abs(move) < be_dist_trade:
                    print(f"⏰ TIME EXIT: 120 mins no progress, closing to free capital.", flush=True)
                    hit_sl = True  # force close, pnl calc below will handle
                if hit_tp or hit_sl:
                    if hit_sl and open_trade.get('be_done'):
                        # BE SL hit = profit = BE distance * qty - total fees (should be >= buffer)
                        pnl = abs(be_dist_trade) * qty - (trading_fee + funding_fee + leverage_fee)
                        print(f"🛡️ BE SAVED! SL hit at BE, PnL +${pnl:.4f} (ALL fees covered).", flush=True)
                    elif hit_tp: pnl = abs(tp-entry)*qty - (trading_fee + funding_fee + leverage_fee)
                    else: pnl = -abs(sl-entry)*qty - (trading_fee + funding_fee + leverage_fee)
                    virtual_bal += pnl; pnl_today += pnl
                    if pnl > 0: wins += 1; print(f"✅ WIN! {side} Entry ${entry} Exit ${btc:.0f} PnL +${pnl:.4f} | Bal ${virtual_bal:.2f}", flush=True)
                    else: losses += 1; print(f"❌ LOSS! {side} Entry ${entry} Exit ${btc:.0f} PnL ${pnl:.4f} | Bal ${virtual_bal:.2f}", flush=True)
                    open_trade = None
                else: print(f">>> OPEN {side} Entry ${entry} TP {tp:.0f} SL {sl:.0f} Cur ${btc} Move {move:+.0f} BE {'DONE' if open_trade.get('be_done') else f'WAIT {be_dist_trade:.0f}'}", flush=True)
                time.sleep(60); continue

            # === HIDDEN / WAITING - DYNAMIC TRAILING TRIGGER, NO FIXED PRICE ===
            if hidden:
                # TRAIL TRIGGER WITH PRICE - this is the fix for "wait forever"
                # If price moves favourably, move trigger with it
                old_trig = hidden['trigger']
                if hidden['side'] == "Buy":
                    # For Buy, we want dip. If BTC goes up, raise trigger to follow (no wait forever)
                    new_trig = btc - atr * 0.5
                    if new_trig > old_trig:
                        hidden['trigger'] = new_trig
                        hidden['entry'] = new_trig
                        # Recalc TP/SL dynamically too
                        hidden['tp'] = new_trig + atr * 1.8
                        hidden['sl'] = new_trig - atr * 1.0
                        print(f"🔄 DYNAMIC TRAIL UP: Trig ${old_trig:.0f} -> ${new_trig:.0f} (BTC moved up, trigger follows, no wait forever)", flush=True)
                else:
                    new_trig = btc + atr * 0.5
                    if new_trig < old_trig:
                        hidden['trigger'] = new_trig
                        hidden['entry'] = new_trig
                        hidden['tp'] = new_trig - atr * 1.8
                        hidden['sl'] = new_trig + atr * 1.0
                        print(f"🔄 DYNAMIC TRAIL DOWN: Trig ${old_trig:.0f} -> ${new_trig:.0f} (BTC moved down, trigger follows)", flush=True)
                trig = hidden['trigger']
                # Check hit + BREAKOUT: If price pumps hard, enter immediately, no wait for trigger
                momentum_5m = 0
                if len(closes) >= 5:
                    momentum_5m = (closes[-1] - closes[-5]) / closes[-5] * 100
                breakout_buy = hidden['side'] == "Buy" and momentum_5m > 0.4
                breakout_sell = hidden['side'] == "Sell" and momentum_5m < -0.4
                hit = (hidden['side']=="Buy" and btc <= trig) or (hidden['side']=="Sell" and btc >= trig)
                if hit or breakout_buy or breakout_sell:
                    reason = "TRIGGER HIT" if hit else f"BREAKOUT {momentum_5m:+.2f}% - ENTER NOW, NO WAIT"
                    print(f"🔥 {reason} - DYNAMIC {hidden['side']} ENTER @ ${btc:.0f}", flush=True)
                    open_trade = {**hidden, "entry": btc, "opened_at": now, "be_done": False}
                    # Recalc TP/SL from actual entry
                    if hidden['side'] == "Buy":
                        open_trade['tp'] = btc + atr * 1.8; open_trade['sl'] = btc - atr * 1.0
                    else:
                        open_trade['tp'] = btc - atr * 1.8; open_trade['sl'] = btc + atr * 1.0
                    hidden = None
                else: print(f">>> DYNAMIC HIDDEN {hidden['side']} wait Trig ${trig:.0f} Cur ${btc} ATR ${atr:.0f} Momentum5m {momentum_5m:+.2f}%", flush=True)
                time.sleep(60); continue

            if pnl_today <= -2.0: print("!!! Daily -$2 hit - SLEEP !!!", flush=True); time.sleep(3600*6); pnl_today = 0; continue

            dxy_p, dxy_pct = yahoo("DX-Y.NYB"); nq_p, nq_pct = yahoo("NQ=F"); spx_p, spx_pct = yahoo("ES=F")
            dax_p, dax_pct = yahoo("^GDAXI"); ftse_p, ftse_pct = yahoo("^FTSE"); nikkei_p, nikkei_pct = yahoo("^N225")
            oil_p, oil_pct = yahoo("CL=F"); gold_p, gold_pct = yahoo("GC=F")
            print(f"LIVE: DXY {dxy_pct:+.2f}% | NQ {nq_pct:+.2f}% | SPX {spx_pct:+.2f}% | DAX {dax_pct:+.2f}% | FTSE {ftse_pct:+.2f}% | Nikkei {nikkei_pct:+.2f}% | Oil {oil_pct:+.2f}% | Gold {gold_pct:+.2f}%", flush=True)
            if now.hour == 1 and now.minute < 45: print(">> ASIA 1:00-1:45 WAIT SWEEP", flush=True); time.sleep(60); continue
            if oil_p and oil_p > 100: print(">> Oil >100 SHIELD - WAIT", flush=True); time.sleep(180); continue

            # === DYNAMIC DIRECTION - EMA + RSI + DXY + STOCKS, NO FIXED BIAS ===
            is_weekend = now.weekday() >= 5
            direction = None; reason = ""
            # BTC trend score
            btc_trend = 0
            if ema9 > ema21: btc_trend += 1
            if ema21 > ema50: btc_trend += 1
            if rsi > 50: btc_trend += 1
            if rsi < 50: btc_trend -= 1
            if ema9 < ema21: btc_trend -= 1
            if ema21 < ema50: btc_trend -= 1

            if is_weekend:
                if dxy_pct < 0 or btc_trend > 0: direction = "Buy"; reason = f"Weekend DXY {dxy_pct:+.2f}% BTC Trend {btc_trend} = LONG"
                elif dxy_pct > 0 or btc_trend < 0: direction = "Sell"; reason = f"Weekend DXY {dxy_pct:+.2f}% BTC Trend {btc_trend} = SHORT"
            else:
                greens = sum(1 for x in [nq_pct, spx_pct, dax_pct, ftse_pct, nikkei_pct] if x > 0)
                # Combined score: BTC trend + Stocks + DXY
                score = btc_trend + (1 if greens >= 3 else -1 if greens <= 2 else 0) + (1 if dxy_pct < 0.1 else -1 if dxy_pct > 0.1 else 0)
                if score >= 2: direction = "Buy"; reason = f"Score {score} BTC {btc_trend} Greens {greens}/5 DXY {dxy_pct:+.2f}% = LONG"
                elif score <= -2: direction = "Sell"; reason = f"Score {score} BTC {btc_trend} Greens {greens}/5 DXY {dxy_pct:+.2f}% = SHORT"
                else: print(f"=> NO CLEAR: Score {score} BTC Trend {btc_trend} Greens {greens}/5 DXY {dxy_pct:+.2f}% RSI {rsi:.1f} - WAIT", flush=True); time.sleep(120); continue

            bank_trap = (direction=="Buy" and dxy_pct > 0.2 and nq_pct < -0.3) or (direction=="Sell" and dxy_pct < -0.2 and nq_pct > 0.3)
            if bank_trap and not is_weekend: print(">> BANK TRAP: NO FOLLOW", flush=True); time.sleep(120); continue

            # === DYNAMIC TP/SL + BE CHECK - IF NO COVER FEES, NO TRADE ===
            if direction == "Buy":
                trigger = btc - atr * 0.5; entry = trigger; tp = entry + atr * 1.8; sl = entry - atr * 1.0
            else:
                trigger = btc + atr * 0.5; entry = trigger; tp = entry - atr * 1.8; sl = entry + atr * 1.0
            # Re-calc fees for this specific setup
            _, _, _, total_fees_setup, be_dist_setup = calc_all_fees(pos_usd, lev, qty)
            est_profit = abs(tp - entry) * qty - total_fees_setup
            est_be_cover = abs(tp - entry) - be_dist_setup
            print(f"DYNAMIC GOLD: {direction} Trig ${trigger:.0f} TP ${tp:.0f} SL ${sl:.0f} ATR ${atr:.0f} Est Profit ${est_profit:.4f} BE Dist ${be_dist_setup:.0f} Total Fees ${total_fees_setup:.4f} | {reason}", flush=True)
            # CRITICAL: If trade won't cover BE over ALL fees, SKIP - no blind trade
            if est_profit <= 0.05 or est_be_cover < 20:
                print(f"⛔ SKIP - Trade NO cover BE over ALL fees! Est ${est_profit:.4f} BE need ${be_dist_setup:.0f} move, TP only {abs(tp-entry):.0f} move. Fees: Trade+Funding+Leverage = ${total_fees_setup:.4f}. WAITING for better setup.", flush=True)
                time.sleep(120); continue
            hidden = {"side": direction, "trigger": trigger, "entry": entry, "tp": tp, "sl": sl, "qty": qty, "be_done": False, "be_dist": be_dist_setup, "lev": lev}
            print(f"✅ DYNAMIC HIDDEN {direction} PLACED Trig ${trigger:.0f} TP ${tp:.0f} SL ${sl:.0f} BE Dist ${be_dist_setup:.0f} (covers Trade+Funding+Leverage). NO FIXED PRICE.", flush=True)
            time.sleep(120)
        except Exception as e: print(f"Error {e} retry 30s", flush=True); time.sleep(30)

if __name__ == "__main__":
    keep_alive(); bot_loop()
