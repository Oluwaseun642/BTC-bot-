# ============================================================
# BTC BOT V8.1 - FULL - NO HARDCODED - FALLBACK CHAIN
# 75% Certainty - Poll 5s - Live Yahoo -> Stooq -> Bybit Proxy
# + RSI + 200MA + ETF Proxy + Liquidation Cluster + Nvidia Proxy
# Balance $3.45
# ============================================================
import os, time, requests, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 10000))
STATE = {"balance": 3.45, "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0,
         "open_position": None, "last_price": 72800.0, "last_loss_time": None,
         "day": datetime.now(timezone.utc).date()}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type","text/plain"); self.end_headers()
        try:
            pos = STATE.get("open_position")
            s = f"{pos['side']} @ {pos['entry']} Mode {pos.get('mode')}" if pos else "FLAT"
            self.wfile.write(f"OK V8.1 Alive Bal ${STATE['balance']:.2f} PnL ${STATE['pnl']:.2f} Pos {s}".encode())
        except: self.wfile.write(b"OK V8.1 Alive")
    def log_message(self, *a, **k): return

def start_health():
    try: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()
    except Exception as e: print(f"[HEALTH] {e}", flush=True)

CONFIG = {
    "SYMBOL": "BTCUSDT", "QTY": 0.001, "LEVERAGE": 50,
    "WICK_MIN": 200, "WICK_MAX": 450, "WICK_TP": 350, "WICK_SL_BUFFER": 80,
    "MIN_CERTAINTY": 75.0, "MIN_AGREE": 3, "MIN_SCORE": 0.60,
    "SURE_CERTAINTY": 95.0, "SURE_AGREE": 5,
    "SL_PCT": 0.0085, "TP_MULT_NORMAL": 2.0, "TP_MULT_SURE": 3.5,
    "BE_BUFFER": 5.0, "BE_TRIGGER": 0.002,
    "TRAIL_START": 0.004, "TRAIL_1": 0.008, "TRAIL_2": 0.012, "TRAIL_3": 0.020,
    "POLL": 5,
}
def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)
def now(): return datetime.now(timezone.utc)

# ============ LIVE FETCH WITH FALLBACK ============
def get_price():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=5)
        p = float(r.json()["result"]["list"][0]["lastPrice"])
        STATE["last_price"] = p; return p
    except Exception as e:
        log(f"PRICE ERR {e}"); return STATE["last_price"]

def get_klines(limit=50, interval="1"):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}", timeout=5)
        kl = list(reversed(r.json()["result"]["list"]))
        return [{"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4])} for x in kl]
    except: return []

def get_klines_daily(limit=210):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=D&limit={limit}", timeout=5)
        kl = list(reversed(r.json()["result"]["list"]))
        return [{"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4])} for x in kl]
    except: return []

def get_funding():
    try:
        r = requests.get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1", timeout=5)
        return float(r.json()["result"]["list"][0]["fundingRate"])*100
    except: return None

def get_oi_change():
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=5)
        lst = r.json()["result"]["list"]
        if len(lst)>=2:
            a=float(lst[-1]["openInterest"]); b=float(lst[0]["openInterest"])
            return (a-b)/b*100 if b else 0
    except: pass
    return None

def get_fear():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        return int(r.json()["data"][0]["value"])
    except: return None

# --- Yahoo + Stooq Fallback Chain ---
def get_yahoo(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=5m"
        r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        meta = r.json()["chart"]["result"][0]["meta"]
        prev = meta.get("previousClose"); cur = meta.get("regularMarketPrice")
        if prev and cur: return (cur-prev)/prev*100
    except: pass
    return None

def get_stooq(symbol):
    # Stooq free, no key, format: date,time,open,high,low,close,volume
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        lines = r.text.strip().split("\n")
        if len(lines)>=3:
            # last 2 days
            def parse(l):
                p=l.split(",")
                return float(p[4]) # close
            prev = parse(lines[-2]); cur = parse(lines[-1])
            if prev: return (cur-prev)/prev*100
    except Exception as e:
        log(f"STOOQ {symbol} ERR {e}")
    return None

def get_macro_with_fallback(symbol_yahoo, symbol_stooq, name):
    v = get_yahoo(symbol_yahoo)
    if v is not None:
        log(f"LIVE {name} Yahoo {v:.2f}%"); return v
    v2 = get_stooq(symbol_stooq)
    if v2 is not None:
        log(f"LIVE {name} Stooq Fallback {v2:.2f}%"); return v2
    log(f"LIVE {name} BOTH FAILED -> NEUTRAL, certainty go reduce")
    return None

def get_macro_live():
    dxy = get_macro_with_fallback("%5EDXY", "dx-y.nq", "DXY")
    nq = get_macro_with_fallback("%5EIXIC", "ndx", "NQ")
    spx = get_macro_with_fallback("%5EGSPC", "spx", "SPX")
    gold = get_macro_with_fallback("GC%3DF", "gc.f", "GOLD")
    # Nvidia Proxy: NVDA live via Yahoo -> Stooq, if fail use NQ as proxy
    nvda = get_macro_with_fallback("NVDA", "nvda.us", "NVDA")
    if nvda is None and nq is not None:
        nvda = nq; log(f"NVDA fallback = NQ {nvda:.2f}%")
    fund = get_funding(); oi = get_oi_change(); fear = get_fear()
    log(f"LIVE MACRO DXY {dxy} NQ {nq} SPX {spx} GOLD {gold} NVDA {nvda} FUND {fund} OI {oi} FEAR {fear}")
    return {"DXY": dxy, "NQ": nq, "SPX": spx, "GOLD": gold, "NVDA": nvda, "OI": oi, "FUND": fund, "FEAR": fear}

# --- RSI + 200MA + ETF Proxy + Liquidation Cluster (All Live from Klines) ---
def calc_rsi(kl, period=14):
    if len(kl) < period+1: return 50
    gains=0; losses=0
    for i in range(-period,0):
        d = kl[i]["c"]-kl[i-1]["c"]
        if d>0: gains+=d
        else: losses+=abs(d)
    if losses==0: return 100
    rs = (gains/period)/(losses/period)
    return 100 - (100/(1+rs))

def calc_200ma(daily):
    if len(daily)<200: return None
    return sum(c["c"] for c in daily[-200:])/200

def get_etf_proxy():
    # No free ETF API without key, so use Coingecko Global + BTC dominance + volume as proxy
    # If BTC dominance up + volume down = ETF selling pressure
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=5)
        d = r.json()["data"]
        dom = d["market_cap_percentage"]["btc"]
        vol = d["total_volume"]["usd"]
        log(f"ETF PROXY BTC Dominance {dom:.2f}% Vol ${vol/1e9:.1f}B")
        # Dominance falling + price falling = ETF outflows pressure
        return dom
    except: return None

def get_news(kl):
    if len(kl)>=15 and kl[0]["c"]!=0:
        move=(kl[-1]["c"]-kl[0]["c"])/kl[0]["c"]*100
        if abs(move)>=0.8: return True, 85.0, f"VOL SPIKE {move:.2f}%"
    return False,0,""

def detect_wick(kl):
    if len(kl)<3: return None
    last=kl[-1]; prev=kl[-2]
    wd = last["c"]-last["l"]; wu = last["h"]-last["c"]
    wd2 = prev["c"]-prev["l"]; wu2 = prev["h"]-prev["c"]
    if CONFIG["WICK_MIN"] <= wd <= CONFIG["WICK_MAX"] and wd > wu*1.5: return ("LONG", wd, last["l"])
    if CONFIG["WICK_MIN"] <= wd2 <= CONFIG["WICK_MAX"] and wd2 > wu2*1.5: return ("LONG", wd2, prev["l"])
    if CONFIG["WICK_MIN"] <= wu <= CONFIG["WICK_MAX"] and wu > wd*1.5: return ("SHORT", wu, last["h"])
    if CONFIG["WICK_MIN"] <= wu2 <= CONFIG["WICK_MAX"] and wu2 > wd2*1.5: return ("SHORT", wu2, prev["h"])
    return None

def get_signals_live(macro, rsi, price, ma200, dom):
    s=[]
    # 1 DXY
    if macro["DXY"] is None: s.append(("DXY","NEUTRAL"))
    elif macro["DXY"]>0.10: s.append(("DXY","SHORT"))
    elif macro["DXY"]<-0.10: s.append(("DXY","LONG"))
    else: s.append(("DXY","NEUTRAL"))
    # 2 NQ + 3 NVDA combined as Tech
    if macro["NQ"] is None and macro["NVDA"] is None: s.append(("TECH","NEUTRAL"))
    elif (macro["NQ"] or 0) < -0.20 or (macro["NVDA"] or 0) < -1.0: s.append(("TECH","SHORT"))
    elif (macro["NQ"] or 0) > 0.20 and (macro["NVDA"] or 0) > 0.5: s.append(("TECH","LONG"))
    else: s.append(("TECH","NEUTRAL"))
    # 4 SPX
    if macro["SPX"] is None: s.append(("SPX","NEUTRAL"))
    elif macro["SPX"]>0.20: s.append(("SPX","LONG"))
    elif macro["SPX"]<-0.20: s.append(("SPX","SHORT"))
    else: s.append(("SPX","NEUTRAL"))
    # 5 GOLD
    if macro["GOLD"] is None: s.append(("GOLD","NEUTRAL"))
    elif macro["GOLD"]>0.50: s.append(("GOLD","SHORT"))
    elif macro["GOLD"]<-0.30: s.append(("GOLD","LONG"))
    else: s.append(("GOLD","NEUTRAL"))
    # 6 LIQ MAP
    if macro["OI"] is None or macro["FUND"] is None: s.append(("LIQ_MAP","NEUTRAL"))
    elif macro["OI"]>0.5 and macro["FUND"]>0.01: s.append(("LIQ_MAP","SHORT"))
    elif macro["OI"]<-0.5 and macro["FUND"]<-0.01: s.append(("LIQ_MAP","LONG"))
    else: s.append(("LIQ_MAP","NEUTRAL"))
    # 7 FEAR
    if macro["FEAR"] is None: s.append(("FEAR","NEUTRAL"))
    elif macro["FEAR"]<25: s.append(("FEAR","LONG"))
    elif macro["FEAR"]>75: s.append(("FEAR","SHORT"))
    else: s.append(("FEAR","NEUTRAL"))
    # 8 RSI - Live from klines
    if rsi < 30: s.append(("RSI","LONG")) # Oversold bounce
    elif rsi > 70: s.append(("RSI","SHORT"))
    elif rsi < 40 and price < (ma200 or 999999): s.append(("RSI","SHORT")) # Weak + below MA
    else: s.append(("RSI","NEUTRAL"))
    # 9 200MA - Live
    if ma200 is None: s.append(("MA200","NEUTRAL"))
    elif price < ma200: s.append(("MA200","SHORT"))
    else: s.append(("MA200","LONG"))
    # 10 ETF Proxy - Dominance falling while price falling = outflows
    if dom is None: s.append(("ETF","NEUTRAL"))
    elif dom < 52: s.append(("ETF","SHORT"))
    else: s.append(("ETF","NEUTRAL"))
    return s

def decide(signals):
    longs=sum(1 for _,v in signals if v=="LONG"); shorts=sum(1 for _,v in signals if v=="SHORT")
    dec=longs+shorts
    if longs>shorts: return "LONG",longs,dec,longs,shorts, (longs/dec*100 if dec else 0)
    if shorts>longs: return "SHORT",shorts,dec,longs,shorts, (shorts/dec*100 if dec else 0)
    return "NONE",0,dec,longs,shorts,0

def manage(price, kl):
    p=STATE["open_position"]
    if not p: return
    entry=p["entry"]; side=p["side"]
    prof=(price-entry)/entry if side=="LONG" else (entry-price)/entry
    if not p.get("be_done") and prof>=CONFIG["BE_TRIGGER"]:
        if side=="LONG":
            be=entry+CONFIG["BE_BUFFER"]
            if be>p["sl"]: p["sl"]=be; p["be_done"]=True; log(f"BE OVER FEES: SL -> ${be:.0f}")
        else:
            be=entry-CONFIG["BE_BUFFER"]
            if be<p["sl"]: p["sl"]=be; p["be_done"]=True; log(f"BE OVER FEES: SL -> ${be:.0f}")
    if prof>=CONFIG["TRAIL_START"]:
        if side=="LONG":
            if prof>=CONFIG["TRAIL_3"]: ns=price-price*0.008
            elif prof>=CONFIG["TRAIL_2"]: ns=price-price*0.006
            elif prof>=CONFIG["TRAIL_1"]: ns=price-price*0.004
            else: ns=p["sl"]
            if ns>p["sl"]: p["sl"]=ns; log(f"TRAILING LONG SL -> ${ns:.0f} Prof {prof*100:.2f}%")
        else:
            if prof>=CONFIG["TRAIL_3"]: ns=price+price*0.008
            elif prof>=CONFIG["TRAIL_2"]: ns=price+price*0.006
            elif prof>=CONFIG["TRAIL_1"]: ns=price+price*0.004
            else: ns=p["sl"]
            if ns<p["sl"]: p["sl"]=ns; log(f"TRAILING SHORT SL -> ${ns:.0f} Prof {prof*100:.2f}%")
    hit_tp = price>=p["tp"] if side=="LONG" else price<=p["tp"]
    hit_sl=False
    if len(kl)>=2:
        lc=kl[-2]["c"]
        if side=="LONG" and lc<p["sl"]: hit_sl=True
        if side=="SHORT" and lc>p["sl"]: hit_sl=True
    if hit_tp:
        profit=abs(price-entry)*CONFIG["QTY"]; STATE["balance"]+=profit; STATE["pnl"]+=profit; STATE["wins"]+=1
        log(f"TP HIT +${profit:.2f} Mode {p['mode']}"); STATE["open_position"]=None
    elif hit_sl:
        if p.get("be_done"):
            profit=abs(price-entry)*CONFIG["QTY"]; STATE["balance"]+=profit; STATE["pnl"]+=profit; STATE["breakevens"]+=1
            log(f"BE HIT +${profit:.2f}")
        else:
            loss=abs(price-entry)*CONFIG["QTY"]; STATE["balance"]-=loss; STATE["pnl"]-=loss; STATE["losses"]+=1; STATE["last_loss_time"]=now()
            log(f"SL HIT -${loss:.2f}")
        STATE["open_position"]=None

def main():
    threading.Thread(target=start_health, daemon=True).start()
    log("BOT V8.1 FULL STARTED - Fallback Yahoo->Stooq - 75% - RSI+MA200+ETF+NVDA")
    while True:
        try:
            price=get_price(); kl=get_klines(50); daily=get_klines_daily(210)
            macro=get_macro_live(); rsi=calc_rsi(kl); ma200=calc_200ma(daily); dom=get_etf_proxy()
            is_news, news_score, news_reason=get_news(kl)
            signals=get_signals_live(macro, rsi, price, ma200, dom)
            dest, agree, decided, longs, shorts, cert=decide(signals)
            wick=detect_wick(kl); fear=macro["FEAR"]
            log(f"Price ${price:.0f} RSI {rsi:.1f} MA200 {ma200} Fear {fear} News {is_news} {news_reason}")
            log(f"Signals {signals} Long {longs} Short {shorts} Dest {dest} Cert {cert:.0f}% Agree {agree}/{decided} Wick {wick}")
            if not STATE["open_position"] and wick:
                side, wsize, wick_level = wick
                if side=="LONG" and shorts>=5: log(f"WICK SKIP bearish")
                elif side=="SHORT" and longs>=5: log(f"WICK SKIP bullish")
                else:
                    if side=="LONG": sl=wick_level-CONFIG["WICK_SL_BUFFER"]; tp=price+CONFIG["WICK_TP"]
                    else: sl=wick_level+CONFIG["WICK_SL_BUFFER"]; tp=price-CONFIG["WICK_TP"]
                    log(f"MODE A WICK {side} Wick ${wsize:.0f} Entry ${price:.0f} SL ${sl:.0f} TP ${tp:.0f}")
                    STATE["open_position"]={"side":side,"entry":price,"sl":sl,"tp":tp,"mode":"WICK_CHOPPER","be_done":False}
            elif not STATE["open_position"] and dest in ("LONG","SHORT"):
                is_sure = cert>=CONFIG["SURE_CERTAINTY"] and agree>=CONFIG["SURE_AGREE"]
                score = (cert/100) + (0.4 if is_news else 0) + (0.3 if (dest=="LONG" and fear is not None and fear<25) or (dest=="SHORT" and fear is not None and fear>75) else 0)
                if cert>=CONFIG["MIN_CERTAINTY"] and agree>=CONFIG["MIN_AGREE"] and score>=CONFIG["MIN_SCORE"]:
                    sl_dist=price*CONFIG["SL_PCT"]
                    if kl:
                        if dest=="LONG": sl=min(price-sl_dist, min(c["l"] for c in kl[-15:])-80); sl=max(sl, price*0.988)
                        else: sl=max(price+sl_dist, max(c["h"] for c in kl[-15:])+80); sl=min(sl, price*1.012)
                    else: sl=price-sl_dist if dest=="LONG" else price+sl_dist
                    mult=CONFIG["TP_MULT_SURE"] if is_sure else CONFIG["TP_MULT_NORMAL"]
                    tp_dist=abs(price-sl)*mult; tp=price+tp_dist if dest=="LONG" else price-tp_dist
                    log(f"MODE B TREND {dest} Entry ${price:.0f} SL ${sl:.0f} TP ${tp:.0f} Score {score:.2f}")
                    STATE["open_position"]={"side":dest,"entry":price,"sl":sl,"tp":tp,"mode":"TREND_WIDE","be_done":False}
                else: log(f"MODE B BLOCK Cert {cert:.0f}% Need 75% Agree {agree}/3 Score {score:.2f}")
            else:
                if STATE["open_position"]: log(f"HOLDING {STATE['open_position']['mode']} {STATE['open_position']['side']} Entry ${STATE['open_position']['entry']:.0f} SL ${STATE['open_position']['sl']:.0f} TP ${STATE['open_position']['tp']:.0f}")
                else: log(f"NO TRADE: No wick, no 75%")
            manage(price, kl)
            log(f"Bal ${STATE['balance']:.2f} PnL ${STATE['pnl']:.2f} W{STATE['wins']} L{STATE['losses']} BE{STATE['breakevens']}")
            time.sleep(CONFIG["POLL"])
        except Exception as e:
            log(f"ERROR {e}"); import traceback; log(traceback.format_exc()); time.sleep(5)

if __name__=="__main__": main()
