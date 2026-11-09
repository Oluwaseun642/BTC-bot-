import os, time, math, requests, datetime, re, xml.etree.ElementTree as ET
import threading

# --- RENDER KEEP-ALIVE + SELF-PING - V5.12.1 BE 0.15 GROWTH ---
try:
    from flask import Flask
    app = Flask(__name__)
    @app.route('/')
    def home(): return "V5.12.1 BE 0.15 Growth + Early Lock is alive!"
    def run_web():
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)
    threading.Thread(target=run_web, daemon=True).start()
    print("Keep-alive started", flush=True)
except Exception as e:
    print(f"Keep-alive skip: {e}", flush=True)

def self_ping_loop():
    while True:
        try:
            url = os.environ.get("RENDER_EXTERNAL_URL")
            if url:
                r = requests.get(url, timeout=10)
                print(f"Self-ping OK {r.status_code}", flush=True)
            else:
                port = os.environ.get("PORT", 10000)
                requests.get(f"http://127.0.0.1:{port}/", timeout=5)
                print("Self-ping localhost OK", flush=True)
        except Exception as e:
            print(f"Self-ping fail: {e}", flush=True)
        time.sleep(300)
threading.Thread(target=self_ping_loop, daemon=True).start()
# --- END KEEP-ALIVE ---

START_BAL = 10.0
paper_balance = START_BAL
paper_pnl = 0.0
wins = 0; losses = 0; be_hits = 0
open_pos = None
history = []
consecutive_losses = 0
consecutive_wins = 0
last_trade_time = time.time()
BYBIT_MIN_QTY = 0.001
BYBIT_QTY_STEP = 0.001
BYBIT_MIN_ORDER_USD = 5.0
BYBIT_MAKER_FEE = 0.00055
BYBIT_TAKER_FEE = 0.0006
last_macro = {"DXY":0.0,"SPX":0.0,"SPX_FUT":0.0,"NQ_FUT":0.0,"NQ_CASH":0.0,"NDX100":0.0,"DAX":0.0,"FTSE":0.0,"NIKKEI":0.0,"OIL":0.0,"GOLD":0.0}
last_news = {"danger": False, "headline": "", "score": 0.0, "time": 0}

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{now} [V5.12.1-BE015] {msg}", flush=True)

def yahoo_direct(symbol, host):
    try:
        url = f"https://{host}/v8/finance/chart/{symbol}?range=5d&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5).json()
        closes = r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2 and closes[-2] != 0:
            return (closes[-1]-closes[-2])/closes[-2]*100
        return None
    except:
        return None

def stooq_backup(symbol):
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        r = requests.get(url, timeout=5).text.strip().split("\n")
        rows = [x for x in r if x.strip() and ",,," not in x]
        if len(rows) >= 3:
            last = rows[-1].split(","); prev = rows[-2].split(",")
            c1 = float(last[4]); c0 = float(prev[4])
            if c0 != 0:
                return (c1-c0)/c0*100
        return None
    except:
        return None

def binance_24h_change(symbol):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=5).json()
        return float(r.get("priceChangePercent", 0))
    except:
        return None

def fast_yahoo_multi(yahoo_symbols, stooq_symbol):
    for ys in yahoo_symbols:
        for host in ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]:
            v = yahoo_direct(ys, host)
            if v is not None:
                return v
    v = stooq_backup(stooq_symbol)
    if v is not None:
        return v
    return None

def get_macro_all():
    global last_macro
    mapping = {
        "DXY": (["DX=F", "^DXY", "DX-Y.NYB", "UUP"], "dx.f"),
        "SPX": (["%5EGSPC", "SPY"], "^spx"),
        "SPX_FUT": (["ES=F", "ES%3DF", "SPY"], "es.f"),
        "NQ_FUT": (["NQ=F", "NQ%3DF", "QQQ"], "nq.f"),
        "NQ_CASH": (["%5EIXIC", "QQQ"], "^ixic"),
        "NDX100": (["%5ENDX", "NDX", "QQQ"], "^ndx"),
        "DAX": (["%5EGDAXI", "DAX"], "^gdaxi"),
        "FTSE": (["%5EFTSE", "FTSE"], "^ftse"),
        "NIKKEI": (["%5EN225", "NIKKEI"], "^n225"),
        "OIL": (["CL=F", "CL%3DF", "USO"], "cl.f"),
        "GOLD": (["GC=F", "GC%3DF", "GLD"], "gc.f"),
    }
    out = {}
    for k, (ys_list, ss) in mapping.items():
        v = fast_yahoo_multi(ys_list, ss)
        if v is None and k == "DXY":
            eur = binance_24h_change("EURUSDT")
            if eur is not None:
                v = -eur * 0.57
        if v is None and k == "SPX_FUT":
            spx_cash = out.get("SPX", last_macro.get("SPX", 0.0))
            if spx_cash != 0.0:
                v = spx_cash
        if v is not None:
            out[k] = v; last_macro[k] = v
        else:
            out[k] = last_macro[k]
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
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()
        return int(r["data"][0]["value"]), r["data"][0]["value_classification"]
    except:
        try:
            r2 = requests.get("https://api.alternative.me/v2/fng/?limit=1", timeout=5).json()
            return int(r2["data"][0]["value"]), r2["data"][0]["value_classification"]
        except:
            return 50, "Neutral (Backup)"

def get_session():
    h = datetime.datetime.utcnow().hour
    wd = datetime.datetime.utcnow().weekday()
    monday_boost = 1.1 if wd == 0 else 1.0
    if 7 <= h < 11: return "LONDON", 1.2 * monday_boost
    elif 12 <= h < 20: return "NEW_YORK", 1.3 * monday_boost
    elif 20 <= h < 23: return "NY_LATE", 0.8
    else: return "ASIA", 0.6

DANGER_WORDS = ["hack", "exploit", "breach", "stolen", "lawsuit", "sue", "sec", "ban", "crash", "collapse", "bankrupt", "war", "attack", "sanction", "regulation crackdown", "etf reject", "fraud", "liquidation cascade", "emergency", "martial", "missile", "invasion", "airstrike", "coup", "earthquake", "tsunami", "assassination", "nuclear", "tariff war", "trade war", "recession", "interest rate hike"]
BULLISH_WORDS = ["etf approve", "etf approved", "adoption", "bullish", "record high", "institutional", "partnership", "upgrade", "rate cut", "peace deal", "ceasefire", "stimulus", "etf inflow record"]
BEARISH_WORDS = ["etf outflow", "etf reject", "rate hike", "recession", "bankrupt", "liquidation", "hack", "fraud", "sec lawsuit"]

def parse_rss_titles(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=6)
        root = ET.fromstring(r.content)
        titles = []
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text)
            if len(titles) >= 5:
                break
        return titles
    except:
        return []

def get_live_news():
    global last_news
    if time.time() - last_news["time"] < 180 and last_news["time"] != 0:
        return last_news
    titles = []
    titles += parse_rss_titles("https://www.coindesk.com/arc/outboundfeed/rss/")
    titles += parse_rss_titles("https://cointelegraph.com/rss")
    titles += parse_rss_titles("https://news.google.com/rss/search?q=world&hl=en-US&gl=US&ceid=US:en")
    titles += parse_rss_titles("https://feeds.bbci.co.uk/news/world/rss.xml")
    titles += parse_rss_titles("https://news.google.com/rss/search?q=Bitcoin%20OR%20crypto%20OR%20Federal%20Reserve%20OR%20war&hl=en-US&gl=US&ceid=US:en")
    danger = False; headline_hit = ""; score = 0.0; direction = "NEUTRAL"
    for t in titles:
        low = t.lower()
        for w in DANGER_WORDS:
            if w in low:
                danger = True; headline_hit = t; score -= 2.0; direction = "BEARISH"
                break
        for w in BULLISH_WORDS:
            if w in low:
                score += 2.0; direction = "BULLISH"
                if not headline_hit: headline_hit = t
        for w in BEARISH_WORDS:
            if w in low:
                score -= 1.0
                if direction == "NEUTRAL": direction = "BEARISH"
    out = {"danger": danger, "headline": headline_hit, "score": score, "direction": direction, "titles": titles[:3], "time": time.time()}
    last_news = out
    if headline_hit:
        log(f"📰 WORLD NEWS: {headline_hit} | Score {score:+.1f} Dir {direction} - OPPORTUNITY, NO BLOCK")
    return out

def get_news_risk(live_news):
    now = datetime.datetime.utcnow()
    h, wd = now.hour, now.weekday()
    if wd == 4 and 12 <= h < 14: log("⚠️ NFP TIME - Trade with care, but still trade if hunt confirms")
    if wd == 2 and 12 <= h < 14: log("⚠️ CPI TIME - Trade with care, but still trade if hunt confirms")
    if wd == 2 and 18 <= h < 20: log("⚠️ FOMC TIME - Trade with care, but still trade if hunt confirms")
    if live_news.get("direction") == "BULLISH":
        return False, f"NEWS OPPORTUNITY LONG: {live_news.get('headline','')[:80]}", "LONG"
    if live_news.get("direction") == "BEARISH":
        return False, f"NEWS OPPORTUNITY SHORT / HUNT: {live_news.get('headline','')[:80]}", "SHORT"
    return False, "", "NEUTRAL"

def get_liquidation_map():
    long_liq = 0.0; short_liq = 0.0; details = []
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=50", timeout=5).json()
        for o in r:
            try:
                price = float(o.get("price", 0))
                qty = float(o.get("origQty", 0))
                usd = price * qty
                if o.get("side") == "SELL":
                    long_liq += usd
                else:
                    short_liq += usd
                if usd > 100000:
                    details.append(f"{o.get('side')} Liq ${usd/1000:.0f}k @ ${price:.0f}")
            except: pass
    except Exception as e:
        print(f"Binance Liq fail: {e}", flush=True)
    total = long_liq + short_liq
    bias = "NEUTRAL"; score = 0.0
    if total > 500000:
        if long_liq > short_liq * 1.5:
            bias = "LONG_HUNT_CONFIRMED"; score = 2.0
        elif short_liq > long_liq * 1.5:
            bias = "SHORT_HUNT_CONFIRMED"; score = -2.0
        elif long_liq > 2000000:
            bias = "HEAVY_LONG_LIQ"; score = 1.5
        elif short_liq > 2000000:
            bias = "HEAVY_SHORT_LIQ"; score = -1.5
    return {"long_liq": long_liq, "short_liq": short_liq, "total": total, "bias": bias, "score": score, "details": details[:3]}

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

def liquidity_hunt_analysis(closes, highs, lows, vols, atr):
    score = 0.0; signal = "No Hunt"; is_hunt = False; hunt_side = None
    if len(closes) < 50: return score, signal, is_hunt, hunt_side
    btc = closes[-1]
    lows_50 = lows[-50:-2]
    highs_50 = highs[-50:-2]
    min_low = min(lows_50)
    low_touches = sum(1 for l in lows_50 if abs(l - min_low)/min_low < 0.002)
    max_high = max(highs_50)
    high_touches = sum(1 for h in highs_50 if abs(h - max_high)/max_high < 0.002)
    last_low = lows[-1]; last_high = highs[-1]; last_close = closes[-1]
    wick_down = last_high - last_low
    wick_pct = wick_down / btc * 100
    if low_touches >= 2:
        if last_low < min_low and last_close > min_low:
            sweep_depth = (min_low - last_low)
            if sweep_depth > atr * 0.3:
                score += 3.0
                is_hunt = True; hunt_side = "LONG"
                signal = f"🎯 LIQ HUNT LONG: Swept Equal Lows ${min_low:.0f} x{low_touches} -> Wicked to ${last_low:.0f} -> Reclaimed ${last_close:.0f}"
                if wick_pct > 1.0:
                    score += 1.0
                    signal += f" + DEEP WICK {wick_pct:.2f}%"
    if high_touches >= 2:
        if last_high > max_high and last_close < max_high:
            sweep_depth = (last_high - max_high)
            if sweep_depth > atr * 0.3:
                score -= 3.0
                is_hunt = True; hunt_side = "SHORT"
                signal = f"🎯 LIQ HUNT SHORT: Swept Equal Highs ${max_high:.0f} x{high_touches} -> Wicked to ${last_high:.0f} -> Rejected ${last_close:.0f}"
                if wick_pct > 1.0:
                    score -= 1.0
                    signal += f" + DEEP WICK {wick_pct:.2f}%"
    if is_hunt and len(closes) >= 3:
        if hunt_side == "LONG" and lows[-1] > highs[-3]:
            score += 0.8; signal += " + VOID FVG LONG"
        if hunt_side == "SHORT" and highs[-1] < lows[-3]:
            score -= 0.8; signal += " + VOID FVG SHORT"
    if not is_hunt:
        recent_high = max(highs[-20:-5])
        recent_low = min(lows[-20:-5])
        if last_low < recent_low and last_close > recent_low:
            score += 2.0; is_hunt = True; hunt_side = "LONG"
            signal = f"SWEEP LONG: Broke ${recent_low:.0f} -> Reclaimed ${last_close:.0f}"
        if last_high > recent_high and last_close < recent_high:
            score -= 2.0; is_hunt = True; hunt_side = "SHORT"
            signal = f"SWEEP SHORT: Broke ${recent_high:.0f} -> Rejected ${last_close:.0f}"
    return score, signal, is_hunt, hunt_side

def human_brain(btc, closes, highs, lows, vols, macro, atr, smart, fear, fear_label, session, session_mult, live_news, liq_map, news_mode):
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
    qty_raw = risk_usd / max(atr, 20)
    qty = max(qty_raw, 0.005)
    qty = max(qty, BYBIT_MIN_QTY)
    qty = min(qty, 0.01)
    qty = round(qty / BYBIT_QTY_STEP) * BYBIT_QTY_STEP
    qty = round(qty, 3)
    pos_usd = qty * btc
    bybit_ok = pos_usd >= BYBIT_MIN_ORDER_USD or paper_balance < 20
    trade_fee = pos_usd * BYBIT_TAKER_FEE
    fund_fee = pos_usd * 0.0001
    lev_fee = pos_usd * 0.0001
    buffer = 0.005 * vol_mult
    total_fees = trade_fee + fund_fee + lev_fee + buffer
    # V5.12.1 BE $0.15 MIN + GROWTH WITH BALANCE - FIRST VERSION
    # $10 -> $0.15, $20 -> $0.30, $50 -> $0.75, $100 -> $1.50
    be_profit = max(paper_balance*0.005 * vol_mult, total_fees*0.3, 0.15, paper_balance * 0.015)
    be_dist = (total_fees + be_profit) / qty
    # Early lock distance: 50% to BE - move SL to Entry, no full loss if BE never triggers
    early_lock_dist = be_dist * 0.5
    tp_mult = 1.8 + (trend_strength*0.5)
    tp_mult = tp_mult * vol_mult
    sl_mult = 0.8 + (0.2 * vol_mult)
    tp_dist_raw = atr * tp_mult
    sl_dist = atr * sl_mult
    min_tp_for_be = be_dist * 2.5
    min_tp_for_sl = sl_dist * 1.5
    tp_dist = max(tp_dist_raw, min_tp_for_be, min_tp_for_sl)
    if sl_dist >= tp_dist * 0.6:
        sl_dist = tp_dist * 0.5
    tp_covers_be = tp_dist > be_dist * 2.0
    tp_covers_sl = tp_dist > sl_dist * 1.5
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
    if macro['SPX_FUT']>0: score += 0.6
    elif macro['SPX_FUT']<0: score -= 0.6
    if macro['NQ_FUT']>0: score += 1.2
    elif macro['NQ_FUT']<0: score -= 1.2
    if macro['NQ_CASH']>0: score += 0.7
    elif macro['NQ_CASH']<0: score -= 0.7
    if macro['NDX100']>0: score += 0.5
    elif macro['NDX100']<0: score -= 0.5
    if (macro['NQ_FUT']>0.3 and macro['NQ_CASH']<-0.3) or (macro['NQ_FUT']<-0.3 and macro['NQ_CASH']>0.3):
        score = score * 0.5
    if macro['DXY']<0: score += 0.8
    elif macro['DXY']>0: score -= 0.8
    if macro['GOLD']>0.5: score += 0.3
    if macro['OIL']>6: score = 0
    liq_score, liq_signal, is_hunt, hunt_side = liquidity_hunt_analysis(closes, highs, lows, vols, atr)
    score += liq_score
    score += liq_map.get("score", 0.0)
    if liq_map.get("bias") == "LONG_HUNT_CONFIRMED" and is_hunt and hunt_side == "LONG":
        score += 1.0
        liq_signal += " + ✅ REAL LIQ MAP CONFIRMED"
    if liq_map.get("bias") == "SHORT_HUNT_CONFIRMED" and is_hunt and hunt_side == "SHORT":
        score -= 1.0
        liq_signal += " + ✅ REAL LIQ MAP CONFIRMED"
    if smart['funding'] > 0.05: score -= 1.0
    elif smart['funding'] < -0.05: score += 1.0
    if smart['oi_change'] > 2 and smart['long_short'] > 1.5: score -= 0.8
    if fear < 20: score += 1.0
    elif fear > 80: score -= 1.0
    score += live_news.get("score", 0.0)
    news_boost = False
    if news_mode == "LONG" and liq_map.get("bias") in ["LONG_HUNT_CONFIRMED", "HEAVY_LONG_LIQ"]:
        score += 1.0; news_boost = True; liq_signal += " + 📰 NEWS+HUNT LONG CONFIRMED"
    if news_mode == "SHORT" and liq_map.get("bias") in ["SHORT_HUNT_CONFIRMED", "HEAVY_SHORT_LIQ"]:
        score -= 1.0; news_boost = True; liq_signal += " + 📰 NEWS+HUNT SHORT CONFIRMED"
    if news_mode == "SHORT" and is_hunt and hunt_side == "LONG":
        score += 1.5; liq_signal += " + 📰 NEWS TRAP - Bear news but sweep reclaim = LONG"
    if news_mode == "LONG" and is_hunt and hunt_side == "SHORT":
        score -= 1.5; liq_signal += " + 📰 NEWS TRAP - Bull news but sweep reject = SHORT"
    effective_session_mult = 1.0 if (is_hunt or news_boost) else session_mult
    score = score * effective_session_mult
    threshold = 1.5 * ai_strictness
    if is_hunt or news_boost:
        threshold = 1.0 * ai_strictness
    win_prob = 0.50 + (abs(score)/5)*0.30 + (vol_conf*0.05)
    if is_hunt or news_boost:
        win_prob = min(win_prob + 0.10, 0.85)
    win_prob = min(win_prob, 0.85)
    tp_profit = tp_dist*qty - total_fees
    sl_loss = sl_dist*qty + total_fees
    ev = (win_prob * tp_profit) - ((1-win_prob) * sl_loss)
    rr = tp_dist / max(sl_dist,1)
    return {
        "regime":regime,"vol_mult":vol_mult,"trend_dir":trend_dir,"trend_strength":trend_strength,
        "vol_ratio":vol_ratio,"win_rate":win_rate,"ai_strictness":ai_strictness,"mindset":mindset,
        "risk_pct":risk_pct,"risk_usd":risk_usd,"lev":lev,"qty":qty,"pos_usd":pos_usd,"bybit_ok":bybit_ok,
        "total_fees":total_fees,"be_profit":be_profit,"be_dist":be_dist,"early_lock_dist":early_lock_dist,"tp_dist":tp_dist,"sl_dist":sl_dist,
        "tp_mult":tp_mult,"sl_mult":sl_mult,"score":score,"threshold":threshold,
        "win_prob":win_prob,"ev":ev,"rr":rr,"tp_profit":tp_profit,"sl_loss":sl_loss,"r":r,
        "ema9":ema9,"ema21":ema21,"ema50":ema50,"smc_signal":liq_signal,"smc_score":liq_score,
        "tp_covers_be":tp_covers_be,"tp_covers_sl":tp_covers_sl,"tp_dist_raw":tp_dist_raw,
        "is_hunt":is_hunt,"hunt_side":hunt_side,"liq_signal":liq_signal,"news_boost":news_boost
    }

def main_loop():
    global paper_balance, paper_pnl, wins, losses, be_hits, open_pos, history, consecutive_losses, consecutive_wins, last_trade_time
    log(f"V5.12.1 STARTED - BE $0.15 GROWTH + EARLY LOCK, NO FEAR INSTANT, WORLD NEWS HUNTER, DYNAMIC ALL")
    while True:
        try:
            closes, highs, lows, vols = get_bybit_klines()
            if closes is None:
                log("Error retry 10s"); time.sleep(10); continue
            btc=closes[-1]
            atr=atr_calc(highs,lows,closes)
            if atr<20: atr=20
            macro = get_macro_all()
            smart = get_bybit_smart_money()
            fear, fear_label = get_fear_greed()
            session, session_mult = get_session()
            live_news = get_live_news()
            liq_map = get_liquidation_map()
            news_block, news_msg, news_mode = get_news_risk(live_news)
            B=human_brain(btc, closes, highs, lows, vols, macro, atr, smart, fear, fear_label, session, session_mult, live_news, liq_map, news_mode)
            log(f"BRAIN: {B['regime']} ATR ${atr:.0f} EMA9 ${B['ema9']:.0f} RSI {B['r']:.1f} Vol x{B['vol_ratio']:.2f} | {B['mindset']}")
            log(f"LIQ HUNT: {B['liq_signal']} | Hunt={B['is_hunt']} Side={B['hunt_side']} NewsBoost={B['news_boost']}")
            log(f"LIQ MAP: Long Liq ${liq_map['long_liq']/1000:.0f}k | Short Liq ${liq_map['short_liq']/1000:.0f}k | Total ${liq_map['total']/1000:.0f}k | Bias {liq_map['bias']} Score {liq_map['score']:+.1f}")
            log(f"WORLD: Fear {fear} ({fear_label}) Funding {smart['funding']:.3f}% OI {smart['oi_change']:+.2f}% L/S {smart['long_short']:.2f} Session {session} x{session_mult}")
            log(f"NEWS: Dir={live_news.get('direction')} Score {live_news.get('score',0):+.1f} | Headline: {live_news.get('headline','No big news')[:100]} | Mode: {news_mode} | Block: NEVER")
            log(f"DYNAMIC: FEES ${B['total_fees']:.4f} BE ${B['be_dist']:.0f} BE_Profit ${B['be_profit']:.2f} EarlyLock ${B['early_lock_dist']:.0f} | TP ${B['tp_dist']:.0f} (ATR x{B['tp_mult']:.1f}) SL ${B['sl_dist']:.0f} (ATR x{B['sl_mult']:.1f}) | Lev {B['lev']}x Qty {B['qty']:.3f} (Risk ${B['risk_usd']:.3f}) | Score {B['score']:.2f} / Thr {B['threshold']:.2f} WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} R:R {B['rr']:.1f} | Bal ${paper_balance:.2f} PnL ${paper_pnl:.2f} W {wins} L {losses} BE {be_hits}")
            log(f"NASDAQ: FUT NQ {macro['NQ_FUT']:+.2f}% | CASH NQ {macro['NQ_CASH']:+.2f}% | NDX100 {macro['NDX100']:+.2f}% | SPX Cash {macro['SPX']:+.2f}% SPX Fut {macro['SPX_FUT']:+.2f}% | DXY {macro['DXY']:+.2f}% Oil {macro['OIL']:+.2f}% Gold {macro['GOLD']:+.2f}%")
            if news_mode in ["LONG", "SHORT"]:
                log(f"🔥 NEWS OPPORTUNITY MODE: {news_msg} - I go take advantage")
            if open_pos:
                side=open_pos['side']; entry=open_pos['entry']; tp=open_pos['tp']; sl=open_pos['sl']; be_price=open_pos['be_price']
                early_price = entry + open_pos['early_lock_dist'] if side=='LONG' else entry - open_pos['early_lock_dist']
                # V5.12.1 EARLY LOCK: 50% to BE -> SL to Entry, no full loss if BE never triggers
                if not open_pos.get('early_done') and not open_pos.get('be_done'):
                    if (side=='LONG' and btc>=early_price) or (side=='SHORT' and btc<=early_price):
                        open_pos['sl']=entry; open_pos['early_done']=True
                        log(f"🛡️ EARLY LOCK HIT! SL -> Entry ${entry:.0f} - No full loss again, even if BE never trigger")
                if not open_pos.get('be_done'):
                    if (side=='LONG' and btc>=be_price) or (side=='SHORT' and btc<=be_price):
                        open_pos['sl']=be_price; open_pos['be_done']=True; be_hits+=1
                        log(f"🟢 BE HIT + PROFIT LOCKED! SL -> BE ${be_price:.0f} = Fees + ${open_pos['be_profit']:.2f} profit secured")
                if open_pos.get('be_done'):
                    if side=='LONG':
                        nsl=btc-atr*0.35
                        if nsl>open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL UP SL ${nsl:.0f}")
                    else:
                        nsl=btc+atr*0.35
                        if nsl<open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL DOWN SL ${nsl:.0f}")
                pnl=0; closed=False; reason=""
                total_fees=open_pos['total_fees']; qty=open_pos['qty']; be_profit=open_pos['be_profit']
                if side=='LONG':
                    if btc>=tp: pnl=(tp-entry)*qty-total_fees; closed=True; reason="TP HIT 🎯"
                    elif btc<=open_pos['sl']:
                        if open_pos.get('be_done'): pnl=be_profit; closed=True; reason=f"BE SL HIT 🟢 +${be_profit:.2f}"
                        elif open_pos.get('early_done'): pnl=-total_fees*0.5; closed=True; reason=f"EARLY LOCK SL HIT 🛡️ ~${pnl:.2f} - No full loss"
                        else: pnl=(open_pos['sl']-entry)*qty-total_fees; closed=True; reason="SL HIT"
                else:
                    if btc<=tp: pnl=(entry-tp)*qty-total_fees; closed=True; reason="TP HIT 🎯"
                    elif btc>=open_pos['sl']:
                        if open_pos.get('be_done'): pnl=be_profit; closed=True; reason=f"BE SL HIT 🟢 +${be_profit:.2f}"
                        elif open_pos.get('early_done'): pnl=-total_fees*0.5; closed=True; reason=f"EARLY LOCK SL HIT 🛡️ ~${pnl:.2f} - No full loss"
                        else: pnl=(entry-open_pos['sl'])*qty-total_fees; closed=True; reason="SL HIT"
                time_limit = 90*60 if B['regime']=="CALM" else 180*60 if B['regime'] in ["WILD","EXTREME"] else 120*60
                if not closed and (time.time()-open_pos['start'])>time_limit:
                    pnl=(btc-entry)*qty-total_fees if side=='LONG' else (entry-btc)*qty-total_fees
                    closed=True; reason=f"TIME EXIT {int(time_limit/60)}min"
                if closed:
                    paper_balance+=pnl; paper_pnl+=pnl; history.append(pnl)
                    last_trade_time = time.time()
                    if pnl>0:
                        wins+=1; consecutive_wins+=1; consecutive_losses=0
                    else:
                        losses+=1; consecutive_losses+=1; consecutive_wins=0
                    log(f"✅ CLOSED {side} {reason} | PnL ${pnl:.4f} | Bal ${paper_balance:.2f} | W {wins} L {losses} BE {be_hits}")
                    open_pos=None; time.sleep(5); continue
                else:
                    log(f"⏳ OPEN {side} Entry ${entry:.0f} Now ${btc:.0f} TP ${tp:.0f} SL ${open_pos['sl']:.0f} BE ${be_price:.0f} Early ${early_price:.0f}")
                    time.sleep(20); continue
            if not B['tp_covers_be']:
                log(f"⛔ SKIP TP ${B['tp_dist']:.0f} no > BE ${B['be_dist']:.0f} x2 - 30s scan")
                time.sleep(30); continue
            if not B['tp_covers_sl']:
                log(f"⛔ SKIP TP ${B['tp_dist']:.0f} no > SL ${B['sl_dist']:.0f} x1.5 - 30s scan")
                time.sleep(30); continue
            if abs(B['score']) < B['threshold']:
                log(f"=> NO CLEAR: Score {B['score']:.2f} < Thr {B['threshold']:.2f}... SCAN AGAIN 30s")
                time.sleep(30); continue
            if B['win_prob'] < 0.60:
                log(f"⛔ SKIP WinProb {B['win_prob']*100:.0f}% < 60% - 30s scan")
                time.sleep(30); continue
            if B['ev'] <= 0:
                log(f"⛔ SKIP EV ${B['ev']:.4f} <= 0 - 30s scan")
                time.sleep(30); continue
            if B['rr'] < 1.4:
                log(f"⛔ SKIP R:R {B['rr']:.1f} < 1.4 - 30s scan")
                time.sleep(30); continue
            if macro['OIL'] > 6:
                log(f"⛔ SKIP Oil spike {macro['OIL']:.2f}% - Bank Trap 30s")
                time.sleep(30); continue
            if B['qty'] < BYBIT_MIN_QTY:
                log(f"⛔ SKIP Qty {B['qty']:.3f} < Bybit min {BYBIT_MIN_QTY}")
                time.sleep(30); continue
            if B['is_hunt'] and B['hunt_side']:
                side = B['hunt_side']
            elif B['news_boost'] and news_mode in ["LONG", "SHORT"]:
                side = news_mode
            else:
                side='LONG' if B['score']>=0 else 'SHORT'
            entry = btc
            if side=='LONG':
                tp=entry+B['tp_dist']; sl=entry-B['sl_dist']; be_price=entry+B['be_dist']
            else:
                tp=entry-B['tp_dist']; sl=entry+B['sl_dist']; be_price=entry-B['be_dist']
            open_pos={'side':side,'entry':entry,'tp':tp,'sl':sl,'be_price':be_price,'be_done':False,'early_done':False,'early_lock_dist':B['early_lock_dist'],'start':time.time(),'total_fees':B['total_fees'],'qty':B['qty'],'be_profit':B['be_profit']}
            last_trade_time = time.time()
            log(f"🔥 INSTANT ENTER {side} {'[LIQ HUNT] ' if B['is_hunt'] else ''}{' [NEWS] ' if B['news_boost'] else ''}Entry ${entry:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f} Early ${entry+B['early_lock_dist'] if side=='LONG' else entry-B['early_lock_dist']:.0f} Qty {B['qty']:.3f} Lev {B['lev']}x | BE Profit ${B['be_profit']:.2f} | WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} R:R {B['rr']:.1f} | {B['liq_signal']}")
            time.sleep(20)
        except Exception as e:
            log(f"Error {e} retry 10s"); time.sleep(10)

if __name__=="__main__":
    main_loop()
