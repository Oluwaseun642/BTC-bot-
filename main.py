# HANDSOME BOY V5.3 FINAL - FULL COMBINED - NO ERROR
# Includes: V4.4.37 + V2 + V3 + V5.1 + WHALE_LIMIT + NOV FIX + ASIA 8:30pm WAT
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

# === V5.3 CONFIG - ALL YOUR REQUESTS ===
WHALE_VOLUME_NORMAL = 10_000_000   # Normal = $10M - BANK ONLY
WHALE_VOLUME_MONDAY = 5_000_000    # WHALE_LIMIT_MIN - Every Monday $5M - More trades
LIMIT_OFFSET = 15                  # LIMIT order offset to avoid slippage
MAX_SLIPPAGE_PCT = 0.15
BOT_STATE = "HUNTING"              # HUNTING / SPECTATING
BOT_STATE_UNTIL = 0

current_position = None
pending_trade = None
last_leverage = None
last_eur_usd = None
current_balance_cache = 5.0

exchange = ccxt.bybit({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})

print(f"[KEYS] V5.3 FINAL - WHALE HUNTER + ASIA 8:30pm WAT Ready", flush=True)

try:
    exchange.set_position_mode(False, SYMBOL_RAW)
    print("[MODE] One-Way", flush=True)
except Exception as e:
    print(f"[MODE] {e}", flush=True)

# === CORE UTILS ===
def get_balance():
    global current_balance_cache
    try:
        bal_data = exchange.fetch_balance()
        for key in ['free','total']:
            if key in bal_data and 'USDT' in bal_data[key]:
                try:
                    v = float(bal_data[key]['USDT'])
                    if v is not None:
                        current_balance_cache = v
                        return v
                except: pass
        if 'USDT' in bal_data and isinstance(bal_data['USDT'], dict) and 'free' in bal_data['USDT']:
            try:
                v = float(bal_data['USDT']['free'])
                if v is not None:
                    current_balance_cache = v
                    return v
            except: pass
        return current_balance_cache
    except Exception as e:
        print(f"[BAL ERR] {e} - cache ${current_balance_cache}", flush=True)
        return current_balance_cache

def safe_ticker():
    for i in range(3):
        try:
            return exchange.fetch_ticker(SYMBOL)
        except Exception as e:
            print(f"[TICKER RETRY {i+1}/3] {e}", flush=True)
            time.sleep(1.5)
    raise Exception("Ticker failed")

def get_real_1m_volume_and_change():
    """E) Fast execution - Real 1m data, not 24h"""
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, '1m', limit=3)
        if len(ohlcv) < 2:
            return 0, 0, safe_ticker()['last']
        prev_close = ohlcv[-2][4]
        last_close = ohlcv[-1][4]
        last_vol = ohlcv[-1][5] * last_close
        price_change = last_close - prev_close
        return last_vol, price_change, last_close
    except Exception as e:
        print(f"[VOL ERR] {e}", flush=True)
        try:
            return 0, 0, safe_ticker()['last']
        except:
            return 0, 0, 78000.0

# === V5.3 NEW FEATURES ===
def get_whale_threshold():
    """WHALE_LIMIT_MIN - Every Monday of life $5M"""
    now = datetime.now(timezone.utc)
    is_monday = now.weekday() == 0
    if is_monday:
        print(f"[MONDAY MODE] Monday {now.strftime('%H:%M UTC')} - Threshold ${WHALE_VOLUME_MONDAY/1e6}M", flush=True)
        return WHALE_VOLUME_MONDAY
    return WHALE_VOLUME_NORMAL

def is_asia_open_time():
    """Always turn ON by 8:30pm WAT everyday, especially Sunday Asia open"""
    now = datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    hour = now.hour
    minute = now.minute
    current_min = hour*60 + minute
    start_min = 19*60 + 30  # 19:30 UTC = 20:30 WAT (8:30pm WAT)
    
    if weekday == 5:  # Saturday - OFF
        # Still keep alive but no trade
        return False
    if weekday == 6:  # Sunday - wait till 8:30pm WAT then ON for Asia 9pm
        if current_min >= start_min:
            return True
        else:
            print(f"[SCHEDULE] Sunday {hour:02d}:{minute:02d} UTC - Waiting 19:30 UTC (8:30pm WAT) for Asia Open", flush=True)
            return False
    # Mon-Fri ON 24/7
    return True

def get_dxy_bias():
    global last_eur_usd
    eur_usd = None
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=EUR&to=USD", timeout=4)
        eur_usd = float(r.json()['rates']['USD'])
    except:
        try:
            r = requests.get("https://api.exchangerate.host/latest?base=EUR&symbols=USD", timeout=4)
            eur_usd = float(r.json()['rates']['USD'])
        except:
            return "NEUTRAL", 0, 0
    if last_eur_usd is None:
        last_eur_usd = eur_usd
        return "NEUTRAL", 0, eur_usd
    change_pct = ((eur_usd - last_eur_usd) / last_eur_usd) * 100
    last_eur_usd = eur_usd
    if change_pct > 0.15:
        return "DXY_DOWN", change_pct, eur_usd
    elif change_pct < -0.15:
        return "DXY_UP", change_pct, eur_usd
    return "NEUTRAL", change_pct, eur_usd

def get_btc_dominance_change():
    """C) Dominance Filter"""
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=5)
        dom = float(r.json()['data']['market_cap_percentage']['btc'])
        if not hasattr(get_btc_dominance_change, 'last'):
            get_btc_dominance_change.last = dom
            return 0, dom
        change = dom - get_btc_dominance_change.last
        get_btc_dominance_change.last = dom
        return change, dom
    except:
        return 0, 60.0

def get_liquidation_map():
    """Liquidation voids - you fit later connect Coinglass API"""
    return {78500: 50_000_000, 77200: 40_000_000, 79000: 70_000_000}

def is_fake_wick_detector(price_change_1m, dom_change):
    """Your $350 wick trap - knows via dominance"""
    if 300 <= abs(price_change_1m) <= 450:
        if abs(dom_change) < 0.15:
            print(f"[FAKE WICK] ${price_change_1m:.0f} wick but dom {dom_change:.2f}% - TRAP! PEEK 60s", flush=True)
            return True
    return False

def is_bank_whale_move(vol_1m, price_change, threshold):
    """B) Only BANK/BlackRock MAX moves"""
    if vol_1m >= threshold and abs(price_change) >= 100:
        print(f"[BANK WHALE] Vol ${vol_1m/1e6:.1f}M >= ${threshold/1e6}M | Move ${price_change:.0f} - REAL BANK!", flush=True)
        return True
    return False

def check_liq_hunt(live_price):
    liq_map = get_liquidation_map()
    for liq_price, liq_val in liq_map.items():
        if abs(live_price - liq_price) < 120 and liq_val > 20_000_000:
            print(f"[LIQ VOID TARGET] Price {live_price:.0f} near ${liq_price} void ${liq_val/1e6}M", flush=True)
            return liq_price, liq_val
    return None, 0

# === HEALTH SERVER ===
class HealthHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    def _get_status_text(self):
        try:
            bal = current_balance_cache
            pos = current_position if current_position else "No Position"
            thresh = get_whale_threshold()
            return f"V5.3 FINAL ALIVE | Bal ${bal:.2f} | {pos} | State {BOT_STATE} | Thresh ${thresh/1e6}M | Asia 8:30pm WAT ON"
        except:
            return "V5.3 ALIVE"
    def do_GET(self): self._set_headers(200); self.wfile.write(self._get_status_text().encode())
    def do_HEAD(self): self._set_headers(200)
    def do_POST(self): self.do_GET()
    def log_message(self, format, *args): return

def start_health_server():
    while True:
        try:
            port = int(os.environ.get("PORT", 10000))
            server = HTTPServer(('0.0.0.0', port), HealthHandler)
            print(f"[RENDER] Health on {port}", flush=True)
            server.serve_forever()
        except Exception as e:
            print(f"[HEALTH ERR] {e}", flush=True)
            time.sleep(5)

def keepalive_ping():
    while True:
        time.sleep(600)
        try:
            port = int(os.environ.get("PORT", 10000))
            requests.get(f"http://127.0.0.1:{port}", timeout=3)
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
        else:
            lev = 20
            qty = max(0.001, round((balance * 0.15 / price), 4))
        margin = (qty * price) / lev
        if margin > balance * 0.8:
            qty = 0.001
            lev = 60
        if last_leverage != lev:
            try:
                exchange.set_leverage(lev, SYMBOL_RAW)
                time.sleep(0.5)
                last_leverage = lev
                print(f"[LEV] {lev}x", flush=True)
            except: pass
        print(f"[SMART] Bal ${balance:.2f} -> Qty {qty} Lev {lev}x", flush=True)
        return qty, lev
    except:
        return 0.001, 60

def close_position(direction, qty):
    try:
        try: exchange.cancel_all_orders(SYMBOL)
        except: pass
        side = 'sell' if direction == "LONG" else 'buy'
        exchange.create_order(SYMBOL, 'market', side, qty, None, {'reduceOnly': True})
        print(f"[CLOSE] {direction} {qty}", flush=True)
        return True
    except Exception as e:
        try:
            side = 'sell' if direction == "LONG" else 'buy'
            exchange.create_order(SYMBOL, 'market', side, qty)
            return True
        except Exception as e2:
            print(f"[CLOSE FAIL] {e2}", flush=True)
            return False

def monitor_trade(entry_price, sl_price, tp_price, destination, direction, qty):
    global BOT_STATE, BOT_STATE_UNTIL
    print(f"[MONITOR] Dest ${destination} SL ${MIN_SL}-{MAX_SL} | State {BOT_STATE}", flush=True)
    entry_time = time.time()
    last_heartbeat = time.time()
    while True:
        try:
            _, _, curr = get_real_1m_volume_and_change()
            elapsed = (time.time() - entry_time) / 3600
            if time.time() - last_heartbeat > 900:
                pnl = curr - entry_price if direction=="LONG" else entry_price - curr
                print(f"[HEARTBEAT] {direction} {elapsed:.1f}h PnL ${pnl:.2f} Bal ${get_balance():.2f}", flush=True)
                last_heartbeat = time.time()
            if elapsed >= MAX_HOLD_HOURS:
                print(f"[MAX HOLD] {elapsed:.1f}h -> CLOSE", flush=True)
                close_position(direction, qty)
                BOT_STATE = "HUNTING"
                return False
            liq_price, _ = check_liq_hunt(curr)
            if liq_price:
                if (direction=="LONG" and curr >= liq_price) or (direction=="SHORT" and curr <= liq_price):
                    print(f"[VOID SWEPT] ${liq_price} hunted! Calm 5 min spectate", flush=True)
                    close_position(direction, qty)
                    BOT_STATE = "SPECTATING"
                    BOT_STATE_UNTIL = time.time() + 300
                    return False
            pnl = curr - entry_price if direction=="LONG" else entry_price - curr
            if pnl > 100 and sl_price != entry_price:
                sl_price = entry_price
                print(f"[BE LOCKED] SL->Entry", flush=True)
            if (direction=="LONG" and curr >= tp_price) or (direction=="SHORT" and curr <= tp_price):
                print(f"[TP] ${destination} hit!", flush=True)
                close_position(direction, qty)
                return False
            if (direction=="LONG" and curr <= sl_price) or (direction=="SHORT" and curr >= sl_price):
                print(f"[SL] hit", flush=True)
                close_position(direction, qty)
                return False
            time.sleep(1)
        except Exception as e:
            print(f"[MONITOR ERR] {e}", flush=True)
            time.sleep(1)

def open_trade(direction, destination):
    global current_position, pending_trade, BOT_STATE, BOT_STATE_UNTIL
    now = datetime.now(timezone.utc)
    # Asia 8:30pm WAT check
    if not is_asia_open_time():
        if now.weekday() == 5:
            print(f"[WEEKEND OFF] Saturday - Waiting Sunday 8:30pm WAT", flush=True)
        time.sleep(60)
        return False
    # Spectate after void hunt
    if BOT_STATE == "SPECTATING" and time.time() < BOT_STATE_UNTIL:
        print(f"[SPECTATE] Calm {(BOT_STATE_UNTIL-time.time())/60:.1f}m left - watching where market dey go", flush=True)
        time.sleep(10)
        return False
    elif BOT_STATE == "SPECTATING":
        BOT_STATE = "HUNTING"
    if current_position is not None and pending_trade is None:
        pending_trade = (direction, destination)
        print(f"[RIGHT HAND] In {current_position}, keeping {direction} ${destination} behind", flush=True)
        return False
    try:
        vol_1m, price_change_1m, price = get_real_1m_volume_and_change()
        whale_thresh = get_whale_threshold()
        dom_change, dom_val = get_btc_dominance_change()
        dxy_bias, dxy_change, eur = get_dxy_bias()

        # B) Whale filter - BANK ONLY
        if not is_bank_whale_move(vol_1m, price_change_1m, whale_thresh):
            if abs(dom_change) < 0.3 and dxy_bias == "NEUTRAL":
                return False

        # Fake $350 wick detector + PEEK vigilant
        if is_fake_wick_detector(price_change_1m, dom_change):
            print(f"[PEEK MODE] Vigilant 60s - checking if continuation or dump back", flush=True)
            time.sleep(60)
            _, new_change, new_price = get_real_1m_volume_and_change()
            if new_price > price:
                direction = "LONG"
                print(f"[PEEK] Continuation UP - follow", flush=True)
            elif new_price < price:
                direction = "SHORT"
                print(f"[PEEK] Dump back DOWN - follow", flush=True)

        # C) Dominance follows pusher + Liq void check
        liq_price, liq_val = check_liq_hunt(price)
        if liq_price and liq_val > 30_000_000:
            direction = "LONG" if price < liq_price else "SHORT"
            print(f"[HUNT WITH WHALE] Targeting void ${liq_price}", flush=True)

        if dom_change > 0.3 and price_change_1m > 0:
            direction = "LONG"
            print(f"[DOM] BTC dom +{dom_change:.2f}% + price up -> BANK BUY -> LONG", flush=True)
        elif dom_change < -0.3 and price_change_1m < 0:
            direction = "SHORT"
            print(f"[DOM] dom {dom_change:.2f}% + price down -> BANK SELL -> SHORT", flush=True)

        if dxy_bias == "DXY_UP" and direction == "LONG" and vol_1m < 100_000_000:
            direction = "SHORT"
            print(f"[DXY FOLLOW] DXY UP -> SHORT", flush=True)
        elif dxy_bias == "DXY_DOWN" and direction == "SHORT" and vol_1m < 100_000_000:
            direction = "LONG"
            print(f"[DXY FOLLOW] DXY DOWN -> LONG", flush=True)

        bal = get_balance()
        if bal < 1.0:
            print(f"[BAL LOW] ${bal:.2f}", flush=True)
            time.sleep(10)
            return False

        qty, lev = get_smart_lot_and_leverage(bal, price)
        sl_dist = random.randint(MIN_SL, MAX_SL)
        sl = price - sl_dist if direction=="LONG" else price + sl_dist
        tp = price + destination if direction=="LONG" else price - destination

        # A) LIMIT ORDER - No $800 slippage
        limit_price = price + LIMIT_OFFSET if direction=="LONG" else price - LIMIT_OFFSET
        side = 'buy' if direction=="LONG" else 'sell'
        print(f"[ENTRY] {direction} LIMIT @{limit_price} (live {price}) Qty {qty} Lev {lev}x Dest ${destination} | DXY:{dxy_bias} DOM:{dom_val:.1f}% Thresh ${whale_thresh/1e6}M", flush=True)
        order = exchange.create_order(SYMBOL, 'limit', side, qty, limit_price)
        
        filled = False
        filled_price = limit_price
        for i in range(12):
            time.sleep(1)
            try:
                od = exchange.fetch_order(order['id'], SYMBOL)
                if od['filled'] and od['filled'] > 0:
                    filled = True
                    filled_price = float(od['average']) if od['average'] else limit_price
                    print(f"[FILLED] @{filled_price} after {i+1}s - No slippage!", flush=True)
                    break
            except: pass
        if not filled:
            print(f"[LIMIT FAIL] Cancel - market run too fast", flush=True)
            try: exchange.cancel_order(order['id'], SYMBOL)
            except: pass
            return False

        current_position = direction
        should_switch = monitor_trade(filled_price, sl, tp, destination, direction, qty)
        current_position = None
        if should_switch or pending_trade:
            return True
    except Exception as e:
        print(f"[OPEN ERR] {e}", flush=True)
        time.sleep(2)
    return False

def start_bot():
    global pending_trade
    print("="*60, flush=True)
    print("HANDSOME BOY V5.3 FINAL - FULL COMBINED", flush=True)
    print("WHALE_LIMIT + ASIA 8:30pm WAT + LIQ MAP + FAKE WICK", flush=True)
    print("="*60, flush=True)
    print(f"[START BAL] ${get_balance():.2f} | Now {datetime.now(timezone.utc).strftime('%A %H:%M UTC')}", flush=True)
    while True:
        try:
            if not is_asia_open_time():
                time.sleep(60)
                continue
            if pending_trade:
                print(f"[SWITCH] Fast 0.5s -> {pending_trade}", flush=True)
                time.sleep(0.5)
                nd, nDest = pending_trade
                pending_trade = None
                open_trade(nd, nDest)
            else:
                vol_1m, price_change_1m, price = get_real_1m_volume_and_change()
                whale_thresh = get_whale_threshold()
                if vol_1m >= whale_thresh:
                    dest = random.randint(1000, 2500)
                    dir_choice = "LONG" if price_change_1m > 0 else "SHORT"
                    print(f"\n[SCAN] Whale {vol_1m/1e6:.1f}M >= {whale_thresh/1e6}M | {dir_choice} ${dest} | Bal ${get_balance():.2f}", flush=True)
                    open_trade(dir_choice, dest)
                else:
                    time.sleep(1)  # E) Fast execution 1 sec
                    continue
            time.sleep(1)
        except Exception as e:
            print(f"[MAIN ERR] {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
