import time, requests, datetime, threading, os
from flask import Flask

# ===== PAPER MODE - NO REAL MONEY =====
VIRTUAL_BALANCE = 10.00
SYMBOL = "BTCUSDT"
PORT = int(os.environ.get("PORT", 10000))

app = Flask(__name__)

@app.route("/")
def home():
    return f"WarshBot V2.3 PAPER ALIVE - Virtual Bal ${VIRTUAL_BALANCE} - Trade Like Real - No Real Money"

@app.route("/health")
def health():
    return "OK"

def keep_alive():
    # Flask for Render - must bind 0.0.0.0 + PORT from Render
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT, threaded=True), daemon=True).start()
    def ping():
        while True:
            try:
                requests.get(f"http://localhost:{PORT}/health", timeout=5)
                print(f"[SELF-PING] ALIVE {datetime.datetime.now().strftime('%H:%M')} - 200 OK", flush=True)
            except Exception as e:
                print(f"[SELF-PING] fail {e}", flush=True)
            time.sleep(600)
    threading.Thread(target=ping, daemon=True).start()

def yahoo(t):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?interval=1m&range=1d", headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        meta = r['chart']['result'][0]['meta']
        price = meta['regularMarketPrice']
        prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        pct = ((price - prev) / prev * 100) if prev else 0
        return price, pct
    except Exception as e:
        print(f"Yahoo {t} fail {e}", flush=True)
        return None, 0

def get_btc():
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT"
        r = requests.get(url, timeout=8).json()
        return float(r['result']['list'][0]['lastPrice'])
    except Exception as e:
        print(f"BTC fetch fail {e}", flush=True)
        return None

def dynamic_params(balance, btc):
    if balance < 5:
        lev = 10
    elif balance < 20:
        lev = 15
    else:
        lev = 20
    pos_usd = min(balance * 0.5 * lev, balance * 8)
    qty = round(pos_usd / btc, 5) if btc else 0.0001
    qty = max(min(qty, 0.005), 0.00005)
    fees = pos_usd * 0.0012
    return lev, qty, pos_usd, fees

def bot_loop():
    virtual_bal = VIRTUAL_BALANCE
    virtual_pnl_today = 0
    hidden_entry = None
    open_trade = None
    wins = 0
    losses = 0
    print("=== WarshBot V2.3 PAPER DEPLOYED - $10 VIRTUAL - TRADE LIKE REAL - NO REAL MONEY ===", flush=True)
    print("If e win wella till Monday, we go allow real $ on Monday.", flush=True)
    while True:
        try:
            now = datetime.datetime.now()
            btc = get_btc()
            if not btc:
                print("BTC fetch fail - retry 30s", flush=True)
                time.sleep(30)
                continue
            lev, qty, pos_usd, fees = dynamic_params(virtual_bal, btc)
            print(f"\n[{now.strftime('%H:%M WAT')}] PAPER Bal ${virtual_bal:.2f} | Today PnL ${virtual_pnl_today:.4f} | Wins {wins} Loss {losses} | BTC ${btc} | DYN {lev}x Qty {qty} Pos ${pos_usd:.2f} Fees ${fees:.4f}", flush=True)

            if open_trade:
                side = open_trade['side']; entry = open_trade['entry']; tp = open_trade['tp']; sl = open_trade['sl']
                hit_tp = (side == "Buy" and btc >= tp) or (side == "Sell" and btc <= tp)
                hit_sl = (side == "Buy" and btc <= sl) or (side == "Sell" and btc >= sl)
                if hit_tp or hit_sl:
                    pnl = (abs(tp - entry) * qty - fees) if hit_tp else (-abs(sl - entry) * qty - fees)
                    virtual_bal += pnl; virtual_pnl_today += pnl
                    if hit_tp:
                        wins += 1
                        print(f"✅ PAPER CASH OUT WIN! {side} Entry ${entry} TP ${tp} PnL +${pnl:.4f} | New Bal ${virtual_bal:.2f}", flush=True)
                    else:
                        losses += 1
                        print(f"❌ PAPER SL HIT! {side} Entry ${entry} SL ${sl} PnL ${pnl:.4f} | New Bal ${virtual_bal:.2f}", flush=True)
                    open_trade = None
                else:
                    print(f">>> PAPER Trade OPEN: {side} Entry ${entry} TP {tp} SL {sl} Current ${btc} - WAIT CASH OUT", flush=True)
                time.sleep(60)
                continue

            if hidden_entry:
                trig = hidden_entry['trigger']
                hit = (hidden_entry['side'] == "Buy" and btc <= trig) or (hidden_entry['side'] == "Sell" and btc >= trig)
                if hit:
                    print(f"🔥 PAPER SWEEP REACH TRIGGER ${trig} - Hidden {hidden_entry['side']} don TRIGGER like real!", flush=True)
                    open_trade = hidden_entry; hidden_entry = None
                else:
                    print(f">>> PAPER Hidden {hidden_entry['side']} dey wait: Trigger ${trig} Current ${btc} - HIDE TILL CASH OUT", flush=True)
                time.sleep(60)
                continue

            if virtual_pnl_today <= -2.0:
                print("!!! PAPER Daily loss -$2 hit - SLEEP TILL TOMORROW !!!", flush=True)
                time.sleep(3600*6); virtual_pnl_today = 0; continue

            dxy_p, dxy_pct = yahoo("DX-Y.NYB"); nq_p, nq_pct = yahoo("NQ=F"); spx_p, spx_pct = yahoo("ES=F")
            dax_p, dax_pct = yahoo("^GDAXI"); ftse_p, ftse_pct = yahoo("^FTSE"); nikkei_p, nikkei_pct = yahoo("^N225")
            oil_p, oil_pct = yahoo("CL=F"); gold_p, gold_pct = yahoo("GC=F")
            print(f"LIVE: DXY {dxy_pct:+.2f}% | NQ {nq_pct:+.2f}% | SPX {spx_pct:+.2f}% | DAX {dax_pct:+.2f}% | FTSE {ftse_pct:+.2f}% | Nikkei {nikkei_pct:+.2f}% | Oil {oil_pct:+.2f}% | Gold {gold_pct:+.2f}%", flush=True)

            if now.hour == 1 and now.minute < 45:
                print(">> ASIA 1:00-1:45 - WAIT SWEEP, NO NEW HIDDEN ENTRY", flush=True)
                time.sleep(60); continue

            direction = None; reason = ""
            if dxy_p and dxy_p < 102.38 and nq_pct > 0 and spx_pct > 0:
                direction = "Buy"; reason = "DXY reject + NQ green + SPX green = LONG"
            elif dxy_p and dxy_p > 102.50 and nq_pct < 0 and spx_pct < 0:
                direction = "Sell"; reason = "DXY break + NQ red + SPX red = SHORT"
            else:
                print("=> Market no clear / banks fit dey trap - NO HIDDEN ENTRY, SPECTATE ONLY", flush=True)
                time.sleep(180); continue

            bank_trap = (direction == "Buy" and dxy_pct > 0.2 and nq_pct < -0.3) or (direction == "Sell" and dxy_pct < -0.2 and nq_pct > 0.3)
            if bank_trap:
                print(">> BANK TRAP: Banks dey buy/sell dip but trend disagree - NO FOLLOW BLINDLY", flush=True)
                time.sleep(180); continue

            if oil_p and oil_p > 100:
                print(">> Oil > $100 SHIELD - WAIT", flush=True)
                time.sleep(180); continue

            if direction == "Buy":
                trigger = int(btc - 600); entry = trigger; tp = int(btc + 300); sl = int(trigger - 400)
            else:
                trigger = int(btc + 600); entry = trigger; tp = int(btc - 300); sl = int(trigger + 400)
            est = abs(tp - entry) * qty
            print(f"GOLD: {direction} Trigger ${trigger} TP {tp} SL {sl} Est ${est:.4f} vs Fees ${fees:.4f} + $0.08 | {reason}", flush=True)
            if est <= (fees + 0.08):
                print("=> Gold too close, profit no pass fees - SKIP", flush=True)
                time.sleep(180); continue

            hidden_entry = {"side": direction, "trigger": trigger, "entry": entry, "tp": tp, "sl": sl, "qty": qty}
            print(f"✅ PAPER HIDDEN {direction} PLACED: Trigger ${trigger} TP {tp} SL {sl} | Hide till sweep reach am, then cash out like real. NO REAL MONEY.", flush=True)
            time.sleep(180)
        except Exception as e:
            print(f"Error {e} retry 30s", flush=True)
            time.sleep(30)

if __name__ == "__main__":
    keep_alive()
    bot_loop()
