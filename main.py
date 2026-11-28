# MAIN SPOT V1 - BUY ONLY, NO CUT LOSS, DCA, PILE-UP CATCHER
# User rules: No max trades, Never sell for loss, DCA on dump, Spot only
import os, time, threading, traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from bybit_client import bybit_get, bybit_post
from data_engine import get_signal, get_price_and_candles

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
def env(k, d="0"): return os.getenv(k, d)

# ---------- SPOT HELPERS ONLY ----------
def usdt_bal():
    r = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
    try: return float(r["result"]["list"][0]["coin"][0]["walletBalance"])
    except: return 0.0

def btc_bal():
    r = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "BTC"})
    try: return float(r["result"]["list"][0]["coin"][0]["walletBalance"])
    except: return 0.0

def spot_buy(usdt_amount):
    # Bybit spot: qty in BTC = USDT / price, category=spot
    price = get_price_only()
    if price <= 0 or usdt_amount < 1.0:
        log(f"[BUY-SKIP] amount ${usdt_amount:.2f} too small / no price")
        return None
    qty = round(usdt_amount / price, 6)  # 6 decimals for BTC spot
    r = bybit_post("/v5/order/create", {
        "category": "spot", "symbol": "BTCUSDT", "side": "Buy",
        "orderType": "Market", "qty": str(qty)
    })
    log(f"[SPOT-BUY] ${usdt_amount:.2f} -> {qty} BTC @ ~{price:.0f} resp={str(r)[:200]}")
    return r

def spot_sell_all():
    qty = btc_bal()
    if qty < 0.00001:
        return None
    r = bybit_post("/v5/order/create", {
        "category": "spot", "symbol": "BTCUSDT", "side": "Sell",
        "orderType": "Market", "qty": str(round(qty, 6))
    })
    log(f"[SPOT-SELL] {qty} BTC resp={str(r)[:200]}")
    return r

def get_price_only():
    try:
        p, _ = get_price_and_candles()
        if isinstance(p, (list, tuple)): return float(p[0])
        if isinstance(p, dict): return float(p.get("close", p.get("c", p.get("price", 0))))
        return float(p)
    except: return 0.0

# ---------- SERVER / PING ----------
class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass

threading.Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.getenv("PORT", "10000"))), H).serve_forever(), daemon=True).start()

def ping():
    import requests
    while True:
        try: requests.get(os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000"), timeout=5)
        except: pass
        time.sleep(60)
threading.Thread(target=ping, daemon=True).start()

# ---------- VOL / CANDLE HELPERS (kept, cleaned) ----------
def _num(x):
    try:
        if isinstance(x, (list, tuple)): return float(x[0]) if len(x) > 0 else 0
        if isinstance(x, dict): return float(x.get("close", x.get("c", x.get("price", 0))))
        return float(x)
    except: return 0

def _candle(c):
    try:
        if isinstance(c, dict):
            return _num(c.get("high", c.get("h", 0))), _num(c.get("low", c.get("l", 0))), _num(c.get("close", c.get("c", 0)))
        if isinstance(c, (list, tuple)):
            if len(c) == 1 and isinstance(c[0], (list, tuple, dict)): return _candle(c[0])
            return _num(c[2]) if len(c) > 2 else 0, _num(c[3]) if len(c) > 3 else 0, _num(c[4]) if len(c) > 4 else 0
        return 0, 0, 0
    except: return 0, 0, 0

def get_vol(candles, price):
    try:
        if not candles or len(candles) < 55: return 0, 0, 0
        parsed = [_candle(c) for c in candles[-55:]]
        ranges = [h - l for h, l, cl in parsed if h > 0 and l > 0]
        if len(ranges) < 55: return 0, 0, 0
        avg_50 = sum(ranges[:-5]) / 50; avg_5 = sum(ranges[-5:]) / 5
        vol_ratio = avg_5 / avg_50 if avg_50 > 0 else 0
        price_5_ago = parsed[-6][2] or price
        velocity = abs(price - price_5_ago) / price_5_ago * 100 if price_5_ago > 0 else 0
        hr = int(time.strftime("%H")); sess_boost = 1.15 if hr in (8, 9, 10, 13, 14, 15) else 1.0
        return round(vol_ratio, 2), round(velocity, 3), round(vol_ratio * sess_boost, 2)
    except Exception as e:
        print(f"[VOL-ERR] {e}", flush=True); return 0, 0, 0

# ---------- STATE ----------
# Avg price = total USDT spent / total BTC bought. We sell only when price > avg + TP.
avg_price = 0.0
total_btc = 0.0
total_spent = 0.0
last_sweep_low = 0.0
sweep_time = 0
last_pileup_price = 0.0  # guard: no buy twice for same pile-up
last_buy_time = 0

BAL = usdt_bal()
log(f"START SPOT V1 Buy-Only Bal ${BAL:.2f} | No Max | No Cut Loss | DCA | Hunter 5m / Cert 15m")

while True:
    try:
        if env("PAUSE_BOT") == "1":
            time.sleep(7); continue

        raw_price, candles = get_price_and_candles()
        price = _num(raw_price)
        if price == 0:
            time.sleep(7); continue

        s = get_signal(candles)
        vol_ratio, velocity, vol_score = get_vol(candles, price)
        BAL = usdt_bal()
        BTC = btc_bal()

        # Sync state from Bybit: if we hold BTC but avg unknown (restart), keep avg from last buy
        # If we hold 0 BTC, reset avg (we sold all for profit)
        if BTC < 0.00001 and total_btc > 0:
            log(f"[RESET] Sold all, avg was {avg_price:.0f}, ready for new cycle")
            avg_price = 0; total_btc = 0; total_spent = 0; last_pileup_price = 0

        cert_dir = s.get("direction", ""); cert = s.get("cert", 0)
        hunt_dir = s.get("hunt_dir", ""); hunt_score = s.get("hunt_score", 0)
        # data_engine may return catastrophe / news flags - if any, pause buying
        catastrophe = s.get("catastrophe", False) or s.get("news_catastrophe", False) or s.get("pause", False)
        news_dir = s.get("news_dir", "")  # e.g. LONG / SHORT / CATASTROPHE

        if catastrophe or news_dir == "CATASTROPHE":
            log(f"[CATASTROPHE-PAUSE] Hold BTC {BTC:.6f} | No buy, No sell | News/Cert say danger | Price {price:.0f}")
            time.sleep(7); continue

        # --- PILE-UP DETECTION: sweep low ---
        # Sweep = price made new low vs last 20 candles, then price is recovering
        # We track lowest low in last 20 candles
        parsed = [_candle(c) for c in candles[-20:]] if candles else []
        low_20 = min([l for h, l, cl in parsed if l > 0], default=price)
        # If price wicked below low_20 recently and now back above, that's a sweep
        # Simplify: if current price is within 0.5% above low_20 and we saw a wick below, mark sweep
        if parsed and low_20 > 0 and abs(price - low_20) / low_20 < 0.005:
            if last_sweep_low == 0 or abs(low_20 - last_sweep_low) > 100:
                last_sweep_low = low_20; sweep_time = time.time()
                log(f"[SWEEP] Low {low_20:.0f} Price {price:.0f} - waiting reclaim")

        # Reclaim checks
        reclaim_5m = False
        reclaim_15m = False
        if sweep_time > 0:
            elapsed = time.time() - sweep_time
            # Reclaim = price back above sweep low + 0.3%
            if price > last_sweep_low * 1.003:
                if elapsed >= 300:  # 5 mins
                    reclaim_5m = True
                if elapsed >= 900:  # 15 mins
                    reclaim_15m = True

        # --- DECIDE BUY ---
        # Rule: One buy per pile-up. No max trades. DCA allowed if new pile-up lower than last buy.
        is_new_pileup = abs(last_sweep_low - last_pileup_price) > 100 if last_pileup_price else True
        # DCA logic: if we already hold, only buy again if price is at least 3% below avg (cheaper) + new pile-up
        is_dca = False
        if total_btc > 0 and avg_price > 0:
            if price < avg_price * 0.97 and is_new_pileup:
                is_dca = True

        buy_type = None
        why = ""
        # TYPE 1: HUNTER - fast, 5m reclaim, hunt >=5
        if reclaim_5m and hunt_dir == "LONG" and hunt_score >= 5 and is_new_pileup:
            buy_type = "HUNTER"; why = f"HUNTER LONG {hunt_score}/9 Sweep {last_sweep_low:.0f} Reclaim 5m Vol {vol_score} Vel {velocity}%"
        # TYPE 2: CERT - sure, 15m reclaim, cert >=70 LONG + news LONG
        elif reclaim_15m and cert_dir == "LONG" and cert >= 70 and is_new_pileup:
            buy_type = "CERT"; why = f"CERT LONG {cert:.0f}% News {news_dir} Sweep {last_sweep_low:.0f} Reclaim 15m Vol {vol_score}"
        # TYPE 2b: CERT without sweep, but strong cert + hunt agree (your rule: no need highest voltage)
        elif cert_dir == "LONG" and cert >= 70 and hunt_dir == "LONG" and hunt_score >= 5 and is_new_pileup and total_btc == 0:
            buy_type = "CERT-TREND"; why = f"CERT-TREND LONG {cert:.0f}% Hunt {hunt_score}/9 Vol {vol_score}"

        # If we hold and it's NOT DCA (price not cheaper), don't buy again for same cycle unless it's a new cheaper pile-up
        if buy_type and total_btc > 0 and not is_dca and buy_type != "CERT-TREND":
            # Allow DCA only - if price not cheaper, skip to avoid buying same price twice
            if price >= avg_price * 0.97:
                buy_type = None; why = ""

        if buy_type:
            # Money split for small account: $2 / $2 / remainder, else 50% for bigger account
            if BAL >= 6 and BAL < 20:
                # $6.16 plan: first buy $2, second $2, third rest
                if total_btc == 0: buy_usdt = 2.0
                elif total_spent < 4.5: buy_usdt = 2.0
                else: buy_usdt = BAL  # last chunk
            else:
                buy_usdt = BAL * 0.5 if BAL >= 2 else BAL

            buy_usdt = min(buy_usdt, BAL)
            if buy_usdt >= 1.0:
                before_btc = BTC
                spot_buy(buy_usdt)
                time.sleep(2)
                after_btc = btc_bal()
                bought = max(0, after_btc - before_btc)
                if bought > 0:
                    # Update average
                    total_spent += buy_usdt; total_btc += bought
                    avg_price = total_spent / total_btc if total_btc > 0 else price
                    last_pileup_price = last_sweep_low
                    last_buy_time = time.time()
                    sweep_time = 0; last_sweep_low = 0
                    log(f"[ENTER] {buy_type} @ {price:.0f} Spent ${buy_usdt:.2f} Avg now {avg_price:.0f} Total BTC {total_btc:.6f} | {why}")
                else:
                    log(f"[BUY-FAIL] {buy_type} @ {price:.0f} - Bybit no fill")
            else:
                log(f"[WAIT-MONEY] Bal ${BAL:.2f} need >=$1 to buy | {why}")
            time.sleep(7); continue

        # --- DECIDE SELL - ONLY FOR PROFIT, NEVER FOR LOSS ---
        if total_btc > 0 and avg_price > 0:
            pnl_pct = (price - avg_price) / avg_price * 100
            tp1 = avg_price * 1.02
            tp2 = avg_price * 1.04
            if price >= tp2:
                log(f"[TP2 +4%] Avg {avg_price:.0f} Price {price:.0f} PnL +{pnl_pct:.2f}% - SELL ALL")
                spot_sell_all(); avg_price = 0; total_btc = 0; total_spent = 0; last_pileup_price = 0
            elif price >= tp1:
                log(f"[TP1 +2%] Avg {avg_price:.0f} Price {price:.0f} PnL +{pnl_pct:.2f}% - SELL ALL (Spot V1: sell all at TP1 for small account)")
                spot_sell_all(); avg_price = 0; total_btc = 0; total_spent = 0; last_pileup_price = 0
            else:
                # HOLD - no cut loss, even if -30%, -50%
                log(f"[HOLD] Avg {avg_price:.0f} Price {price:.0f} PnL {pnl_pct:.2f}% BTC {total_btc:.6f} USDT Bal ${BAL:.2f} | No cut loss, wait for TP or DCA | Cert {cert_dir} {cert:.0f}% Hunt {hunt_dir} {hunt_score}/9 Vol {vol_score}")
            time.sleep(7); continue

        # --- NO POSITION ---
        log(f"[WAIT] Bal ${BAL:.2f} Price {price:.0f} Cert {cert_dir} {cert:.0f}% Hunt {hunt_dir} {hunt_score}/9 Sweep {last_sweep_low:.0f} Reclaim5 {reclaim_5m} Reclaim15 {reclaim_15m} Vol {vol_score} Vel {velocity}%")
        time.sleep(7)

    except Exception as e:
        log(f"[ERR] {e}"); traceback.print_exc(); time.sleep(7)
