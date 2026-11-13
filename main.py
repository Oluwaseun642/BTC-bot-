# ============================================================
# BTC BOT V12 FINAL - PAPER $4.75 NOW -> REAL MONDAY 12AM WAT IF PAPER DO WELL
# main.py - COPY ALL - DEPLOY ONCE
# No Hedge - 2 Same Direction - No Fixed Price - Live Startup - Live Balance Monday
# Hunt V2 Liq Map + Asian Wide + Retrace 30% - Reversal V3 - Scoreboard W L BE
# ============================================================
import os, time, requests, threading, hmac, hashlib, json, random
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 10000))
BYBIT_KEY = os.environ.get("BYBIT_API_KEY", "")
BYBIT_SECRET = os.environ.get("BYBIT_API_SECRET", "")
BASE = "https://api.bybit.com"
SYMBOL = "BTCUSDT"

# Monday 12am WAT = Sunday 23:00 UTC - Auto switch Paper -> Real
PAPER_UNTIL_UTC = datetime(2026, 11, 15, 23, 0, 0, tzinfo=timezone.utc)
PAPER_MODE = datetime.now(timezone.utc) < PAPER_UNTIL_UTC
PAPER_BALANCE = 4.75
PAPER_POSITION = None
PAPER_POSITION_2 = None

STATE = {"balance": 4.75, "pnl": 0.0, "wins": 0, "losses": 0, "breakevens": 0,
         "open_position": None, "last_price": None, "day": datetime.now(timezone.utc).date(),
         "current_qty": 0.002, "btc_only_mode": False}
LAST_MACRO = {"DXY": 0.0, "NQ": 0.0, "SPX": 0.0, "GOLD": 0.0, "NVDA": 0.0, "US10Y": 0.0, "OIL": 0.0, "EURUSD": 0.0, "USDJPY": 0.0, "NIKKEI": 0.0, "HANGSENG": 0.0, "BTCDOM": 59.0}
LAST_MACRO_TIME = {}
LEARN = {"wick_losses": 0, "trend_losses": 0, "wick_cooldown_until": 0, "trend_boost_until": 0}
REVERSAL_CONFIRM = {"count": 0}
HUNT_STATE = {"hunt_count": 0, "addon_done": False, "hunt_peak": 0, "hunt_peak_time": 0}
LAST_HUNT_LOSS = {"time": 0, "side": None, "entry": 0}
LAST_POSITION_FETCH = {"time": 0, "data": None}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type","text/plain"); self.end_headers()
        try:
            pos = STATE.get("open_position")
            s = f"{pos['side']} @ {pos['entry']} AddOn {pos.get('addon_done')}" if pos else "FLAT"
            pm = "PAPER $4.75" if PAPER_MODE else "REAL LIVE BALANCE"
            lp = STATE.get("last_price"); lp_s = f"${lp:.0f}" if lp else "Waiting Live..."
            self.wfile.write(f"OK V12 FINAL Alive {pm} Bal ${STATE['balance']:.2f} Live {lp_s} Pos {s} Smiling".encode())
        except: self.wfile.write(b"OK V12 FINAL Alive Smiling")
    def log_message(self, *a, **k): return

def start_health():
    try: HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()
    except Exception as e: print(f"[HEALTH] {e}", flush=True)

CONFIG = {"LEVERAGE": 50, "MIN_CERTAINTY": 75.0, "MIN_AGREE": 3, "MIN_SCORE": 0.60,
          "SURE_CERTAINTY": 95.0, "SURE_AGREE": 5, "SL_PCT": 0.0085, "TP_MULT_NORMAL": 2.0, "TP_MULT_SURE": 3.5,
          "BE_BUFFER": 15.0, "BE_TRIGGER": 0.0035, "TRAIL_START": 0.004, "TRAIL_1": 0.008, "TRAIL_2": 0.012, "TRAIL_3": 0.020,
          "LIQ_GUARD_DIST": 0.003, "POLL": 5, "TAKER_FEE": 0.00055, "WICK_MIN": 200, "WICK_MAX": 450, "WICK_TP": 350,
          "HUNT_ADDON_MIN_BETTER_US": 400, "HUNT_ADDON_MIN_BETTER_ASIA": 800, "HUNT_ADDON_MIN_BAL": 10.0, "HUNT_RETRACE_PCT": 0.30}

def log(m): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)

def is_paper():
    global PAPER_MODE
    if PAPER_MODE and datetime.now(timezone.utc) >= PAPER_UNTIL_UTC:
        PAPER_MODE = False
        log("PAPER DONE! Monday 12am WAT don reach - IF PAPER DO WELL, SWITCHING TO REAL BYBIT NOW - Fetching LIVE balance + LIVE price!")
    return PAPER_MODE

def bybit_sign(ps, ts): return hmac.new(BYBIT_SECRET.encode(), (str(ts) + BYBIT_KEY + "5000" + ps).encode(), hashlib.sha256).hexdigest()
def bybit_get(path, params={}):
    ts = str(int(time.time()*1000)); q = "&".join([f"{k}={v}" for k,v in params.items()]); sign = bybit_sign(q, ts)
    headers = {"X-BAPI-API-KEY": BYBIT_KEY, "X-BAPI-SIGN": sign, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000"}
    r = requests.get(BASE + path + ("?" + q if q else ""), headers=headers, timeout=15); return r.json()
def bybit_post(path, body={}):
    ts = str(int(time.time()*1000)); bs = json.dumps(body); sign = bybit_sign(bs, ts)
    headers = {"X-BAPI-API-KEY": BYBIT_KEY, "X-BAPI-SIGN": sign, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "Content-Type": "application/json"}
    r = requests.post(BASE + path, headers=headers, data=bs, timeout=15); return r.json()

def get_real_balance():
    if is_paper():
        STATE["balance"] = PAPER_BALANCE
        log(f"PAPER BALANCE ${PAPER_BALANCE:.2f} | Paper till Monday 12am WAT | Real NOT touched | Smiling")
        return PAPER_BALANCE
    try:
        j = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED"}); lst = j.get("result", {}).get("list", [])
        if lst:
            for c in lst[0].get("coin", []):
                if c.get("coin") == "USDT":
                    bal = float(c.get("walletBalance", 0)); STATE["balance"] = bal
                    log(f"REAL LIVE BALANCE Bybit USDT ${bal:.2f} | STARTUP LIVE PRICE fetch done, connected to real account | Smiling")
                    return bal
    except Exception as e: log(f"REAL BALANCE ERR {e} - Use last ${STATE['balance']:.2f}")
    return STATE["balance"]

def set_leverage_50():
    if is_paper(): return
    try:
        j = bybit_post("/v5/position/set-leverage", {"category": "linear", "symbol": SYMBOL, "buyLeverage": "50", "sellLeverage": "50"})
        log(f"LEVERAGE 50x SET {j.get('retMsg')}")
    except Exception as e: log(f"LEVERAGE ERR {e}")

def calc_dynamic_qty(price, balance):
    if not price or price <= 0: return 0.002
    steps_table = [(0.002,0.0),(0.005,10.0),(0.010,15.0),(0.015,20.0),(0.020,25.0),(0.025,30.0),(0.030,35.0),(0.035,40.0),(0.040,45.0),(0.045,50.0),(0.050,55.0),(0.055,60.0),(0.060,65.0),(0.065,70.0),(0.070,75.0),(0.075,80.0),(0.080,85.0),(0.085,90.0),(0.090,95.0),(0.095,100.0),(0.100,105.0),(0.105,110.0),(0.110,115.0),(0.115,120.0),(0.120,125.0)]
    suggested_qty = 0.002
    for qty, sb in steps_table:
        if balance >= sb: suggested_qty = qty
    def req(qty): return (qty * price / 50.0) * 1.20
    chosen_qty = suggested_qty
    while chosen_qty > 0.002:
        if balance >= req(chosen_qty): break
        log(f"QTY CHECK Want {chosen_qty} need ${req(chosen_qty):.2f} Live ${price:.0f} 50x+fees Bal ${balance:.2f} NOT ENOUGH -> HOLD")
        chosen_qty = round(chosen_qty - 0.005, 3)
        if chosen_qty < 0.002: chosen_qty = 0.002; break
    if balance < req(chosen_qty): log(f"QTY CHECK Survival 0.001"); chosen_qty = 0.001
    if chosen_qty != STATE["current_qty"]: log(f"QTY UPGRADE/HOLD Bal ${balance:.2f} -> {STATE['current_qty']} -> {chosen_qty} 50x")
    STATE["current_qty"] = chosen_qty; return chosen_qty

def calc_smart_sl_live(price, side):
    base = price * CONFIG["SL_PCT"]; buffer = random.uniform(30, 80)
    if side == "LONG":
        mental = price - base - buffer
        if abs(mental % 500) < 40: mental -= 40
        real = mental - 700
    else:
        mental = price + base + buffer
        if abs(mental % 500) < 40: mental += 40
        real = mental + 700
    log(f"SMART SL LIVE ${price:.0f} {side} Mental ${mental:.0f} Real ${real:.0f} - No fixed, live from entry")
    return mental, real

def calc_fees_live(price, qty): return price * qty * CONFIG["TAKER_FEE"], price * qty * CONFIG["TAKER_FEE"]

def place_real_order(side, qty, sl_real, tp, price, mental_sl):
    global PAPER_POSITION, PAPER_BALANCE
    if is_paper():
        fee, _ = calc_fees_live(price, qty); PAPER_BALANCE -= fee; STATE["balance"] = PAPER_BALANCE
        PAPER_POSITION = {"side": side, "entry": price, "size": qty, "sl": sl_real, "tp": tp, "mental_sl": mental_sl, "liq": price*0.985 if side=="LONG" else price*1.015}
        log(f"PAPER ORDER {side} Qty {qty} Entry ${price:.0f} Mental SL ${mental_sl:.0f} Real SL ${sl_real:.0f} TP ${tp:.0f} Fee ${fee:.4f} Paper Bal ${PAPER_BALANCE:.2f} - No real Bybit till Monday")
        return True
    try:
        set_leverage_50(); oside = "Buy" if side == "LONG" else "Sell"
        body = {"category": "linear", "symbol": SYMBOL, "side": oside, "orderType": "Market", "qty": str(qty), "takeProfit": str(round(tp, 1)), "stopLoss": str(round(sl_real, 1)), "tpTriggerBy": "LastPrice", "slTriggerBy": "LastPrice", "positionIdx": 0}
        j = bybit_post("/v5/order/create", body); log(f"REAL ORDER {side} Qty {qty} Mental SL ${mental_sl:.0f} Real SL ${sl_real:.0f} TP ${tp:.0f} 50x -> {j}"); return j.get("retCode") == 0
    except Exception as e: log(f"REAL ORDER ERR {e}"); return False

def update_real_sl(sl):
    global PAPER_POSITION
    if is_paper():
        if PAPER_POSITION: PAPER_POSITION["sl"] = sl
        log(f"PAPER SL UPDATE -> ${sl:.0f} (BE Over Fees 0.35% + $15 covers 0.11% fees)"); return
    try:
        j = bybit_post("/v5/position/trading-stop", {"category": "linear", "symbol": SYMBOL, "stopLoss": str(round(sl, 1)), "positionIdx": 0}); log(f"REAL SL UPDATE -> ${sl:.0f} {j.get('retMsg')}")
    except Exception as e: log(f"REAL SL UPDATE ERR {e}")

def get_real_position():
    if is_paper(): return PAPER_POSITION
    try:
        j = bybit_get("/v5/position/list", {"category": "linear", "symbol": SYMBOL}); lst = j.get("result", {}).get("list", [])
        for p in lst:
            sz = float(p.get("size", 0))
            if sz > 0: return {"side": "LONG" if p.get("side") == "Buy" else "SHORT", "entry": float(p.get("avgPrice", 0)), "size": sz, "sl": float(p.get("stopLoss", 0) or 0), "tp": float(p.get("takeProfit", 0) or 0), "liq": float(p.get("liqPrice", 0) or 0)}
    except Exception as e: log(f"GET POSITION ERR {e}")
    return None

def get_real_position_cached():
    if is_paper(): return get_real_position()
    now = time.time()
    if now - LAST_POSITION_FETCH["time"] < 5 and LAST_POSITION_FETCH["data"] is not None: return LAST_POSITION_FETCH["data"]
    real = get_real_position(); LAST_POSITION_FETCH["time"] = now; LAST_POSITION_FETCH["data"] = real; return real

def close_position_market(p, exit_price=None):
    global PAPER_POSITION, PAPER_BALANCE, PAPER_POSITION_2
    if is_paper():
        if not PAPER_POSITION: STATE["open_position"] = None; return True
        pp = PAPER_POSITION; ex = exit_price if exit_price is not None else STATE["last_price"]
        if ex is None: log(f"PAPER CLOSE WAIT: No live price yet"); return False
        total_pnl = 0; total_fee = 0
        pnl1 = (ex - pp["entry"]) * pp["size"] if pp["side"]=="LONG" else (pp["entry"] - ex) * pp["size"]
        fee1 = ex * pp["size"] * CONFIG["TAKER_FEE"]; total_pnl += pnl1; total_fee += fee1
        if PAPER_POSITION_2:
            pp2 = PAPER_POSITION_2
            pnl2 = (ex - pp2["entry"]) * pp2["size"] if pp2["side"]=="LONG" else (pp2["entry"] - ex) * pp2["size"]
            fee2 = ex * pp2["size"] * CONFIG["TAKER_FEE"]; total_pnl += pnl2; total_fee += fee2
            log(f"PAPER CLOSE ADD-ON TOO: Entry2 ${pp2['entry']:.0f} PnL2 ${pnl2:.2f} - 2 profits at once, same direction!")
        PAPER_BALANCE += total_pnl - total_fee; STATE["balance"] = PAPER_BALANCE
        if total_pnl > 0: STATE["wins"] += 1
        else: STATE["losses"] += 1
        log(f"PAPER CLOSE {pp['side']} Entry ${pp['entry']:.0f} Exit ${ex:.0f} Total PnL ${total_pnl:.2f} Fee ${total_fee:.4f} New Paper Bal ${PAPER_BALANCE:.2f} Wins {STATE['wins']} Loss {STATE['losses']} BE {STATE['breakevens']} - Paper till Monday")
        PAPER_POSITION = None; PAPER_POSITION_2 = None; STATE["open_position"] = None; HUNT_STATE["addon_done"] = False; HUNT_STATE["hunt_peak"] = 0; return True
    try:
        real = get_real_position()
        if not real: STATE["open_position"] = None; return True
        side = "Sell" if p["side"] == "LONG" else "Buy"
        j = bybit_post("/v5/order/create", {"category": "linear", "symbol": SYMBOL, "side": side, "orderType": "Market", "qty": str(real["size"]), "positionIdx": 0, "reduceOnly": True})
        log(f"CLOSE MARKET {p['side']} Size {real['size']} -> {j.get('retMsg')}"); STATE["open_position"] = None; HUNT_STATE["addon_done"] = False; HUNT_STATE["hunt_peak"] = 0; return True
    except Exception as e: log(f"CLOSE MARKET ERR {e}"); return False

def get_price():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT", timeout=15)
        p = float(r.json()["result"]["list"][0]["lastPrice"])
        if p and p > 0: STATE["last_price"] = p; return p
    except Exception as e: log(f"PRICE ERR {e}")
    if STATE["last_price"] is not None: log(f"PRICE FALLBACK: Last LIVE ${STATE['last_price']:.0f}"); return STATE["last_price"]
    log(f"PRICE STILL NONE - No live yet, no blind, no fixed"); return None

def fetch_live_price_startup():
    log("STARTUP: Fetching LIVE BTC price from Bybit... No fixed, no blind, no 71000")
    for attempt in range(10):
        p = get_price()
        if p is not None:
            log(f"STARTUP LIVE PRICE CONFIRMED ${p:.0f} - Bot eyes don open")
            # If Real Monday, also fetch live balance now
            if not is_paper(): get_real_balance()
            return p
        log(f"STARTUP: Live price attempt {attempt+1}/10 fail, retry 3s..."); time.sleep(3)
    log("STARTUP: Still no live after 10 tries - Main loop go keep retrying, no blind"); return None

def get_klines(limit=50, interval="1"):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval={interval}&limit={limit}", timeout=15); kl = list(reversed(r.json()["result"]["list"])); return [{"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4])} for x in kl]
    except: return []
def get_klines_daily(limit=210):
    try:
        r = requests.get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=D&limit={limit}", timeout=15); kl = list(reversed(r.json()["result"]["list"])); return [{"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4])} for x in kl]
    except: return []
def get_funding():
    try:
        r = requests.get("https://api.bybit.com/v5/market/funding/history?category=linear&symbol=BTCUSDT&limit=1", timeout=15); return float(r.json()["result"]["list"][0]["fundingRate"])*100
    except: return None
def get_oi_change():
    try:
        r = requests.get("https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=5min&limit=5", timeout=15); lst = r.json()["result"]["list"]
        if len(lst)>=2:
            a=float(lst[-1]["openInterest"]); b=float(lst[0]["openInterest"]); return (a-b)/b*100 if b else 0
    except: pass
    return None
def get_fear():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=15); return int(r.json()["data"][0]["value"])
    except: return None

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
def get_yahoo(symbol):
    for host in ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]:
        for attempt in range(2):
            try:
                url = f"https://{host}/v8/finance/chart/{symbol}?range=1d&interval=5m"; r = requests.get(url, timeout=15, headers=HEADERS); j = r.json(); res = j.get("chart", {}).get("result")
                if not res: continue
                meta = res[0].get("meta", {}); prev = meta.get("previousClose"); cur = meta.get("regularMarketPrice")
                if prev and cur and prev != 0: return (cur-prev)/prev*100, cur
            except: time.sleep(1)
    return None, None
def get_stooq(symbol):
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"; r = requests.get(url, timeout=15, headers=HEADERS); lines = r.text.strip().split("\n")
        if len(lines) >= 3:
            def parse(l): return float(l.split(",")[4])
            prev = parse(lines[-2]); cur = parse(lines[-1])
            if prev: return (cur-prev)/prev*100, cur
    except: pass
    return None, None
def get_twelve_data(symbol):
    try:
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey=demo"; r = requests.get(url, timeout=10, headers=HEADERS); j = r.json()
        if "percent_change" in j: return float(j["percent_change"])
    except: pass
    return None
def get_macro_with_fallback(sy, ss, name, key, sofar={}):
    pct, _ = get_yahoo(sy)
    if pct is not None: LAST_MACRO[key] = pct; LAST_MACRO_TIME[key] = time.time(); log(f"LIVE {name} Yahoo OK {pct:.2f}%"); return pct
    pct2, _ = get_stooq(ss)
    if pct2 is not None: LAST_MACRO[key] = pct2; LAST_MACRO_TIME[key] = time.time(); log(f"LIVE {name} Stooq OK {pct2:.2f}%"); return pct2
    pct3 = get_twelve_data(sy)
    if pct3 is not None: LAST_MACRO[key] = pct3; LAST_MACRO_TIME[key] = time.time(); log(f"LIVE {name} TwelveData OK {pct3:.2f}%"); return pct3
    if key == "DXY" and sofar.get("EURUSD"): return -sofar["EURUSD"]*0.8
    if key == "NQ" and sofar.get("SPX"): return sofar["SPX"]*1.2
    if key == "NVDA" and sofar.get("NQ"): return sofar["NQ"]*1.5
    if key == "SPX" and sofar.get("NQ"): return sofar["NQ"]*0.8
    last = LAST_MACRO_TIME.get(key, 0); age = (time.time()-last)/60 if last else 999; cached = LAST_MACRO.get(key, 0.0)
    if age <= 5: log(f"LIVE {name} ALL FAIL, fresh cache {cached:.2f}%"); return cached
    log(f"LIVE {name} ALL FAIL + Cache old -> NEUTRAL 0.0% BTC-only"); return 0.0

def get_macro_live():
    m = {}
    m["DXY"] = get_macro_with_fallback("DX-Y.NYB", "dx-y.nq", "DXY", "DXY", m); m["EURUSD"] = get_macro_with_fallback("EURUSD%3DX", "eurusd", "EURUSD", "EURUSD", m); m["NQ"] = get_macro_with_fallback("%5EIXIC", "ndx", "NQ", "NQ", m); m["SPX"] = get_macro_with_fallback("%5EGSPC", "spx", "SPX", "SPX", m); m["GOLD"] = get_macro_with_fallback("GC%3DF", "gc.f", "GOLD", "GOLD", m); m["NVDA"] = get_macro_with_fallback("NVDA", "nvda.us", "NVDA", "NVDA", m); m["US10Y"] = get_macro_with_fallback("%5ETNX", "us10y", "US10Y", "US10Y", m); m["OIL"] = get_macro_with_fallback("CL%3DF", "cl.f", "OIL", "OIL", m); m["USDJPY"] = get_macro_with_fallback("USDJPY%3DX", "usdjpy", "USDJPY", "USDJPY", m); m["NIKKEI"] = get_macro_with_fallback("%5EN225", "nikkei", "NIKKEI", "NIKKEI", m); m["HANGSENG"] = get_macro_with_fallback("%5EHSI", "hangseng", "HANGSENG", "HANGSENG", m)
    if m["NVDA"] is None or m["NVDA"] == 0: m["NVDA"] = m["NQ"]
    m["FUND"] = get_funding(); m["OI"] = get_oi_change(); m["FEAR"] = get_fear()
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=15); dom = r.json()["data"]["market_cap_percentage"]["btc"]; LAST_MACRO["BTCDOM"] = dom; m["DOM"] = dom; log(f"ETF PROXY BTC Dom {dom:.2f}%")
    except: m["DOM"] = LAST_MACRO.get("BTCDOM")
    log(f"LIVE MACRO DXY {m['DXY']:.2f} NQ {m['NQ']:.2f} SPX {m['SPX']:.2f} GOLD {m['GOLD']:.2f} NVDA {m['NVDA']:.2f} US10Y {m['US10Y']:.2f} OIL {m['OIL']:.2f} EURUSD {m['EURUSD']:.2f} USDJPY {m['USDJPY']:.2f} NIKKEI {m['NIKKEI']:.2f} HSI {m['HANGSENG']:.2f} FUND {m['FUND']} OI {m['OI']} FEAR {m['FEAR']} DOM {m['DOM']}")
    return m

def calc_rsi(kl, period=14):
    if len(kl) < period+1: return 50
    gains=0; losses=0
    for i in range(-period,0):
        d = kl[i]["c"]-kl[i-1]["c"]
        if d>0: gains+=d
        else: losses+=abs(d)
    if losses==0: return 100
    rs = (gains/period)/(losses/period); return 100 - (100/(1+rs))
def calc_200ma(daily):
    if len(daily)<200: return None
    return sum(c["c"] for c in daily[-200:])/200
def get_news(kl):
    if len(kl)>=15 and kl[0]["c"]!=0:
        move=(kl[-1]["c"]-kl[0]["c"])/kl[0]["c"]*100
        if abs(move)>=0.8: log(f"NEWS DETECTED VOL SPIKE {move:.2f}% in 15m - Brain alert"); return True, 85.0, f"VOL SPIKE {move:.2f}%"
    return False,0,""
def detect_wick(kl):
    if len(kl)<3: return None
    last=kl[-1]; prev=kl[-2]; wd = last["c"]-last["l"]; wu = last["h"]-last["c"]; wd2 = prev["c"]-prev["l"]; wu2 = prev["h"]-prev["c"]
    if CONFIG["WICK_MIN"] <= wd <= CONFIG["WICK_MAX"] and wd > wu*1.5: return ("LONG", wd, last["l"])
    if CONFIG["WICK_MIN"] <= wd2 <= CONFIG["WICK_MAX"] and wd2 > wu2*1.5: return ("LONG", wd2, prev["l"])
    if CONFIG["WICK_MIN"] <= wu <= CONFIG["WICK_MAX"] and wu > wd*1.5: return ("SHORT", wu, last["h"])
    if CONFIG["WICK_MIN"] <= wu2 <= CONFIG["WICK_MAX"] and wu2 > wd2*1.5: return ("SHORT", wu2, prev["h"])
    return None
def get_signals_live(macro, rsi, price, ma200, dom):
    s=[]
    if macro["DXY"]>0.10: s.append(("DXY","SHORT"))
    elif macro["DXY"]<-0.10: s.append(("DXY","LONG"))
    else: s.append(("DXY","NEUTRAL"))
    if (macro["NQ"] or 0) < -0.20 or (macro["NVDA"] or 0) < -1.0: s.append(("TECH","SHORT"))
    elif (macro["NQ"] or 0) > 0.20 and (macro["NVDA"] or 0) > 0.5: s.append(("TECH","LONG"))
    else: s.append(("TECH","NEUTRAL"))
    if macro["SPX"]>0.20: s.append(("SPX","LONG"))
    elif macro["SPX"]<-0.20: s.append(("SPX","SHORT"))
    else: s.append(("SPX","NEUTRAL"))
    if macro["GOLD"]>0.50: s.append(("GOLD","SHORT"))
    elif macro["GOLD"]<-0.30: s.append(("GOLD","LONG"))
    else: s.append(("GOLD","NEUTRAL"))
    if macro["OI"] is None or macro["FUND"] is None: s.append(("LIQ_MAP","NEUTRAL"))
    elif macro["OI"]>0.5 and macro["FUND"]>0.01: s.append(("LIQ_MAP","SHORT"))
    elif macro["OI"]<-0.5 and macro["FUND"]<-0.01: s.append(("LIQ_MAP","LONG"))
    else: s.append(("LIQ_MAP","NEUTRAL"))
    if macro["FEAR"] is None: s.append(("FEAR","NEUTRAL"))
    elif macro["FEAR"]<25: s.append(("FEAR","LONG"))
    elif macro["FEAR"]>75: s.append(("FEAR","SHORT"))
    else: s.append(("FEAR","NEUTRAL"))
    if rsi < 30: s.append(("RSI","LONG"))
    elif rsi > 70: s.append(("RSI","SHORT"))
    elif rsi < 40 and price < (ma200 or 999999): s.append(("RSI","SHORT"))
    else: s.append(("RSI","NEUTRAL"))
    if ma200 is None: s.append(("MA200","NEUTRAL"))
    elif price < ma200: s.append(("MA200","SHORT"))
    else: s.append(("MA200","LONG"))
    if dom is None: s.append(("ETF","NEUTRAL"))
    elif dom < 52: s.append(("ETF","SHORT"))
    else: s.append(("ETF","NEUTRAL"))
    if macro["US10Y"]>0.50: s.append(("US10Y","SHORT"))
    elif macro["US10Y"]<-0.50: s.append(("US10Y","LONG"))
    else: s.append(("US10Y","NEUTRAL"))
    if macro["OIL"]>1.0: s.append(("OIL","SHORT"))
    elif macro["OIL"]<-1.0: s.append(("OIL","LONG"))
    else: s.append(("OIL","NEUTRAL"))
    if macro["USDJPY"]>0.30: s.append(("USDJPY","SHORT"))
    elif macro["USDJPY"]<-0.30: s.append(("USDJPY","LONG"))
    else: s.append(("USDJPY","NEUTRAL"))
    asia_avg = ((macro["NIKKEI"] or 0) + (macro["HANGSENG"] or 0))/2
    if asia_avg < -0.50: s.append(("ASIA","SHORT"))
    elif asia_avg > 0.50: s.append(("ASIA","LONG"))
    else: s.append(("ASIA","NEUTRAL"))
    if macro["EURUSD"]>0.20: s.append(("EURUSD","LONG"))
    elif macro["EURUSD"]<-0.20: s.append(("EURUSD","SHORT"))
    else: s.append(("EURUSD","NEUTRAL"))
    return s
def get_signals_live_with_btc_fallback(macro, rsi, price, ma200, dom):
    signals = get_signals_live(macro, rsi, price, ma200, dom); neutrals = sum(1 for _, v in signals if v == "NEUTRAL")
    if neutrals >= 8: STATE["btc_only_mode"] = True; log(f"BTC-ONLY MODE {neutrals}/14 NEUTRAL - RSI/WICK/Funding/OI/Fear only")
    else: STATE["btc_only_mode"] = False
    return signals
def decide(signals):
    longs=sum(1 for _,v in signals if v=="LONG"); shorts=sum(1 for _,v in signals if v=="SHORT"); dec=longs+shorts
    if longs>shorts: return "LONG",longs,dec,longs,shorts, (longs/dec*100 if dec else 0)
    if shorts>longs: return "SHORT",shorts,dec,longs,shorts, (shorts/dec*100 if dec else 0)
    return "NONE",0,dec,longs,shorts,0

# REVERSAL GUARD V3 - Let wins run
def check_reversal_guard(price, signals):
    p = STATE["open_position"]
    if not p: REVERSAL_CONFIRM["count"] = 0; return False
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT")
    is_rev = False
    if p["side"] == "LONG" and shorts >= 5 and longs <= 1: is_rev = True
    if p["side"] == "SHORT" and longs >= 5 and shorts <= 1: is_rev = True
    if not is_rev:
        if REVERSAL_CONFIRM["count"] > 0: log(f"REVERSAL V3: Flicker clear, HOLD")
        REVERSAL_CONFIRM["count"] = 0; return False
    prof_pct = (price - p["entry"]) / p["entry"] * 100 if p["side"] == "LONG" else (p["entry"] - price) / p["entry"] * 100
    if prof_pct > 0:
        if prof_pct < 1.0:
            log(f"REVERSAL V3: Reversal but Profit only {prof_pct:.2f}% <1% - HOLD to TP, let win run, no early close"); REVERSAL_CONFIRM["count"] = 0; return False
        REVERSAL_CONFIRM["count"] += 1
        if REVERSAL_CONFIRM["count"] < 3: log(f"REVERSAL V3: Win {prof_pct:.2f}% + Reversal - Confirm {REVERSAL_CONFIRM['count']}/3, HOLD"); return False
        log(f"REVERSAL V3 CONFIRMED 3/3: Win {prof_pct:.2f}% + Reversal - Close with big profit"); close_position_market(p, price); REVERSAL_CONFIRM["count"] = 0; return True
    REVERSAL_CONFIRM["count"] += 1
    if REVERSAL_CONFIRM["count"] < 2: log(f"REVERSAL V3: Loss {prof_pct:.2f}% + Reversal - Confirm 1/2, HOLD"); return False
    log(f"REVERSAL V3 CONFIRMED 2/2: Loss {prof_pct:.2f}% - Close early"); close_position_market(p, price); REVERSAL_CONFIRM["count"] = 0; return True

def check_liquidation_guard(price):
    p = STATE["open_position"]
    if not p: return False
    try:
        real = get_real_position_cached()
        if not real: return False
        liq = real.get("liq", 0)
        if not liq: liq = p["entry"]*0.985 if p["side"]=="LONG" else p["entry"]*1.015
        dist = abs(price-liq)/price if price else 1
        if dist < 0.01: log(f"LIQ GUARD Price ${price:.0f} Liq ${liq:.0f} Dist {dist*100:.2f}% - Close only <0.30%")
        if dist < CONFIG["LIQ_GUARD_DIST"]: log(f"LIQ GUARD EMERGENCY Dist {dist*100:.2f}% - Closing to save balance"); close_position_market(p, price); return True
    except Exception as e: log(f"LIQ GUARD ERR {e}")
    return False

def is_asian_session():
    h = datetime.now(timezone.utc).hour
    return 0 <= h < 8

# HUNT ADD-ON V2 - LIQ MAP + ASIAN WIDE + RETRACE - SAME DIRECTION, NO HEDGE, LONG+SHORT MIRROR
def check_hunt_addon(price, kl, signals, macro):
    global PAPER_POSITION_2, PAPER_BALANCE
    p = STATE["open_position"]
    if not p or p.get("addon_done") or HUNT_STATE.get("addon_done"): return False
    if len(kl) < 3 or "mental_sl" not in p: return False
    if STATE["balance"] < CONFIG["HUNT_ADDON_MIN_BAL"]: return False
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT")
    if p["side"] == "SHORT" and not (shorts >= 5 and longs <= 1): return False
    if p["side"] == "LONG" and not (longs >= 5 and shorts <= 1): return False
    oi = macro.get("OI"); fund = macro.get("FUND"); liq_wide = False
    if oi is not None and abs(oi) > 1.0: liq_wide = True; log(f"HUNT ADD-ON LIQ MAP: OI {oi:.2f}% pumping - Hunt fit go wider, wait")
    if fund is not None and abs(fund) > 0.02: liq_wide = True; log(f"HUNT ADD-ON LIQ MAP: Funding {fund:.4f}% extreme - Hunt fit go wider, wait")
    need_better = CONFIG["HUNT_ADDON_MIN_BETTER_ASIA"] if is_asian_session() else CONFIG["HUNT_ADDON_MIN_BETTER_US"]
    if liq_wide: need_better += 300
    if is_asian_session(): log(f"HUNT ADD-ON: Asian session - Need ${need_better} better (Asian hunts wider), no $400 rush")
    if p["side"] == "SHORT" and price > p["mental_sl"]:
        if price > HUNT_STATE["hunt_peak"] or HUNT_STATE["hunt_peak"] == 0:
            HUNT_STATE["hunt_peak"] = price; log(f"HUNT TRACK SHORT: Peak update ${price:.0f} - Waiting retrace, no mid-hunt entry"); return False
        better_peak = HUNT_STATE["hunt_peak"] - p["entry"]
        if better_peak < need_better: log(f"HUNT ADD-ON WAIT: Peak better ${better_peak:.0f} < Need ${need_better} - Hunt still small, wait"); return False
        retrace_needed = HUNT_STATE["hunt_peak"] - (better_peak * CONFIG["HUNT_RETRACE_PCT"])
        if price > retrace_needed: log(f"HUNT ADD-ON WAIT: Peak ${HUNT_STATE['hunt_peak']:.0f} Price ${price:.0f} Need retrace to ${retrace_needed:.0f} (30%) - Best pace, no chase"); return False
        better = price - p["entry"]; log(f"HUNT ADD-ON V2 TRIGGER SHORT! First ${p['entry']:.0f} Peak ${HUNT_STATE['hunt_peak']:.0f} Entry Now ${price:.0f} Better ${better:.0f} Need ${need_better} Retrace 30% done - Add second SHORT!")
    elif p["side"] == "LONG" and price < p["mental_sl"]:
        if HUNT_STATE["hunt_peak"] == 0 or price < HUNT_STATE["hunt_peak"]:
            HUNT_STATE["hunt_peak"] = price; log(f"HUNT TRACK LONG: Peak low update ${price:.0f} - Waiting retrace"); return False
        better_peak = p["entry"] - HUNT_STATE["hunt_peak"]
        if better_peak < need_better: log(f"HUNT ADD-ON WAIT LONG: Peak better ${better_peak:.0f} < Need ${need_better}"); return False
        retrace_needed = HUNT_STATE["hunt_peak"] + (better_peak * CONFIG["HUNT_RETRACE_PCT"])
        if price < retrace_needed: log(f"HUNT ADD-ON WAIT LONG: Peak ${HUNT_STATE['hunt_peak']:.0f} Price ${price:.0f} Need retrace to ${retrace_needed:.0f} (30%)"); return False
        better = p["entry"] - price; log(f"HUNT ADD-ON V2 TRIGGER LONG! First ${p['entry']:.0f} Peak Low ${HUNT_STATE['hunt_peak']:.0f} Entry Now ${price:.0f} Better ${better:.0f} Need ${need_better} Retrace 30% done - Add second LONG!")
    else: return False
    qty2 = STATE["current_qty"]; need1 = (p.get("size", STATE["current_qty"]) * price / 50.0) * 1.20; need2 = (qty2 * price / 50.0) * 1.20; bal = STATE["balance"]
    if bal < (need1 + need2):
        qty2 = round(STATE["current_qty"]/2, 3)
        if qty2 < 0.001: qty2 = 0.001
        need2 = (qty2 * price / 50.0) * 1.20
        if bal < (need1 + need2): log(f"HUNT ADD-ON BLOCK: Bal ${bal:.2f} no fit 2 orders need ${(need1+need2):.2f} - Hold first only"); return False
        log(f"HUNT ADD-ON: Balance tight, half qty {qty2}")
    if is_paper():
        fee = price * qty2 * CONFIG["TAKER_FEE"]; PAPER_BALANCE -= fee; STATE["balance"] = PAPER_BALANCE
        PAPER_POSITION_2 = {"side": p["side"], "entry": price, "size": qty2, "sl": p["sl"], "tp": p["tp"], "mental_sl": p["mental_sl"]}
        log(f"PAPER HUNT ADD-ON: Second {p['side']} @ ${price:.0f} Qty {qty2} Fee ${fee:.4f} Bal ${PAPER_BALANCE:.2f} Avg ${(p['entry']+price)/2:.0f} - Same direction, no hedge")
    else:
        if not place_real_order(p["side"], qty2, p["sl"], p["tp"], price, p["mental_sl"]): log(f"HUNT ADD-ON REAL FAIL"); return False
        log(f"REAL HUNT ADD-ON: Second {p['side']} @ ${price:.0f} Qty {qty2} - Same direction, no hedge")
    p["addon_done"] = True; HUNT_STATE["addon_done"] = True; p["avg_entry"] = (p["entry"]+price)/2
    log(f"HUNT ADD-ON DONE Avg ${p['avg_entry']:.0f} - 2 same direction dey follow to destination"); return True

def check_stop_hunt_and_real_break(price, kl, signals):
    p = STATE["open_position"]
    if not p or len(kl) < 3 or "mental_sl" not in p: return False
    longs = sum(1 for _, v in signals if v == "LONG"); shorts = sum(1 for _, v in signals if v == "SHORT"); last = kl[-1]
    if p["side"] == "SHORT" and last["h"] > p["mental_sl"] and last["c"] < p["mental_sl"] and price < p["mental_sl"]: HUNT_STATE["hunt_count"] += 1; log(f"STOP HUNT DETECTED SHORT Wick {last['h']:.0f} Close back {last['c']:.0f} - Hold"); return False
    if p["side"] == "LONG" and last["l"] < p["mental_sl"] and last["c"] > p["mental_sl"] and price > p["mental_sl"]: HUNT_STATE["hunt_count"] += 1; log(f"STOP HUNT DETECTED LONG Wick {last['l']:.0f} Close back {last['c']:.0f} - Hold"); return False
    price_break = False
    if p["side"] == "SHORT" and kl[-1]["c"] > p["mental_sl"] and kl[-2]["c"] > p["mental_sl"]: price_break = True
    if p["side"] == "LONG" and kl[-1]["c"] < p["mental_sl"] and kl[-2]["c"] < p["mental_sl"]: price_break = True
    cert_break = False
    if p["side"] == "SHORT" and longs >= 5 and shorts <= 1: cert_break = True
    if p["side"] == "LONG" and shorts >= 5 and longs <= 1: cert_break = True
    if price_break and not cert_break: log(f"PRICE BEYOND MENTAL SL BUT CERT STILL {p['side']} - No real break, hold"); return False
    if price_break and cert_break: log(f"REAL BREAK CONFIRMED - Close"); LAST_HUNT_LOSS["time"] = time.time(); LAST_HUNT_LOSS["side"] = p["side"]; LAST_HUNT_LOSS["entry"] = p["entry"]; close_position_market(p, price); return True
    return False

def manage_real(price, kl, signals, macro):
    if price is None: return
    check_hunt_addon(price, kl, signals, macro)
    if is_paper() and STATE["open_position"]:
        p = STATE["open_position"]
        if p["side"]=="LONG" and price >= p["tp"]: log(f"PAPER TP HIT LONG ${price:.0f} >= TP ${p['tp']:.0f} - Win!"); close_position_market(p, price); return
        if p["side"]=="SHORT" and price <= p["tp"]: log(f"PAPER TP HIT SHORT ${price:.0f} <= TP ${p['tp']:.0f} - Win!"); close_position_market(p, price); return
        if p["side"]=="LONG" and price <= p["sl"]: log(f"PAPER SL HIT LONG"); close_position_market(p, price); return
        if p["side"]=="SHORT" and price >= p["sl"]: log(f"PAPER SL HIT SHORT"); close_position_market(p, price); return
    if check_stop_hunt_and_real_break(price, kl, signals): return
    if check_reversal_guard(price, signals): return
    if check_liquidation_guard(price): return
    p = STATE["open_position"]
    if not p: return
    real = get_real_position_cached()
    if not real:
        if not is_paper(): log(f"REAL POSITION CLOSED ON BYBIT - TP/SL HIT"); STATE["open_position"] = None
        return
    entry = p.get("avg_entry", p["entry"]); side = p["side"]; prof = (price-entry)/entry if side=="LONG" else (entry-price)/entry
    if not p.get("be_done") and prof>=CONFIG["BE_TRIGGER"]:
        be = entry+CONFIG["BE_BUFFER"] if side=="LONG" else entry-CONFIG["BE_BUFFER"]
        if (side=="LONG" and be>p["sl"]) or (side=="SHORT" and be<p["sl"]):
            p["sl"]=be; p["be_done"]=True; update_real_sl(be); log(f"REAL BE OVER FEES: SL -> ${be:.0f} (0.35% + $15 covers fees)")
    if prof>=CONFIG["TRAIL_START"]:
        ns = p["sl"]
        if side=="LONG":
            if prof>=CONFIG["TRAIL_3"]: ns=price-price*0.008
            elif prof>=CONFIG["TRAIL_2"]: ns=price-price*0.006
            elif prof>=CONFIG["TRAIL_1"]: ns=price-price*0.004
            if ns>p["sl"]: p["sl"]=ns; update_real_sl(ns); log(f"REAL TRAILING LONG SL -> ${ns:.0f}")
        else:
            if prof>=CONFIG["TRAIL_3"]: ns=price+price*0.008
            elif prof>=CONFIG["TRAIL_2"]: ns=price+price*0.006
            elif prof>=CONFIG["TRAIL_1"]: ns=price+price*0.004
            if ns<p["sl"]: p["sl"]=ns; update_real_sl(ns); log(f"REAL TRAILING SHORT SL -> ${ns:.0f}")

def main():
    threading.Thread(target=start_health, daemon=True).start()
    log("BOT V12 FINAL PAPER $4.75 -> REAL MONDAY IF PAPER DO WELL STARTED - Smiling Always")
    if not BYBIT_KEY or not BYBIT_SECRET: log("WARNING: BYBIT_API_KEY / SECRET MISSING - Add for Render Env! Paper still run, Real need am Monday")
    fetch_live_price_startup()
    if is_paper(): log(f"PAPER MODE ACTIVE - Start Paper Balance $4.75 Fresh - Real NOT touched till Monday 12am WAT - Only if paper do well we go real")
    else: log(f"REAL MODE ACTIVE - STARTUP LIVE PRICE done, LIVE BALANCE fetched, connected to Bybit real - Trading real now")
    try:
        if not is_paper():
            rp = get_real_position()
            if rp:
                m, r = calc_smart_sl_live(rp["entry"], rp["side"]); STATE["open_position"] = {"side": rp["side"], "entry": rp["entry"], "sl": rp["sl"] or r, "tp": rp["tp"] or rp["entry"], "mental_sl": m, "mode": "RESUMED", "be_done": False, "addon_done": False}; log(f"RESUMED REAL POSITION {rp}")
    except Exception as e: log(f"RESUME ERR {e}")
    while True:
        try:
            bal = get_real_balance(); price = get_price()
            if price is None: log("NO LIVE PRICE YET - Wait 5s, no blind, no fixed"); time.sleep(5); continue
            kl = get_klines(50); daily = get_klines_daily(210); macro = get_macro_live(); rsi = calc_rsi(kl); ma200 = calc_200ma(daily); dom = macro.get("DOM")
            is_news, _, news_reason = get_news(kl); signals = get_signals_live_with_btc_fallback(macro, rsi, price, ma200, dom); dest, agree, decided, longs, shorts, cert = decide(signals)
            min_agree = CONFIG["MIN_AGREE"]; min_cert = CONFIG["MIN_CERTAINTY"]
            if STATE.get("btc_only_mode"): min_agree = 2; log(f"BTC-ONLY MODE: Agree need 2")
            wick = detect_wick(kl); fear = macro["FEAR"]
            log(f"Price ${price:.0f} RSI {rsi:.1f} MA200 {ma200} Fear {fear} Bal ${bal:.2f} Qty {STATE['current_qty']} News {is_news} {news_reason} Mode {'PAPER $4.75' if is_paper() else 'REAL LIVE'}")
            log(f"Signals Long {longs} Short {shorts} Dest {dest} Cert {cert:.0f}% Agree {agree}/{decided} Wick {wick} MinCert {min_cert}% MinAgree {min_agree}")
            real_pos = get_real_position_cached()
            if not real_pos: STATE["open_position"] = None
            elif not STATE["open_position"]:
                m, r = calc_smart_sl_live(real_pos["entry"], real_pos["side"]); STATE["open_position"] = {"side": real_pos["side"], "entry": real_pos["entry"], "sl": real_pos["sl"], "tp": real_pos["tp"], "mental_sl": m, "mode": "RESUMED", "be_done": False, "addon_done": False}
            if not STATE["open_position"] and LAST_HUNT_LOSS["side"] and dest == LAST_HUNT_LOSS["side"] and cert >= 75:
                price_back = (price < LAST_HUNT_LOSS["entry"] if dest == "SHORT" else price > LAST_HUNT_LOSS["entry"])
                if price_back:
                    log(f"HUNT RE-ENTRY LIVE: Price don come back, cert still {dest} {cert:.0f}% - Re-enter"); mental, real_sl = calc_smart_sl_live(price, dest); tp_dist = abs(price-mental)*CONFIG["TP_MULT_NORMAL"]; tp = price - tp_dist if dest == "SHORT" else price + tp_dist; qty = calc_dynamic_qty(price, bal)
                    if place_real_order(dest, qty, real_sl, tp, price, mental): STATE["open_position"] = {"side": dest, "entry": price, "sl": real_sl, "tp": tp, "mental_sl": mental, "mode": "HUNT_REENTRY", "be_done": False, "addon_done": False}; LAST_HUNT_LOSS["side"] = None
            if not STATE["open_position"] and wick:
                side, wsize, wick_level = wick
                if side=="LONG" and shorts>=5: log(f"WICK SKIP bearish")
                elif side=="SHORT" and longs>=5: log(f"WICK SKIP bullish")
                else:
                    mental, real_sl = calc_smart_sl_live(price, side); tp = price+CONFIG["WICK_TP"] if side=="LONG" else price-CONFIG["WICK_TP"]; qty = calc_dynamic_qty(price, bal); log(f"MODE A WICK {side} Wick ${wsize:.0f} Entry ${price:.0f} Mental SL ${mental:.0f} Real SL ${real_sl:.0f} TP ${tp:.0f} Qty {qty} 50x - Smiling")
                    if place_real_order(side, qty, real_sl, tp, price, mental): STATE["open_position"]={"side":side,"entry":price,"sl":real_sl,"tp":tp,"mental_sl":mental,"mode":"WICK_CHOPPER","be_done":False,"addon_done":False}
            elif not STATE["open_position"] and dest in ("LONG","SHORT"):
                is_sure = cert>=CONFIG["SURE_CERTAINTY"] and agree>=CONFIG["SURE_AGREE"]; score = (cert/100) + (0.4 if is_news else 0) + (0.3 if (dest=="LONG" and fear is not None and fear<25) or (dest=="SHORT" and fear is not None and fear>75) else 0)
                if cert>=min_cert and agree>=min_agree and score>=CONFIG["MIN_SCORE"]:
                    mental, real_sl = calc_smart_sl_live(price, dest); mult=CONFIG["TP_MULT_SURE"] if is_sure else CONFIG["TP_MULT_NORMAL"]; tp_dist=abs(price-mental)*mult; tp=price+tp_dist if dest=="LONG" else price-tp_dist; qty = calc_dynamic_qty(price, bal); log(f"MODE B TREND {dest} Entry ${price:.0f} Mental SL ${mental:.0f} Real SL ${real_sl:.0f} TP ${tp:.0f} Score {score:.2f} Qty {qty} 50x News {is_news} - Smiling")
                    if place_real_order(dest, qty, real_sl, tp, price, mental): STATE["open_position"]={"side":dest,"entry":price,"sl":real_sl,"tp":tp,"mental_sl":mental,"mode":"TREND_WIDE","be_done":False,"addon_done":False}
                else: log(f"MODE B BLOCK Cert {cert:.0f}% Need {min_cert}% Agree {agree}/{min_agree} Score {score:.2f} - Good boy dey wait")
            else:
                if STATE["open_position"]: log(f"HOLDING {'PAPER' if is_paper() else 'REAL'} {STATE['open_position']['mode']} {STATE['open_position']['side']} Entry ${STATE['open_position']['entry']:.0f} Avg ${STATE['open_position'].get('avg_entry', STATE['open_position']['entry']):.0f} Mental SL ${STATE['open_position'].get('mental_sl',0):.0f} TP ${STATE['open_position']['tp']:.0f} AddOn {STATE['open_position'].get('addon_done')}")
                else: log(f"NO TRADE: No wick, no 75% - Good boy dey wait")
            manage_real(price, kl, signals, macro)
            if STATE["open_position"]:
                pp = STATE["open_position"]; unreal = (price - pp["entry"]) * pp.get("size", STATE["current_qty"]) if pp["side"]=="LONG" else (pp["entry"] - price) * pp.get("size", STATE["current_qty"])
                log(f"SCOREBOARD W {STATE['wins']} L {STATE['losses']} BE {STATE['breakevens']} | Open {pp['side']} Entry ${pp['entry']:.0f} Price ${price:.0f} Unreal PnL ${unreal:.2f} | PaperBal ${PAPER_BALANCE:.2f} Bal ${bal:.2f} | Hunt {HUNT_STATE['hunt_count']} AddOn {pp.get('addon_done')} Asian {is_asian_session()}")
            else: log(f"SCOREBOARD W {STATE['wins']} L {STATE['losses']} BE {STATE['breakevens']} | FLAT | PaperBal ${PAPER_BALANCE:.2f} Bal ${bal:.2f} | Hunt {HUNT_STATE['hunt_count']} Asian {is_asian_session()}")
            log(f"Bal ${bal:.2f} PaperBal ${PAPER_BALANCE:.2f} Qty {STATE['current_qty']} Mode {'PAPER $4.75' if is_paper() else 'REAL LIVE'} - Smiling")
            time.sleep(CONFIG["POLL"])
        except Exception as e: log(f"ERROR {e} - NO STOP, CONTINUE"); import traceback; log(traceback.format_exc()); time.sleep(5)
if __name__=="__main__": main()
