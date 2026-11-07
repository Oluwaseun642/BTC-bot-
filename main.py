# V36 LOOSEN ENTRY RAPID WIN RATE - FOR REAL $2.20 BYBIT - BE OVER FEES STILL NEVER MINUS
# FIX V35 TOO TIGHT: 5 hours = 1 WIN PnL +$0.12 Wick $2.70 Need $15+ -> disaster. V36 LOOSEN: Wick $15->$6, Whale 0.30->0.15, Orderbook 1.5x->1.2x, Need Weekend 3->2 Weekday 5->3, Cooldown 15s->8s, Max Hold 3s->5s, Pullback $0.50->$0.80. KEEP BE OVER FEES $3.50 -> +$0.08 NEVER MINUS, TP $4.00 WIN +$0.14, SL $1.50 LOSS -$0.30. SELF PING 1 MIN + HEARTBEAT KEEP.
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse, traceback, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.20
LEVERAGE = 80
QTY_FIXED = 0.001
CHECK_INTERVAL = 0.5
LIVE_CHECK = 0.05
COOLDOWN_SEC = 8  # V36: 15s -> 8s rapid
MIN_WHALE_BTC = 0.15  # V36: 0.30 -> 0.15 loosen for weekend quiet
MIN_WICK_USD = 6.0  # V36: $15 -> $6 loosen, Wick $2.70 -> $6 fit happen
TP_FIXED_USD = 4.00
SL_FIXED_USD = 1.50
SLIPPAGE_USD = 0.5
BE_TRIGGER = 3.50  # V36: KEEP BE OVER FEES, never loosen BE to minus
BE_LOCK = 3.50  # V36: KEEP Entry + $3.50 = +$0.08 PROFIT never minus
MAX_HOLD_SEC = 5  # V36: 3s -> 5s give price time to reach BE $3.50
MIN_BALANCE_STOP = 0.80
REAL_FEE_PER_TRADE = 0.18
FUNDING_FEE_EST = 0.02
REAL_LATENCY_SEC = 0.2
PULLBACK_USD = 0.80  # V36: $0.50 -> $0.80 loosen
HEARTBEAT_SEC = 60

balance = 2.32  # V36: Start from current balance $2.32 from screenshot, not $2.20
wins = 1
be_count = 0
losses = 0
pnl = 0.12
last_trade_time = 0
stopped = False
consecutive_losses = 0
last_wick_seen = 0.0
last_price_seen = 0.0

def safe_float(x, default=None):
    try:
        if x is None: return default
        if isinstance(x, str):
            s = x.strip().lower()
            if s in ("none", "", "null", "nan"): return default
        v = float(x)
        if v != v: return default
        return v
    except: return default

def lagos_time_str():
    try:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
        return now.strftime("%H:%M:%S Lagos")
    except:
        return datetime.datetime.utcnow().strftime("%H:%M:%S UTC")

def http_get(url, headers={}, timeout=5):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[HTTP ERR] {url[:80]} {e}", flush=True)
        return None

def bybit_get(path, params={}):
    try:
        ts = str(int(time.time()*1000))
        qs = urllib.parse.urlencode(sorted(params.items()))
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000"}
        if API_KEY:
            sig = hmac.new(API_SECRET.encode(), (ts + API_KEY + "5000" + qs).encode(), hashlib.sha256).hexdigest()
            headers["X-BAPI-SIGN"] = sig
        url = f"https://api.bybit.com{path}?{qs}" if qs else f"https://api.bybit.com{path}"
        return http_get(url, headers, timeout=3)
    except: return None

def bybit_post(path, body):
    if not REAL_MODE:
        return {"retCode": 0, "result": {"orderId": "PAPER-V36-LOOSEN"}}
    try:
        ts = str(int(time.time()*1000))
        payload = json.dumps(body)
        sig = hmac.new(API_SECRET.encode(), (ts + API_KEY + "5000" + payload).encode(), hashlib.sha256).hexdigest()
        headers = {"X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": "5000", "X-BAPI-SIGN": sig, "Content-Type": "application/json"}
        req = urllib.request.Request(f"https://api.bybit.com{path}", data=payload.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[ERR] POST {e}", flush=True)
        return None

def get_live_price(sym=SYMBOL):
    d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": sym})
    if d and d.get("result") and d["result"].get("list"):
        p = safe_float(d["result"]["list"][0].get("lastPrice"))
        if p is not None: return p
    return None

def get_recent_trades():
    d = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
    if d and d.get("result") and d["result"].get("list"):
        clean = []
        for t in d["result"]["list"]:
            p = safe_float(t.get("price")); s = safe_float(t.get("size")); side = t.get("side")
            if p is None or s is None or side not in ("Buy", "Sell"): continue
            clean.append({"price": str(p), "size": str(s), "side": side})
        if len(clean) >= 5: return clean
    return []

def is_weekend():
    try:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
        return now.weekday() >= 5
    except:
        return datetime.datetime.utcnow().weekday() >= 5

def yahoo_quote(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=2d&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        d = http_get(url, headers, timeout=5)
        if d and d.get("chart") and d["chart"].get("result"):
            res = d["chart"]["result"][0]
            meta = res.get("meta", {})
            closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]
            if len(closes) >= 1:
                last = closes[-1]
                prev = meta.get("previousClose") or (closes[-2] if len(closes)>=2 else last)
                pct = (last - prev)/prev*100 if prev else 0
                return {"price": last, "prev": prev, "pct": pct, "ok": True}
    except Exception as e:
        print(f"[YAHOO ERR] {symbol} {e}", flush=True)
    return {"price": None, "prev": None, "pct": 0, "ok": False}

def get_worldwide_v36():
    weekend = is_weekend()
    dxy = yahoo_quote("DX-Y.NYB")
    if dxy["ok"]:
        if weekend:
            dxy_bias = "NEUTRAL"; dxy_reason = f"DXY ${dxy['price']:.2f} {dxy['pct']:+.2f}% - CLOSED Weekend - NEUTRAL"
        else:
            if dxy["pct"] > 0.05:
                dxy_bias = "SELL_BTC"; dxy_reason = f"DXY UP +{dxy['pct']:.2f}% - Dollar STRONG -> SELL PRIORITY"
            elif dxy["pct"] < -0.05:
                dxy_bias = "BUY_BTC"; dxy_reason = f"DXY DOWN {dxy['pct']:.2f}% - Dollar WEAK -> BUY PRIORITY"
            else:
                dxy_bias = "NEUTRAL"; dxy_reason = f"DXY FLAT {dxy['pct']:.2f}% - NEUTRAL"
    else:
        dxy_bias = "NEUTRAL"; dxy_reason = "DXY fail - NEUTRAL"
    nas = yahoo_quote("^IXIC")
    if not nas["ok"]:
        nas = yahoo_quote("^NDX")
    if nas["ok"]:
        if weekend:
            nas_bias = "NEUTRAL"; nas_reason = f"NASDAQ ${nas['price']:.1f} {nas['pct']:+.2f}% - CLOSED Weekend - NEUTRAL"
        else:
            if nas["pct"] > 0.10:
                nas_bias = "BUY_BTC"; nas_reason = f"NASDAQ UP +{nas['pct']:.2f}% - Tech PUMP -> BUY PRIORITY"
            elif nas["pct"] < -0.10:
                nas_bias = "SELL_BTC"; nas_reason = f"NASDAQ DOWN {nas['pct']:.2f}% - Tech DUMP -> SELL PRIORITY"
            else:
                nas_bias = "NEUTRAL"; nas_reason = f"NASDAQ FLAT {nas['pct']:.2f}% - NEUTRAL"
    else:
        nas_bias = "NEUTRAL"; nas_reason = "NASDAQ fail - NEUTRAL"
    spx = yahoo_quote("^GSPC")
    if spx["ok"]:
        if weekend:
            spx_bias = "NEUTRAL"; spx_reason = f"SPX CLOSED {spx['pct']:+.2f}% - NEUTRAL"
        else:
            spx_bias = "BUY_BTC" if spx["pct"] > 0.10 else ("SELL_BTC" if spx["pct"] < -0.10 else "NEUTRAL")
            spx_reason = f"SPX {spx['pct']:+.2f}% - {spx_bias}"
    else:
        spx_bias = "NEUTRAL"; spx_reason = "SPX fail - NEUTRAL"
    gold = yahoo_quote("GC=F")
    if gold["ok"]:
        if weekend:
            gold_bias = "NEUTRAL"; gold_reason = f"GOLD CLOSED {gold['pct']:+.2f}% - NEUTRAL"
        else:
            gold_bias = "SELL_BTC" if gold["pct"] > 0.50 else ("BUY_BTC" if gold["pct"] < -0.50 else "NEUTRAL")
            gold_reason = f"GOLD {gold['pct']:+.2f}% - {gold_bias}"
    else:
        gold_bias = "NEUTRAL"; gold_reason = "GOLD fail - NEUTRAL"
    ema_bias = "NEUTRAL"; ema_reason = "EMA neutral"
    try:
        d = bybit_get("/v5/market/kline", {"category": "linear", "symbol": SYMBOL, "interval": "1", "limit": "30"})
        if d and d.get("result") and d["result"].get("list"):
            closes = []
            for k in reversed(d["result"]["list"]):
                c = safe_float(k[4] if len(k)>4 else None)
                if c is not None: closes.append(c)
            if len(closes) >= 20:
                ema = closes[0]
                kk = 2/(20+1)
                for c in closes[1:]:
                    ema = c*kk + ema*(1-kk)
                price = closes[-1]
                ema_bias = "BUY_BTC" if price > ema else "SELL_BTC"
                ema_reason = f"Price {'ABOVE' if price>ema else 'BELOW'} EMA20 ${ema:.1f}"
    except: pass
    eth_bias = "NEUTRAL"; eth_reason = "ETH/Funding neutral"
    try:
        d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": "ETHUSDT"})
        eth_chg = 0
        if d and d.get("result") and d["result"].get("list"):
            eth_chg = (safe_float(d["result"]["list"][0].get("price24hPcnt"), 0) or 0) * 100
        d1 = bybit_get("/v5/market/funding/history", {"category": "linear", "symbol": SYMBOL, "limit": "1"})
        funding = 0
        if d1 and d1.get("result") and d1["result"].get("list"):
            funding = safe_float(d1["result"]["list"][0].get("fundingRate"), 0) or 0
        eth_b = "BUY_BTC" if eth_chg > 0.05 else ("SELL_BTC" if eth_chg < -0.05 else "NEUTRAL")
        fund_b = "BUY_BTC" if funding < -0.00005 else ("SELL_BTC" if funding > 0.00005 else "NEUTRAL")
        if eth_b != "NEUTRAL" and fund_b != "NEUTRAL" and eth_b == fund_b:
            eth_bias = eth_b; eth_reason = f"ETH {eth_chg:.2f}% {eth_b} + Funding {funding*100:.4f}% {fund_b} - agree"
        elif eth_b != "NEUTRAL" and fund_b == "NEUTRAL":
            eth_bias = eth_b; eth_reason = f"ETH {eth_chg:.2f}% {eth_b} | Funding neutral"
        elif fund_b != "NEUTRAL" and eth_b == "NEUTRAL":
            eth_bias = fund_b; eth_reason = f"ETH neutral | Funding {funding*100:.4f}% {fund_b}"
        else:
            eth_reason = f"ETH {eth_chg:.2f}% {eth_b} vs Funding {fund_b} - neutral"
    except: pass
    ob_bias = "NEUTRAL"; ob_reason = "Orderbook neutral"
    try:
        d = bybit_get("/v5/market/orderbook", {"category": "linear", "symbol": SYMBOL, "limit": "25"})
        if d and d.get("result"):
            bids = d["result"].get("b", [])
            asks = d["result"].get("a", [])
            bid_vol = sum(safe_float(x[1], 0) or 0 for x in bids[:10])
            ask_vol = sum(safe_float(x[1], 0) or 0 for x in asks[:10])
            if bid_vol > ask_vol * 1.2:  # V36: 1.5x -> 1.2x loosen
                ob_bias = "BUY_BTC"; ob_reason = f"Orderbook Buy Wall {bid_vol:.2f} vs Sell {ask_vol:.2f} (1.2x) - fit push $3.50"
            elif ask_vol > bid_vol * 1.2:
                ob_bias = "SELL_BTC"; ob_reason = f"Orderbook Sell Wall {ask_vol:.2f} vs Buy {bid_vol:.2f} (1.2x) - fit push $3.50"
            else:
                ob_reason = f"Orderbook balanced Buy {bid_vol:.2f} Sell {ask_vol:.2f}"
    except: pass
    return {"weekend": weekend, "votes": [("DXY-PRIORITY", dxy_bias, dxy_reason), ("NASDAQ-PRIORITY", nas_bias, nas_reason), ("SPX", spx_bias, spx_reason), ("GOLD", gold_bias, gold_reason), ("EMA-TREND", ema_bias, ema_reason), ("ETH+FUNDING", eth_bias, eth_reason), ("ORDERBOOK-1.2x", ob_bias, ob_reason)]}

def worldwide_score_v36(whale_side, wick):
    whale_bias = "BUY_BTC" if whale_side=="Buy" else "SELL_BTC"
    ww = get_worldwide_v36()
    weekend = ww["weekend"]
    votes = [("WHALE", whale_bias, f"Whale {whale_side}")] + ww["votes"]
    weighted_agree = 0
    weighted_total = 0
    print(f"[WORLDWIDE] {'WEEKEND' if weekend else 'WEEKDAY'} Whale {whale_side} Wick ${wick:.2f} | V36 LOOSEN Need {2 if weekend else 3}", flush=True)
    for name, bias, reason in votes:
        weight = 2 if name in ("DXY-PRIORITY", "NASDAQ-PRIORITY") and not weekend else 1
        if weekend and name in ("DXY-PRIORITY", "NASDAQ-PRIORITY", "SPX", "GOLD"):
            weight = 0
        if weight == 0:
            print(f"[WORLDWIDE] ➖ {name}: {bias} - {reason} (CLOSED, weight 0)", flush=True)
            continue
        mark = "✅" if bias==whale_bias else ("❌" if bias!="NEUTRAL" else "➖")
        print(f"[WORLDWIDE] {mark} {name}: {bias} - {reason} (weight {weight})", flush=True)
        if bias == whale_bias:
            weighted_agree += weight
        if bias != "NEUTRAL":
            weighted_total += weight
    need = 2 if weekend else 3  # V36: Weekend 3->2, Weekday 5->3 loosen rapid
    print(f"[WORLDWIDE] Weighted Agree {weighted_agree} / Live Total {weighted_total} | Need {need} V36 LOOSEN", flush=True)
    return weighted_agree, weighted_total, need, votes

def detect_signal(trades):
    if not trades: return None
    clean_trades = []
    for t in trades:
        p = safe_float(t.get("price")); s = safe_float(t.get("size"))
        if p is None or s is None: continue
        clean_trades.append({"price": str(p), "size": str(s), "side": t.get("side")})
    if len(clean_trades) < 5: return None
    prices = [safe_float(t["price"]) for t in clean_trades]
    prices = [p for p in prices if p is not None]
    if not prices: return None
    wick = max(prices) - min(prices)
    current = safe_float(clean_trades[0].get("price"))
    if current is None: return None
    biggest = max(clean_trades, key=lambda t: safe_float(t.get("size"), 0) or 0)
    biggest_size = safe_float(biggest.get("size"), 0) or 0
    biggest_side = biggest.get("side", "")
    if biggest_size >= MIN_WHALE_BTC:
        return {"type": "WHALE", "side": biggest_side, "size": biggest_size, "wick": wick, "current": current, "wick_pct": wick / current * 100 if current else 0}
    return None

def calc_real_pnl(move_usd, entry_price):
    notional = entry_price * QTY_FIXED * LEVERAGE
    gross = (move_usd / entry_price) * notional if entry_price else 0
    net = gross - REAL_FEE_PER_TRADE - FUNDING_FEE_EST
    return gross, net

def place_stealth_trio(side, entry_price, tp_price, sl_price, qty):
    close_side = "Sell" if side == "Buy" else "Buy"
    entry_dir = 2 if side == "Buy" else 1
    tp_dir = 1 if side == "Buy" else 2
    sl_dir = 1 if side == "Buy" else 2
    entry_body = {"category": "linear", "symbol": SYMBOL, "side": side, "orderType": "Limit", "qty": str(qty), "price": f"{entry_price:.1f}", "triggerPrice": f"{entry_price:.1f}", "triggerDirection": entry_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": False}
    tp_body = {"category": "linear", "symbol": SYMBOL, "side": close_side, "orderType": "Limit", "qty": str(qty), "price": f"{tp_price:.1f}", "triggerPrice": f"{tp_price:.1f}", "triggerDirection": tp_dir, "triggerBy": "LastPrice", "timeInForce": "PostOnly", "positionIdx": 0, "reduceOnly": True}
    sl_body = {"category": "linear", "symbol": SYMBOL, "side": close_side, "orderType": "Market", "qty": str(qty), "triggerPrice": f"{sl_price:.1f}", "triggerDirection": sl_dir, "triggerBy": "LastPrice", "timeInForce": "GoodTillCancel", "positionIdx": 0, "reduceOnly": True, "stopLoss": f"{sl_price:.1f}"}
    r1 = bybit_post("/v5/order/create", entry_body); r2 = bybit_post("/v5/order/create", tp_body); r3 = bybit_post("/v5/order/create", sl_body)
    return r1, r2, r3

def run_alive_trade(side, entry_price, tp_price, sl_price):
    start = time.time()
    best_move = 0.0
    be_active = False
    current_sl = sl_price
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} TP ${tp_price:.1f} (+$4.00 WIN +$0.14) SL ${sl_price:.1f} (-$1.50 LOSS -$0.30) | BE OVER FEES +$3.50 -> +$0.08 NEVER MINUS | V36 LOOSEN", flush=True)
    while True:
        elapsed = time.time() - start
        live = get_live_price()
        if live is None:
            time.sleep(LIVE_CHECK); continue
        cur_move = (live - entry_price) if side == "Buy" else (entry_price - live)
        if cur_move > best_move: best_move = cur_move
        if not be_active and best_move >= BE_TRIGGER:
            be_active = True
            current_sl = entry_price + BE_LOCK if side == "Buy" else entry_price - BE_LOCK
            print(f"[BE-OVER-FEES] {side} Best +${best_move:.2f} - SL moved to Entry +$3.50 = ${current_sl:.1f} - If wick off, close +$0.08 PROFIT, never minus.", flush=True)
        if side == "Buy" and live >= tp_price: return ("WIN", cur_move, elapsed, live)
        if side == "Sell" and live <= tp_price: return ("WIN", cur_move, elapsed, live)
        if be_active:
            if side == "Buy" and live <= current_sl: return ("BE-PROFIT", BE_LOCK, elapsed, live)
            if side == "Sell" and live >= current_sl: return ("BE-PROFIT", BE_LOCK, elapsed, live)
        if not be_active and cur_move <= -SL_FIXED_USD: return ("LOSS", cur_move, elapsed, live)
        if elapsed >= MAX_HOLD_SEC: return ("TIMEOUT", cur_move, elapsed, live)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped, consecutive_losses, last_wick_seen, last_price_seen
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-SIM'} $2.32 START Lev 80x Qty 0.001 V36 LOOSEN RAPID", flush=True)
    print(f"[EYE] V36 LOOSEN - Wick $6 Whale 0.15 Orderbook 1.2x Need 2/3 Cooldown 8s Hold 5s | BE $3.50 -> +$0.08 NEVER MINUS | TP WIN +$0.14 | SL -$0.30", flush=True)
    while True:
        try:
            if stopped:
                time.sleep(10); continue
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} < $0.80 - HARD STOP", flush=True)
                time.sleep(10); continue
            if consecutive_losses >= 2:
                print(f"[PAUSE] 2 LOSS in a row - Pause 60s", flush=True)
                consecutive_losses = 0
                time.sleep(60); continue
            now = time.time()
            trades = get_recent_trades()
            if trades:
                prices_tmp = [safe_float(t.get("price")) for t in trades]
                prices_tmp = [p for p in prices_tmp if p is not None]
                if prices_tmp:
                    last_wick_seen = max(prices_tmp) - min(prices_tmp)
                    last_price_seen = prices_tmp[0]
            sig = detect_signal(trades)
            if sig is None:
                time.sleep(CHECK_INTERVAL); continue
            if now - last_trade_time < COOLDOWN_SEC:
                time.sleep(CHECK_INTERVAL); continue
            if sig["wick"] < MIN_WICK_USD:
                time.sleep(CHECK_INTERVAL); continue
            side = sig["side"]
            agree, total, need, votes = worldwide_score_v36(side, sig["wick"])
            if agree < need:
                print(f"[WORLDWIDE-SKIP] {side} Weighted Agree {agree} < Need {need} - SKIP V36", flush=True)
                last_trade_time = time.time()
                time.sleep(2); continue
            print(f"[WORLDWIDE-APPROVED] {side} Weighted Agree {agree} >= Need {need} - V36 LOOSEN enter", flush=True)
            current = sig["current"]
            cached = get_live_price()
            if cached is not None: current = cached
            if balance - 0.30 < 0:
                print(f"[MARGIN] Balance ${balance:.2f} no fit cover worst loss -$0.30 - REJECT", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            margin_needed = (current * QTY_FIXED) / LEVERAGE
            if margin_needed > balance:
                print(f"[MARGIN] Margin ${margin_needed:.2f} > Bal ${balance:.2f} - REJECT", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            price_before = current
            time.sleep(0.5)
            price_after = get_live_price()
            if price_after is None: price_after = price_before
            pullback_move = (price_after - price_before) if side == "Buy" else (price_before - price_after)
            if pullback_move < -PULLBACK_USD:
                print(f"[PULLBACK-SKIP] {side} Price waka against us ${pullback_move:.2f} - SKIP", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            time.sleep(REAL_LATENCY_SEC)
            real_current = get_live_price()
            if real_current is not None: current = real_current
            raw_entry = current - 0.5 if side == "Buy" else current + 0.5
            entry_price = raw_entry + SLIPPAGE_USD if side == "Buy" else raw_entry - SLIPPAGE_USD
            tp_price = entry_price + TP_FIXED_USD if side == "Buy" else entry_price - TP_FIXED_USD
            sl_price = entry_price - SL_FIXED_USD if side == "Buy" else entry_price + SL_FIXED_USD
            gross_tp, net_tp = calc_real_pnl(TP_FIXED_USD, entry_price)
            gross_be, net_be = calc_real_pnl(BE_LOCK, entry_price)
            gross_sl, net_sl = calc_real_pnl(-SL_FIXED_USD, entry_price)
            print(f"[{sig['type']}] {side} Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} | Current ${current:.1f} | Pullback ${pullback_move:.2f} OK", flush=True)
            print(f"[STEALTH] {side} -> Entry ${entry_price:.1f} TP ${tp_price:.1f} (+$4.00 Net ${net_tp:.2f}) BE-OVER-FEES ${entry_price+BE_LOCK:.1f} (+$3.50 Net ${net_be:.2f} PROFIT) SL ${sl_price:.1f} (-$1.50 Net ${net_sl:.2f}) | V36", flush=True)
            if REAL_MODE:
                place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
            else:
                print(f"[PAPER-REAL-SIM] HIDDEN Entry+TP+SL - TP TAG ${tp_price:.1f} BE TAG ${entry_price+BE_LOCK:.1f}", flush=True)
            result, real_move, elapsed, live_price = run_alive_trade(side, entry_price, tp_price, sl_price)
            if result == "WIN":
                _, real_net = calc_real_pnl(TP_FIXED_USD, entry_price)
            elif result == "BE-PROFIT":
                _, real_net = calc_real_pnl(BE_LOCK, entry_price)
            elif result == "LOSS":
                _, real_net = calc_real_pnl(-SL_FIXED_USD, entry_price)
            else:
                _, real_net = calc_real_pnl(real_move, entry_price)
                if real_net >= 0.05:
                    result = "WIN-TIMEOUT"
                elif real_net >= 0.00:
                    result = "BE-PROFIT-TIMEOUT"
                else:
                    result = "LOSS-TIMEOUT"
            last_trade_time = time.time()
            if result == "WIN" or result == "WIN-TIMEOUT":
                wins += 1; pnl += real_net; balance += real_net; consecutive_losses = 0
                print(f"[WIN] {side} Net +${real_net:.4f} Bal ${balance:.2f} - V36 WIN {result}", flush=True)
            elif result == "BE-PROFIT" or result == "BE-PROFIT-TIMEOUT":
                be_count += 1; pnl += real_net; balance += real_net
                print(f"[BE-PROFIT] {side} Net +${real_net:.4f} Bal ${balance:.2f} - BE OVER FEES, wick off but PROFIT ✅", flush=True)
            else:
                losses += 1; pnl += real_net; balance += real_net; consecutive_losses += 1
                print(f"[LOSS] {side} Net {real_net:.4f} Bal ${balance:.2f} - Never reach BE $3.50 - Consecutive {consecutive_losses}/2 - {result}", flush=True)
            total_tr = wins + be_count + losses
            wr = (wins / total_tr * 100) if total_tr > 0 else 0
            print(f"[SUMMARY] $2.32 START | Wins {wins} BE-PROFIT {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} | TP WIN +$0.14 | BE PROFIT +$0.08 NEVER MINUS | SL -$0.30 | V36 LOOSEN", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} - HARD STOP", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            time.sleep(1)

def heartbeat_loop():
    while True:
        try:
            time.sleep(HEARTBEAT_SEC)
            if RENDER_URL:
                try:
                    req = urllib.request.Request(RENDER_URL, headers={"User-Agent": "Bot-Self-Ping-V36"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        print(f"[SELF-PING] Ping RENDER_URL ... OK {r.status} - {lagos_time_str()} - Bot dey alive, Render no go sleep", flush=True)
                except Exception as e:
                    print(f"[SELF-PING] Ping RENDER_URL ... FAIL {e} - {lagos_time_str()} - Still alive, retry next min", flush=True)
            else:
                print(f"[SELF-PING] No RENDER_URL set - Self ping skip - {lagos_time_str()}", flush=True)
            weekend = is_weekend()
            market_note = "DXY/NASDAQ CLOSED Weekend" if weekend else "DXY/NASDAQ LIVE Weekday"
            price_note = f"${last_price_seen:.1f}" if last_price_seen else "fetching..."
            wick_note = f"${last_wick_seen:.2f}" if last_wick_seen else "$0.00"
            print(f"[ALIVE] Bot dey alive 👌 - {lagos_time_str()} | Balance ${balance:.2f} | Wins {wins} BE-PROFIT {be_count} Losses {losses} PnL ${pnl:.4f} | BTC {price_note} Wick {wick_note} (Need $6+ V36 LOOSEN) | {market_note} | BE OVER FEES $3.50 -> +$0.08 | Waiting...", flush=True)
        except Exception as e:
            print(f"[HEARTBEAT ERR] {e}", flush=True)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        ua = self.headers.get("User-Agent", "unknown")
        is_uptime = "UptimeRobot" in ua or "uptimerobot" in ua.lower()
        is_self = "Bot-Self-Ping" in ua
        if is_uptime:
            print(f"[UPTIMEROBOT] Ping from UptimeRobot - {lagos_time_str()} - Bot ALIVE - 200 OK - Balance ${balance:.2f} Wins {wins} BE {be_count} Losses {losses}", flush=True)
        elif is_self:
            print(f"[SELF-PING] HTTP GET from Self-Ping - {lagos_time_str()} - Bot ALIVE - 200 OK", flush=True)
        else:
            print(f"[HTTP] GET / from {ua[:40]} - {lagos_time_str()} - Bot ALIVE", flush=True)
        self.send_response(200); self.end_headers(); self.wfile.write(b"V36 LOOSEN ALIVE - BE OVER FEES")
    def log_message(self, *a):
        print(f"[HTTP-LOG] {a}", flush=True)

def keep_alive():
    while True:
        time.sleep(60)
        if RENDER_URL:
            try: urllib.request.urlopen(RENDER_URL, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    print(f"[START] V36 LOOSEN RAPID starting on port {port} - {lagos_time_str()}", flush=True)
    HTTPServer(("0.0.0.0", port), H).serve_forever()
