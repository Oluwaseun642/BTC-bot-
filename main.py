# V31 WORLDWIDE VISION - FOR REAL $2.20 BYBIT - NO MORE BLIND TRADE
# FIX: Whale only -> Whale + DXY + NASDAQ + Trend EMA + Funding/OI + Liquidation. Must pass 3/5 to trade. TP $4.00 WIN +$0.14, SL $1.50 LOSS -$0.30 REAL MATH, BE +$0.80 -> +$0.30, PULLBACK $0.50, HARD STOP $0.80
import os, time, hmac, hashlib, json, threading, urllib.request, urllib.parse, traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

REAL_MODE = os.getenv("REAL_MODE", "false").lower() == "true"
API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
RENDER_URL = os.getenv("RENDER_URL", "")
SYMBOL = "BTCUSDT"
BASE_BALANCE = 2.20
LEVERAGE = 80
QTY_FIXED = 0.001
CHECK_INTERVAL = 0.5  # V31: slower check, need fetch DXY/NASDAQ, 0.5s not 0.1s
LIVE_CHECK = 0.05
COOLDOWN_SEC = 15
MIN_WHALE_BTC = 0.30
MIN_WICK_USD = 12.0
TP_FIXED_USD = 4.00  # V31: $4.00 to beat fee $0.18, WIN +$0.14 real
SL_FIXED_USD = 1.50
SLIPPAGE_USD = 0.5
BE_TRIGGER = 0.80
BE_LOCK = 0.30
MAX_HOLD_SEC = 3
MIN_BALANCE_STOP = 0.80
REAL_FEE_PER_TRADE = 0.18
REAL_LATENCY_SEC = 0.2
PULLBACK_USD = 0.50

balance = BASE_BALANCE
wins = 0
be_count = 0
losses = 0
pnl = 0.0
last_trade_time = 0
stopped = False
consecutive_losses = 0

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

def http_get(url, headers={}, timeout=4):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[HTTP ERR] {url[:60]} {e}", flush=True)
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
        return {"retCode": 0, "result": {"orderId": "PAPER-V31-WORLDWIDE"}}
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

# ===== V31 WORLDWIDE VISION =====
def get_dxy_trend():
    # DXY from Stooq free - no API key needed. DXY up = BTC down, DXY down = BTC up
    try:
        # Stooq: https://stooq.com/q/d/l/?s=dx.f&i=d - use daily close, compare last 2 closes
        req = urllib.request.Request("https://stooq.com/q/d/l/?s=dx.f&i=d", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            txt = r.read().decode()
            lines = [l for l in txt.strip().split("\n") if l and not l.startswith("Date")]
            if len(lines) >= 2:
                last = float(lines[-1].split(",")[4])
                prev = float(lines[-2].split(",")[4])
                change = last - prev
                # Also try intraday via Yahoo alternative: if change >0, DXY rising
                return {"dxy": last, "change": change, "bias": "SELL_BTC" if change > 0 else "BUY_BTC", "reason": f"DXY {'UP' if change>0 else 'DOWN'} {change:.3f}"}
    except Exception as e:
        print(f"[DXY ERR] {e} - skip DXY, neutral", flush=True)
    return {"dxy": None, "change": 0, "bias": "NEUTRAL", "reason": "DXY neutral (fetch fail)"}

def get_nasdaq_trend():
    # NASDAQ via Bybit US100 if available, else Stooq NQ
    try:
        # Try Bybit US100 ticker (Bybit has indices)
        d = bybit_get("/v5/market/tickers", {"category": "linear", "symbol": "US100USDT"})
        if d and d.get("result") and d["result"].get("list"):
            lst = d["result"]["list"][0]
            p = safe_float(lst.get("lastPrice"))
            chg = safe_float(lst.get("price24hPcnt"))
            if p is not None and chg is not None:
                return {"nasdaq": p, "change_pct": chg*100, "bias": "BUY_BTC" if chg > 0 else "SELL_BTC", "reason": f"NASDAQ US100 {'UP' if chg>0 else 'DOWN'} {chg*100:.2f}%"}
    except: pass
    try:
        req = urllib.request.Request("https://stooq.com/q/d/l/?s=%5Enq&i=d", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            txt = r.read().decode()
            lines = [l for l in txt.strip().split("\n") if l and not l.startswith("Date")]
            if len(lines) >= 2:
                last = float(lines[-1].split(",")[4]); prev = float(lines[-2].split(",")[4])
                pct = (last-prev)/prev*100 if prev else 0
                return {"nasdaq": last, "change_pct": pct, "bias": "BUY_BTC" if pct>0 else "SELL_BTC", "reason": f"NASDAQ {'UP' if pct>0 else 'DOWN'} {pct:.2f}%"}
    except Exception as e:
        print(f"[NASDAQ ERR] {e} - neutral", flush=True)
    return {"nasdaq": None, "change_pct": 0, "bias": "NEUTRAL", "reason": "NASDAQ neutral"}

def get_btc_trend_ema():
    # EMA20 from 1m klines - if price above EMA, uptrend, below, downtrend
    try:
        d = bybit_get("/v5/market/kline", {"category": "linear", "symbol": SYMBOL, "interval": "1", "limit": "30"})
        if d and d.get("result") and d["result"].get("list"):
            closes = []
            for k in reversed(d["result"]["list"]):
                c = safe_float(k[4] if len(k)>4 else None)
                if c is not None: closes.append(c)
            if len(closes) >= 20:
                # EMA20
                ema = closes[0]
                k = 2/(20+1)
                for c in closes[1:]:
                    ema = c*k + ema*(1-k)
                price = closes[-1]
                bias = "BUY_BTC" if price > ema else "SELL_BTC"
                return {"ema20": ema, "price": price, "bias": bias, "reason": f"Price {'ABOVE' if price>ema else 'BELOW'} EMA20 ${ema:.1f}"}
    except Exception as e:
        print(f"[EMA ERR] {e}", flush=True)
    return {"ema20": None, "price": None, "bias": "NEUTRAL", "reason": "EMA neutral"}

def get_funding_oi_liq():
    # Funding + OI + Liquidation - Bybit free endpoints
    try:
        # Funding rate
        d1 = bybit_get("/v5/market/funding/history", {"category": "linear", "symbol": SYMBOL, "limit": "1"})
        funding = 0
        if d1 and d1.get("result") and d1["result"].get("list"):
            funding = safe_float(d1["result"]["list"][0].get("fundingRate"), 0) or 0
        # Open Interest
        d2 = bybit_get("/v5/market/open-interest", {"category": "linear", "symbol": SYMBOL, "intervalTime": "5min", "limit": "2"})
        oi_change = 0
        if d2 and d2.get("result") and d2["result"].get("list"):
            lst = d2["result"]["list"]
            if len(lst) >= 2:
                oi1 = safe_float(lst[0].get("openInterest"), 0) or 0
                oi2 = safe_float(lst[1].get("openInterest"), 0) or 0
                oi_change = (oi1-oi2)/oi2*100 if oi2 else 0
        # Liquidation - last 50, sum Buy vs Sell liquidations
        d3 = bybit_get("/v5/market/recent-trade", {"category": "linear", "symbol": SYMBOL, "limit": "50"})
        # Use liquidation endpoint if available
        liq_bias = "NEUTRAL"
        liq_reason = "Liq neutral"
        try:
            dliq = bybit_get("/v5/market/liquidation", {"category": "linear", "symbol": SYMBOL, "limit": "20"})
            if dliq and dliq.get("result") and dliq["result"].get("list"):
                lst = dliq["result"]["list"]
                buy_liq = sum(safe_float(x.get("size"),0) or 0 for x in lst if x.get("side")=="Buy")
                sell_liq = sum(safe_float(x.get("size"),0) or 0 for x in lst if x.get("side")=="Sell")
                if buy_liq > sell_liq*1.2:
                    liq_bias = "SELL_BTC"  # Many longs liquidated, price falling, shorts win
                    liq_reason = f"Liq: Longs getting chopped {buy_liq:.2f} vs {sell_liq:.2f} -> SELL"
                elif sell_liq > buy_liq*1.2:
                    liq_bias = "BUY_BTC"
                    liq_reason = f"Liq: Shorts getting chopped {sell_liq:.2f} vs {buy_liq:.2f} -> BUY"
                else:
                    liq_reason = f"Liq balanced {buy_liq:.2f}/{sell_liq:.2f}"
        except: pass
        # Funding bias: Funding very negative = shorts pay longs, too many shorts, squeeze up -> BUY. Funding very positive = too many longs, dump -> SELL
        fund_bias = "NEUTRAL"
        if funding < -0.0001:
            fund_bias = "BUY_BTC"
        elif funding > 0.0001:
            fund_bias = "SELL_BTC"
        return {"funding": funding, "fund_bias": fund_bias, "oi_change": oi_change, "liq_bias": liq_bias, "liq_reason": liq_reason, "reason": f"Funding {funding*100:.4f}% {fund_bias} | OI {oi_change:.2f}% | {liq_reason}"}
    except Exception as e:
        print(f"[FUND/OI ERR] {e}", flush=True)
        return {"funding": 0, "fund_bias": "NEUTRAL", "oi_change": 0, "liq_bias": "NEUTRAL", "liq_reason": "Liq neutral", "reason": "Funding neutral"}

def worldwide_score(whale_side):
    # Score: whale + DXY + NASDAQ + EMA + Funding/Liq = 5 votes. Need 3/5 agree with whale to trade.
    dxy = get_dxy_trend()
    nas = get_nasdaq_trend()
    ema = get_btc_trend_ema()
    fund = get_funding_oi_liq()
    votes = []
    # Whale vote
    whale_bias = "BUY_BTC" if whale_side=="Buy" else "SELL_BTC"
    votes.append(("WHALE", whale_bias, f"Whale {whale_side}"))
    votes.append(("DXY", dxy["bias"], dxy["reason"]))
    votes.append(("NASDAQ", nas["bias"], nas["reason"]))
    votes.append(("EMA-TREND", ema["bias"], ema["reason"]))
    # Funding/Liq combined as 1 vote: if both agree, that vote, else neutral
    if fund["fund_bias"] != "NEUTRAL" and fund["liq_bias"] != "NEUTRAL" and fund["fund_bias"]==fund["liq_bias"]:
        votes.append(("FUND+LIQ", fund["fund_bias"], fund["reason"]))
    elif fund["fund_bias"] != "NEUTRAL":
        votes.append(("FUND+LIQ", fund["fund_bias"], fund["reason"]))
    elif fund["liq_bias"] != "NEUTRAL":
        votes.append(("FUND+LIQ", fund["liq_bias"], fund["reason"]))
    else:
        votes.append(("FUND+LIQ", "NEUTRAL", fund["reason"]))
    agree = sum(1 for _, b, _ in votes if b == whale_bias)
    disagree = sum(1 for _, b, _ in votes if b != whale_bias and b != "NEUTRAL")
    neutral = sum(1 for _, b, _ in votes if b == "NEUTRAL")
    print(f"[WORLDWIDE] Whale {whale_side} | Votes: Agree {agree}/5 Disagree {disagree} Neutral {neutral}", flush=True)
    for name, bias, reason in votes:
        mark = "✅" if bias==whale_bias else ("❌" if bias!="NEUTRAL" else "➖")
        print(f"[WORLDWIDE] {mark} {name}: {bias} - {reason}", flush=True)
    return agree, disagree, votes

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
    net = gross - REAL_FEE_PER_TRADE
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
    print(f"[ALIVE] Trade open {side} Entry ${entry_price:.1f} TP ${tp_price:.1f} (+$4.00) SL ${sl_price:.1f} (-$1.50) | BE +$0.80 -> +$0.30 | WORLDWIDE APPROVED", flush=True)
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
            print(f"[BE] {side} Best +${best_move:.2f} - SL to ${current_sl:.1f}", flush=True)
        if side == "Buy" and live >= tp_price: return ("WIN", cur_move, elapsed, live)
        if side == "Sell" and live <= tp_price: return ("WIN", cur_move, elapsed, live)
        if be_active:
            if side == "Buy" and live <= current_sl: return ("BE-SMALL", BE_LOCK, elapsed, live)
            if side == "Sell" and live >= current_sl: return ("BE-SMALL", BE_LOCK, elapsed, live)
        if not be_active and cur_move <= -SL_FIXED_USD: return ("LOSS", cur_move, elapsed, live)
        if elapsed >= MAX_HOLD_SEC: return ("TIMEOUT", cur_move, elapsed, live)
        time.sleep(LIVE_CHECK)

def bot_loop():
    global balance, wins, be_count, losses, pnl, last_trade_time, stopped, consecutive_losses
    print(f"[AUTO-CONFIG] Done! {'REAL' if REAL_MODE else 'PAPER-REAL-SIM'} $2.20 REAL START Lev 80x Qty 0.001 V31 WORLDWIDE", flush=True)
    print(f"[EYE] V31 WORLDWIDE - Whale + DXY + NASDAQ + EMA + Funding/Liq = Need 3/5 Agree | TP $4.00 WIN +$0.14 | SL $1.50 LOSS -$0.30 | BE -$0.14 | STOP $0.80", flush=True)
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
            sig = detect_signal(trades)
            if sig is None:
                time.sleep(CHECK_INTERVAL); continue
            if now - last_trade_time < COOLDOWN_SEC:
                time.sleep(CHECK_INTERVAL); continue
            if sig["wick"] < MIN_WICK_USD:
                time.sleep(CHECK_INTERVAL); continue
            side = sig["side"]
            # V31 WORLDWIDE CHECK - No more blind trade
            agree, disagree, votes = worldwide_score(side)
            if agree < 3:
                print(f"[WORLDWIDE-SKIP] {side} Agree {agree}/5 < 3 - SKIP, world no agree, no blind trade", flush=True)
                last_trade_time = time.time()  # Cooldown to avoid spam check
                time.sleep(2); continue
            print(f"[WORLDWIDE-APPROVED] {side} Agree {agree}/5 - World agree, enter", flush=True)
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
                print(f"[PULLBACK-SKIP] {side} Price waka against us ${pullback_move:.2f} - SKIP, no chase", flush=True)
                time.sleep(CHECK_INTERVAL); continue
            time.sleep(REAL_LATENCY_SEC)
            real_current = get_live_price()
            if real_current is not None: current = real_current
            raw_entry = current - 0.5 if side == "Buy" else current + 0.5
            entry_price = raw_entry + SLIPPAGE_USD if side == "Buy" else raw_entry - SLIPPAGE_USD
            tp_price = entry_price + TP_FIXED_USD if side == "Buy" else entry_price - TP_FIXED_USD
            sl_price = entry_price - SL_FIXED_USD if side == "Buy" else entry_price + SL_FIXED_USD
            gross_tp, net_tp = calc_real_pnl(TP_FIXED_USD, entry_price)
            gross_sl, net_sl = calc_real_pnl(-SL_FIXED_USD, entry_price)
            print(f"[{sig['type']}] {side} Size {sig['size']:.3f} BTC | Wick ${sig['wick']:.2f} | Current ${current:.1f} | Pullback ${pullback_move:.2f} OK", flush=True)
            print(f"[STEALTH] {side} -> Entry ${entry_price:.1f} TP ${tp_price:.1f} (+$4.00 Net ${net_tp:.2f}) SL ${sl_price:.1f} (-$1.50 Net ${net_sl:.2f}) | WORLDWIDE APPROVED", flush=True)
            if REAL_MODE:
                place_stealth_trio(side, entry_price, tp_price, sl_price, QTY_FIXED)
            else:
                print(f"[PAPER-REAL-SIM] HIDDEN Entry+TP+SL - TP TAG ${tp_price:.1f}", flush=True)
            result, real_move, elapsed, live_price = run_alive_trade(side, entry_price, tp_price, sl_price)
            if result == "WIN":
                _, real_net = calc_real_pnl(TP_FIXED_USD, entry_price)
            elif result == "BE-SMALL":
                _, real_net = calc_real_pnl(BE_LOCK, entry_price)
            elif result == "LOSS":
                _, real_net = calc_real_pnl(-SL_FIXED_USD, entry_price)
            else:
                _, real_net = calc_real_pnl(real_move, entry_price)
            last_trade_time = time.time()
            if result == "WIN":
                wins += 1; pnl += real_net; balance += real_net; consecutive_losses = 0
                print(f"[WIN] {side} Net +${real_net:.4f} Bal ${balance:.2f} - WORLDWIDE WIN", flush=True)
            elif result == "BE-SMALL":
                be_count += 1; pnl += real_net; balance += real_net
                print(f"[BE-SMALL] {side} Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            elif result == "LOSS":
                losses += 1; pnl += real_net; balance += real_net; consecutive_losses += 1
                print(f"[LOSS] {side} Net {real_net:.4f} Bal ${balance:.2f} - REAL LOSS -$0.30 - Consecutive {consecutive_losses}/2", flush=True)
            else:
                if real_net >= 0.10:
                    wins += 1; pnl += real_net; balance += real_net; consecutive_losses = 0
                    print(f"[WIN] TIMEOUT Net +${real_net:.4f} Bal ${balance:.2f}", flush=True)
                elif real_net >= -0.20:
                    be_count += 1; pnl += real_net; balance += real_net
                    print(f"[BE-SMALL] TIMEOUT Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
                else:
                    losses += 1; pnl += real_net; balance += real_net; consecutive_losses += 1
                    print(f"[LOSS] TIMEOUT Net {real_net:.4f} Bal ${balance:.2f}", flush=True)
            total = wins + be_count + losses
            wr = (wins / total * 100) if total > 0 else 0
            print(f"[SUMMARY] $2.20 REAL START | Wins {wins} BE {be_count} Losses {losses} WinRate {wr:.0f}% PnL ${pnl:.4f} Bal ${balance:.2f} | TP $4.00 WIN +$0.14 | SL LOSS -$0.30 | WORLDWIDE 3/5", flush=True)
            if balance < MIN_BALANCE_STOP:
                stopped = True
                print(f"[STOP] Balance ${balance:.2f} - HARD STOP", flush=True)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"[ERR LOOP] {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            time.sleep(1)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"V31 WORLDWIDE ALIVE")
    def log_message(self, *a): pass

def keep_alive():
    while True:
        time.sleep(240)
        if RENDER_URL:
            try: urllib.request.urlopen(RENDER_URL, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.getenv("PORT", "10000"))
    print(f"[START] V31 WORLDWIDE starting on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), H).serve_forever()
