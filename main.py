# HANDSOME BOY V4.4.32 - DXY BRAIN + MARKET DRIVER - FINAL MASTER
# Gee's $5 to $1000 - 0.001 + 20x-60x + DXY Filter + No Error

import time, random, ccxt, os, requests
from datetime import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ===== CONFIG =====
API_KEY = os.environ.get("BYBIT_KEY", "YOUR_BYBIT_KEY")
API_SECRET = os.environ.get("BYBIT_SECRET", "YOUR_BYBIT_SECRET")
SYMBOL = "BTC/USDT:USDT"
SYMBOL_RAW = "BTCUSDT"
MIN_SL = 600
MAX_SL = 800

current_position = None
pending_trade = None
last_leverage = None
last_eur_usd = None  # For DXY proxy

exchange = ccxt.bybit({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})

if API_KEY == "YOUR_BYBIT_KEY":
    print("[WARNING] Set BYBIT_KEY + BYBIT_SECRET in Render Env!")
else:
    print(f"[KEYS] Loaded - V4.4.32 DXY Brain Ready")

try:
    exchange.set_position_mode(False, SYMBOL_RAW)
    print("[MODE] One-Way Mode set")
except Exception as e:
    print(f"[MODE] Already One-Way - {e}")

# ===== RENDER HEALTH =====
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Handsome Boy V4.4.32 - DXY + Market Driver - Alive")
    def log_message(self, format, *args):
        return

def start_health_server():
    while True:
        try:
            port = int(os.environ.get("PORT", 10000))
            server = HTTPServer(('0.0.0.0', port), HealthHandler)
            print(f"[RENDER] Health on {port}")
            server.serve_forever()
        except Exception as e:
            print(f"[HEALTH ERR] {e} - restart 5sec")
            time.sleep(5)

threading.Thread(target=start_health_server, daemon=True).start()

def get_balance():
    try:
        bal_data = exchange.fetch_balance()
        try:
            if 'USDT' in bal_data and isinstance(bal_data['USDT'], dict):
                if 'free' in bal_data['USDT'] and bal_data['USDT']['free'] is not None:
                    return float(bal_data['USDT']['free'])
        except: pass
        try:
            if 'free' in bal_data and 'USDT' in bal_data['free']:
                if bal_data['free']['USDT'] is not None:
                    return float(bal_data['free']['USDT'])
        except: pass
        try:
            if 'total' in bal_data and 'USDT' in bal_data['total']:
                if bal_data['total']['USDT'] is not None:
                    return float(bal_data['total']['USDT'])
        except: pass
        return 5.0
    except Exception as e:
        print(f"[BAL ERR] {e} - using $5 default")
        return 5.0

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
                print(f"[LEV SET] {lev}x + 0.5s safe")
            except:
                try:
                    exchange.set_leverage(lev, SYMBOL)
                    time.sleep(0.5)
                    last_leverage = lev
                except Exception as e:
                    print(f"[LEV] Keep {lev}x - {e}")
                    last_leverage = lev
        print(f"[SMART] Bal ${balance:.2f} -> Qty {qty} Lev {lev}x")
        return qty, lev
    except:
        return 0.001, 60

# ===== NEW DXY BRAIN - FOLLOW DXY OR MARKET =====
def get_dxy_bias():
    global last_eur_usd
    try:
        # Use EUR/USD as DXY proxy (57% of DXY) - EUR up = DXY down
        resp = requests.get("https://api.frankfurter.app/latest?from=EUR&to=USD", timeout=4)
        data = resp.json()
        eur_usd = float(data['rates']['USD'])
        
        if last_eur_usd is None:
            last_eur_usd = eur_usd
            print(f"[DXY] Init EUR/USD {eur_usd:.5f} -> NEUTRAL")
            return "NEUTRAL", 0
        
        change_pct = ((eur_usd - last_eur_usd) / last_eur_usd) * 100
        last_eur_usd = eur_usd
        
        # DXY logic: EUR up = DXY down
        if change_pct > 0.15:
            print(f"[DXY] EUR/USD UP {change_pct:.3f}% => DXY DOWN STRONG -> BTC BULL")
            return "DXY_DOWN", change_pct  # Dollar weak -> BTC up
        elif change_pct < -0.15:
            print(f"[DXY] EUR/USD DOWN {change_pct:.3f}% => DXY UP STRONG -> BTC BEAR")
            return "DXY_UP", change_pct  # Dollar strong -> BTC down
        else:
            print(f"[DXY] EUR/USD {change_pct:.3f}% => DXY NEUTRAL -> FOLLOW MARKET")
            return "NEUTRAL", change_pct
            
    except Exception as e:
        print(f"[DXY ERR] {e} -> NEUTRAL follow market")
        return "NEUTRAL", 0

def world_dominance_check(curr, entry_price):
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        vol = ticker['quoteVolume'] or 0
        move = abs(curr - entry_price) if entry_price else 0
        if vol > 50000000 and move > 200:
            return random.randint(1000, 2500)
        return 0
    except:
        return 0

def close_position(direction, qty):
    try:
        side = 'sell' if direction == "LONG" else 'buy'
        exchange.create_order(SYMBOL, 'market', side, qty)
        print(f"[LEFT HAND] Closed {direction} {qty}")
        return True
    except:
        time.sleep(0.5)
        try:
            exchange.create_order(SYMBOL, 'market', side, qty)
            return True
        except:
            return False

def monitor_trade(entry_price, sl_price, tp_price, destination, direction, qty):
    global pending_trade
    print(f"[MONITOR] Dest ${destination}")
    while True:
        try:
            curr = exchange.fetch_ticker(SYMBOL)['last']
            bal = get_balance()
            new_impulse = world_dominance_check(curr, entry_price)
            if new_impulse >= 1000 and new_impulse > destination:
                print(f"[ALERT] NEW WINNER ${new_impulse} > ${destination}")
                pending_trade = ("LONG" if curr > entry_price else "SHORT", new_impulse)
                print(f"[RIGHT HAND] ${new_impulse} behind back")
                if close_position(direction, qty):
                    time.sleep(5)
                    return True
            elif new_impulse and new_impulse < 800:
                print(f"[WORLD] Small ${new_impulse} IGNORE")
            pnl = curr - entry_price if direction=="LONG" else entry_price - curr
            if bal < 100:
                if pnl > 100:
                    print("[BE SKIP] <$100 mental only")
            else:
                if pnl > 100 and sl_price != entry_price:
                    sl_price = entry_price
                    print("[BE LOCKED] >=$100 SL->Entry")
            if (direction=="LONG" and curr >= tp_price) or (direction=="SHORT" and curr <= tp_price):
                print(f"[TP] ${destination} hit!")
                close_position(direction, qty)
                return False
            if (direction=="LONG" and curr <= sl_price) or (direction=="SHORT" and curr >= sl_price):
                print(f"[SL] {MIN_SL}-{MAX_SL} hit")
                close_position(direction, qty)
                return False
            time.sleep(1)
        except Exception as e:
            print(f"[MONITOR ERR] {e}")
            time.sleep(1)

def open_trade(direction, destination):
    global current_position, pending_trade
    if datetime.utcnow().weekday() >= 5:
        print("[NEURAL WEEKEND] Sat/Sun - 1hr check")
        time.sleep(3600)
        return False
    if current_position is not None and pending_trade is None:
        pending_trade = (direction, destination)
        print(f"[RIGHT HAND] In {current_position}, keeping {direction} ${destination} behind")
        return False
    try:
        # ===== DXY + MARKET DRIVER LOGIC =====
        dxy_bias, dxy_change = get_dxy_bias()
        
        # If DXY strongly up and we want LONG -> block, follow DXY (only SHORT)
        if dxy_bias == "DXY_UP" and direction == "LONG":
            print(f"[DXY FILTER] DXY UP STRONG - BLOCK LONG {destination} - Follow DXY, SHORT only")
            # If market driver strong (high vol), allow override
            price_tmp = exchange.fetch_ticker(SYMBOL)['last']
            vol_tmp = exchange.fetch_ticker(SYMBOL)['quoteVolume'] or 0
            if vol_tmp > 100000000:  # Very high BTC volume = market bigger than DXY
                print(f"[MARKET OVERRIDE] BTC Vol ${vol_tmp} > 100M - Market bigger than DXY - ALLOW LONG")
            else:
                direction = "SHORT"  # Follow DXY
                print(f"[DXY FOLLOW] Switched to SHORT ${destination}")
        
        # If DXY strongly down and we want SHORT -> block
        elif dxy_bias == "DXY_DOWN" and direction == "SHORT":
            print(f"[DXY FILTER] DXY DOWN STRONG - BLOCK SHORT {destination} - Follow DXY, LONG only")
            price_tmp = exchange.fetch_ticker(SYMBOL)['last']
            vol_tmp = exchange.fetch_ticker(SYMBOL)['quoteVolume'] or 0
            if vol_tmp > 100000000:
                print(f"[MARKET OVERRIDE] BTC Vol ${vol_tmp} > 100M - Market bigger than DXY - ALLOW SHORT")
            else:
                direction = "LONG"
                print(f"[DXY FOLLOW] Switched to LONG ${destination}")
        else:
            print(f"[DRIVER] {dxy_bias} - Follow Market: {direction} ${destination}")
        
        price = exchange.fetch_ticker(SYMBOL)['last']
        bal = get_balance()
        qty, lev = get_smart_lot_and_leverage(bal, price)
        sl_dist = random.randint(MIN_SL, MAX_SL)
        sl = price - sl_dist if direction=="LONG" else price + sl_dist
        tp = price + destination if direction=="LONG" else price - destination
        side = 'buy' if direction=="LONG" else 'sell'
        exchange.create_order(SYMBOL, 'market', side, qty)
        current_position = direction
        print(f"\n[ENTRY] {direction} @ {price} Qty {qty} Lev {lev}x SL {sl_dist} Dest ${destination} | DXY:{dxy_bias}")
        should_switch = monitor_trade(price, sl, tp, destination, direction, qty)
        current_position = None
        if should_switch or pending_trade:
            return True
    except Exception as e:
        print(f"[OPEN ERR] {e}")
        time.sleep(2)
    return False

def start_bot():
    global pending_trade
    print("="*60)
    print("HANDSOME BOY V4.4.32 DXY + MARKET DRIVER")
    print("0.001 + 20x-60x + DXY Brain + No Error")
    print("="*60)
    while True:
        try:
            if pending_trade:
                print("[SWITCH] Right hand 0.5sec fast!")
                time.sleep(0.5)
                nd, nDest = pending_trade
                pending_trade = None
                open_trade(nd, nDest)
            else:
                dest = random.randint(600, 3000)
                dir = random.choice(["LONG","SHORT"])
                print(f"\n[SCAN] Dest ${dest} {dir}")
                switched = open_trade(dir, dest)
                if switched and pending_trade:
                    continue
            time.sleep(5)
        except Exception as e:
            print(f"[MAIN ERR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
