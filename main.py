import os, time, math, requests, datetime, xml.etree.ElementTree as ET
import threading, traceback

# --- V5.13.3 FINAL FIXED ---
# BTCUSDT | 0.001 FIXED | 50x ISOLATED | Cert 95% + Agree 6 | TP 3x Fees | Cooldown 5min | No Pause | PreFlip 2/2 Once | News Override | SL->Entry
START_BAL = 10.0
paper_balance = START_BAL
paper_pnl = 0.0
wins = 0; losses = 0; be_hits = 0
open_pos = None; waiting = None
history = []
consecutive_losses = 0
consecutive_wins = 0
last_trade_time = 0
last_loss_time = 0

PAIR = "BTCUSDT"
FIXED_QTY = 0.001
FIXED_LEV = 50
MIN_CERTAINTY = 95
MIN_AGREE = 6
TP_FEE_MULTIPLIER = 3.0
COOLDOWN_MIN = 5
BYBIT_MIN_QTY = 0.001
BYBIT_QTY_STEP = 0.001
BYBIT_MIN_ORDER_USD = 5.0
BYBIT_TAKER_FEE = 0.0006
preflip_history = []

last_macro = {"DXY":0.0,"SPX":0.0,"SPX_FUT":0.0,"NQ_FUT":0.0,"NQ_CASH":0.0,"NDX100":0.0,"DAX":0.0,"FTSE":0.0,"NIKKEI":0.0,"OIL":0.0,"GOLD":0.0}
last_macro_time = 0
last_news = {"danger": False, "headline": "", "score": 0.0, "time": 0, "direction": "NEUTRAL", "fed": "NEUTRAL"}

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{now} [V5.13.3] {msg}", flush=True)

try:
    from flask import Flask
    app = Flask(__name__)
    @app.route('/')
    def home():
        return f"V5.13.3 Alive! Bal ${paper_balance:.2f} PnL ${paper_pnl:.2f} W {wins} L {losses} BE {be_hits}"
    @app.route('/health')
    def health(): return "OK", 200
    @app.route('/ping')
    def ping(): return "pong", 200
except Exception as e:
    print(f"Flask fail: {e}", flush=True)
    app = None

def self_ping_loop():
    while True:
        try:
            url = os.environ.get("RENDER_EXTERNAL_URL")
            if url:
                r = requests.get(url + "/health", timeout=10)
                log(f"💓 SELF-PING OK {r.status_code}")
            else:
                port = os.environ.get("PORT", 10000)
                requests.get(f"http://127.0.0.1:{port}/health", timeout=5)
                log(f"💓 SELF-PING localhost OK")
        except Exception as e:
            log(f"Self-ping fail: {e}")
        time.sleep(240)

def heartbeat_loop():
    while True:
        time.sleep(60)
        log(f"💓 HEARTBEAT Bal ${paper_balance:.2f} W {wins} L {losses} BE {be_hits} Open {open_pos is not None} Waiting {waiting is not None}")

def yahoo_direct(symbol, host):
    try:
        url = f"https://{host}/v8/finance/chart/{symbol}?range=5d&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=4).json()
        closes = r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2 and closes[-2] != 0:
            return (closes[-1]-closes[-2])/closes[-2]*100
        return None
    except: return None

def stooq_backup(symbol):
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        r = requests.get(url, timeout=4).text.strip().split("\n")
        rows = [x for x in r if x.strip() and ",,," not in x]
        if len(rows) >= 3:
            last = rows[-1].split(","); prev = rows[-2].split(",")
            c1 = float(last[4]); c0 = float(prev[4])
            if c0 != 0: return (c1-c0)/c0*100
        return None
    except: return None

def binance_1m_change(symbol):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=10", timeout=4).json()
        if len(r) >= 2:
            c0 = float(r[0][4]); c1 = float(r[-1][4])
            if c0 != 0: return (c1-c0)/c0*100
        return None
    except: return None

def fast_yahoo_multi(yahoo_symbols, stooq_symbol):
    for ys in yahoo_symbols:
        for host in ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]:
            v = yahoo_direct(ys, host)
            if v is not None: return v
    v = stooq_backup(stooq_symbol)
    if v is not None: return v
    return None

def get_macro_all():
    global last_macro, last_macro_time
    if time.time() - last_macro_time < 5 and last_macro_time != 0:
        return last_macro
    last_macro_time = time.time()
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
    eur_1m = binance_1m_change("EURUSDT")
    eth_1m = binance_1m_change("ETHUSDT")
    btc_1m = binance_1m_change("BTCUSDT")
    for k, (ys_list, ss) in mapping.items():
        try:
            v_daily = fast_yahoo_multi(ys_list, ss)
            v_live = None
            if k == "DXY":
                if eur_1m is not None: v_live = -eur_1m * 0.57 * 10
            if k in ["NQ_FUT","SPX_FUT","NQ_CASH","SPX","NDX100"]:
                if eth_1m is not None: v_live = eth_1m * 1.2
                elif btc_1m is not None: v_live = btc_1m * 1.0
            if k == "OIL":
                if btc_1m is not None: v_live = btc_1m * 0.3
            if k == "GOLD":
                if eur_1m is not None: v_live = eur_1m * 0.8
            if v_daily is not None and v_live is not None: v = v_daily * 0.15 + v_live * 0.85
            elif v_daily is not None: v = v_daily
            elif v_live is not None: v = v_live
            else: v = None
            if v is not None: out[k] = v; last_macro[k] = v
            else: out[k] = last_macro[k]
        except: out[k] = last_macro[k]
    return out

def get_bybit_klines(symbol="BTCUSDT", interval="1", limit=200):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}", timeout=6).json()
        kl = r["result"]["list"][::-1]
        closes = [float(x[4]) for x in kl]
        highs = [float(x[2]) for x in kl]
        lows = [float(x[3]) for x in kl]
        vols = [float(x[5]) for x in kl]
        return closes, highs, lows, vols
    except: return None, None, None, None

def get_bybit_smart_money():
    out = {"funding": 0.0, "oi_change": 0.0, "long_short": 1.0}
    try:
        f = requests.get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1", timeout=4).json()
        out["funding"] = float(f["result"]["list"][0]["fundingRate"]) * 100
    except: pass
    try:
        o = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=2", timeout=4).json()
        lst = o["result"]["list"]
        if len(lst) >= 2: out["oi_change"] = (float(lst[0]["openInterest"]) - float(lst[1]["openInterest"])) / float(lst[1]["openInterest"]) * 100
    except: pass
    try:
        ls = requests.get("https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=5min&limit=1", timeout=4).json()
        out["long_short"] = float(ls["result"]["list"][0]["longShortRatio"])
    except: pass
    return out

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=4).json()
        return int(r["data"][0]["value"]), r["data"][0]["value_classification"]
    except:
        try:
            r2 = requests.get("https://api.alternative.me/v2/fng/?limit=1", timeout=4).json()
            return int(r2["data"][0]["value"]), r2["data"][0]["value_classification"]
        except: return 50, "Neutral (Backup)"

def get_session():
    h = datetime.datetime.utcnow().hour
    wd = datetime.datetime.utcnow().weekday()
    monday_boost = 1.1 if wd == 0 else 1.0
    if 7 <= h < 11: return "LONDON", 1.2 * monday_boost
    elif 12 <= h < 20: return "NEW_YORK", 1.3 * monday_boost
    elif 20 <= h < 23: return "NY_LATE", 0.8
    else: return "ASIA", 0.6

FED_HAWKISH = ["rate hike", "hike rates", "higher for longer", "inflation sticky", "inflation persistent", "tighten", "tightening", "hawkish", "restrictive", "no rate cut", "delay rate cut", "powell hawkish", "fed warns", "debt ceiling", "treasury selloff"]
FED_DOVISH = ["rate cut", "cut rates", "easing", "dovish", "pause", "soft landing", "disinflation", "powell dovish", "fed signals cut", "stimulus", "quantitative easing"]
STRONG_BEARISH = ["hack", "exploit", "breach", "stolen", "sec lawsuit", "sec sues", "sec charges", "etf reject", "etf outflow", "bankrupt", "collapse", "crash", "fraud", "liquidation cascade", "missile", "invasion", "airstrike", "nuclear", "martial law", "coup", "assassination", "recession", "war", "sanction", "bank failure", "bank collapse"]
STRONG_BULLISH = ["etf approve", "etf approved", "etf inflow", "etf inflow record", "peace deal", "ceasefire", "institutional buys", "adoption", "bitcoin reserve", "strategic reserve", "bullish", "all-time high"]

def parse_rss_titles(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        root = ET.fromstring(r.content)
        titles = []
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text: titles.append(t.text)
            if len(titles) >= 6: break
        return titles
    except: return []

def get_live_news():
    global last_news
    if time.time() - last_news["time"] < 10 and last_news["time"] != 0:
        return last_news
    titles = []
    titles += parse_rss_titles("https://www.coindesk.com/arc/outboundfeed/rss/")
    titles += parse_rss_titles("https://cointelegraph.com/rss")
    titles += parse_rss_titles("https://news.google.com/rss/search?q=Federal+Reserve+OR+FOMC+OR+Powell+OR+interest+rate&hl=en-US&gl=US&ceid=US:en")
    titles += parse_rss_titles("https://news.google.com/rss/search?q=Bitcoin+OR+crypto+OR+ETF&hl=en-US&gl=US&ceid=US:en")
    titles += parse_rss_titles("https://news.google.com/rss/search?q=war+OR+missile+OR+sanction+OR+bank+collapse&hl=en-US&gl=US&ceid=US:en")
    titles += parse_rss_titles("https://feeds.bbci.co.uk/news/world/rss.xml")
    titles += parse_rss_titles("https://news.google.com/rss/search?q=ECB+OR+BOJ+OR+central+bank+OR+CPI+OR+inflation&hl=en-US&gl=US&ceid=US:en")
    danger = False; headline_hit = ""; score = 0.0; direction = "NEUTRAL"; fed = "NEUTRAL"; fed_hit = ""
    # FIX: One title = one vote, no double count
    for t in titles:
        low = t.lower()
        matched = False
        for w in FED_HAWKISH:
            if w in low:
                score -= 2.5; direction = "BEARISH"; fed = "HAWKISH"; fed_hit = t; headline_hit = t; danger = True; matched = True; break
        if matched: continue
        for w in FED_DOVISH:
            if w in low:
                score += 2.5; direction = "BULLISH"; fed = "DOVISH"; fed_hit = t; headline_hit = t; matched = True; break
        if matched: continue
        for w in STRONG_BEARISH:
            if w in low:
                score -= 2.0; direction = "BEARISH"; danger = True
                if not headline_hit: headline_hit = t
                matched = True; break
        if matched: continue
        for w in STRONG_BULLISH:
            if w in low:
                score += 2.0; direction = "BULLISH"
                if not headline_hit: headline_hit = t
                break
    out = {"danger": danger, "headline": headline_hit, "score": score, "direction": direction, "fed": fed, "fed_hit": fed_hit, "titles": titles[:4], "time": time.time()}
    last_news = out
    if headline_hit: log(f"🌍 WORLD NEWS: Fed={fed} Dir={direction} Score {score:+.1f} | {headline_hit[:110]}")
    else: log(f"🌍 WORLD NEWS: No big news - Neutral, roaming...")
    return out

def get_news_risk(live_news):
    if live_news.get("direction") == "BULLISH": return False, f"NEWS LONG: {live_news.get('headline','')[:80]}", "LONG"
    if live_news.get("direction") == "BEARISH": return False, f"NEWS SHORT: {live_news.get('headline','')[:80]}", "SHORT"
    return False, "", "NEUTRAL"

def get_liquidation_map():
    long_liq = 0.0; short_liq = 0.0; details = []
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100", timeout=4).json()
        for o in r:
            try:
                price = float(o.get("price", 0)); qty = float(o.get("origQty", 0)); usd = price * qty
                if o.get("side") == "SELL": long_liq += usd
                else: short_liq += usd
                if usd > 100000: details.append(f"{o.get('side')} Liq ${usd/1000:.0f}k @ ${price:.0f}")
            except: pass
    except Exception as e: print(f"Binance Liq fail: {e}", flush=True)
    total = long_liq + short_liq
    bias = "NEUTRAL"; score = 0.0
    if total > 500000:
        if long_liq > short_liq * 1.5: bias = "LONG_HUNT_CONFIRMED"; score = 2.0
        elif short_liq > long_liq * 1.5: bias = "SHORT_HUNT_CONFIRMED"; score = -2.0
        elif long_liq > 2000000: bias = "HEAVY_LONG_LIQ"; score = 1.5
        elif short_liq > 2000000: bias = "HEAVY_SHORT_LIQ"; score = -1.5
    return {"long_liq": long_liq, "short_liq": short_liq, "total": total, "bias": bias, "score": score, "details": details[:4]}

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

def pre_flip_detector(closes, highs, lows):
    if len(closes) < 30: return "NEUTRAL", 0
    e9 = ema(closes[-30:], 9); e21 = ema(closes[-30:], 21)
    e9_prev = ema(closes[-31:-1], 9); e21_prev = ema(closes[-31:-1], 21)
    r = rsi_calc(closes); r_prev = rsi_calc(closes[:-1])
    last_close = closes[-1]; prev_close = closes[-2]
    signals_long = 0; signals_short = 0
    if e9 > e21 and e9_prev <= e21_prev: signals_long += 2
    if e9 < e21 and e9_prev >= e21_prev: signals_short += 2
    if r > 50 and r_prev <= 50: signals_long += 1
    if r < 50 and r_prev >= 50: signals_short += 1
    if len(closes) >= 4:
        if closes[-3] < closes[-4] and closes[-2] < closes[-3] and last_close > prev_close: signals_long += 1
        if closes[-3] > closes[-4] and closes[-2] > closes[-3] and last_close < prev_close: signals_short += 1
    if last_close > max(closes[-11:-1]): signals_long += 1
    if last_close < min(closes[-11:-1]): signals_short += 1
    if signals_long >= 2 and signals_long > signals_short: return "LONG", signals_long * 20
    if signals_short >= 2 and signals_short > signals_long: return "SHORT", signals_short * 20
    return "NEUTRAL", 0

def check_preflip_stable(pre_flip, destination):
    # FIX: Called ONLY once per loop in main, for entry. Not in profit-flip.
    global preflip_history
    pf = pre_flip[0]
    if pf == "NEUTRAL":
        preflip_history = []
        return False, "PreFlip NEUTRAL - BLOCKED"
    if destination != "NEUTRAL" and pf != destination:
        preflip_history = []
        return False, f"PreFlip {pf} vs DEST {destination} - VETO - BLOCKED"
    preflip_history.append(pf)
    if len(preflip_history) > 2: preflip_history.pop(0)
    if len(preflip_history) < 2 or preflip_history[0] != preflip_history[1]:
        return False, f"PreFlip {pf} not stable yet (1/2) - Wait confirmation"
    return True, f"PreFlip {pf} stable 2/2 - CONFIRMED"

def liquidity_hunt_analysis(closes, highs, lows, vols, atr):
    score = 0.0; signal = "No Hunt"; is_hunt = False; hunt_side = None; void = None; sweep_type = "NONE"
    if len(closes) < 50: return score, signal, is_hunt, hunt_side, void, sweep_type
    btc = closes[-1]
    lows_50 = lows[-50:-2]; highs_50 = highs[-50:-2]
    min_low = min(lows_50); low_touches = sum(1 for l in lows_50 if abs(l - min_low)/min_low < 0.002)
    max_high = max(highs_50); high_touches = sum(1 for h in highs_50 if abs(h - max_high)/max_high < 0.002)
    last_low = lows[-1]; last_high = highs[-1]; last_close = closes[-1]
    wick_pct = (last_high - last_low) / btc * 100
    if len(closes) >= 3:
        if lows[-1] > highs[-3]: void = f"VOID LONG ${highs[-3]:.0f}-${lows[-1]:.0f}"
        elif highs[-1] < lows[-3]: void = f"VOID SHORT ${highs[-1]:.0f}-${lows[-3]:.0f}"
    if low_touches >= 2 and last_low < min_low:
        if last_close > min_low:
            score += 3.0; is_hunt = True; hunt_side = "LONG"; sweep_type = "REVERSAL_LONG"
            signal = f"🎯 CASE 1 LONG: SWEPT LOWS ${min_low:.0f} -> BACK UP ${last_close:.0f} - FAKE DOWN, REAL UP"
            if wick_pct > 1.0: score += 0.5; signal += f" + WICK {wick_pct:.2f}%"
        else:
            score -= 3.0; is_hunt = True; hunt_side = "SHORT"; sweep_type = "CONTINUATION_SHORT"
            signal = f"🎯 CASE 2 SHORT: SWEPT LOWS ${min_low:.0f} -> STILL BELOW ${last_close:.0f} - REAL DOWN"
    if high_touches >= 2 and last_high > max_high:
        if last_close < max_high:
            score -= 3.0; is_hunt = True; hunt_side = "SHORT"; sweep_type = "REVERSAL_SHORT"
            signal = f"🎯 CASE 3 SHORT: SWEPT HIGHS ${max_high:.0f} -> BACK DOWN ${last_close:.0f} - FAKE UP, REAL DOWN"
            if wick_pct > 1.0: score -= 0.5; signal += f" + WICK {wick_pct:.2f}%"
        else:
            score += 3.0; is_hunt = True; hunt_side = "LONG"; sweep_type = "CONTINUATION_LONG"
            signal = f"🎯 CASE 4 LONG: SWEPT HIGHS ${max_high:.0f} -> STILL ABOVE ${last_close:.0f} - REAL UP"
    if is_hunt and len(closes) >= 3:
        if hunt_side == "LONG" and lows[-1] > highs[-3]: score += 0.5; signal += " + VOID LONG"
        if hunt_side == "SHORT" and highs[-1] < lows[-3]: score -= 0.5; signal += " + VOID SHORT"
    if not is_hunt:
        recent_high = max(highs[-20:-5]); recent_low = min(lows[-20:-5])
        if last_low < recent_low and last_close > recent_low:
            score += 2.0; is_hunt = True; hunt_side = "LONG"; sweep_type = "REVERSAL_LONG"; signal = f"SWEEP LONG: Swept ${recent_low:.0f} -> Reclaimed"
        elif last_low < recent_low and last_close < recent_low:
            score -= 2.0; is_hunt = True; hunt_side = "SHORT"; sweep_type = "CONTINUATION_SHORT"; signal = f"SWEEP DOWN CONTINUE: Swept ${recent_low:.0f} -> Still below"
        if last_high > recent_high and last_close < recent_high:
            score -= 2.0; is_hunt = True; hunt_side = "SHORT"; sweep_type = "REVERSAL_SHORT"; signal = f"SWEEP SHORT: Swept ${recent_high:.0f} -> Rejected"
        elif last_high > recent_high and last_close > recent_high:
            score += 2.0; is_hunt = True; hunt_side = "LONG"; sweep_type = "CONTINUATION_LONG"; signal = f"SWEEP UP CONTINUE: Swept ${recent_high:.0f} -> Still above"
    return score, signal, is_hunt, hunt_side, void, sweep_type

def confluence_engine(macro, smart, fear, live_news, liq_map, hunt_side, sweep_type, trend_dir, r, closes, pre_flip):
    votes = {}
    if hunt_side == "LONG": votes["SWEEP"] = "LONG"
    elif hunt_side == "SHORT": votes["SWEEP"] = "SHORT"
    else: votes["SWEEP"] = "NEUTRAL"
    if macro['DXY'] < -0.05: votes["DXY"] = "LONG"
    elif macro['DXY'] > 0.05: votes["DXY"] = "SHORT"
    else: votes["DXY"] = "NEUTRAL"
    nq_spx = (macro['NQ_FUT'] + macro['SPX_FUT'] + macro['NQ_CASH'] + macro['SPX']) / 4
    if nq_spx > 0.1: votes["NQ_SPX"] = "LONG"
    elif nq_spx < -0.1: votes["NQ_SPX"] = "SHORT"
    else: votes["NQ_SPX"] = "NEUTRAL"
    if live_news.get("fed") == "DOVISH": votes["FED"] = "LONG"
    elif live_news.get("fed") == "HAWKISH": votes["FED"] = "SHORT"
    else: votes["FED"] = "NEUTRAL"
    if live_news.get("direction") == "BULLISH": votes["NEWS"] = "LONG"
    elif live_news.get("direction") == "BEARISH": votes["NEWS"] = "SHORT"
    else: votes["NEWS"] = "NEUTRAL"
    fund_vote = "NEUTRAL"
    if smart['funding'] < -0.02: fund_vote = "LONG"
    elif smart['funding'] > 0.02: fund_vote = "SHORT"
    if liq_map.get("bias") == "LONG_HUNT_CONFIRMED": fund_vote = "LONG"
    if liq_map.get("bias") == "SHORT_HUNT_CONFIRMED": fund_vote = "SHORT"
    votes["SMART_MONEY"] = fund_vote
    trend_vote = "NEUTRAL"
    if trend_dir == 1 and r > 50: trend_vote = "LONG"
    elif trend_dir == -1 and r < 50: trend_vote = "SHORT"
    votes["TREND"] = trend_vote
    if pre_flip[0] in ["LONG","SHORT"]: votes["PRE_FLIP_1M"] = pre_flip[0]
    else: votes["PRE_FLIP_1M"] = "NEUTRAL"
    long_votes = sum(1 for v in votes.values() if v == "LONG")
    short_votes = sum(1 for v in votes.values() if v == "SHORT")
    decided = long_votes + short_votes
    if long_votes > short_votes:
        destination = "LONG"; agree = long_votes; certainty = (agree / decided * 100) if decided > 0 else 0
    elif short_votes > long_votes:
        destination = "SHORT"; agree = short_votes; certainty = (agree / decided * 100) if decided > 0 else 0
    else:
        destination = "NEUTRAL"; agree = 0; certainty = 0
    sweep_agrees = (hunt_side == destination) if hunt_side else False
    # NEWS OVERRIDE: FED + NEWS + SWEEP all same = strong news trade, allow even if one other vote neutral
    news_override = False
    fed_dir = "LONG" if live_news.get("fed") == "DOVISH" else "SHORT" if live_news.get("fed") == "HAWKISH" else "NEUTRAL"
    news_dir = "LONG" if live_news.get("direction") == "BULLISH" else "SHORT" if live_news.get("direction") == "BEARISH" else "NEUTRAL"
    if fed_dir != "NEUTRAL" and fed_dir == news_dir and fed_dir == hunt_side:
        news_override = True
    # Normal pass: 95% + 6 agree. News override pass: 95% + 5 agree + news trio
    if news_override:
        confluence_pass = (decided >= 5 and certainty >= MIN_CERTAINTY and agree >= 5)
    else:
        confluence_pass = (decided >= 6 and certainty >= MIN_CERTAINTY and agree >= MIN_AGREE and (sweep_agrees or not hunt_side))
    return {"votes": votes, "long_votes": long_votes, "short_votes": short_votes, "decided": decided, "destination": destination, "certainty": certainty, "agree": agree, "sweep_agrees": sweep_agrees, "confluence_pass": confluence_pass, "nq_spx": nq_spx, "news_override": news_override}

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
    mindset="V5.13.3: Brain - I don't want to loss - Only A+ + News ready"
    if consecutive_wins >= 3: mindset="V5.13.3: Hot streak - Still only A+"
    qty = FIXED_QTY; lev = FIXED_LEV
    pos_usd = qty * btc
    margin_needed = pos_usd / max(lev, 1)
    bybit_ok = pos_usd >= BYBIT_MIN_ORDER_USD or paper_balance < 20
    entry_fee = pos_usd * BYBIT_TAKER_FEE
    exit_fee = pos_usd * BYBIT_TAKER_FEE
    real_funding = abs(smart.get('funding', 0.01)) / 100.0
    real_funding = max(real_funding, 0.0001)
    fund_fee = pos_usd * real_funding * 3
    lev_fee = pos_usd * 0.0001
    slippage = pos_usd * 0.0002
    buffer = 0.01 * vol_mult
    total_fees = entry_fee + exit_fee + fund_fee + lev_fee + slippage + buffer
    # FIXED BE MATH for 0.001: BE = fees + $0.05 only
    be_profit = 0.05
    be_dist = (total_fees + be_profit) / qty
    early_lock_dist = be_dist * 0.35
    # TP: Must make >= 3x fees profit
    required_tp_profit = total_fees * TP_FEE_MULTIPLIER
    tp_dist = (required_tp_profit + total_fees) / qty
    # Also at least ATR * 1.5 so TP no be too tight for noise
    tp_dist = max(tp_dist, atr * 1.5)
    # SL: ATR based, but must be < TP for RR >= 1.4, and < 0.7% for 50x safety
    sl_dist = max(atr * 0.9, be_dist * 1.2)
    max_sl = btc * 0.007
    if sl_dist > max_sl: sl_dist = max_sl
    if tp_dist < sl_dist * 1.4: tp_dist = sl_dist * 1.5
    # Re-check TP 3x after SL adjust
    if tp_dist * qty - total_fees < required_tp_profit:
        tp_dist = (required_tp_profit + total_fees) / qty
    tp_covers_be = tp_dist > be_dist * 2.0; tp_covers_sl = tp_dist > sl_dist * 1.4
    r = rsi_calc(closes)
    score = 0.0
    if ema9>ema21: score += 1.0
    else: score -= 1.0
    if r>55: score += 0.5
    elif r<45: score -= 0.5
    if r > 75: score -= 0.5
    if r < 25: score += 0.5
    if macro['SPX_FUT']>0: score += 0.5
    elif macro['SPX_FUT']<0: score -= 0.5
    if macro['NQ_FUT']>0: score += 0.5
    elif macro['NQ_FUT']<0: score -= 0.5
    if macro['DXY']<0: score += 0.5
    elif macro['DXY']>0: score -= 0.5
    if macro['OIL']>6: score = 0
    liq_score, liq_signal, is_hunt, hunt_side, void, sweep_type = liquidity_hunt_analysis(closes, highs, lows, vols, atr)
    score += max(min(liq_score, 3.0), -3.0)
    if smart['funding'] > 0.05: score -= 0.5
    elif smart['funding'] < -0.05: score += 0.5
    if fear < 20: score += 0.5
    elif fear > 80: score -= 0.5
    news_score = max(min(live_news.get("score", 0.0), 2.0), -2.0)
    score += news_score
    news_boost = False
    if live_news.get("fed") == "HAWKISH" and is_hunt and hunt_side == "SHORT": news_boost = True; liq_signal += " + 🏦 FED HAWKISH + SHORT"
    if live_news.get("fed") == "DOVISH" and is_hunt and hunt_side == "LONG": news_boost = True; liq_signal += " + 🏦 FED DOVISH + LONG"
    if news_mode == "SHORT" and is_hunt and hunt_side == "LONG": liq_signal += " + 📰 NEWS TRAP LONG"
    if news_mode == "LONG" and is_hunt and hunt_side == "SHORT": liq_signal += " + 📰 NEWS TRAP SHORT"
    pre_flip = pre_flip_detector(closes, highs, lows)
    if pre_flip[0] == "LONG": score += 0.3
    if pre_flip[0] == "SHORT": score -= 0.3
    conf = confluence_engine(macro, smart, fear, live_news, liq_map, hunt_side, sweep_type, trend_dir, r, closes, pre_flip)
    if conf['destination'] != "NEUTRAL" and hunt_side and conf['destination'] != hunt_side and conf['agree'] >= 3 and not conf.get("news_override"):
        liq_signal += f" + ⚠️ SWEEP {hunt_side} BUT WORLDWIDE SAY {conf['destination']} ({conf['agree']}/{conf['decided']})"
        hunt_side_effective = conf['destination']
    else:
        hunt_side_effective = hunt_side
    score = max(min(score, 6.0), -6.0)
    effective_session_mult = 1.0 if (is_hunt or news_boost) else session_mult
    score = score * effective_session_mult
    score = max(min(score, 6.0), -6.0)
    if conf['confluence_pass']:
        threshold = 0.50; win_prob_needed = 0.55
    else:
        threshold = 1.5; win_prob_needed = 0.60
    destination_block = False; destination_reason = ""
    if not conf['confluence_pass'] and conf['destination'] != "NEUTRAL":
        destination_block = True; destination_reason = f"V5.13.3 BLOCK: Only {conf['agree']}/{conf['decided']} for {conf['destination']} Certainty {conf['certainty']:.0f}% - Need 95% + 6 agree (or News Override 5)"
    if conf['destination'] == "NEUTRAL":
        destination_block = True; destination_reason = f"CONFLUENCE NEUTRAL: Long {conf['long_votes']} Short {conf['short_votes']} Decided {conf['decided']}"
    win_prob = 0.50 + (abs(score)/6)*0.30 + (vol_conf*0.05)
    if is_hunt or news_boost: win_prob = min(win_prob + 0.10, 0.85)
    if conf['confluence_pass']: win_prob = min(win_prob + 0.05, 0.85)
    win_prob = min(win_prob, 0.85)
    tp_profit = tp_dist*qty - total_fees; sl_loss = sl_dist*qty + total_fees
    ev = (win_prob * tp_profit) - ((1-win_prob) * sl_loss); rr = tp_dist / max(sl_dist,1)
    flip_signal = None
    if conf['certainty'] >= MIN_CERTAINTY and conf['confluence_pass']:
        flip_signal = conf['destination']
    return {
        "regime":regime,"vol_mult":vol_mult,"trend_dir":trend_dir,"trend_strength":trend_strength,
        "vol_ratio":vol_ratio,"win_rate":win_rate,"ai_strictness":1.0,"mindset":mindset,
        "risk_pct":0.01,"risk_usd":paper_balance*0.01,"lev":lev,"qty":qty,"qty_raw":qty,"pos_usd":pos_usd,"margin_needed":margin_needed,"max_qty_real":qty,"bybit_ok":bybit_ok,
        "total_fees":total_fees,"entry_fee":entry_fee,"exit_fee":exit_fee,"fund_fee":fund_fee,"real_funding":real_funding,"be_profit":be_profit,"be_dist":be_dist,"early_lock_dist":early_lock_dist,"tp_dist":tp_dist,"sl_dist":sl_dist,
        "tp_mult":1.5,"sl_mult":0.9,"score":score,"threshold":threshold,"win_prob_needed":win_prob_needed,
        "win_prob":win_prob,"ev":ev,"rr":rr,"tp_profit":tp_profit,"sl_loss":sl_loss,"r":r,
        "ema9":ema9,"ema21":ema21,"ema50":ema50,"smc_signal":liq_signal,"smc_score":liq_score,
        "tp_covers_be":tp_covers_be,"tp_covers_sl":tp_covers_sl,"tp_dist_raw":tp_dist,
        "is_hunt":is_hunt,"hunt_side":hunt_side,"hunt_side_effective":hunt_side_effective,"liq_signal":liq_signal,"news_boost":news_boost,
        "void":void,"sweep_type":sweep_type,"destination_block":destination_block,"destination_reason":destination_reason,
        "confluence":conf,"flip_signal":flip_signal,"pre_flip":pre_flip
    }

def main_loop():
    global paper_balance, paper_pnl, wins, losses, be_hits, open_pos, waiting, history, consecutive_losses, consecutive_wins, last_trade_time, last_loss_time
    log(f"V5.13.3 STARTED - BTCUSDT 0.001 50x Isolated - Cert 95% Agree 6 TP 3x Fees Cooldown 5min No Pause PreFlip Fixed News Override SL->Entry")
    while True:
        try:
            closes, highs, lows, vols = get_bybit_klines()
            if closes is None: log("Error retry 2s"); time.sleep(2); continue
            btc=closes[-1]; atr=atr_calc(highs,lows,closes)
            if atr<20: atr=20
            macro = get_macro_all(); smart = get_bybit_smart_money(); fear, fear_label = get_fear_greed()
            session, session_mult = get_session(); live_news = get_live_news(); liq_map = get_liquidation_map()
            news_block, news_msg, news_mode = get_news_risk(live_news)
            B=human_brain(btc, closes, highs, lows, vols, macro, atr, smart, fear, fear_label, session, session_mult, live_news, liq_map, news_mode)
            conf = B['confluence']
            log(f"BRAIN: {B['regime']} ATR ${atr:.0f} RSI {B['r']:.1f} | {B['mindset']} | Lev {B['lev']}x FIXED | PreFlip {B['pre_flip']} FlipSignal {B['flip_signal']} NewsOverride {conf.get('news_override')}")
            log(f"🌍 FED: {live_news.get('fed')} | News {live_news.get('direction')} | {live_news.get('headline','No big news')[:110]}")
            log(f"🎯 SWEEP: {B['liq_signal']} | Type={B['sweep_type']} Sweep={B['hunt_side']} Effective={B['hunt_side_effective']}")
            log(f"🗳️ CONFLUENCE V5.13.3: {conf['votes']} | Long {conf['long_votes']} Short {conf['short_votes']} Decided {conf['decided']} | DEST {conf['destination']} Certainty {conf['certainty']:.0f}% Agree {conf['agree']}/{conf['decided']} Pass {conf['confluence_pass']} Override {conf.get('news_override')} | Thr {B['threshold']:.2f}")
            log(f"QTY: Bal ${paper_balance:.2f} Qty {B['qty']:.3f} FIXED Pos ${B['pos_usd']:.0f} Margin ${B['margin_needed']:.2f} Lev {B['lev']}x | DXY {macro['DXY']:+.2f}% NQ {macro['NQ_FUT']:+.2f}% SPX {macro['SPX_FUT']:+.2f}%")
            log(f"FEES: Total ${B['total_fees']:.4f} | BE ${B['be_dist']:.0f} Profit ${B['be_profit']:.2f} | TP ${B['tp_dist']:.0f} SL ${B['sl_dist']:.0f} | TP Profit ${B['tp_profit']:.4f} >= 3x Fees ${B['total_fees']*3:.4f} ? {B['tp_profit'] >= B['total_fees']*3} | Score {B['score']:.2f} / Thr {B['threshold']:.2f} WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} RR {B['rr']:.2f} | Bal ${paper_balance:.2f} PnL ${paper_pnl:.2f} W {wins} L {losses} BE {be_hits}")
            if not open_pos and not waiting and last_trade_time and (time.time() - last_trade_time) < COOLDOWN_MIN*60:
                log(f"⏳ COOLDOWN {COOLDOWN_MIN}min - Waiting, no pause logic"); time.sleep(5); continue
            if B['destination_block'] and not open_pos and not waiting:
                log(f"⛔ BLOCK: {B['destination_reason']}"); time.sleep(5); continue
            if open_pos:
                side=open_pos['side']; entry=open_pos['entry']; tp=open_pos['tp']; sl=open_pos['sl']; be_price=open_pos['be_price']
                unreal = (btc-entry)*open_pos['qty']-open_pos['total_fees'] if side=='LONG' else (entry-btc)*open_pos['qty']-open_pos['total_fees']
                profit_dist = btc-entry if side=='LONG' else entry-btc
                profit_flip = False; profit_flip_reason = ""
                if unreal > 0.05 and profit_dist > 50:
                    if conf['destination'] != side and conf['destination'] != "NEUTRAL" and conf['certainty'] >= MIN_CERTAINTY:
                        if (side=="LONG" and B['score'] < -1.0) or (side=="SHORT" and B['score'] > 1.0):
                            profit_flip = True; profit_flip_reason = f"💰 PROFIT FLIP: Was {side} +${unreal:.2f}, Market flipping to {conf['destination']} {conf['certainty']:.0f}% Score {B['score']:.2f} PreFlip {B['pre_flip']} - Take profit, flip now!"
                    # FIX: Profit flip via PreFlip uses raw preflip, NO history touch
                    if not profit_flip and B['pre_flip'][0] != "NEUTRAL" and B['pre_flip'][0] != side and B['pre_flip'][1] >= 40:
                        if (side=="LONG" and B['score'] < 0) or (side=="SHORT" and B['score'] > 0):
                            profit_flip = True; profit_flip_reason = f"💰 PROFIT FLIP (PRE-FLIP): Was {side} +${unreal:.2f}, 1-min flipped to {B['pre_flip'][0]} - Take profit now!"
                rescue_flip = False; rescue_reason = ""
                if not profit_flip and conf['confluence_pass'] and conf['certainty'] >= MIN_CERTAINTY and conf['destination'] != side and conf['destination'] != "NEUTRAL":
                    if (side == "LONG" and B['score'] < -2.5) or (side == "SHORT" and B['score'] > 2.5):
                        rescue_flip = True; rescue_reason = f"🛟 RESCUE FLIP: Was {side} PnL ${unreal:.2f}, World now {conf['destination']} {conf['certainty']:.0f}% Score {B['score']:.2f} - Exit early"
                if profit_flip or rescue_flip:
                    pnl = unreal
                    paper_balance+=pnl; paper_pnl+=pnl; history.append(pnl); last_trade_time=time.time()
                    if pnl>0: wins+=1; consecutive_wins+=1; consecutive_losses=0
                    else: losses+=1; consecutive_losses+=1; consecutive_wins=0; last_loss_time=time.time()
                    reason = profit_flip_reason if profit_flip else rescue_reason
                    log(f"🔄 {reason} | PnL ${pnl:.4f} | Bal ${paper_balance:.2f} | W {wins} L {losses} BE {be_hits} | Will re-enter opposite if still valid")
                    open_pos=None; time.sleep(2); continue
                # SL -> ENTRY: Early Lock + BE + Trail - CONFIRMED STILL DEY
                if side == "LONG":
                    if profit_dist > B['early_lock_dist'] and not open_pos.get('early_done'):
                        open_pos['sl']=entry; open_pos['early_done']=True; log(f"🛡️ EARLY LOCK! SL -> Entry ${entry:.0f} Profit +${profit_dist:.0f}")
                    elif profit_dist > B['be_dist'] * 0.8 and not open_pos.get('be_done'):
                        nsl = entry + (profit_dist * 0.5)
                        if nsl > open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL UP EARLY ${nsl:.0f}")
                else:
                    if profit_dist > B['early_lock_dist'] and not open_pos.get('early_done'):
                        open_pos['sl']=entry; open_pos['early_done']=True; log(f"🛡️ EARLY LOCK! SL -> Entry ${entry:.0f} Profit +${profit_dist:.0f}")
                    elif profit_dist > B['be_dist'] * 0.8 and not open_pos.get('be_done'):
                        nsl = entry - (profit_dist * 0.5)
                        if nsl < open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL DOWN EARLY ${nsl:.0f}")
                if not open_pos.get('be_done'):
                    if (side=='LONG' and btc>=be_price) or (side=='SHORT' and btc<=be_price):
                        open_pos['sl']=be_price; open_pos['be_done']=True; be_hits+=1; log(f"🟢 BE HIT! SL -> BE ${be_price:.0f} = Fees + ${open_pos['be_profit']:.2f}")
                if open_pos.get('be_done'):
                    if side=='LONG':
                        nsl=btc-atr*0.80
                        if nsl>open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL UP ${nsl:.0f}")
                    else:
                        nsl=btc+atr*0.80
                        if nsl<open_pos['sl']: open_pos['sl']=nsl; log(f"🔄 TRAIL DOWN ${nsl:.0f}")
                pnl=0; closed=False; reason=""; total_fees=open_pos['total_fees']; qty=open_pos['qty']; be_profit=open_pos['be_profit']
                if side=='LONG':
                    if btc>=tp: pnl=(tp-entry)*qty-total_fees; closed=True; reason="TP HIT 🎯 LONG"
                    elif btc<=open_pos['sl']:
                        if open_pos.get('be_done'): pnl=be_profit; closed=True; reason=f"BE SL 🟢 +${be_profit:.2f}"
                        elif open_pos.get('early_done'): pnl=-total_fees*0.5; closed=True; reason=f"EARLY SL 🛡️"
                        else: pnl=(open_pos['sl']-entry)*qty-total_fees; closed=True; reason="SL HIT LONG"
                else:
                    if btc<=tp: pnl=(entry-tp)*qty-total_fees; closed=True; reason="TP HIT 🎯 SHORT"
                    elif btc>=open_pos['sl']:
                        if open_pos.get('be_done'): pnl=be_profit; closed=True; reason=f"BE SL 🟢 +${be_profit:.2f}"
                        elif open_pos.get('early_done'): pnl=-total_fees*0.5; closed=True; reason=f"EARLY SL 🛡️"
                        else: pnl=(entry-open_pos['sl'])*qty-total_fees; closed=True; reason="SL HIT SHORT"
                time_limit = 60*60 if B['regime']=="CALM" else 90*60 if B['regime'] in ["WILD","EXTREME"] else 75*60
                if not closed and (time.time()-open_pos['start'])>time_limit:
                    pnl=(btc-entry)*qty-total_fees if side=='LONG' else (entry-btc)*qty-total_fees; closed=True; reason=f"TIME EXIT {int(time_limit/60)}min - No hold forever"
                if closed:
                    paper_balance+=pnl; paper_pnl+=pnl; history.append(pnl); last_trade_time = time.time()
                    if pnl>0: wins+=1; consecutive_wins+=1; consecutive_losses=0
                    else: losses+=1; consecutive_losses+=1; consecutive_wins=0; last_loss_time=time.time()
                    log(f"✅ CLOSED {side} {reason} | PnL ${pnl:.4f} | Bal ${paper_balance:.2f} | W {wins} L {losses} BE {be_hits}")
                    open_pos=None; time.sleep(2); continue
                else:
                    log(f"⏳ OPEN {side} Entry ${entry:.0f} Now ${btc:.0f} PnL ${unreal:+.4f} TP ${tp:.0f} SL ${open_pos['sl']:.0f} BE ${be_price:.0f} FlipCheck {conf['destination']} {conf['certainty']:.0f}% PreFlip {B['pre_flip']}"); time.sleep(2); continue
            if waiting:
                trig=waiting['trig']; tp=waiting['tp']; sl=waiting['sl']; side=waiting['side']
                hit=(btc>=trig) if side=='LONG' else (btc<=trig)
                expired=(time.time()-waiting['start'])>2*60
                opposite=(btc<=trig-atr*1.5) if side=='LONG' else (btc>=trig+atr*1.5)
                if conf['confluence_pass'] and conf['destination'] != side and conf['certainty'] >= MIN_CERTAINTY:
                    log(f"❌ WAITING CANCELLED {side} - Confluence flipped to {conf['destination']} {conf['certainty']:.0f}%"); waiting=None; time.sleep(2); continue
                if hit:
                    be_price=trig+B['be_dist'] if side=='LONG' else trig-B['be_dist']
                    open_pos={'side':side,'entry':trig,'tp':tp,'sl':sl,'be_price':be_price,'be_done':False,'early_done':False,'early_lock_dist':B['early_lock_dist'],'start':time.time(),'total_fees':B['total_fees'],'qty':B['qty'],'be_profit':B['be_profit']}
                    log(f"🔥 TRIGGER HIT {side} Entry ${trig:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f} Qty {B['qty']:.3f} - FAST"); waiting=None
                elif expired or opposite: log(f"❌ WAITING CANCELLED {side} - 2min"); waiting=None
                else: log(f"👀 HIDDEN WAITING {side} Trig ${trig:.0f} Now ${btc:.0f} TP ${tp:.0f} SL ${sl:.0f}")
                time.sleep(2); continue
            if not B['tp_covers_be'] or not B['tp_covers_sl']: log(f"⛔ SKIP TP/BE/SL"); time.sleep(5); continue
            if abs(B['score']) < B['threshold']: log(f"=> NO CLEAR Score {B['score']:.2f} < Thr {B['threshold']:.2f}"); time.sleep(5); continue
            if B['win_prob'] < B['win_prob_needed'] or B['ev'] <= 0 or B['rr'] < 1.4: log(f"⛔ SKIP WinProb/EV/RR Need {B['win_prob_needed']*100:.0f}%"); time.sleep(5); continue
            if B['tp_profit'] < B['total_fees'] * TP_FEE_MULTIPLIER: log(f"⛔ SKIP TP Profit ${B['tp_profit']:.4f} < 3x Fees ${B['total_fees']*3:.4f}"); time.sleep(5); continue
            if macro['OIL'] > 6: log(f"⛔ SKIP Oil"); time.sleep(5); continue
            if B['qty'] < BYBIT_MIN_QTY: log(f"⛔ SKIP Qty"); time.sleep(5); continue
            # PREFILP GATE - ONLY ONCE HERE
            if conf['destination'] != "NEUTRAL":
                pf_ok, pf_msg = check_preflip_stable(B['pre_flip'], conf['destination'])
                if not pf_ok:
                    log(f"⛔ PREFILP GATE: {pf_msg}"); time.sleep(5); continue
                log(f"✅ PREFILP GATE: {pf_msg}")
            if conf['destination'] != "NEUTRAL" and conf['confluence_pass']:
                side = conf['destination']
            elif B['is_hunt'] and B['hunt_side_effective']:
                side = B['hunt_side_effective']
            elif B['news_boost'] and news_mode in ["LONG", "SHORT"]: side = news_mode
            elif live_news.get("fed") == "HAWKISH" and B['score'] < 0: side = "SHORT"
            elif live_news.get("fed") == "DOVISH" and B['score'] > 0: side = "LONG"
            else: side='LONG' if B['score']>=0 else 'SHORT'
            trig_offset = atr * 0.15
            if side=='LONG': trig=btc+trig_offset; tp=trig+B['tp_dist']; sl=trig-B['sl_dist']; be_price=trig+B['be_dist']
            else: trig=btc-trig_offset; tp=trig-B['tp_dist']; sl=trig+B['sl_dist']; be_price=trig-B['be_dist']
            waiting={'side':side,'trig':trig,'tp':tp,'sl':sl,'be_price':be_price,'start':time.time()}
            log(f"✅ HIDDEN {side} [2MIN] Trig ${trig:.0f} TP ${tp:.0f} SL ${sl:.0f} BE ${be_price:.0f} Qty {B['qty']:.3f} Lev {B['lev']}x FIXED 50x | Confluence {conf['agree']}/{conf['decided']} {conf['certainty']:.0f}% NewsOverride {conf.get('news_override')} Thr {B['threshold']:.2f} | WinProb {B['win_prob']*100:.0f}% EV ${B['ev']:.4f} | {B['liq_signal']}")
            time.sleep(5)
        except Exception as e:
            log(f"❌ Error: {e}"); traceback.print_exc(); time.sleep(2)

if __name__=="__main__":
    threading.Thread(target=self_ping_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=main_loop, daemon=True).start()
    if app:
        port = int(os.environ.get("PORT", 10000))
        log(f"Flask starting on {port}")
        app.run(host="0.0.0.0", port=port)
    else: main_loop()
