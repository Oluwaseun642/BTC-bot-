import os, time, math, requests, datetime
import yfinance as yf

# ============ NO FIXED VALUES - ALL DYNAMIC ============
# Only starting balance is fixed, everything else bot calculates
START_BAL = 10.0
paper_balance = START_BAL
paper_pnl = 0.0
wins = 0; losses = 0; be_hits = 0
open_pos = None; waiting = None
history = []  # for AI learning: list of pnl
trade_times = []

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{now} [tnpbc] {msg}", flush=True)

def get_btc():
    try:
        r = requests.get("https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&limit=200", timeout=10).json()
        kl = r["result"]["list"][::-1]
        closes = [float(x[4]) for x in kl]
        highs = [float(x[2]) for x in kl]
        lows = [float(x[3]) for x in kl]
        vols = [float(x[5]) for x in kl]
        return closes, highs, lows, vols
    except:
        return None, None, None, None

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

def get_macro():
    tickers={"DXY":"DX-Y.NYB","NQ":"^IXIC","SPX":"^GSPC","DAX":"^GDAXI","FTSE":"^FTSE","NIKKEI":"^N225","OIL":"CL=F","GOLD":"GC=F"}
    out={}
    for k,t in tickers.items():
        try:
            df=yf.download(t, period="2d", interval="1d", progress=False, auto_adjust=True)
            c=df["Close"]
            out[k]=float((c.iloc[-1].item()-c.iloc[-2].item())/c.iloc[-2].item()*100) if len(c)>=2 else 0.0
        except: out[k]=0.0
    return out

# ============ DYNAMIC BRAIN - HUMAN + AI ============
def dynamic_brain(btc, closes, highs, lows, vols, macro, atr):
    # --- 1. VOLATILITY REGIME (dynamic) ---
    atr_pct = (atr / btc) * 100
    if atr_pct < 0.08: regime="CALM"; vol_mult=0.7
    elif atr_pct < 0.20: regime="NORMAL"; vol_mult=1.0
    elif atr_pct < 0.40: regime="WILD"; vol_mult=1.4
    else: regime="EXTREME"; vol_mult=1.8

    # --- 2. TREND STRENGTH (dynamic, not fixed) ---
    ema9=ema(closes,9); ema21=ema(closes,21); ema50=ema(closes,50); ema200=ema(closes,100)
    ema_spread = abs(ema9-ema50)/btc*100
    trend_strength = min(ema_spread*10, 3.0)  # 0 to 3
    if ema9>ema21>ema50: trend_dir=1; trend_strength+=1
    elif ema9<ema21<ema50: trend_dir=-1; trend_strength+=1
    else: trend_dir=0

    # --- 3. VOLUME CONFIRMATION (dynamic) ---
    avg_vol=sum(vols[-20:])/20 if len(vols)>=20 else 1
    vol_ratio=vols[-1]/avg_vol if avg_vol>0 else 1
    vol_conf = 1.0 if vol_ratio>1.2 else 0.5 if vol_ratio>0.8 else 0.0

    # --- 4. AI LEARNING: WIN RATE ADAPTIVE ---
    total=wins+losses
    win_rate = (wins/total) if total>=3 else 0.55  # start neutral 55%
    recent = history[-5:] if history else []
    recent_losses = sum(1 for x in recent if x<0)
    # If losing streak, become strict + reduce risk. If winning, become confident.
    if recent_losses>=3: ai_strictness=1.5; ai_risk_mult=0.5
    elif recent_losses==2: ai_strictness=1.2; ai_risk_mult=0.7
    elif wins>=3 and losses==0: ai_strictness=0.9; ai_risk_mult=1.2
    else: ai_strictness=1.0; ai_risk_mult=1.0

    # --- 5. DYNAMIC RISK (never fixed 2%) ---
    # Base risk = win_rate driven: high win rate = slightly higher risk, low = lower
    base_risk_pct = 0.01 + (win_rate*0.02)  # 1% to 3% dynamic
    risk_pct = base_risk_pct * ai_risk_mult
    risk_pct = max(0.005, min(risk_pct, 0.03))
    risk_usd = paper_balance * risk_pct

    # --- 6. DYNAMIC LEVERAGE (from volatility, not fixed) ---
    # Calm market = can use more lev, Wild = less lev
    # Target: position volatility should be ~ same always
    lev = max(5, min(20, int(1.5 / max(atr_pct,0.05) * 0.5)))
    # Example: atr_pct 0.08% -> lev ~18, atr_pct 0.3% -> lev ~5
    # Cap by balance: small balance = cap lev
    if paper_balance < 20: lev = min(lev, 15)
    if paper_balance < 50: lev = min(lev, 18)

    # --- 7. DYNAMIC QTY (from risk + ATR) ---
    qty = risk_usd / max(atr, 20)
    qty = max(0.001, min(qty, 0.01))
    qty = round(qty, 3)
    if qty<0.001: qty=0.001
    pos_usd = qty * btc

    # --- 8. DYNAMIC FEES (live calculation) ---
    trade_fee = pos_usd * 0.0006
    fund_fee = pos_usd * 0.0001
    lev_fee = pos_usd * 0.0001
    # Buffer dynamic: bigger in wild market
    buffer = 0.02 * vol_mult
    total_fees = trade_fee + fund_fee + lev_fee + buffer

    # --- 9. DYNAMIC BE PROFIT (human + AI: BE must grow balance) ---
    # BE profit = max(2% of balance, 50% of total fees, $0.10) - scales with balance
    be_profit = max(paper_balance*0.02, total_fees*0.8, 0.10)
    be_profit = min(be_profit, paper_balance*0.05)  # never too greedy
    be_target = total_fees + be_profit
    be_dist = be_target / qty

    # --- 10. DYNAMIC TP / SL (from trend + regime) ---
    # Strong trend = bigger TP, Weak trend = smaller TP
    tp_mult = 1.8 + (trend_strength*0.5)  # 1.8 to 3.3 dynamic
    tp_mult = tp_mult * vol_mult
    sl_mult = 0.8 + (0.2 * vol_mult)  # 0.94 to 1.16
    tp_dist = atr * tp_mult
    sl_dist = atr * sl_mult

    # --- 11. DYNAMIC SCORE WITH WEIGHTS (not 1 point each) ---
    r = rsi_calc(closes)
    score = 0.0
    # Trend weight = strongest
    if ema9>ema21: score += 1.5 * (trend_strength/2)
    else: score -= 1.5 * (trend_strength/2)
    if r>55: score += 1.0
    elif r<45: score -= 1.0
    elif r>50: score += 0.5
    else: score -= 0.5
    # Macro weights
    if macro['SPX']>0: score += 0.8
    elif macro['SPX']<0: score -= 0.8
    if macro['DXY']<0: score += 0.8
    elif macro['DXY']>0: score -= 0.8
    if macro['GOLD']>0.5: score += 0.3  # risk-on
    if macro['OIL']>2: score = 0  # trap, kill score
    # Volume confirmation boosts score
    score = score * (1 + vol_conf*0.3)

    # --- 12. DYNAMIC THRESHOLD (AI strictness) ---
    threshold = 1.8 * ai_strictness  # 1.62 if winning, 2.7 if losing streak
    # Win probability estimate
    win_prob = 0.50 + (abs(score)/5)*0.30 + (vol_conf*0.05)  # 50% to 85%
    win_prob = min(win_prob, 0.85)

    # --- 13. EXPECTED VALUE (must be positive, strictly) ---
    # EV = (win_prob * TP profit) - ((1-win_prob) * SL loss) - fees
    tp_profit = tp_dist*qty - total_fees
    sl_loss = sl_dist*qty + total_fees
    ev = (win_prob * tp_profit) - ((1-win_prob) * sl_loss)
    # Reward:Risk dynamic
    rr = tp_dist / max(sl_dist,1)

    return {
        "regime":regime,"vol_mult":vol_mult,"trend_dir":trend_dir,"trend_strength":trend_strength,
        "vol_ratio":vol_ratio,"win_rate":win_rate,"ai_strictness":ai_strictness,
        "risk_pct":risk_pct,"risk_usd":risk_usd,"lev":lev,"qty":qty,"pos_usd":pos_usd,
        "total_fees":total_fees,"trade_fee":trade_fee,"fund_fee":fund_fee,"lev_fee":lev_fee,
        "be_profit":be_profit,"be_dist":be_dist,"tp_dist":tp_dist,"sl_dist":sl_dist,
        "tp_mult":tp_mult,"sl_mult":sl_mult,"score":score,"threshold":threshold,
        "win_prob":win_prob,"ev":ev,"rr":rr,"tp_profit":tp_profit,"sl_loss":sl_loss,"r":r,
        "ema9":ema9,"ema21":ema21,"ema50":ema50
    }

def main_loop():
    global paper_balance, paper_pnl, wins, losses, be_hits, open_pos, waiting, history
    log("V4 FULL DYNAMIC BRAIN STARTED - NOTHING FIXED, EVERYTHING CALCULATED LIVE")
    while True:
        try:
            closes, highs, lows, vols = get_btc()
            if closes is None:
                log("Error retry 30s"); time.sleep(30); continue
            btc=closes[-1]
            atr=atr_calc(highs,lows,closes)
            if atr<20: atr=20
            macro=get_macro()
            B=dynamic_brain(btc, closes, highs, lows, vols, macro, atr)

            log(f"DYNAMIC BRAIN: Regime {B['regime']} ATR ${atr:.0f} ({atr/btc*100:.3f}%) EMA9 ${B['ema9']:.0f} EMA21 ${B['ema21']:.0f} RSI {B['r']:.1f} Vol x{B['vol_ratio']:.2f} TrendStr {B['trend_strength']:.1f} | WinRate {B['win_rate']*100:.0f}% AI Strict x{B['ai_strictness']} | Risk {B['risk_pct']*100:.2f}%=${B['risk_usd']:.2f} Lev {B['lev']}x Qty {B['qty']} Pos ${B['pos_usd']:.1f}")
            log(f"FEES Dyn Total ${B['total_fees']:.4f} | BE Dist ${B['be_dist']:.0f} = Fees + BE Profit ${B['be_profit']:.2f} (BE hit = balance +${B['be_profit']:.2f}) | TP Dist ${B['tp_dist']:.0f} (x{B['tp_mult']:.1f} ATR) SL ${B['sl_dist']:.0f} | Score {B['score']:.2f} / Thr {B['threshold']:.2f} WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} R:R {B['rr']:.1f} | Bal ${paper_balance:.2f} PnL ${paper_pnl:.2f} W {wins} L {losses} BE {be_hits}")
            log(f"LIVE: DXY {macro['DXY']:+.2f}% NQ {macro['NQ']:+.2f}% SPX {macro['SPX']:+.2f}% DAX {macro['DAX']:+.2f}% FTSE {macro['FTSE']:+.2f}% Nikkei {macro['NIKKEI']:+.2f}% Oil {macro['OIL']:+.2f}% Gold {macro['GOLD']:+.2f}%")

            # ===== MANAGE OPEN =====
            if open_pos:
                side=open_pos['side']; entry=open_pos['entry']; tp=open_pos['tp']; sl=open_pos['sl']; be_price=open_pos['be_price']
                if not open_pos.get('be_done'):
                    if (side=='LONG' and btc>=be_price) or (side=='SHORT' and btc<=be_price):
                        open_pos['sl']=be_price; open_pos['be_done']=True; be_hits+=1
                        log(f"🟢 BE HIT + PROFIT LOCKED! SL -> BE ${be_price:.0f} = Fees + ${open_pos['be_profit']:.2f} profit secured, balance go increase even if e reverse")
                if open_pos.get('be_done'):
                    # Dynamic trailing: trail by 0.5 ATR, adapts to volatility
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
                # Dynamic time exit: calm market = 90min, wild = 180min
                time_limit = 90*60 if B['regime']=="CALM" else 180*60 if B['regime'] in ["WILD","EXTREME"] else 120*60
                if not closed and (time.time()-open_pos['start'])>time_limit:
                    pnl=(btc-entry)*qty-total_fees if side=='LONG' else (entry-btc)*qty-total_fees
                    closed=True; reason=f"TIME EXIT {int(time_limit/60)}min"
                if closed:
                    paper_balance+=pnl; paper_pnl+=pnl; history.append(pnl)
                    if pnl>0: wins+=1
                    else: losses+=1
                    log(f"✅ CLOSED {reason} | PnL ${pnl:.4f} | Bal ${paper_balance:.2f} | W {wins} L {losses} BE {be_hits} | AI go learn from this trade")
                    open_pos=None; time.sleep(10); continue
                else:
                    log(f"⏳ OPEN {side} Entry ${entry:.0f} Now ${btc:.0f} TP ${tp:.0f} SL ${open_pos['sl']:.0f} BE ${be_price:.0f} (BE=+${be_profit:.2f})")
                    time.sleep(60); continue

            # ===== MANAGE WAITING =====
            if waiting:
                trig=waiting['trig']; tp=waiting['tp']; sl=waiting['sl']; side=waiting['side']
                hit=(btc>=trig) if side=='LONG' else (btc<=trig)
                # Dynamic waiting expiry: calm = 45min, wild = 20min
                expire_mins = 45 if B['regime']=="CALM" else 20 if B['regime'] in ["WILD","EXTREME"] else 30
                expired=(time.time()-waiting['start'])>expire_mins*60
                opposite=(btc<=trig-atr*1.5) if side=='LONG' else (btc>=trig+atr*1.5)
                if hit:
                    # Recalc BE live at entry, not fixed from before
                    be_price=trig+B['be_dist'] if side=='LONG' else trig-B['be_dist']
                    open_pos={'side':side,'entry':trig,'tp':tp,'sl':sl,'be_price':be_price,'be_done':False,'start':time.time(),'total_fees':B['total_fees'],'qty':B['qty'],'be_profit':B['be_profit']}
                    log(f"🔥 TRIGGER HIT {side} Entry ${trig:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f} (BE = Fees + ${B['be_profit']:.2f})")
                    waiting=None
                elif expired or opposite:
                    log(f"❌ WAITING CANCELLED {side} Trig ${trig:.0f} Now ${btc:.0f} - market change, AI re-scan")
                    waiting=None
                else:
                    log(f"👀 WAITING {side} Trig ${trig:.0f} Now ${btc:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${trig+B['be_dist'] if side=='LONG' else trig-B['be_dist']:.0f}")
                time.sleep(60); continue

            # ===== NEW SETUP - STRICT AI FILTERS, ALL DYNAMIC =====
            # Filter 1: Score must beat dynamic threshold
            if abs(B['score']) < B['threshold']:
                log(f"=> NO CLEAR: Score {B['score']:.2f} < Thr {B['threshold']:.2f} (AI Strict x{B['ai_strictness']})... WAIT")
                time.sleep(60); continue
            # Filter 2: Win Prob must be >65% strictly
            if B['win_prob'] < 0.65:
                log(f"⛔ SKIP WinProb {B['win_prob']*100:.0f}% < 65% - AI no confident, WAIT for better setup")
                time.sleep(60); continue
            # Filter 3: EV must be positive strictly
            if B['ev'] <= 0:
                log(f"⛔ SKIP EV ${B['ev']:.4f} <= 0 - Trade go lose on average, WAIT")
                time.sleep(60); continue
            # Filter 4: TP must cover BE x 1.5 strictly
            if B['tp_dist'] < B['be_dist']*1.5:
                log(f"⛔ SKIP TP ${B['tp_dist']:.0f} no cover BE x1.5 (${B['be_dist']*1.5:.0f}) - WAIT")
                time.sleep(60); continue
            # Filter 5: R:R must be >=1.5
            if B['rr'] < 1.5:
                log(f"⛔ SKIP R:R {B['rr']:.1f} < 1.5 - Risk too big vs reward, WAIT")
                time.sleep(60); continue
            # Filter 6: Oil trap
            if macro['OIL'] > 5:
                log(f"⛔ SKIP Oil spike {macro['OIL']:.2f}% - Bank Trap")
                time.sleep(60); continue

            side='LONG' if B['score']>=0 else 'SHORT'
            # Dynamic hidden trigger: 0.3 to 0.7 ATR in front, depends on trend strength
            trig_offset = atr * (0.3 + (B['trend_strength']*0.1))
            if side=='LONG':
                trig=btc+trig_offset; tp=trig+B['tp_dist']; sl=trig-B['sl_dist']; be_price=trig+B['be_dist']
            else:
                trig=btc-trig_offset; tp=trig-B['tp_dist']; sl=trig+B['sl_dist']; be_price=trig-B['be_dist']
            waiting={'side':side,'trig':trig,'tp':tp,'sl':sl,'be_price':be_price,'start':time.time()}
            log(f"✅ DYNAMIC HIDDEN {side} PLACED Trig ${trig:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f} | WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} R:R {B['rr']:.1f} | BE hit = +${B['be_profit']:.2f} balance increase")
            time.sleep(60)
        except Exception as e:
            log(f"Error {e} retry 30s"); time.sleep(30)

if __name__=="__main__":
    main_loop()
