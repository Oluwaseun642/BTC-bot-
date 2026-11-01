# HANDSOME BOY V4.4.37 - NO BUFFER - INSTANT LOGS
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

if API_KEY == "YOUR_BYBIT_KEY":
    print("[WARNING] Set BYBIT_KEY + SECRET in Render Env!", flush=True)
else:
    print(f"[KEYS] V4.4.37 No-Buffer Ready", flush=True)

try:
    exchange.set_position_mode(False, SYMBOL_RAW)
    print("[MODE] One-Way Mode set", flush=True)
except Exception as e:
    print(f"[MODE] Already One-Way - {e}", flush=True)

def get_balance():
    global current_balance_cache
    try:
        bal_data = exchange.fetch_balance()
        val = None
        try:
            if 'USDT' in bal_data and isinstance(bal_data['USDT'], dict):
                if 'free' in bal_data['USDT'] and bal_data['USDT']['free'] is not None:
                    val = float(bal_data['USDT']['free'])
        except: pass
        if val is None:
            try:
                if 'free' in bal_data and 'USDT' in bal_data['free']:
                    val = float(bal_data['free']['USDT'])
            except: pass
        if val is None:
            try:
                if 'total' in bal_data and 'USDT' in bal_data['total']:
                    val = float(bal_data['total']['USDT'])
            except: pass
        if val is not None:
            current_balance_cache = val
            return val
        return current_balance_cache
    except Exception as e:
        print(f"[BAL ERR] {e} - using ${current_balance_cache} cache", flush=True)
        return current_balance_cache

def safe_ticker():
    for i in range(3):
        try:
            return exchange.fetch_ticker(SYMBOL)
        except Exception as e:
            print(f"[TICKER RETRY {i+1}/3] {e}", flush=True)
            time.sleep(1.5)
    raise Exception("Ticker failed 3 times")

class HealthHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    def _get_status_text(self):
        try:
            bal = current_balance_cache
            pos = current_position if current_position else "No Position"
            return f"handsome boy ALIVE - V4.4.37 | Bal ${bal:.2f} | {pos} | DXY Brain ON - No Hold Fix"
        except:
            return "handsome boy ALIVE - V4.4.37"
    def do_GET(self): self._set_headers(200); self.wfile.write(self._get_status_text().encode())
    def do_HEAD(self): self._set_headers(200)
    def do_POST(self): self.do_GET()
    def do_OPTIONS(self): self._set_headers(200)
    def do_PUT(self): self.do_GET()
    def do_DELETE(self): self.do_GET()
    def log_message(self, format, *args): return

def start_health_server():
    while True:
        try:
            port = int(os.environ.get("PORT", 10000))
            server = HTTPServer(('0.0.0.0', port), HealthHandler)
            print(f"[RENDER] Health on {port}", flush=True)
            server.serve_forever()
        except Exception as e:
            print(f"[HEALTH ERR] {e} - restart 5sec", flush=True)
            time.sleep(5)

def keepalive_ping():
    while True:
        time.sleep(600)
        try:
            port = int(os.environ.get("PORT", 10000))
            requests.get(f"http://127.0.0.1:{port}", timeout=3)
            print(f"[KEEPALIVE] Self-ping {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC", flush=True)
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
                print(f"[LEV SET] {lev}x + 0.5s safe", flush=True)
            except:
                try:
                    exchange.set_leverage(lev, SYMBOL)
                    time.sleep(0.5)
                    last_leverage = lev
                except Exception as e:
                    print(f"[LEV] Keep {lev}x - {e}", flush=True)
                    last_leverage = lev
        print(f"[SMART] Bal ${balance:.2f} -> Qty {qty} Lev {lev}x", flush=True)
        return qty, lev
    except:
        return 0.001, 60

def get_dxy_bias():
    global last_eur_usd
    eur_usd = None
    try:
        resp = requests.get("https://api.frankfurter.app/latest?from=EUR&to=USD", timeout=4)
        data = resp.json()
        eur_usd = float(data['rates']['USD'])
    except Exception as e1:
        try:
            resp = requests.get("https://api.exchangerate.host/latest?base=EUR&symbols=USD", timeout=4)
            data = resp.json()
            eur_usd = float(data['rates']['USD'])
            print(f"[DXY] Backup OK", flush=True)
        except Exception as e2:
            print(f"[DXY ERR] Both failed {e2} -> NEUTRAL", flush=True)
            return "NEUTRAL", 0
    if last_eur_usd is None:
        last_eur_usd = eur_usd
        print(f"[DXY] Init EUR/USD {eur_usd:.5f} -> NEUTRAL", flush=True)
        return "NEUTRAL", 0
    change_pct = ((eur_usd - last_eur_usd) / last_eur_usd) * 100
    last_eur_usd = eur_usd
    if change_pct > 0.15:
        print(f"[DXY] EUR/USD UP {change_pct:.3f}% => DXY DOWN -> BULL", flush=True)
        return "DXY_DOWN", change_pct
    elif change_pct < -0.15:
        print(f"[DXY] EUR/USD DOWN {change_pct:.3f}% => DXY UP -> BEAR", flush=True)
        return "DXY_UP", change_pct
    else:
        print(f"[DXY] EUR/USD {change_pct:.3f}% => NEUTRAL", flush=True)
        return "NEUTRAL", change_pct

def world_dominance_check(curr, entry_price):
    try:
        ticker = safe_ticker()
        vol = ticker['quoteVolume'] or 0
        move = abs(curr - entry_price) if entry_price else 0
        if vol > 50000000 and move > 200:
            return random.randint(1000, 2500)
        return 0
    except: return 0

def close_position(direction, qty):
    try:
        try: exchange.cancel_all_orders(SYMBOL)
        except: pass
        side = 'sell' if direction == "LONG" else 'buy'
        exchange.create_order(SYMBOL, 'market', side, qty, None, {'reduceOnly': True})
        print(f"[LEFT HAND] Closed {direction} {qty} reduceOnly", flush=True)
        return True
    except Exception as e:
        print(f"[CLOSE RETRY] {e}", flush=True)
        time.sleep(0.5)
        try:
            side = 'sell' if direction == "LONG" else 'buy'
            exchange.create_order(SYMBOL, 'market', side, qty)
            return True
        except Exception as e2:
            print(f"[CLOSE FAIL] {e2}", flush=True)
            return False

def monitor_trade(entry_price, sl_price, tp_price, destination, direction, qty):
    global pending_trade
    print(f"[MONITOR] Dest ${destination} SL ${MIN_SL}-{MAX_SL} MaxHold {MAX_HOLD_HOURS}h", flush=True)
    last_heartbeat = time.time()
    entry_time = time.time()
    while True:
        try:
            curr = safe_ticker()['last']
            elapsed = (time.time() - entry_time) / 3600
            if time.time() - last_heartbeat > 900:
                pnl = curr - entry_price if direction=="LONG" else entry_price - curr
                bal = get_balance()
                print(f"[HEARTBEAT] {direction} {elapsed:.1f}h alive | Curr ${curr} Entry ${entry_price} PnL ${pnl:.2f} | Bal ${bal:.2f}", flush=True)
                last_heartbeat = time.time()
            if elapsed >= MAX_HOLD_HOURS:
                print(f"[MAX HOLD] {elapsed:.1f}h >= {MAX_HOLD_HOURS}h -> FORCE CLOSE", flush=True)
                close_position(direction, qty)
                return False
            bal = get_balance()
            new_impulse = world_dominance_check(curr, entry_price)
            if new_impulse >= 1000 and new_impulse > destination:
                print(f"[ALERT] NEW WINNER ${new_impulse} > ${destination}", flush=True)
                pending_trade = ("LONG" if curr > entry_price else "SHORT", new_impulse)
                print(f"[RIGHT HAND] ${new_impulse} behind back", flush=True)
                if close_position(direction, qty):
                    time.sleep(5)
                    return True
            pnl = curr - entry_price if direction=="LONG" else entry_price - curr
            if pnl > 100 and sl_price != entry_price:
                sl_price = entry_price
                print(f"[BE LOCKED] PnL ${pnl:.2f} >=$100 SL->Entry ${sl_price}", flush=True)
            if (direction=="LONG" and curr >= tp_price) or (direction=="SHORT" and curr <= tp_price):
                print(f"[TP] ${destination} hit! {curr}", flush=True)
                close_position(direction, qty)
                return False
            if (direction=="LONG" and curr <= sl_price) or (direction=="SHORT" and curr >= sl_price):
                print(f"[SL] {MIN_SL}-{MAX_SL} hit {curr} vs {sl_price}", flush=True)
                close_position(direction, qty)
                return False
            time.sleep(1)
        except Exception as e:
            print(f"[MONITOR ERR] {e}", flush=True)
            time.sleep(1)

def open_trade(direction, destination):
    global current_position, pending_trade
    now_utc = datetime.now(timezone.utc)
    if now_utc.weekday() >= 5:
        for i in range(4):
            print(f"[NEURAL WEEKEND] Sat/Sun Alive {i+1}/4 - {60 - i*15}min left - {now_utc.strftime('%H:%M UTC')}", flush=True)
            time.sleep(900)
        return False
    if current_position is not None and pending_trade is None:
        pending_trade = (direction, destination)
        print(f"[RIGHT HAND] In {current_position}, keeping {direction} ${destination} behind", flush=True)
        return False
    try:
        dxy_bias, dxy_change = get_dxy_bias()
        if dxy_bias == "DXY_UP" and direction == "LONG":
            print(f"[DXY FILTER] DXY UP - BLOCK LONG {destination}", flush=True)
            vol_tmp = safe_ticker()['quoteVolume'] or 0
            if vol_tmp > 100000000:
                print(f"[MARKET OVERRIDE] Vol > 100M - ALLOW LONG", flush=True)
            else:
                direction = "SHORT"
                print(f"[DXY FOLLOW] Switched to SHORT ${destination}", flush=True)
        elif dxy_bias == "DXY_DOWN" and direction == "SHORT":
            print(f"[DXY FILTER] DXY DOWN - BLOCK SHORT {destination}", flush=True)
            vol_tmp = safe_ticker()['quoteVolume'] or 0
            if vol_tmp > 100000000:
                print(f"[MARKET OVERRIDE] Vol > 100M - ALLOW SHORT", flush=True)
            else:
                direction = "LONG"
                print(f"[DXY FOLLOW] Switched to LONG ${destination}", flush=True)
        else:
            print(f"[DRIVER] {dxy_bias} - Follow Market: {direction} ${destination}", flush=True)
        price = safe_ticker()['last']
        bal = get_balance()
        if bal < 1.0:
            print(f"[BAL LOW] ${bal:.2f} too low - skip", flush=True)
            time.sleep(10)
            return False
        qty, lev = get_smart_lot_and_leverage(bal, price)
        sl_dist = random.randint(MIN_SL, MAX_SL)
        sl = price - sl_dist if direction=="LONG" else price + sl_dist
        tp = price + destination if direction=="LONG" else price - destination
        side = 'buy' if direction=="LONG" else 'sell'
        exchange.create_order(SYMBOL, 'market', side, qty)
        current_position = direction
        print(f"\n[ENTRY] {direction} @ {price} Qty {qty} Lev {lev}x SL {sl_dist} Dest ${destination} | DXY:{dxy_bias}", flush=True)
        should_switch = monitor_trade(price, sl, tp, destination, direction, qty)
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
    print("HANDSOME BOY V4.4.37 FINAL - NO BUFFER", flush=True)
    print("No Hold + Instant Logs + No Spin-Down", flush=True)
    print("="*60, flush=True)
    print(f"[START BAL] ${get_balance():.2f}", flush=True)
    while True:
        try:
            if pending_trade:
                print(f"[SWITCH] Right hand 0.5sec fast! -> {pending_trade}", flush=True)
                time.sleep(0.5)
                nd, nDest = pending_trade
                pending_trade = None
                open_trade(nd, nDest)
            else:
                dest = random.randint(600, 3000)
                dir = random.choice(["LONG","SHORT"])
                print(f"\n[SCAN] Dest ${dest} {dir} - {datetime.now(timezone.utc).strftime('%H:%M UTC')} - Bal ${get_balance():.2f}", flush=True)
                switched = open_trade(dir, dest)
                if switched and pending_trade:
                    continue
            time.sleep(5)
        except Exception as e:
            print(f"[MAIN ERR] {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
