# HANDSOME BOY V5.3.3.2 FINAL - $500K + NO BLOCK + MARKET STADIUM READY
import time, random, ccxt, os, requests, sys
sys.stdout.reconfigure(line_buffering=True)
from datetime import datetime, timezone
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

API_KEY = os.environ.get("BYBIT_KEY", "YOUR_BYBIT_KEY")
API_SECRET = os.environ.get("BYBIT_SECRET", "YOUR_BYBIT_SECRET")
SYMBOL = "BTC/USDT:USDT"
SYMBOL_RAW = "BTCUSDT"
MIN_SL = 600
MAX_SL = 800
MAX_HOLD_HOURS = 12

OVER_LEV_INJURY_PCT = 0.0035
WICK_ANT_DROP = 0.0010
WHALE_THRESHOLD = 500_000 # $500k FINAL - Haffar Gee

LIMIT_OFFSET = 15
BOT_STATE = "HUNTING"
BOT_STATE_UNTIL = 0

current_position = None
pending_trade = None
last_leverage = 60
last_eur_usd = None
current_balance_cache = 3.71
last_heartbeat_log = 0
last_price_cache = 78000.0
last_vol_cache = 0
dxy_cache = {"bias": "NEUTRAL", "change": 0, "eur": 0, "ts": 0}
dom_cache = {"change": 0, "val": 60.0, "ts": 0, "last": 60.0}

exchange = ccxt.bybit({'apiKey': API_KEY,'secret': API_SECRET,'enableRateLimit': True,'options': {'defaultType': 'swap'}})
print(f"[KEYS] V5.3.3.2 FINAL - $500k STADIUM READY", flush=True)
try:
    exchange.set_position_mode(False, SYMBOL_RAW)
    print("[MODE] One-Way", flush=True)
except Exception as e:
    if "110025" in str(e) or "not modified" in str(e).lower():
        print("[MODE] Already One-Way - OK ✅", flush=True)
    else:
        print(f"[MODE] {e}", flush=True)

try:
    exchange.load_markets()
    print(f"[MARKETS] Loaded - precision fixed", flush=True)
except Exception as e:
    print(f"[MARKETS] {e}", flush=True)

def get_balance():
    global current_balance_cache
    try:
        bal_data = exchange.fetch_balance()
        for key in ['free','total']:
            if key in bal_data and 'USDT' in bal_data[key]:
                try:
                    v = float(bal_data[key]['USDT'])
                    if v is not None and v > 0:
                        current_balance_cache = v
                        return v
                except: pass
        if 'USDT' in bal_data and isinstance(bal_data['USDT'], dict) and 'free' in bal_data['USDT']:
            try:
                v = float(bal_data['USDT']['free'])
                if v is not None and v > 0:
                    current_balance_cache = v
                    return v
            except: pass
        return current_balance_cache
    except Exception as e:
        print(f"[BAL ERR] {e}", flush=True)
        return current_balance_cache

def get_real_1m_volume_and_change():
    global last_price_cache, last_vol_cache
    # Primary: OHLCV
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, '1m', limit=3)
        if len(ohlcv) >= 2:
            prev_close = ohlcv[-2][4]
            last_close = ohlcv[-1][4]
            last_vol = ohlcv[-1][5] * last_close
            price_change = last_close - prev_close
            last_price_cache = last_close
            last_vol_cache = last_vol
            return last_vol, price_change, last_close
    except Exception as e:
        if "10006" in str(e):
            print(f"[RATE LIMIT] 10006 - Trying ticker for fresh price", flush=True)
        else:
            print(f"[VOL ERR] {e} - Trying ticker", flush=True)
    
    # Fallback 1: Ticker for CURRENT market price (never stale!)
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        curr_price = float(ticker['last'])
        if curr_price > 0:
            change = curr_price - last_price_cache
            last_price_cache = curr_price
            # Keep last vol cache but price is fresh
            return last_vol_cache, change, curr_price
    except Exception as e:
        print(f"[TICKER ERR] {e}", flush=True)
    
    # Fallback 2: Use cache but warn if >60s old
    return last_vol_cache, 0, last_price_cache

def get_whale_threshold():
    return WHALE_THRESHOLD

def is_asia_open_time():
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    current_min = now.hour*60 + now.minute
    start_min = 19*60 + 30
    if weekday == 5: return False
    if weekday == 6:
        if current_min >= start_min: return True
        else: return False
    return True

def get_dxy_bias():
    global last_eur_usd, dxy_cache
    if time.time() - dxy_cache["ts"] < 300:
        return dxy_cache["bias"], dxy_cache["change"], dxy_cache["eur"]
    eur_usd = None
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=EUR&to=USD", timeout=3)
        eur_usd = float(r.json()['rates']['USD'])
    except:
        try:
            r = requests.get("https://api.exchangerate-api.com/v4/latest/EUR", timeout=3)
            eur_usd = float(r.json()['rates']['USD'])
        except:
            return dxy_cache["bias"], dxy_cache["change"], dxy_cache["eur"]
    if last_eur_usd is None:
        last_eur_usd = eur_usd
        dxy_cache.update({"bias": "NEUTRAL", "change": 0, "eur": eur_usd, "ts": time.time()})
        return "NEUTRAL", 0, eur_usd
    change_pct = ((eur_usd - last_eur_usd) / last_eur_usd) * 100
    last_eur_usd = eur_usd
    bias = "NEUTRAL"
    if change_pct > 0.15: bias = "DXY_DOWN"
    elif change_pct < -0.15: bias = "DXY_UP"
    dxy_cache.update({"bias": bias, "change": change_pct, "eur": eur_usd, "ts": time.time()})
    return bias, change_pct, eur_usd

def get_btc_dominance_change():
    global dom_cache
    if time.time() - dom_cache["ts"] < 300:
        return dom_cache["change"], dom_cache["val"]
    
    # Try 1: CoinGecko
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=4)
        data = r.json()
        dom = None
        if isinstance(data, dict):
            if 'data' in data and isinstance(data['data'], dict) and 'market_cap_percentage' in data['data']:
                dom = float(data['data']['market_cap_percentage']['btc'])
            elif 'market_cap_percentage' in data:
                dom = float(data['market_cap_percentage']['btc'])
        if dom and 30 < dom < 80:
            if 'last' not in dom_cache or dom_cache["last"] == 60.0:
                dom_cache.update({"change": 0, "val": dom, "ts": time.time(), "last": dom})
                return 0, dom
            change = dom - dom_cache["last"]
            dom_cache.update({"change": change, "val": dom, "ts": time.time(), "last": dom})
            return change, dom
    except Exception as e:
        pass
    
    # Try 2: CoinLore Global (no key)
    try:
        r = requests.get("https://api.coinlore.net/api/global/", timeout=4)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            dom = float(data[0]['btc_d'])
            if 30 < dom < 80:
                change = dom - dom_cache.get("last", dom)
                dom_cache.update({"change": change, "val": dom, "ts": time.time(), "last": dom})
                return change, dom
    except:
        pass

    # Try 3: Use cache silently - NEVER BLOCK TRADE
    return dom_cache["change"], dom_cache["val"]

def get_liquidation_map(): return {78500: 50_000_000, 77200: 40_000_000, 79000: 70_000_000}

def is_fake_wick_detector(price_change_1m, dom_change):
    if 300 <= abs(price_change_1m) <= 450:
        if abs(dom_change) < 0.15:
            print(f"[FAKE WICK] ${price_change_1m:.0f} wick dom {dom_change:.2f}% - PEEK 60s", flush=True)
            return True
    return False

def is_bank_whale_move(vol_1m, price_change, threshold):
    if vol_1m >= threshold and abs(price_change) >= 30:
        print(f"[BANK WHALE] Vol ${vol_1m/1e6:.2f}M >= ${threshold/1e6:.1f}M | Move ${price_change:.0f} REAL!", flush=True)
        return True
    return False

def check_liq_hunt(live_price):
    liq_map = get_liquidation_map()
    for liq_price, liq_val in liq_map.items():
        if abs(live_price - liq_price) < 120 and liq_val > 20_000_000:
            print(f"[LIQ VOID] {live_price:.0f} near ${liq_price} void ${liq_val/1e6}M", flush=True)
            return liq_price, liq_val
    return None, 0

class HealthHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')
        self.end_headers()
    def _get_status_text(self):
        try:
            bal = current_balance_cache
            pos = current_position if current_position else "No Position"
            lev = last_leverage
            return f"V5.3.3.2 ALIVE $500k | Bal ${bal:.2f} | {pos} | Lev {lev}x | Thresh $0.5M | {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        except:
            return "V5.3.3.2 ALIVE"
    def do_GET(self):
        try:
            self._set_headers(200)
            self.wfile.write(self._get_status_text().encode())
        except:
            try:
                self._set_headers(200)
                self.wfile.write(b"ALIVE")
            except: pass
    def do_HEAD(self): self.do_GET()
    def do_POST(self): self.do_GET()
    def do_PUT(self): self.do_GET()
    def do_DELETE(self): self.do_GET()
    def do_OPTIONS(self): self._set_headers(200); self.wfile.write(b'')
    def do_PATCH(self): self.do_GET()
    def log_message(self, format, *args): return

def start_health_server():
    while True:
        try:
            port = int(os.environ.get("PORT", 10000))
            server = HTTPServer(('0.0.0.0', port), HealthHandler)
            print(f"[RENDER] Health on {port} - $500k GREEN - Never Block", flush=True)
            server.serve_forever()
        except Exception as e: print(f"[HEALTH ERR] {e}", flush=True); time.sleep(5)

def keepalive_ping():
    while True:
        time.sleep(300)
        try:
            port = int(os.environ.get("PORT", 10000))
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        except: pass

threading.Thread(target=start_health_server, daemon=True).start()
threading.Thread(target=keepalive_ping, daemon=True).start()

def get_smart_lot_and_leverage(balance, price):
    global last_leverage
    try:
        if balance <= 10: lev, qty = 60, 0.001
        elif balance <= 25: lev, qty = 50, 0.001
        elif balance <= 50: lev, qty = 40, 0.001
        elif balance <= 100: lev, qty = 30, 0.002
        else: lev = 20; qty = max(0.001, round((balance * 0.15 / price), 4))
        try: qty = float(exchange.amount_to_precision(SYMBOL, qty))
        except: pass
        margin = (qty * price) / lev
        if margin > balance * 0.8: qty = 0.001; lev = 60
        if last_leverage != lev:
            try:
                exchange.set_leverage(lev, SYMBOL_RAW)
                time.sleep(0.5)
                last_leverage = lev
                print(f"[AUTO LEV] Bal ${balance:.2f} -> {lev}x!", flush=True)
            except Exception as e:
                if "not modified" not in str(e).lower() and "110043" not in str(e):
                    print(f"[LEV ERR] {e}", flush=True)
        print(f"[SMART] Bal ${balance:.2f} Qty {qty} Lev {lev}x | $0.5M Injury 0.35%", flush=True)
        return qty, lev
    except: return 0.001, 60

def close_position(direction, qty):
    try:
        try: qty = float(exchange.amount_to_precision(SYMBOL, qty))
        except: pass
        try: exchange.cancel_all_orders(SYMBOL)
        except: pass
        side = 'sell' if direction == "LONG" else 'buy'
        exchange.create_order(SYMBOL, 'market', side, qty, None, {'reduceOnly': True})
        print(f"[CLOSE] {direction} {qty} Injury!", flush=True); return True
    except Exception as e:
        try:
            side = 'sell' if direction == "LONG" else 'buy'
            exchange.create_order(SYMBOL, 'market', side, qty); return True
        except Exception as e2: print(f"[CLOSE FAIL] {e2}", flush=True); return False

def monitor_trade(entry_price, sl_price, tp_price, destination, direction, qty):
    global BOT_STATE, BOT_STATE_UNTIL
    print(f"[MONITOR-INJURY] Entry ${entry_price:.2f} | Lev {last_leverage}x | BEST % over 0.35% BLINK", flush=True)
    entry_time = time.time(); last_heartbeat = time.time()
    peak_price = entry_price
    best_pump_seen = 0
    while True:
        try:
            _, _, curr = get_real_1m_volume_and_change()
            elapsed = (time.time() - entry_time) / 3600
            if time.time() - last_heartbeat > 900:
                print(f"[HEARTBEAT] {direction} {elapsed:.1f}h Best {best_pump_seen*100:.3f}% Curr ${curr:.2f}", flush=True)
                last_heartbeat = time.time()
            if elapsed >= MAX_HOLD_HOURS:
                print(f"[MAX HOLD] {elapsed:.1f}h CLOSE", flush=True); close_position(direction, qty); BOT_STATE = "HUNTING"; return False
            liq_price, _ = check_liq_hunt(curr)
            if liq_price:
                if (direction=="LONG" and curr >= liq_price) or (direction=="SHORT" and curr <= liq_price):
                    print(f"[VOID SWEPT] ${liq_price} hunted! Calm 5 min", flush=True); close_position(direction, qty); BOT_STATE = "SPECTATING"; BOT_STATE_UNTIL = time.time() + 300; return False
            curr_profit_pct = (curr - entry_price)/entry_price if direction=="LONG" else (entry_price - curr)/entry_price
            if curr_profit_pct > best_pump_seen:
                best_pump_seen = curr_profit_pct
                if best_pump_seen >= OVER_LEV_INJURY_PCT:
                    print(f"[PEAK] New BEST {best_pump_seen*100:.4f}% @ ${curr:.2f}", flush=True)
                peak_price = curr
            if best_pump_seen >= OVER_LEV_INJURY_PCT:
                drop_from_peak = (peak_price - curr)/peak_price if direction=="LONG" else (curr - peak_price)/abs(peak_price) if peak_price!=0 else 0
                if drop_from_peak >= WICK_ANT_DROP:
                    print(f"[INJURY TP - BLINK] BEST {best_pump_seen*100:.4f}%! Peak ${peak_price:.2f} -> ${curr:.2f} Drop {drop_from_peak*100:.3f}% CLOSING + NEURAL", flush=True)
                    close_position(direction, qty)
                    BOT_STATE = "HUNTING"; time.sleep(2); return False
            if (direction=="LONG" and curr <= sl_price) or (direction=="SHORT" and curr >= sl_price):
                print(f"[SL] hit @ ${curr:.2f} Best {best_pump_seen*100:.3f}%", flush=True); close_position(direction, qty); return False
            time.sleep(1)
        except Exception as e: print(f"[MONITOR ERR] {e}", flush=True); time.sleep(2)

def open_trade(direction, destination):
    global current_position, pending_trade, BOT_STATE, BOT_STATE_UNTIL
    if not is_asia_open_time():
        time.sleep(60); return False
    if BOT_STATE == "SPECTATING" and time.time() < BOT_STATE_UNTIL:
        time.sleep(10); return False
    elif BOT_STATE == "SPECTATING": BOT_STATE = "HUNTING"
    if current_position is not None and pending_trade is None:
        pending_trade = (direction, destination)
        print(f"[RIGHT HAND] In {current_position}, keeping {direction} ${destination}", flush=True); return False
    try:
        vol_1m, price_change_1m, price = get_real_1m_volume_and_change()
        whale_thresh = get_whale_threshold()
        dom_change, dom_val = get_btc_dominance_change()
        dxy_bias, dxy_change, eur = get_dxy_bias()
        # Never block trade on DOM/DXY error - they return cache
        if not is_bank_whale_move(vol_1m, price_change_1m, whale_thresh):
            if abs(dom_change) < 0.3 and dxy_bias == "NEUTRAL": return False
        if is_fake_wick_detector(price_change_1m, dom_change):
            time.sleep(60)
            _, new_change, new_price = get_real_1m_volume_and_change()
            if new_price > price: direction = "LONG"
            elif new_price < price: direction = "SHORT"
        liq_price, liq_val = check_liq_hunt(price)
        if liq_price and liq_val > 30_000_000: direction = "LONG" if price < liq_price else "SHORT"
        if dom_change > 0.3 and price_change_1m > 0: direction = "LONG"
        elif dom_change < -0.3 and price_change_1m < 0: direction = "SHORT"
        if dxy_bias == "DXY_UP" and direction == "LONG" and vol_1m < 100_000_000: direction = "SHORT"
        elif dxy_bias == "DXY_DOWN" and direction == "SHORT" and vol_1m < 100_000_000: direction = "LONG"
        bal = get_balance()
        if bal < 1.0: print(f"[BAL LOW] ${bal:.2f} - Still PERP injury", flush=True)
        qty, lev = get_smart_lot_and_leverage(bal, price)
        sl_dist = random.randint(MIN_SL, MAX_SL)
        sl = price - sl_dist if direction=="LONG" else price + sl_dist
        tp = price + destination if direction=="LONG" else price - destination
        try:
            limit_price_raw = price + LIMIT_OFFSET if direction=="LONG" else price - LIMIT_OFFSET
            limit_price = float(exchange.price_to_precision(SYMBOL, limit_price_raw))
            sl = float(exchange.price_to_precision(SYMBOL, sl))
            tp = float(exchange.price_to_precision(SYMBOL, tp))
        except:
            limit_price = price + LIMIT_OFFSET if direction=="LONG" else price - LIMIT_OFFSET
        side = 'buy' if direction=="LONG" else 'sell'
        print(f"[ENTRY] {direction} LIMIT @{limit_price} (live {price}) Qty {qty} AutoLev {lev}x | $0.5M Injury 0.35%", flush=True)
        params = {}
        try: params = {'stopLoss': str(sl), 'takeProfit': str(tp), 'slTriggerBy': 'LastPrice', 'tpTriggerBy': 'LastPrice'}
        except: pass
        order = exchange.create_order(SYMBOL, 'limit', side, qty, limit_price, params)
        filled = False; filled_price = limit_price
        for i in range(12):
            time.sleep(1)
            try:
                od = exchange.fetch_order(order['id'], SYMBOL)
                if od['filled'] and od['filled'] > 0:
                    filled = True; filled_price = float(od['average']) if od['average'] else limit_price
                    print(f"[FILLED] @{filled_price} after {i+1}s", flush=True); break
            except Exception as e:
                if "10006" in str(e): time.sleep(3)
                pass
        if not filled:
            print(f"[LIMIT FAIL] Cancel", flush=True)
            try: exchange.cancel_order(order['id'], SYMBOL)
            except: pass
            return False
        current_position = direction
        should_switch = monitor_trade(filled_price, sl, tp, destination, direction, qty)
        current_position = None
        if should_switch or pending_trade: return True
    except Exception as e: print(f"[OPEN ERR] {e}", flush=True); time.sleep(2)
    return False

def start_bot():
    global pending_trade, last_heartbeat_log
    print("="*60, flush=True)
    print("HANDSOME BOY V5.3.3.2 - $500k FINAL STADIUM", flush=True)
    print(f"All fixes: $500k, 0.35%, DOM never block, Price always fresh, No 150x yet", flush=True)
    print("="*60, flush=True)
    bal_init = get_balance()
    print(f"[START BAL] ${bal_init:.2f} REAL | {datetime.now(timezone.utc).strftime('%A %H:%M UTC')} | Thresh $0.5M", flush=True)
    while True:
        try:
            if not is_asia_open_time():
                time.sleep(60); continue
            if pending_trade:
                print(f"[SWITCH] Fast -> {pending_trade}", flush=True); time.sleep(1)
                nd, nDest = pending_trade; pending_trade = None; open_trade(nd, nDest)
            else:
                vol_1m, price_change_1m, price = get_real_1m_volume_and_change()
                whale_thresh = get_whale_threshold()
                if vol_1m >= whale_thresh:
                    time.sleep(3) # Cooldown to avoid 10006
                    dest = random.randint(1000, 2500)
                    dir_choice = "LONG" if price_change_1m > 0 else "SHORT"
                    print(f"\n[SCAN] Whale {vol_1m/1e6:.2f}M >= {whale_thresh/1e6:.1f}M | {dir_choice} ${dest}", flush=True)
                    open_trade(dir_choice, dest)
                else:
                    now_ts = time.time()
                    if now_ts - last_heartbeat_log > 300:
                        print(f"[HUNTING] Alive {datetime.now(timezone.utc).strftime('%H:%M UTC')} | ${price:.0f} | Vol ${vol_1m/1e6:.2f}M < ${whale_thresh/1e6:.1f}M | Bal ${current_balance_cache:.2f} | Lev {last_leverage}x", flush=True)
                        last_heartbeat_log = now_ts
                    time.sleep(2); continue
            time.sleep(2)
        except Exception as e:
            print(f"[MAIN ERR] {e}", flush=True); time.sleep(10)

if __name__ == "__main__":
    start_bot()
