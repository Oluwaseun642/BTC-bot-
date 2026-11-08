import time, requests, datetime, threading, os
from flask import Flask

# ===== V2.7 FINAL - PAPER $10 - NO PARTIAL - BE = PARTIAL =====
# FIX: Partial removed because $10 / $1.20 account = qty 0.001 only.
# Bybit no fit split 0.001. BE now dey do partial job:
# BE at +120 -> SL to Entry +100 -> locks profit over fees.
VIRTUAL_BALANCE = 10.00
SYMBOL = "BTCUSDT"
PORT = int(os.environ.get("PORT", 10000))
app = Flask(__name__)

@app.route("/")
def home(): return "WarshBot V2.7 PAPER ALIVE - $10 Virtual - BE = Partial - No Split"
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

def dynamic_params(balance, btc):
    # BYBIT MIN QTY 0.001 FIXED
    if balance < 5: lev = 10
    elif balance < 20: lev = 15
    elif balance < 50: lev = 20
    else: lev = 25
    pos_usd = min(balance * 0.5 * lev, balance * 8)
    qty_raw = pos_usd / btc if btc else 0.001
    qty = max(qty_raw, 0.001)
    qty = round(qty, 3)
    if qty < 0.001: qty = 0.001
    pos_usd = qty * btc
    fees = pos_usd * 0.0012
    return lev, qty, pos_usd, fees

def bot_loop():
    virtual_bal = VIRTUAL_BALANCE
    pnl_today = 0; wins = 0; losses = 0; be_hits = 0
    hidden = None; open_trade = None
    print("=== V2.7 DEPLOYED - $10 PAPER - NO PARTIAL - BE = PARTIAL ===", flush=True)
    while True:
        try:
            now = datetime.datetime.now(); btc = get_btc()
            if not btc: time.sleep(30); continue
            lev, qty, pos_usd, fees = dynamic_params(virtual_bal, btc)
            print(f"\n[{now.strftime('%H:%M WAT')}] PAPER Bal ${virtual_bal:.2f} | PnL ${pnl_today:.4f} | W {wins} L {losses} BE {be_hits} | BTC ${btc} | DYN {lev}x Qty {qty} Pos ${pos_usd:.2f} Fees ${fees:.4f}", flush=True)

            # === OPEN TRADE: BE = PARTIAL - NO SPLIT ===
            if open_trade:
                side = open_trade['side']; entry = open_trade['entry']; tp = open_trade['tp']; sl = open_trade['sl']
                move = (btc - entry) if side == "Buy" else (entry - btc)
                # BE = PARTIAL: If move >= 120, move SL to Entry +100 / -100
                # +100 * 0.001 = $0.10 gross - $0.09 fees = +$0.01 locked profit. Fees covered, small profit locked.
                # No need to split 0.001 qty. BE don do partial job.
                if not open_trade.get('be_done') and move >= 120:
                    open_trade['be_done'] = True; be_hits += 1
                    if side == "Buy": open_trade['sl'] = entry + 100
                    else: open_trade['sl'] = entry - 100
                    print(f"🛡️ BE = PARTIAL ACTIVATED! Move +120, SL -> Entry +100 (${open_trade['sl']}) - Fees covered + profit locked. No split needed for 0.001 qty.", flush=True)
                sl = open_trade['sl']
                hit_tp = (side == "Buy" and btc >= tp) or (side == "Sell" and btc <= tp)
                hit_sl = (side == "Buy" and btc <= sl) or (side == "Sell" and btc >= sl)
                if hit_tp or hit_sl:
                    # If BE hit SL, e don already lock +$0.01, no be loss
                    if hit_sl and open_trade.get('be_done'):
                        pnl = abs(100) * qty - fees  # +100 locked
                        print(f"🛡️ BE = PARTIAL SAVED US! SL hit at +100, PnL +${pnl:.4f} (fees covered). No loss.", flush=True)
                    elif hit_tp: pnl = abs(tp-entry)*qty - fees
                    else: pnl = -abs(sl-entry)*qty - fees
                    virtual_bal += pnl; pnl_today += pnl
                    if hit_tp: wins += 1; print(f"✅ WIN! {side} Entry ${entry} TP ${tp} PnL +${pnl:.4f} | Bal ${virtual_bal:.2f}", flush=True)
                    else:
                        if open_trade.get('be_done'): wins += 1; print(f"✅ BE WIN! {side} Entry ${entry} SL ${sl} PnL +${pnl:.4f} | Bal ${virtual_bal:.2f}", flush=True)
                        else: losses += 1; print(f"❌ SL! {side} Entry ${entry} SL ${sl} PnL ${pnl:.4f} | Bal ${virtual_bal:.2f}", flush=True)
                    open_trade = None
                else: print(f">>> OPEN {side} Entry ${entry} TP {tp} SL {sl} Cur ${btc} Move {move:+.0f} BE {'YES +100 LOCKED' if open_trade.get('be_done') else 'WAIT +120'}", flush=True)
                time.sleep(60); continue

            if hidden:
                trig = hidden['trigger']
                hit = (hidden['side']=="Buy" and btc <= trig) or (hidden['side']=="Sell" and btc >= trig)
                if hit: print(f"🔥 SWEEP REACH ${trig} - Hidden {hidden['side']} TRIGGER!", flush=True); open_trade = hidden; hidden = None
                else: print(f">>> HIDDEN {hidden['side']} wait Trig ${trig} Cur ${btc}", flush=True)
                time.sleep(60); continue

            if pnl_today <= -2.0: print("!!! Daily -$2 hit - SLEEP !!!", flush=True); time.sleep(3600*6); pnl_today = 0; continue

            dxy_p, dxy_pct = yahoo("DX-Y.NYB"); nq_p, nq_pct = yahoo("NQ=F"); spx_p, spx_pct = yahoo("ES=F")
            dax_p, dax_pct = yahoo("^GDAXI"); ftse_p, ftse_pct = yahoo("^FTSE"); nikkei_p, nikkei_pct = yahoo("^N225")
            oil_p, oil_pct = yahoo("CL=F"); gold_p, gold_pct = yahoo("GC=F")
            print(f"LIVE: DXY {dxy_pct:+.2f}% (${dxy_p}) | NQ {nq_pct:+.2f}% | SPX {spx_pct:+.2f}% | DAX {dax_pct:+.2f}% | FTSE {ftse_pct:+.2f}% | Nikkei {nikkei_pct:+.2f}% | Oil {oil_pct:+.2f}% | Gold {gold_pct:+.2f}%", flush=True)
            if now.hour == 1 and now.minute < 45: print(">> ASIA 1:00-1:45 WAIT SWEEP", flush=True); time.sleep(60); continue
            if oil_p and oil_p > 100: print(">> Oil >100 SHIELD - WAIT", flush=True); time.sleep(180); continue

            is_weekend = now.weekday() >= 5
            direction = None; reason = ""
            if is_weekend:
                print(f">> WEEKEND MODE: Stocks closed, use BTC + DXY only", flush=True)
                if dxy_pct < 0: direction = "Buy"; reason = "Weekend + DXY falling = LONG"
                elif dxy_pct > 0: direction = "Sell"; reason = "Weekend + DXY rising = SHORT"
                else: direction = "Buy"; reason = "Weekend + DXY flat = BUY DIP"
            else:
                greens = sum(1 for x in [nq_pct, spx_pct, dax_pct, ftse_pct, nikkei_pct] if x > 0)
                if dxy_pct < 0.1 and nq_pct >= -0.2 and greens >= 2: direction = "Buy"; reason = f"DXY not strong + {greens}/5 green = LONG"
                elif dxy_pct > 0.1 and nq_pct <= 0.2 and greens <= 3: direction = "Sell"; reason = f"DXY strong + {greens}/5 green = SHORT"
                else: print(f"=> NO CLEAR: DXY {dxy_pct:+.2f}% Greens {greens}/5 - WAIT", flush=True); time.sleep(180); continue

            bank_trap = (direction=="Buy" and dxy_pct > 0.2 and nq_pct < -0.3) or (direction=="Sell" and dxy_pct < -0.2 and nq_pct > 0.3)
            if bank_trap and not is_weekend: print(">> BANK TRAP: NO FOLLOW", flush=True); time.sleep(180); continue

            if direction == "Buy": trigger = int(btc-250); entry = trigger; tp = int(btc+150); sl = int(trigger-180)
            else: trigger = int(btc+250); entry = trigger; tp = int(btc-150); sl = int(trigger+180)
            est = abs(tp-entry)*qty
            print(f"GOLD: {direction} Trig ${trigger} TP {tp} SL {sl} Est ${est:.4f} vs Fees ${fees:.4f}+0.08 | {reason}", flush=True)
            if est <= (fees+0.08): print("=> Gold too close - SKIP", flush=True); time.sleep(180); continue
            # NO partial_done again - BE dey do am
            hidden = {"side": direction, "trigger": trigger, "entry": entry, "tp": tp, "sl": sl, "qty": qty, "be_done": False}
            print(f"✅ HIDDEN {direction} PLACED Trig ${trigger} TP {tp} SL {sl} BE=Partial at +120. NO REAL MONEY.", flush=True)
            time.sleep(180)
        except Exception as e: print(f"Error {e} retry 30s", flush=True); time.sleep(30)

if __name__ == "__main__":
    keep_alive(); bot_loop()
