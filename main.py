import os, time, math, requests, datetime
import threading

# --- RENDER KEEP-ALIVE ---
try:
    from flask import Flask
    app = Flask(__name__)
    @app.route('/')
    def home(): return "V5.1 Human Skull Brain is alive!"
    def run_web():
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
    threading.Thread(target=run_web, daemon=True).start()
    print("Keep-alive started", flush=True)
except Exception as e:
    print(f"Keep-alive skip: {e}", flush=True)
# --- END ---

START_BAL = 10.0
paper_balance = START_BAL
paper_pnl = 0.0
wins = 0; losses = 0; be_hits = 0
open_pos = None; waiting = None
history = []
consecutive_losses = 0
consecutive_wins = 0
# Backup memory - if API fail, use last good value, never 0 blind
last_macro = {"DXY":0.0,"SPX":0.0,"NQ":0.0,"DAX":0.0,"FTSE":0.0,"NIKKEI":0.0,"OIL":0.0,"GOLD":0.0}

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{now} [V5.1-HUMAN] {msg}", flush=True)

# ============ FAST DATA WITH 3 BACKUPS - NO YFINANCE ============
def yahoo_direct(symbol, host):
    try:
        url = f"https://{host}/v8/finance/chart/{symbol}?range=2d&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5).json()
        closes = r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            return (closes[-1]-closes[-2])/closes[-2]*100
        return None
    except:
        return None

def stooq_backup(symbol):
    # Stooq - never blocks, CSV format, best backup
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        r = requests.get(url, timeout=5).text.strip().split("\n")
        # Format: Date,Open,High,Low,Close,Volume
        if len(r) >= 3:
            last = r[-1].split(",")
            prev = r[-2].split(",")
            c1 = float(last[4]); c0 = float(prev[4])
            if c0 != 0:
                return (c1-c0)/c0*100
        return None
    except:
        return None

def fast_yahoo(symbol, stooq_symbol):
    # Try 1: Yahoo query1, Try 2: Yahoo query2, Try 3: Stooq
    v = yahoo_direct(symbol, "query1.finance.yahoo.com")
    if v is not None:
        return v
    v = yahoo_direct(symbol, "query2.finance.yahoo.com")
    if v is not None:
        return v
    v = stooq_backup(stooq_symbol)
    if v is not None:
        return v
    return None

def get_macro_all():
    global last_macro
    # symbol map: (yahoo_symbol, stooq_symbol)
    mapping = {
        "DXY": ("DX-Y.NYB", "dx-y.nyb"),
        "SPX": ("%5EGSPC", "^spx"),
        "NQ": ("%5EIXIC", "^ixic"),
        "DAX": ("%5EGDAXI", "^gdaxi"),
        "FTSE": ("%5EFTSE", "^ftse"),
        "NIKKEI": ("%5EN225", "^n225"),
        "OIL": ("CL%3DF", "cl.f"),
        "GOLD": ("GC%3DF", "gc.f"),
    }
    out = {}
    for k, (ys, ss) in mapping.items():
        v = fast_yahoo(ys, ss)
        if v is not None:
            out[k] = v
            last_macro[k] = v
        else:
            out[k] = last_macro[k]  # Use last good, never blind 0
            log(f"Macro backup used for {k}: {out[k]:+.2f}% (last good)")
    return out

def get_bybit_klines(symbol="BTCUSDT", interval="1", limit=200):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}", timeout=8).json()
        kl = r["result"]["list"][::-1]
        closes = [float(x[4]) for x in kl]
        highs = [float(x[2]) for x in kl]
        lows = [float(x[3]) for x in kl]
        vols = [float(x[5]) for x in kl]
        return closes, highs, lows, vols
    except:
        return None, None, None, None

def get_bybit_smart_money():
    out = {"funding": 0.0, "oi_change": 0.0, "long_short": 1.0}
    try:
        f = requests.get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1", timeout=5).json()
        out["funding"] = float(f["result"]["list"][0]["fundingRate"]) * 100
    except: pass
    try:
        o = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=2", timeout=5).json()
        lst = o["result"]["list"]
        if len(lst) >= 2:
            out["oi_change"] = (float(lst[0]["openInterest"]) - float(lst[1]["openInterest"])) / float(lst[1]["openInterest"]) * 100
    except: pass
    try:
        ls = requests.get("https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=5min&limit=1", timeout=5).json()
        out["long_short"] = float(ls["result"]["list"][0]["longShortRatio"])
    except: pass
    return out

def get_fear_greed():
    # Backup: if alternative.me fails, try Bybit sentiment via funding as proxy
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()
        return int(r["data"][0]["value"]), r["data"][0]["value_classification"]
    except:
        try:
            # Backup 2: CoinMarketCap Fear Greed via alternative endpoint
            r2 = requests.get("https://api.alternative.me/v2/fng/?limit=1", timeout=5).json()
            return int(r2["data"][0]["value"]), r2["data"][0]["value_classification"]
        except:
            return 50, "Neutral (Backup)"

def get_session():
    h = datetime.datetime.utcnow().hour
    if 7 <= h < 11: return "LONDON", 1.2
    elif 12 <= h < 20: return "NEW_YORK", 1.3
    elif 20 <= h < 23: return "NY_LATE", 0.8
    else: return "ASIA", 0.6

def get_news_risk():
    now = datetime.datetime.utcnow()
    h, wd = now.hour, now.weekday()
    if wd == 4 and 12 <= h < 14: return True, "NFP NEWS - WAIT"
    if wd == 2 and 12 <= h < 14: return True, "CPI NEWS - WAIT"
    if wd == 2 and 18 <= h < 20: return True, "FOMC NEWS - WAIT"
    return False, ""

def ema(data, n):
    if len(data) < n: return data[-1]
    k = 2/(n+1); e = data[0]
    for v in data[1:]: e = v*k + e*(1-k)
    return e

def rsi_calc(data, n=14):
    if len(data) < n+1: return 50
    gains=[]; loss=[]
    for i in range(1, n+1):
        d = data[-i]-data[-i-1]
        gains.append(max(d,0)); loss.append(max(-d,0))
    ag=sum(gains)/n; al=sum(loss)/n
    if al==0: return 70
    return 100-(100/(1+ag/al))

def atr_calc(highs, lows, closes, n=14):
    trs=[]
    for i in range(1,len(closes)):
        tr=max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        trs.append(tr)
    if len(trs)<n: return sum(trs)/max(len(trs),1)
    return sum(trs[-n:])/n

def smc_analysis(closes, highs, lows):
    score = 0.0; signal = "NONE"
    if len(highs) < 20: return score, signal
    recent_high = max(highs[-20:-5])
    recent_low = min(lows[-20:-5])
    last_high = highs[-1]; last_low = lows[-1]; last_close = closes[-1]
    if last_high > recent_high and last_close < recent_high:
        score -= 2.0; signal = "BEARISH SWEEP - Trap LONGs"
    if last_low < recent_low and last_close > recent_low:
        score += 2.0; signal = "BULLISH SWEEP - Trap SHORTs"
    if len(closes) >= 3:
        if lows[-1] > highs[-3]: score += 1.0; signal += " + BULLISH FVG"
        if highs[-1] < lows[-3]: score -= 1.0; signal += " + BEARISH FVG"
    return score, signal

def human_brain(btc, closes, highs, lows, vols, macro, atr, smart, fear, fear_label, session, session_mult, news_block, news_msg):
    atr_pct = (atr / btc) * 100
    if atr_pct < 0.08: regime="CALM"; vol_mult=0.7
    elif atr_pct < 0.20: regime="NORMAL"; vol_mult=1.0
    elif atr_pct < 0.40: regime="WILD"; vol_mult=1.4
    else: regime="EXTREME"; vol_mult=1.8
    ema9=ema(closes,9); ema21=ema(closes,21); ema50=ema(closes,50)
    ema_spread = abs(ema9-ema50)/btc*100
    trend_strength = min(ema_spread*10, 3.0)
    if ema9>ema21>ema50: trend_dir=1; trend_strength+=1
    elif ema9<ema21<ema50: trend_dir=-1; trend_strength+=1
    else: trend_dir=0
    avg_vol=sum(vols[-20:])/20 if len(vols)>=20 else 1
    vol_ratio=vols[-1]/avg_vol if avg_vol>0 else 1
    vol_conf = 1.0 if vol_ratio>1.2 else 0.5 if vol_ratio>0.8 else 0.0
    total=wins+losses
    win_rate = (wins/total) if total>=3 else 0.55
    if consecutive_losses >= 3:
        ai_strictness=1.6; ai_risk_mult=0.6; mindset="HUMAN: 3 losses, wait A+ only, protect $10"
    elif consecutive_losses == 2:
        ai_strictness=1.3; ai_risk_mult=0.8; mindset="HUMAN: 2 losses, careful, no revenge"
    elif consecutive_wins >= 3:
        ai_strictness=0.9; ai_risk_mult=1.2; mindset="HUMAN: Hot streak, ride momentum"
    else:
        ai_strictness=1.0; ai_risk_mult=1.0; mindset="HUMAN: Balanced, patient"
    base_risk_pct = 0.01 + (win_rate*0.02)
    risk_pct = base_risk_pct * ai_risk_mult * session_mult
    risk_pct = max(0.005, min(risk_pct, 0.025))
    risk_usd = paper_balance * risk_pct
    lev = max(5, min(20, int(1.5 / max(atr_pct,0.05) * 0.5)))
    if paper_balance < 20: lev = min(lev, 15)
    qty = risk_usd / max(atr, 20)
    qty = max(0.001, min(qty, 0.01)); qty = round(qty, 3)
    pos_usd = qty * btc
    trade_fee = pos_usd * 0.0006; fund_fee = pos_usd * 0.0001; lev_fee = pos_usd * 0.0001
    buffer = 0.02 * vol_mult
    total_fees = trade_fee + fund_fee + lev_fee + buffer
    be_profit = max(paper_balance*0.02, total_fees*0.8, 0.10)
    be_profit = min(be_profit, paper_balance*0.05)
    be_dist = (total_fees + be_profit) / qty
    tp_mult = 1.8 + (trend_strength*0.5); tp_mult = tp_mult * vol_mult
    sl_mult = 0.8 + (0.2 * vol_mult)
    tp_dist = atr * tp_mult; sl_dist = atr * sl_mult
    r = rsi_calc(closes)
    score = 0.0
    if ema9>ema21: score += 1.5 * (trend_strength/2)
    else: score -= 1.5 * (trend_strength/2)
    if r>55: score += 1.0
    elif r<45: score -= 1.0
    elif r>50: score += 0.5
    else: score -= 0.5
    if r > 75: score -= 1.5
    if r < 25: score += 1.5
    if macro['SPX']>0: score += 0.8
    elif macro['SPX']<0: score -= 0.8
    if macro['DXY']<0: score += 0.8
    elif macro['DXY']>0: score -= 0.8
    if macro['GOLD']>0.5: score += 0.3
    if macro['OIL']>2: score = 0
    smc_score, smc_signal = smc_analysis(closes, highs, lows)
    score += smc_score
    if smart['funding'] > 0.05: score -= 1.0
    elif smart['funding'] < -0.05: score += 1.0
    if smart['oi_change'] > 2 and smart['long_short'] > 1.5: score -= 0.8
    if fear < 20: score += 1.0
    elif fear > 80: score -= 1.0
    score = score * session_mult
    threshold = 1.8 * ai_strictness
    win_prob = 0.50 + (abs(score)/5)*0.30 + (vol_conf*0.05)
    win_prob = min(win_prob, 0.85)
    tp_profit = tp_dist*qty - total_fees
    sl_loss = sl_dist*qty + total_fees
    ev = (win_prob * tp_profit) - ((1-win_prob) * sl_loss)
    rr = tp_dist / max(sl_dist,1)
    return {
        "regime":regime,"vol_mult":vol_mult,"trend_dir":trend_dir,"trend_strength":trend_strength,
        "vol_ratio":vol_ratio,"win_rate":win_rate,"ai_strictness":ai_strictness,"mindset":mindset,
        "risk_pct":risk_pct,"risk_usd":risk_usd,"lev":lev,"qty":qty,"pos_usd":pos_usd,
        "total_fees":total_fees,"be_profit":be_profit,"be_dist":be_dist,"tp_dist":tp_dist,"sl_dist":sl_dist,
        "tp_mult":tp_mult,"sl_mult":sl_mult,"score":score,"threshold":threshold,
        "win_prob":win_prob,"ev":ev,"rr":rr,"tp_profit":tp_profit,"sl_loss":sl_loss,"r":r,
        "ema9":ema9,"ema21":ema21,"ema50":ema50,"smc_signal":smc_signal,"smc_score":smc_score
    }

def main_loop():
    global paper_balance, paper_pnl, wins, losses, be_hits, open_pos, waiting, history, consecutive_losses, consecutive_wins
    log("V5.1 HUMAN SKULL BRAIN STARTED - NO YFINANCE, 3 BACKUPS, I NEVER GO BLIND, I PROTECT $10")
    while True:
        try:
            closes, highs, lows, vols = get_bybit_klines()
            if closes is None:
                log("Error retry 30s"); time.sleep(30); continue
            btc=closes[-1]
            atr=atr_calc(highs,lows,closes)
            if atr<20: atr=20
            macro = get_macro_all()
            smart = get_bybit_smart_money()
            fear, fear_label = get_fear_greed()
            session, session_mult = get_session()
            news_block, news_msg = get_news_risk()
            B=human_brain(btc, closes, highs, lows, vols, macro, atr, smart, fear, fear_label, session, session_mult, news_block, news_msg)
            log(f"BRAIN: {B['regime']} ATR ${atr:.0f} EMA9 ${B['ema9']:.0f} RSI {B['r']:.1f} Vol x{B['vol_ratio']:.2f} | {B['mindset']}")
            log(f"WORLD: Fear {fear} ({fear_label}) Funding {smart['funding']:.3f}% OI {smart['oi_change']:+.2f}% L/S {smart['long_short']:.2f} Session {session} x{session_mult} News: {news_msg if news_block else 'Clear'} | SMC: {B['smc_signal']} ({B['smc_score']:+.1f})")
            log(f"FEES ${B['total_fees']:.4f} BE ${B['be_dist']:.0f} = Fees + BE Profit ${B['be_profit']:.2f} | TP ${B['tp_dist']:.0f} SL ${B['sl_dist']:.0f} | Score {B['score']:.2f} / Thr {B['threshold']:.2f} WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} R:R {B['rr']:.1f} | Bal ${paper_balance:.2f} PnL ${paper_pnl:.2f} W {wins} L {losses} BE {be_hits} Streak W{consecutive_wins} L{consecutive_losses}")
            log(f"LIVE: DXY {macro['DXY']:+.2f}% SPX {macro['SPX']:+.2f}% NQ {macro['NQ']:+.2f}% DAX {macro['DAX']:+.2f}% Oil {macro['OIL']:+.2f}% Gold {macro['GOLD']:+.2f}%")
            if news_block:
                log(f"🛑 HUMAN WAIT: {news_msg} - I no go trade inside bomb, I protect $10")
                time.sleep(60); continue
            if open_pos:
                side=open_pos['side']; entry=open_pos['entry']; tp=open_pos['tp']; sl=open_pos['sl']; be_price=open_pos['be_price']
                if not open_pos.get('be_done'):
                    if (side=='LONG' and btc>=be_price) or (side=='SHORT' and btc<=be_price):
                        open_pos['sl']=be_price; open_pos['be_done']=True; be_hits+=1
                        log(f"🟢 BE HIT + PROFIT LOCKED! SL -> BE ${be_price:.0f} = Fees + ${open_pos['be_profit']:.2f} profit secured")
                if open_pos.get('be_done'):
                    if side=='LONG':
                        nsl=btc-atr*0.5
                        if nsl>open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL UP SL ${nsl:.0f}")
                    else:
                        nsl=btc+atr*0.5
                        if nsl<open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL DOWN SL ${nsl:.0f}")
                pnl=0; closed=False; reason=""
                total_fees=open_pos['total_fees']; qty=open_pos['qty']; be_profit=open_pos['be_profit']
                if side=='LONG':
                    if btc>=tp: pnl=(tp-entry)*qty-total_fees; closed=True; reason="TP HIT 🎯"
                    elif btc<=open_pos['sl']:
                        if open_pos.get('be_done'): pnl=be_profit; closed=True; reason=f"BE SL HIT 🟢 +${be_profit:.2f}"
                        else: pnl=(open_pos['sl']-entry)*qty-total_fees; closed=True; reason="SL HIT"
                else:
                    if btc<=tp: pnl=(entry-tp)*qty-total_fees; closed=True; reason="TP HIT 🎯"
                    elif btc>=open_pos['sl']:
                        if open_pos.get('be_done'): pnl=be_profit; closed=True; reason=f"BE SL HIT 🟢 +${be_profit:.2f}"
                        else: pnl=(entry-open_pos['sl'])*qty-total_fees; closed=True; reason="SL HIT"
                time_limit = 90*60 if B['regime']=="CALM" else 180*60 if B['regime'] in ["WILD","EXTREME"] else 120*60
                if not closed and (time.time()-open_pos['start'])>time_limit:
                    pnl=(btc-entry)*qty-total_fees if side=='LONG' else (entry-btc)*qty-total_fees
                    closed=True; reason=f"TIME EXIT {int(time_limit/60)}min"
                if closed:
                    paper_balance+=pnl; paper_pnl+=pnl; history.append(pnl)
                    if pnl>0:
                        wins+=1; consecutive_wins+=1; consecutive_losses=0
                    else:
                        losses+=1; consecutive_losses+=1; consecutive_wins=0
                    log(f"✅ CLOSED {reason} | PnL ${pnl:.4f} | Bal ${paper_balance:.2f} | W {wins} L {losses} BE {be_hits} | Streak W{consecutive_wins} L{consecutive_losses} - I learn, I no give up")
                    open_pos=None; time.sleep(10); continue
                else:
                    log(f"⏳ OPEN {side} Entry ${entry:.0f} Now ${btc:.0f} TP ${tp:.0f} SL ${open_pos['sl']:.0f} BE ${be_price:.0f}")
                    time.sleep(60); continue
            if waiting:
                trig=waiting['trig']; tp=waiting['tp']; sl=waiting['sl']; side=waiting['side']
                hit=(btc>=trig) if side=='LONG' else (btc<=trig)
                expire_mins = 45 if B['regime']=="CALM" else 20 if B['regime'] in ["WILD","EXTREME"] else 30
                expired=(time.time()-waiting['start'])>expire_mins*60
                opposite=(btc<=trig-atr*1.5) if side=='LONG' else (btc>=trig+atr*1.5)
                if hit:
                    be_price=trig+B['be_dist'] if side=='LONG' else trig-B['be_dist']
                    open_pos={'side':side,'entry':trig,'tp':tp,'sl':sl,'be_price':be_price,'be_done':False,'start':time.time(),'total_fees':B['total_fees'],'qty':B['qty'],'be_profit':B['be_profit']}
                    log(f"🔥 TRIGGER HIT {side} Entry ${trig:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f}")
                    waiting=None
                elif expired or opposite:
                    log(f"❌ WAITING CANCELLED {side} Trig ${trig:.0f} Now ${btc:.0f} - market change, I re-scan")
                    waiting=None
                else:
                    log(f"👀 WAITING {side} Trig ${trig:.0f} Now ${btc:.0f} TP ${tp:.0f} SL ${sl:.0f}")
                time.sleep(60); continue
            if abs(B['score']) < B['threshold']:
                log(f"=> NO CLEAR: Score {B['score']:.2f} < Thr {B['threshold']:.2f}... I WAIT, I no rush my $10")
                time.sleep(60); continue
            if B['win_prob'] < 0.65:
                log(f"⛔ SKIP WinProb {B['win_prob']*100:.0f}% < 65% - I no confident, I WAIT")
                time.sleep(60); continue
            if B['ev'] <= 0:
                log(f"⛔ SKIP EV ${B['ev']:.4f} <= 0 - This trade go lose on average, I WAIT")
                time.sleep(60); continue
            if B['tp_dist'] < B['be_dist']*1.5:
                log(f"⛔ SKIP TP no cover BE x1.5 - I WAIT")
                time.sleep(60); continue
            if B['rr'] < 1.5:
                log(f"⛔ SKIP R:R {B['rr']:.1f} < 1.5 - Risk too big, I WAIT")
                time.sleep(60); continue
            if macro['OIL'] > 5:
                log(f"⛔ SKIP Oil spike {macro['OIL']:.2f}% - Bank Trap")
                time.sleep(60); continue
            if session == "ASIA" and abs(B['score']) < 3.5:
                log(f"⛔ SKIP Asia session, score no strong enough - I go sleep, wait London")
                time.sleep(60); continue
            side='LONG' if B['score']>=0 else 'SHORT'
            trig_offset = atr * (0.3 + (B['trend_strength']*0.1))
            if side=='LONG':
                trig=btc+trig_offset; tp=trig+B['tp_dist']; sl=trig-B['sl_dist']; be_price=trig+B['be_dist']
            else:
                trig=btc-trig_offset; tp=trig-B['tp_dist']; sl=trig+B['sl_dist']; be_price=trig-B['be_dist']
            waiting={'side':side,'trig':trig,'tp':tp,'sl':sl,'be_price':be_price,'start':time.time()}
            log(f"✅ HUMAN HIDDEN {side} PLACED Trig ${trig:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f} | WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} R:R {B['rr']:.1f} | Fear {fear} Session {session} SMC {B['smc_signal']}")
            time.sleep(60)
        except Exception as e:
            log(f"Error {e} retry 30s"); time.sleep(30)

if __name__=="__main__":
    main_loop()
