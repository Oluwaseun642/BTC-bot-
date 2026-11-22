# ============================================================
# MAIN.PY V16.2 - PATCHED FROM V16.1
# BE = CLOSE Normal $800 / Hunt $600, TP Backup $1200
# Hunt SL $1000 / Normal SL $1200, CALM 150s After EVERY Big/Normal Trade/Fake/Flip
# Flip 3-Ways: Normal->Hunt, Hunt->Normal (Wide), Hunt->Normal (Exhausted)
# TIER2 + 2 Confirmations, Wide Cert -> Normal, Chase Fake + Eat Bounce
# Qty NOT touched - Full Qty for Hunt + Normal + Flip + Pile-Up (sync from current code)
# --- V16.1: PILE-UPS TRADING MODE - PART 2 FOR MAIN.PY ---
# Pro-Type Calm Hunters Flip: Seamless, no hard max, escalating strictness
# Re-Pile Certain only -> flip immediately, no wait $300 to SL
# No fixed TP for Pile-Up: Follow until Done / Done For (Void Eaten Live + 1 confirm)
# Cooldowns separate: Pile-Up 60s-150s only, Big/Normal 2-3 mins (CALM 150s) only
# --- V16.2: PRE-ENTRY PILE-UP BYPASS ---
# Pre-Entry lock holds Normal/Hunt/Fake/Wide, but NOT Pile-Up Certain.
# Pile-Up hunters pile BEFORE entry - we hunt them there, no wait NY open.
# Fresh Pile-Up entry (from flat) has no original dir -> on Done, CLOSE + CALM + reset, no flip-back to nothing.
# No 4-5 confirmations, No 1-flip limit, No qty/leverage code here - reuse current code
# NO First Aid - NO Daily Loss Hard-Code - NO duplicates - NO dead code
# ============================================================
import os, time, threading, hmac, hashlib, json
from datetime import datetime, timezone
import requests

# --- V13 KEEP-ALIVE: Flask + Self-Ping ---
try:
    from flask import Flask
    _flask_app = Flask(__name__)
    @_flask_app.route("/")
    def _health(): return "BOT ALIVE V16.2 - TIER2 + FLIP 3-WAYS + PILE-UP + PRE-ENTRY BYPASS", 200
    @_flask_app.route("/health")
    def _health2(): return "OK", 200
    def _run_flask():
        try:
            port = int(os.getenv("PORT", 10000))
            _flask_app.run(host="0.0.0.0", port=port, use_reloader=False)
        except Exception as e: print(f"Flask error {e}", flush=True)
    threading.Thread(target=_run_flask, daemon=True).start()
    print("Flask keep-alive ON", flush=True)
except Exception as e: print(f"Flask OFF {e}", flush=True)

def _self_ping_loop():
    SELF_URL = os.getenv("RENDER_URL", "https://YOUR-BOT-NAME.onrender.com/")
    while True:
        try:
            time.sleep(240); requests.get(SELF_URL, timeout=10); print("SELF-PING OK", flush=True)
        except Exception as e: print(f"SELF-PING FAIL {e}", flush=True)
threading.Thread(target=_self_ping_loop, daemon=True).start()

try:
    import data_engine as DE
    print("✅ Data Engine Connected V16.2", flush=True)
    HAS_DE = True
except Exception as e:
    DE = None; HAS_DE = False
    print(f"❌ Data Engine NOT Found: {e}", flush=True)

BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "").strip()
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
SYMBOL = "BTCUSDT"; CATEGORY = "linear"; BASE_URL = "https://api.bybit.com"

# --- V16 NUMBERS: BE = CLOSE - QTY NOT TOUCHED - NO DAILY LOSS HARD-CODE ---
NORMAL_BE_USD = 800.0; HUNT_BE_USD = 600.0
NORMAL_TP_USD = 1200.0; HUNT_TP_USD = 1200.0
NORMAL_SL_USD = 1200.0; HUNT_SL_USD = 1000.0
CERT_MIN = 75.0; CERT_HUNT = 85.0
CALM_SEC = 150
QTY_BASE = 0.010; QTY_STEP = 0.005; QTY_MIN = 0.001; REAL_MAX_QTY = 0.100
FEE_RATE = 0.0006
balance = 0.0; leverage = 25
in_position = False; side = None; entry = 0.0; qty = 0.0
mode = "NORMAL"
daily_pnl = 0.0; wins = 0; losses = 0; breakevens = 0
recheck_until = 0; recheck_dir = None; recheck_mode = None
last_flip_time = 0

def log(msg): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)
def tg(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

# ============================================================
# PILE-UPS TRADING MODE - PART 2 FOR MAIN.PY
# Flip brain only. No detection, no qty, no leverage.
# Uses DE.is_pileup_done / DE.decay_pileup_by_1 / DE.reset_pileup / DE.remember_void
# ============================================================
def is_repile_certain(pileup_count, hunt_score, cvd_agg, direction_against_position,
                      two_candles_confirm=False, void_is_fresh=True,
                      expected_move_to_void=0.0, flip_number=1,
                      price_already_moved_for_pile=0.0, cert_vivid_against_pileup=False):
    if pileup_count < 3:
        return False, f"Re-Pile NOT certain - Count {pileup_count}/3 < 3"
    if hunt_score < 4:
        return False, f"Re-Pile NOT certain - Score {hunt_score} < 4"
    if direction_against_position == "UP" and cvd_agg != "BUY":
        return False, f"Re-Pile NOT certain - CVD {cvd_agg} != BUY for UP pile-up"
    if direction_against_position == "DOWN" and cvd_agg != "SELL":
        return False, f"Re-Pile NOT certain - CVD {cvd_agg} != SELL for DOWN pile-up"
    if not two_candles_confirm:
        return False, "Re-Pile NOT certain - Need 2 candles confirm, no be one wick"
    if expected_move_to_void < 150:
        return False, f"Re-Pile NOT certain - Expected move ${expected_move_to_void:.0f} < $150 - fees go chop am, hold"
    if flip_number >= 3 and not void_is_fresh:
        return False, f"Re-Pile NOT certain - Flip #{flip_number} needs fresh void, old void don chop"
    if flip_number >= 5:
        if hunt_score < 5:
            return False, f"Re-Pile NOT certain - Flip #{flip_number} needs Score 5, got {hunt_score}"
        if price_already_moved_for_pile < 200:
            return False, f"Re-Pile NOT certain - Flip #{flip_number} needs price don move $200 for pile, got ${price_already_moved_for_pile:.0f}"
        if cert_vivid_against_pileup:
            return False, f"Re-Pile NOT certain - Flip #{flip_number} + Cert vivid against pile-up - hold"
    return True, f"Re-Pile CERTAIN - Flip #{flip_number} - Count {pileup_count}/3 Score {hunt_score} CVD {cvd_agg} 2 candles Void fresh Move ${expected_move_to_void:.0f} - Flip IMMEDIATELY, no wait $300 to SL"

class PileupFlipBrain:
    def __init__(self):
        self.original_dir = None
        self.original_entry = 0.0
        self.original_cert = 0.0
        self.original_mode = "NORMAL"
        self.in_pileup_hunt = False
        self.pileup_dir = None
        self.pileup_flip_count = 0
        self.last_pileup_flip_ts = 0.0
        self.last_pileup_done_ts = 0.0
        self.void_remembered_for = None
    def save_original(self, direction, entry, cert, mode_="NORMAL"):
        if self.original_dir is None:
            self.original_dir = direction; self.original_entry = float(entry or 0)
            self.original_cert = float(cert or 0); self.original_mode = mode_ or "NORMAL"
        return self.original_dir
    def can_flip_pileup_now(self, now_ts=None):
        now_ts = now_ts or time.time()
        elapsed = now_ts - self.last_pileup_flip_ts if self.last_pileup_flip_ts else 9999
        if elapsed < 60:
            return False, f"Pile-Up 60s cooldown - {int(60 - elapsed)}s left, hold - same pile-up, no flip again"
        return True, "Pile-Up 60s cooldown passed - can flip"
    def should_flip_to_pileup(self, in_position_dir, pileup_up_active, pileup_down_active,
                              pileup_count, hunt_score, cvd_agg, two_candles_confirm,
                              void_is_fresh, expected_move_to_void, wide_cert, now_ts=None):
        now_ts = now_ts or time.time()
        if not in_position_dir or in_position_dir not in ("LONG", "SHORT"):
            return False, "No position - no flip to pile-up", None
        if wide_cert:
            return False, "Lock 2 - Wide Cert - ignore pile-up", None
        if in_position_dir == "SHORT" and not pileup_up_active:
            return False, "No UP pile-up opposite SHORT", None
        if in_position_dir == "LONG" and not pileup_down_active:
            return False, "No DOWN pile-up opposite LONG", None
        pileup_dir = "LONG" if in_position_dir == "SHORT" else "SHORT"
        dir_against = "UP" if pileup_dir == "LONG" else "DOWN"
        next_flip_no = self.pileup_flip_count + 1
        certain, reason = is_repile_certain(pileup_count=pileup_count, hunt_score=hunt_score, cvd_agg=cvd_agg,
            direction_against_position=dir_against, two_candles_confirm=two_candles_confirm,
            void_is_fresh=void_is_fresh, expected_move_to_void=expected_move_to_void, flip_number=next_flip_no)
        if not certain:
            return False, reason, None
        can_flip, cool_reason = self.can_flip_pileup_now(now_ts)
        if not can_flip:
            return False, cool_reason, None
        return True, f"FLIP TO PILE-UP {pileup_dir} - {reason}", pileup_dir
    def should_flip_back_to_original(self, is_pileup_done_fn, price, liq_now, ob_wall_now, k1_norm,
                                     hunt_score, cvd_agg, cert_against_pileup=False):
        if not self.in_pileup_hunt or not self.pileup_dir:
            return False, "Not in pile-up hunt - no flip back", None
        dir_against = "UP" if self.pileup_dir == "LONG" else "DOWN"
        done, reason = is_pileup_done_fn(dir_against, price, liq_now, ob_wall_now, k1_norm,
                                          hunt_score, cvd_agg, cert_against_pileup)
        if not done:
            return False, reason, None
        if not self.original_dir:
            return True, f"PILE-UP DONE (fresh entry, no original) - {reason} - CLOSE + CALM, no flip-back to nothing", "CLOSE"
        return True, f"FLIP BACK TO ORIGINAL {self.original_dir} - {reason} - Take profit from pile-up, follow original bounce", self.original_dir
    def mark_flip_to_pileup(self, pileup_dir, original_dir, entry, cert, mode_="NORMAL", reset_pileup_fn=None, now_ts=None):
        self.save_original(original_dir, entry, cert, mode_)
        self.in_pileup_hunt = True; self.pileup_dir = pileup_dir
        self.pileup_flip_count += 1; self.last_pileup_flip_ts = now_ts or time.time()
        if reset_pileup_fn:
            dir_against = "UP" if pileup_dir == "LONG" else "DOWN"
            reset_pileup_fn(dir_against)
        return self.pileup_flip_count
    def mark_fresh_pileup_entry(self, pileup_dir, now_ts=None):
        # Fresh entry from flat: no original to flip back to. Keep original_dir = None on purpose.
        self.original_dir = None; self.original_entry = 0.0; self.original_cert = 0.0; self.original_mode = "PILEUP"
        self.in_pileup_hunt = True; self.pileup_dir = pileup_dir
        self.pileup_flip_count = 1; self.last_pileup_flip_ts = now_ts or time.time()
        return self.pileup_flip_count
    def mark_flip_back_to_original(self, now_ts=None):
        self.in_pileup_hunt = False; self.pileup_dir = None
        self.last_pileup_flip_ts = now_ts or time.time(); self.last_pileup_done_ts = now_ts or time.time()
        return self.original_dir
    def reset_after_big_or_normal_takeover(self):
        self.original_dir = None; self.original_entry = 0.0; self.original_cert = 0.0; self.original_mode = "NORMAL"
        self.in_pileup_hunt = False; self.pileup_dir = None; self.pileup_flip_count = 0
        self.last_pileup_flip_ts = 0.0; self.last_pileup_done_ts = 0.0; self.void_remembered_for = None

pileup_brain = PileupFlipBrain()
_pileup_decay_mark = {"price": 0.0}

def _two_candles_confirm(candles, want_dir):
    if not candles or len(candles) < 3: return False
    c1, c2 = candles[-2], candles[-1]
    if want_dir == "UP":
        return c1["close"] > c1["open"] and c2["close"] > c2["open"] and c2["close"] > c1["close"]
    if want_dir == "DOWN":
        return c1["close"] < c1["open"] and c2["close"] < c2["open"] and c2["close"] < c1["close"]
    return False

def _preentry_pileup_dir(pileup, pileup_allowed, pileup_up_count, pileup_down_count, pileup_up_eff, pileup_down_eff, hunt_cert, cvd_live, candles, price, wide_cert):
    # V16.2 single helper for Pre-Entry + CALM bypass. No duplicate pile-up check.
    # Returns LONG / SHORT if Pile-Up Certain from flat, else None.
    if not pileup_allowed or wide_cert: return None, "Wide Cert blocks pile-up"
    if not (pileup_up_eff or pileup_down_eff): return None, "No effective pile-up"
    # Prefer the side with Count 3/3. If both, prefer higher count.
    if pileup_up_eff and pileup_down_eff:
        want_up = pileup_up_count >= pileup_down_count
    elif pileup_up_eff:
        want_up = True
    else:
        want_up = False
    want_dir = "UP" if want_up else "DOWN"
    count = pileup_up_count if want_up else pileup_down_count
    cvd_agg = cvd_live.get("aggressive", "NEUTRAL")
    two_c = _two_candles_confirm(candles, want_dir)
    expected = abs(price - (hunt_cert.get("target", price) or price))
    void_fresh = pileup_brain.void_remembered_for != hunt_cert.get("target", 0)
    certain, reason = is_repile_certain(pileup_count=count, hunt_score=hunt_cert.get("score", 0), cvd_agg=cvd_agg,
        direction_against_position=want_dir, two_candles_confirm=two_c, void_is_fresh=void_fresh,
        expected_move_to_void=expected, flip_number=1)
    if not certain: return None, reason
    can_flip, cool = pileup_brain.can_flip_pileup_now()
    if not can_flip: return None, cool
    return ("LONG" if want_up else "SHORT"), reason

# ------------------------------------------------------------
# V13 AUTH - X-BAPI-* - PROVEN
# ------------------------------------------------------------
RECV_WINDOW = "5000"
def _sign_v5(payload_str, ts):
    msg = ts + BYBIT_API_KEY + RECV_WINDOW + payload_str
    return hmac.new(BYBIT_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

def _headers(sign, ts):
    return {"X-BAPI-API-KEY": BYBIT_API_KEY, "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": RECV_WINDOW, "X-BAPI-SIGN": sign,
            "Content-Type": "application/json"}

def _safe_json(r):
    try:
        txt = r.text.strip() if r.text else ""
        if not txt: return {"retCode": -1, "retMsg": "Empty response from Bybit", "result": {}}
        return r.json()
    except Exception as e:
        return {"retCode": -1, "retMsg": f"JSON parse fail: {e}", "result": {}}

def bybit_get(path, params):
    try:
        ts = str(int(time.time()*1000))
        qs = "&".join([f"{k}={v}" for k, v in sorted((params or {}).items())])
        sign = _sign_v5(qs, ts)
        url = BASE_URL + path + (f"?{qs}" if qs else "")
        r = requests.get(url, headers=_headers(sign, ts), timeout=10)
        return _safe_json(r)
    except Exception as e: log(f"Bybit GET error {e}"); return {"retCode": -1, "retMsg": str(e), "result": {}}

def bybit_post(path, params):
    try:
        ts = str(int(time.time()*1000))
        body = json.dumps(params or {}, separators=(',', ':'))
        sign = _sign_v5(body, ts)
        r = requests.post(BASE_URL + path, headers=_headers(sign, ts), data=body, timeout=10)
        return _safe_json(r)
    except Exception as e: log(f"Bybit POST error {e}"); return {"retCode": -1, "retMsg": str(e), "result": {}}

def get_balance():
    global balance
    try:
        j = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": "USDT"})
        if j.get("retCode") != 0:
            log(f"REAL BALANCE API WARN {j.get('retMsg')} - using last ${balance:.2f}")
            return balance or 12.56
        lst = j.get("result", {}).get("list", [])
        if lst:
            for coin in lst[0].get("coin", []):
                if coin.get("coin") == "USDT":
                    balance = float(coin.get("walletBalance", 0)); return balance
    except Exception as e: log(f"Balance error {e} - using last ${balance:.2f}")
    return balance or 12.56

def get_position():
    try:
        j = bybit_get("/v5/position/list", {"category": CATEGORY, "symbol": SYMBOL})
        lst = j.get("result", {}).get("list", [])
        if lst and float(lst[0].get("size", 0)) > 0: return lst[0]
    except: pass
    return None

def get_dynamic_leverage(bal=None):
    global leverage
    if bal is None: bal = balance or 12.56
    lev = 50 if bal >= 20 else 25 if bal >= 10 else 20 if bal >= 5 else 15
    leverage = lev; return lev

def get_dynamic_qty(price, lev, bal=None):
    if bal is None: bal = balance or 12.56
    if price <= 0: return 0.0
    base_qty = QTY_BASE if bal < 20 else round(QTY_BASE + int((bal-20)//8)*QTY_STEP, 3)
    max_affordable = (bal * 0.90 * lev) / price
    if max_affordable < QTY_MIN:
        log(f"QTY BLOCK Bal ${bal:.2f} Lev {lev}x too small"); return 0.0
    q = max(QTY_MIN, min(min(base_qty, max_affordable), REAL_MAX_QTY))
    q = int(q*1000)/1000.0
    log(f"DYN LEV {lev}x QTY Bal ${bal:.2f} -> Qty {q} Margin ${q*price/lev:.2f}")
    return q

def set_isolated_margin():
    try:
        lev = get_dynamic_leverage()
        r = bybit_post("/v5/position/switch-isolated", {"category": CATEGORY, "symbol": SYMBOL, "tradeMode": 1, "buyLeverage": str(lev), "sellLeverage": str(lev)})
        log(f"Margin ISOLATED | Lev {lev}x | {r.get('retMsg','')}")
        bybit_post("/v5/position/set-leverage", {"category": CATEGORY, "symbol": SYMBOL, "buyLeverage": str(lev), "sellLeverage": str(lev)})
    except Exception as e: log(f"Margin ISOLATED error {e}")

def calc_sl_tp(price, side_, mode_):
    if mode_ == "PILEUP":
        sl_dist, tp_dist = HUNT_SL_USD, HUNT_TP_USD
    elif mode_ == "HUNT_RIDE":
        sl_dist, tp_dist = HUNT_SL_USD, HUNT_TP_USD
    else:
        sl_dist, tp_dist = NORMAL_SL_USD, NORMAL_TP_USD
    if side_ == "LONG": return (round(price-sl_dist,1), round(price+tp_dist,1))
    return (round(price+sl_dist,1), round(price-tp_dist,1))

def be_target_for(mode_):
    if mode_ == "PILEUP": return float("inf")
    return HUNT_BE_USD if mode_ == "HUNT_RIDE" else NORMAL_BE_USD

def place_order(order_side, qty_, sl, tp):
    try:
        lev = get_dynamic_leverage()
        bybit_post("/v5/position/set-leverage", {"category": CATEGORY, "symbol": SYMBOL, "buyLeverage": str(lev), "sellLeverage": str(lev)})
        r = bybit_post("/v5/order/create", {"category": CATEGORY, "symbol": SYMBOL, "side": order_side, "orderType": "Market", "qty": str(qty_), "takeProfit": str(round(tp,1)), "stopLoss": str(round(sl,1)), "tpslMode": "Full", "positionIdx": 0})
        log(f"Order {order_side} {qty_} Lev {lev}x -> {r.get('retMsg','')} retCode {r.get('retCode')}")
        return r
    except Exception as e: log(f"Order error {e}"); return {}

def close_position_market(reason="CLOSE"):
    try:
        if not in_position or not side: return False
        close_side = "Sell" if side == "LONG" else "Buy"
        r = bybit_post("/v5/order/create", {"category": CATEGORY, "symbol": SYMBOL, "side": close_side, "orderType": "Market", "qty": str(qty), "reduceOnly": True, "positionIdx": 0})
        log(f"{reason} CLOSE {side} {qty} -> {r.get('retMsg','')}")
        return r.get("retCode",1)==0
    except Exception as e: log(f"Close error {e}"); return False

def get_votes(price, atr, candles):
    default = {"cert":0,"direction":"NONE","agree":0,"wide_cert":False,"grounded_cert":False,"hunt_soon":False,"hunt_cert":0,"hunter_score":0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_ride_dir":"NONE","hunt_done":False,"hunt_exhausted":False,"hunt_state":{},"sweep_done":False,"sweep_dir":"NONE","hunt_certainty":{"score":0,"label":"NO_HUNT","hunt_dir":"NONE"},"spread":{},"spread_score":0,"spread_bias":"NEUTRAL","spread_boost":0,"news":{"score":0,"direction":"NEUTRAL"},"news_boost":0,"flip_allowed":False,"flip_reason":"","flip_dir":"NONE","market_against":{},"run_needed":800,"fake_type":"NONE","fake_reason":"","fake_move":0,"pre_entry":{},"pileup":{"allowed":False,"allowed_reason":"no DE","pileup_up":False,"pileup_up_count":0,"pileup_down":False,"pileup_down_count":0,"pileup_up_effective":False,"pileup_down_effective":False}}
    if not HAS_DE or DE is None: return default
    try:
        fn = getattr(DE, "get_signal", None)
        if fn is None: return default
        res = fn(price, atr, candles)
        if isinstance(res, dict):
            out = dict(default); out.update(res); return out
    except Exception as e: log(f"get_votes error {e}")
    return default

def get_price_and_candles():
    if HAS_DE:
        try:
            price,_ = DE.get_price_live()
            k1 = DE.get_klines("1",20)
            candles = [{"open":k["open"],"high":k["high"],"low":k["low"],"close":k["close"],"volume":k.get("volume",1),"time":k.get("time",0)} for k in k1]
            return price, candles
        except: pass
    try:
        r = requests.get(f"{BASE_URL}/v5/market/tickers?category=linear&symbol={SYMBOL}", timeout=5).json()
        return float(r["result"]["list"][0]["lastPrice"]), []
    except: return 0.0, []

def calc_atr(candles):
    if not candles or len(candles)<15: return 0.0
    trs=[max(candles[i]["high"]-candles[i]["low"],abs(candles[i]["high"]-candles[i-1]["close"]),abs(candles[i]["low"]-candles[i-1]["close"])) for i in range(1,len(candles))]
    return sum(trs[-14:])/len(trs[-14:]) if trs else 0.0

def _record_close(exit_price, profit_move, result_tag, cert, atr, hunter_score, hunter_bias, spread_score, spread_bias):
    global daily_pnl, wins, losses, breakevens
    fees=qty*entry*FEE_RATE*2; gross=(exit_price-entry)*qty if side=="LONG" else (entry-exit_price)*qty; net=gross-fees
    if net>0: wins+=1; result="WIN"
    elif net<0: losses+=1; result="LOSS"
    else: breakevens+=1; result="BE"
    daily_pnl+=net
    log(f"🔴 CLOSED {result} [{result_tag}] Mode {mode} | Exit {exit_price:.1f} Move ${profit_move:.0f} Net ${net:.2f} | Daily ${daily_pnl:.2f}")
    tg(f"🔴 <b>CLOSED {result} [{result_tag}]</b>\nMode {mode} Exit {exit_price:.1f}\nNet ${net:.2f}\nW{wins} L{losses} BE{breakevens}\nDaily PNL ${daily_pnl:.2f}")
    if HAS_DE and hasattr(DE,"save_trade"):
        try: DE.save_trade({"time":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),"side":side,"entry":entry,"exit":exit_price,"move":round(profit_move,1),"qty":qty,"net_pnl":round(net,2),"result":result_tag,"mode":mode,"balance_after":round(balance,2),"cert":cert,"atr":round(atr,1),"lev":leverage,"margin":"ISOLATED","hunter_score":hunter_score,"hunter_bias":hunter_bias,"spread_score":spread_score,"spread_bias":spread_bias})
        except Exception as e: log(f"Save trade error {e}")
    return net

def _start_calm(reason):
    global recheck_until, recheck_dir, recheck_mode
    recheck_until=time.time()+CALM_SEC; recheck_dir=side; recheck_mode=mode
    log(f"😌 CALM {CALM_SEC}s after {reason} - Watch hunters only, no enter")

def _do_flip(flip_to, flip_tag, flip_reason2, price, cert, atr, hunter_score, hunter_bias, spread_score, spread_bias, new_mode, is_pileup=False):
    global in_position, side, entry, qty, mode
    log(f"🔄 {flip_tag}: {side} -> {flip_to} | {flip_reason2} | Price ${price:.0f}")
    tg(f"🔄 <b>{flip_tag}</b>\n{side} -> {flip_to}\n{flip_reason2}")
    profit_move = (price-entry) if side=="LONG" else (entry-price)
    if not close_position_market(flip_tag):
        log("FLIP CLOSE FAILED - retry"); return False
    _record_close(price, profit_move, flip_tag, cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
    qty2=get_dynamic_qty(price, get_dynamic_leverage())
    if qty2<=0: return True
    sl2,tp2=calc_sl_tp(price,flip_to,new_mode)
    r2=place_order("Buy" if flip_to=="LONG" else "Sell", qty2, sl2, tp2)
    if r2.get("retCode",1)==0:
        in_position=True; side=flip_to; entry=price; qty=qty2; mode=new_mode
        log(f"✅ FLIP ENTERED {flip_to} [{new_mode}] Qty {qty2} SL ${sl2:.0f} TP ${tp2:.0f} {'No fixed TP - Follow until Done' if is_pileup else ''}")
    return True

def main():
    global in_position, side, entry, qty, mode, daily_pnl, wins, losses, breakevens, recheck_until, recheck_dir, recheck_mode, last_flip_time
    log("V16.2 TIER2 + FLIP 3-WAYS + PILE-UP + PRE-ENTRY BYPASS | ISOLATED | Normal BE $800 / Hunt BE $600 / Pile-Up No Fixed TP | TP $1200 | Normal SL $1200 / Hunt SL $1000 / Pile-Up SL $1000 | CALM 150s Big/Normal | Pile-Up 60s | No First Aid | No Daily Loss Hard-Code")
    log(f"DEBUG KEY LEN {len(BYBIT_API_KEY)} START {BYBIT_API_KEY[:4]}**** | SECRET LEN {len(BYBIT_API_SECRET)}")
    tg("🤖 <b>BTC Bot V16.2 STARTED</b>\nISOLATED | TIER2 + Flip 3-Ways + Pile-Up + Pre-Entry Bypass\nNormal BE $800 / Hunt BE $600 / Pile-Up No Fixed TP\nTP $1200 | SL $1200 / $1000\nCALM 150s Big/Normal | Pile-Up 60s")
    set_isolated_margin(); get_balance()
    log(f"Balance ${balance:.2f} | Lev {get_dynamic_leverage()}x")
    last_vote_time=0
    while True:
        try:
            time.sleep(2)
            price, candles = get_price_and_candles()
            if price==0: continue
            atr = calc_atr(candles)
            if time.time()-last_vote_time<5: continue
            last_vote_time=time.time()
            v=get_votes(price,atr,candles)
            cert=v.get("cert",0); direction=v.get("direction","NONE"); agree=v.get("agree",0)
            wide_cert=v.get("wide_cert",False); grounded_cert=v.get("grounded_cert",False)
            hunter_score=v.get("hunter_score",0); hunter_bias=v.get("hunter_bias","NEUTRAL")
            hunt_ride_sig=v.get("hunt_ride",False); hunt_ride_dir=v.get("hunt_ride_dir","NONE")
            hunt_done=v.get("hunt_done",False); hunt_exhausted=v.get("hunt_exhausted",False); hunt_state=v.get("hunt_state",{}) or {}
            spot_prem=v.get("spot_premium_usd",0); fc=v.get("funding_cascade",{}) or {}; liq_c=v.get("liq_clusters",{}) or {}
            ob_c=v.get("ob_clusters",{}) or {}; cvd_live=v.get("cvd_live",{}) or {}
            sweep_done=v.get("sweep_done",False); sweep_dir=v.get("sweep_dir","NONE")
            hunt_cert=v.get("hunt_certainty",{}) or {}; spread=v.get("spread",{}) or {}
            spread_score=v.get("spread_score",0); spread_bias=v.get("spread_bias","NEUTRAL"); spread_boost=v.get("spread_boost",0)
            news=v.get("news",{}) or {}; news_boost=v.get("news_boost",0)
            flip_allowed=v.get("flip_allowed",False); flip_reason=v.get("flip_reason",""); flip_dir=v.get("flip_dir","NONE")
            fake_type=v.get("fake_type","NONE"); fake_reason=v.get("fake_reason",""); fake_move=v.get("fake_move",0)
            pre_entry=v.get("pre_entry",{}) or {}
            pileup=v.get("pileup",{}) or {}
            pileup_allowed=pileup.get("allowed",False)
            pileup_up_eff=pileup.get("pileup_up_effective",False); pileup_down_eff=pileup.get("pileup_down_effective",False)
            pileup_up_count=pileup.get("pileup_up_count",0); pileup_down_count=pileup.get("pileup_down_count",0)

            # V16.2: Compute Pre-Entry Pile-Up bypass ONCE, reuse for CALM + Pre-Entry + Entry. No duplicate check.
            bypass_dir = None; bypass_reason = ""
            if not in_position and HAS_DE:
                bypass_dir, bypass_reason = _preentry_pileup_dir(pileup, pileup_allowed, pileup_up_count, pileup_down_count, pileup_up_eff, pileup_down_eff, hunt_cert, cvd_live, candles, price, wide_cert)

            # --- CALM 150s: Big/Normal only. Pile-Up Certain bypasses CALM too, same as Pre-Entry. ---
            if not in_position and recheck_until>0 and time.time()<recheck_until and not bypass_dir:
                log(f"😌 CALM {int(recheck_until-time.time())}s | Watching hunters: Hunter {hunter_bias} {hunter_score} Hunt {hunt_cert.get('score',0)}/9 {hunt_cert.get('label')} Flip {flip_allowed} {flip_dir} Fake {fake_type} PileUp Up {pileup_up_count}/3 Down {pileup_down_count}/3 Allowed {pileup_allowed} | Cert {cert}% {direction} Wide {wide_cert}")
                continue
            if not in_position and recheck_until>0 and time.time()>=recheck_until and not bypass_dir:
                can_reenter=False; re_dir=recheck_dir; re_mode=recheck_mode
                if flip_allowed and flip_dir in ("LONG","SHORT") and flip_dir!=re_dir:
                    re_dir=flip_dir; re_mode="HUNT_RIDE"; can_reenter=True; log(f"✅ CALM DONE: Opposite TIER2 -> FLIP to {re_dir} | {flip_reason}")
                elif wide_cert and direction in ("LONG","SHORT"):
                    re_dir=direction; re_mode="NORMAL"; can_reenter=True; log(f"✅ CALM DONE: Wide Cert {cert}% -> Normal {re_dir}")
                elif re_mode=="HUNT_RIDE" and hunt_ride_sig and hunt_ride_dir==re_dir:
                    can_reenter=True; log(f"✅ CALM DONE: Hunt still vital {hunt_cert.get('score',0)}/9 - Re-enter Hunt {re_dir}")
                elif re_mode=="HUNT_RIDE" and hunt_done:
                    re_dir=direction; re_mode="NORMAL"; can_reenter=(direction in ("LONG","SHORT") and cert>=CERT_MIN); log(f"✅ CALM DONE: Hunt Done -> Normal {re_dir} Cert {cert}%")
                elif re_mode=="NORMAL" and hunt_ride_sig:
                    re_dir=hunt_ride_dir; re_mode="HUNT_RIDE"; can_reenter=True; log(f"✅ CALM DONE: Hunt now vital - Hunt {re_dir}")
                elif re_mode=="NORMAL" and direction==re_dir and cert>=CERT_MIN and not flip_allowed:
                    can_reenter=True; log(f"✅ CALM DONE: Normal still strong {cert}% {direction} - Re-enter")
                else:
                    log(f"❌ CALM DONE: No re-entry Cert {cert}% {direction} Hunter {hunt_cert.get('score',0)}/9 Flip {flip_allowed}")
                recheck_until=0; recheck_dir=None; recheck_mode=None
                if not can_reenter: continue
                direction=re_dir; enter_mode=re_mode; enter_dir=re_dir
                qty_preview=get_dynamic_qty(price, get_dynamic_leverage())
                if qty_preview==0: continue
                sl,tp=calc_sl_tp(price,enter_dir,enter_mode)
                order_side="Buy" if enter_dir=="LONG" else "Sell"
                log(f"🚀 RE-ENTER {enter_dir} [{enter_mode}] | Price ${price:.0f} Qty {qty_preview} | SL ${sl:.0f} TP ${tp:.0f} BE ${be_target_for(enter_mode):.0f} CLOSE | Cert {cert}%")
                tg(f"🚀 <b>RE-ENTER {enter_dir} [{enter_mode}]</b>\nPrice ${price:.0f}\nQty {qty_preview}\nSL ${sl:.0f} TP ${tp:.0f}\nBE ${be_target_for(enter_mode):.0f} CLOSE\nCert {cert}%")
                r=place_order(order_side,qty_preview,sl,tp)
                if r.get("retCode",1)==0:
                    in_position=True; side=enter_dir; entry=price; qty=qty_preview; mode=enter_mode
                    pileup_brain.reset_after_big_or_normal_takeover()
                continue

            if in_position:
                profit_move=(price-entry) if side=="LONG" else (entry-price)
                be_target=be_target_for(mode)
                if HAS_DE and profit_move>=200 and abs(price-_pileup_decay_mark["price"])>=200:
                    if side=="SHORT" and pileup_up_count>0:
                        new_c=DE.decay_pileup_by_1("UP"); log(f"PILE-UP DECAY UP {pileup_up_count} -> {new_c} - Price ${profit_move:.0f} for us but hunters still dey, no reset to 0")
                        _pileup_decay_mark["price"]=price
                    elif side=="LONG" and pileup_down_count>0:
                        new_c=DE.decay_pileup_by_1("DOWN"); log(f"PILE-UP DECAY DOWN {pileup_down_count} -> {new_c} - Price ${profit_move:.0f} for us but hunters still dey, no reset to 0")
                        _pileup_decay_mark["price"]=price
                if profit_move>=be_target and mode!="PILEUP":
                    log(f"🎯 BE CLOSE {mode} | Move ${profit_move:.0f} >= ${be_target:.0f} | Closing {side} @ ${price:.0f} for quick profit")
                    if close_position_market("BE_CLOSE"):
                        _record_close(price, profit_move, "BE_CLOSE", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                        _start_calm("BE_CLOSE")
                        in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
                        pileup_brain.reset_after_big_or_normal_takeover()
                    else: log("BE CLOSE FAILED - retry next loop")
                    continue
                # --- PILE-UP FLIP - CHECK FIRST, BEFORE OLD FLIP 3-WAYS - UNTOUCHED V16.1 ---
                pileup_handled=False
                if HAS_DE and pileup_allowed:
                    if pileup_brain.in_pileup_hunt and mode=="PILEUP":
                        dir_against = "UP" if side=="LONG" else "DOWN"
                        liq_now = liq_c.get("short_liq",0) if dir_against=="UP" else liq_c.get("long_liq",0)
                        ob_now = ob_c.get("ask_wall_usd",0) if dir_against=="UP" else ob_c.get("bid_wall_usd",0)
                        cert_against = cert>=85 and direction!=side
                        back_ok, back_reason, back_to = pileup_brain.should_flip_back_to_original(DE.is_pileup_done, price, liq_now, ob_now, candles, hunt_cert.get("score",0), cvd_live.get("aggressive","NEUTRAL"), cert_against)
                        if back_ok and back_to=="CLOSE":
                            # Fresh Pile-Up entry, no original -> CLOSE + CALM + reset, no flip-back to nothing
                            log(f"PILE-UP DONE (fresh) -> CLOSE {side} | {back_reason}")
                            if close_position_market("PILEUP_DONE_CLOSE"):
                                _record_close(price, profit_move, "PILEUP_DONE_CLOSE", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                                pileup_brain.reset_after_big_or_normal_takeover()
                                _start_calm("PILEUP_DONE_CLOSE")
                                in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
                                pileup_handled=True
                        elif back_ok and back_to in ("LONG","SHORT"):
                            orig_mode = pileup_brain.original_mode or "NORMAL"
                            log(f"PILE-UP DONE -> FLIP BACK {side} -> {back_to} [{orig_mode}] | {back_reason}")
                            pileup_brain.mark_flip_back_to_original()
                            if _do_flip(back_to, "FLIP_PILEUP_TO_ORIGINAL", back_reason, price, cert, atr, hunter_score, hunter_bias, spread_score, spread_bias, orig_mode, is_pileup=False):
                                pileup_handled=True
                        else:
                            log(f"PILE-UP HOLD {side} | Not Done: {back_reason} | Move ${profit_move:.0f} | Up {pileup_up_count}/3 Down {pileup_down_count}/3")
                    elif not pileup_brain.in_pileup_hunt and mode in ("NORMAL","HUNT_RIDE"):
                        opp_count = pileup_up_count if side=="SHORT" else pileup_down_count
                        want_dir = "UP" if side=="SHORT" else "DOWN"
                        two_c = _two_candles_confirm(candles, want_dir)
                        expected = abs(price - (hunt_cert.get("target", price) or price))
                        void_fresh = pileup_brain.void_remembered_for != hunt_cert.get("target",0)
                        to_ok, to_reason, to_dir = pileup_brain.should_flip_to_pileup(side, pileup_up_eff, pileup_down_eff, opp_count, hunt_cert.get("score",0), cvd_live.get("aggressive","NEUTRAL"), two_c, void_fresh, expected, wide_cert)
                        if to_ok and to_dir in ("LONG","SHORT"):
                            try:
                                dir_against2 = "UP" if to_dir=="LONG" else "DOWN"
                                liq_at = liq_c.get("short_liq",0) if dir_against2=="UP" else liq_c.get("long_liq",0)
                                ob_at = ob_c.get("ask_wall_usd",0) if dir_against2=="UP" else ob_c.get("bid_wall_usd",0)
                                DE.remember_void(dir_against2, hunt_cert.get("target", price) or price, liq_at, ob_at)
                                pileup_brain.void_remembered_for = hunt_cert.get("target",0)
                            except Exception as e: log(f"Remember void error {e}")
                            orig_dir, orig_entry, orig_cert, orig_mode = side, entry, cert, mode
                            log(f"PILE-UP FLIP {orig_dir} -> {to_dir} [PILEUP] | {to_reason}")
                            pileup_brain.mark_flip_to_pileup(to_dir, orig_dir, orig_entry, orig_cert, orig_mode, DE.reset_pileup if HAS_DE else None)
                            if _do_flip(to_dir, "FLIP_TO_PILEUP", to_reason, price, cert, atr, hunter_score, hunter_bias, spread_score, spread_bias, "PILEUP", is_pileup=True):
                                pileup_handled=True
                if pileup_handled: continue
                # --- FLIP 3-WAYS IN POSITION - SYMMETRIC LONG/SHORT - Full Qty ---
                flip_now=False; flip_to="NONE"; flip_tag=""; flip_reason2=""
                can_flip_time=(time.time()-last_flip_time)>=CALM_SEC
                if mode=="NORMAL" and flip_allowed and flip_dir in ("LONG","SHORT") and flip_dir!=side and can_flip_time:
                    flip_now=True; flip_to=flip_dir; flip_tag="FLIP_NORMAL_TO_HUNT"; flip_reason2=flip_reason
                elif mode=="HUNT_RIDE" and wide_cert and direction in ("LONG","SHORT") and direction!=side and can_flip_time:
                    flip_now=True; flip_to=direction; flip_tag="FLIP_HUNT_TO_NORMAL_WIDE"; flip_reason2=f"Wide Cert {cert}% {direction} overrides hunters"
                elif mode=="HUNT_RIDE" and hunt_exhausted and direction in ("LONG","SHORT") and direction!=side and can_flip_time:
                    flip_now=True; flip_to=direction; flip_tag="FLIP_HUNT_TO_NORMAL_EXHAUSTED"; flip_reason2=f"Hunt exhausted, flip back with little profit Move ${profit_move:.0f} to Normal {direction}"
                elif mode=="HUNT_RIDE" and hunt_done and direction in ("LONG","SHORT") and direction!=side:
                    flip_now=True; flip_to=direction; flip_tag="FLIP_HUNT_DONE_TO_NORMAL"; flip_reason2="Hunt Done -> Normal"
                if flip_now:
                    if _do_flip(flip_to, flip_tag, flip_reason2, price, cert, atr, hunter_score, hunter_bias, spread_score, spread_bias, "HUNT_RIDE" if "TO_HUNT" in flip_tag else "NORMAL", is_pileup=False):
                        last_flip_time=time.time()
                        pileup_brain.reset_after_big_or_normal_takeover()
                    continue
                elif get_position() is None:
                    _record_close(price, profit_move, "SL_TP_EXCHANGE", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                    _start_calm("SL_TP_EXCHANGE")
                    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
                    pileup_brain.reset_after_big_or_normal_takeover()
                    continue
                else:
                    sl,tp=calc_sl_tp(entry,side,mode)
                    log(f"HOLDING [{mode}] {side} Entry ${entry:.0f} Price ${price:.0f} Move ${profit_move:.0f} | SL ${sl:.0f} {'BE CLOSE $inf - Pile-Up Follow until Done' if mode=='PILEUP' else f'BE CLOSE ${be_target:.0f} TP Backup ${tp:.0f}'} | W{wins} L{losses} BE{breakevens} | HuntDone {hunt_done} Exhausted {hunt_exhausted} Flip {flip_allowed} {flip_dir} Fake {fake_type} Wide {wide_cert} PileUp Up {pileup_up_count}/3 Down {pileup_down_count}/3 Allowed {pileup_allowed} News {news.get('direction')} {news.get('score')} Boost {news_boost}%")
                    if in_position: continue

            # --- NOT IN POSITION: Entry Logic ---
            lev=get_dynamic_leverage(); qty_preview=get_dynamic_qty(price,lev)
            log(f"Price ${price:.0f} | ATR {atr:.0f} | {direction} Cert {cert}% Agree {agree}/8 Wide {wide_cert} Grounded {grounded_cert} | Bal ${balance:.2f} | Sweep {sweep_done} {sweep_dir} | Fake {fake_type} {fake_reason}")
            log(f"HUNTER {hunter_bias} {hunter_score} | Hunt {hunt_cert.get('label','?')} {hunt_cert.get('score',0)}/9 {hunt_cert.get('hunt_dir','')} Type {hunt_state.get('hunt_type','')} State {hunt_state.get('state','')} | HuntRide {hunt_ride_sig} {hunt_ride_dir} HuntDone {hunt_done} Exhausted {hunt_exhausted} Flip {flip_allowed} {flip_dir} | Liq Long ${liq_c.get('long_liq',0):,.0f} Short ${liq_c.get('short_liq',0):,.0f} ({liq_c.get('dominant','?')}) | Spot ${spot_prem:.0f} | CVD {v.get('cvd_live',{}).get('buy_pct',50)}% | Funding {fc.get('risk','NONE')} | PileUp Up {pileup_up_count}/3 Down {pileup_down_count}/3 Allowed {pileup_allowed}")
            log(f"SPREAD {spread_bias} Score {spread_score} Boost {spread_boost}% | NEWS {news.get('direction')} {news.get('score')} Boost {news_boost}% | {news.get('headline_note','')} | PreEntry {pre_entry.get('active')} {pre_entry.get('name')} Bypass {bypass_dir or 'NONE'}")
            if flip_reason: log(f"🔄 FLIP CHECK: {flip_reason}")
            log(f"Qty {qty_preview} Lev {lev}x | Normal BE $800 CLOSE SL $1200 TP $1200 | Hunt BE $600 CLOSE SL $1000 TP $1200 | Pile-Up No Fixed TP SL $1000 | W{wins} L{losses} BE{breakevens} PnL ${daily_pnl:.2f} | CALM {CALM_SEC}s Big/Normal | Pile-Up 60s")
            # V16.2: Pre-Entry lock holds Normal/Hunt/Fake/Wide, NOT Pile-Up Certain.
            if pre_entry.get("active") and not sweep_done and not bypass_dir:
                log(f"👀 PRE-ENTRY {pre_entry.get('name')} - Watching only, no entry: {pre_entry.get('note')} | Hunt {hunt_cert.get('score',0)}/9 Pile-Up Up {pileup_up_count}/3 Down {pileup_down_count}/3 Bypass {bypass_reason}")
                continue
            if pre_entry.get("active") and bypass_dir:
                log(f"🏹 PRE-ENTRY PILE-UP BYPASS {pre_entry.get('name')} - {bypass_reason} - Enter {bypass_dir} [PILEUP] before NY open")
            enter_dir=None; enter_mode="NORMAL"
            # V16.2: Bypass wins first, no overwrite by priority chain below.
            if bypass_dir in ("LONG","SHORT"):
                enter_dir=bypass_dir; enter_mode="PILEUP"; log(f"🏹 PILE-UP BYPASS ENTER {enter_dir} [PILEUP] @ ${price:.0f} - Pre-Entry/CALM bypass, Certain")
            elif sweep_done and direction in ("LONG","SHORT"):
                enter_dir=direction; enter_mode="NORMAL"; log(f"⚡ SWEEP ENTER {enter_dir} @ ${price:.0f} - No bounce wait")
            elif wide_cert and direction in ("LONG","SHORT"):
                enter_dir=direction; enter_mode="NORMAL"; log(f"✅ WIDE CERT ENTER {enter_dir} Cert {cert}% - Ignore TIER2, hunters cannot dare")
            elif flip_allowed and flip_dir in ("LONG","SHORT"):
                enter_dir=flip_dir; enter_mode="HUNT_RIDE"; log(f"🏹 FLIP/HUNT ENTER {enter_dir} | {flip_reason}")
            elif hunt_ride_sig and hunt_ride_dir in ("LONG","SHORT"):
                enter_dir=hunt_ride_dir; enter_mode="HUNT_RIDE"; log(f"🏹 HUNT RIDE ENTER {enter_dir} | Hunter {hunt_cert.get('score',0)}/9 {hunt_cert.get('hunt_dir')} target ${hunt_cert.get('target',0):,.0f} Normal {direction} Cert {cert}% - Ride hunters, BE $600 CLOSE")
            elif fake_type in ("FAKE_DUMP","FAKE_PUMP"):
                enter_dir="LONG" if fake_type=="FAKE_DUMP" else "SHORT"; enter_mode="HUNT_RIDE"; log(f"🎯 WIDE FAKE BOUNCE ENTER {enter_dir} | {fake_reason} | Move ${fake_move:.0f}")
            elif direction in ("LONG","SHORT") and cert>=CERT_MIN and not flip_allowed:
                enter_dir=direction; enter_mode="NORMAL"; log(f"✅ NORMAL ENTER {enter_dir} Cert {cert}% >= {CERT_MIN}% - No opposite TIER2")
            elif direction!="NONE":
                log(f"⏳ Cert {cert}% < {CERT_MIN}% or Flip blocks - No trade | HuntRide {hunt_ride_sig} Sweep {sweep_done} Fake {fake_type}")
                continue
            else:
                log(f"⏳ No direction - Wait | Cert {cert}% Hunt {hunt_cert.get('label')}")
                continue
            if enter_dir is None: continue
            if qty_preview==0: log("BLOCK QTY TOO SMALL"); continue
            sl,tp=calc_sl_tp(price,enter_dir,enter_mode); be_t=be_target_for(enter_mode)
            fees=qty_preview*price*FEE_RATE*2
            sl_loss=(NORMAL_SL_USD if enter_mode=="NORMAL" else HUNT_SL_USD)*qty_preview
            log(f"FEES CHECK BE Profit ${be_t*qty_preview:.2f} vs Fees ${fees:.2f} | SL Loss ${sl_loss:.2f} | TP Backup Profit ${NORMAL_TP_USD*qty_preview:.2f}")
            order_side="Buy" if enter_dir=="LONG" else "Sell"
            log(f"🚀 ENTER {enter_dir} [{enter_mode}] | Price ${price:.0f} | Qty {qty_preview} Lev {lev}x ISOLATED | SL ${sl:.0f} | BE CLOSE ${be_t:.0f} | TP Backup ${tp:.0f} | Cert {cert}% Agree {agree} | Hunter {hunter_bias} {hunter_score} | Hunt {hunt_cert.get('label')} {hunt_cert.get('score',0)}/9 | News {news.get('direction')} {news.get('score')} Boost {news_boost}%")
            tg(f"🚀 <b>ENTER {enter_dir} [{enter_mode}]</b>\nPrice ${price:.0f}\nQty {qty_preview} Lev {lev}x ISOLATED\nSL ${sl:.0f}\nBE ${be_t:.0f} CLOSE\nTP Backup ${tp:.0f}\nCert {cert}% Agree {agree}/8\nHunter {hunter_bias} {hunter_score}\nNews {news.get('direction')} {news.get('score')} Boost {news_boost}%")
            r=place_order(order_side,qty_preview,sl,tp)
            if r.get("retCode",1)==0:
                in_position=True; side=enter_dir; entry=price; qty=qty_preview; mode=enter_mode
                _pileup_decay_mark["price"]=price
                if enter_mode=="PILEUP":
                    # Fresh Pile-Up entry: remember void + mark brain, no original dir
                    try:
                        _da = "UP" if enter_dir=="LONG" else "DOWN"
                        _liq = liq_c.get("short_liq",0) if _da=="UP" else liq_c.get("long_liq",0)
                        _ob = ob_c.get("ask_wall_usd",0) if _da=="UP" else ob_c.get("bid_wall_usd",0)
                        if HAS_DE: DE.remember_void(_da, hunt_cert.get("target", price) or price, _liq, _ob)
                        pileup_brain.void_remembered_for = hunt_cert.get("target",0)
                        if HAS_DE: DE.reset_pileup(_da)
                    except Exception as e: log(f"Fresh pile-up mark error {e}")
                    pileup_brain.mark_fresh_pileup_entry(enter_dir)
            else: log(f"Order failed: {r}")
        except Exception as e: log(f"MAIN LOOP ERROR: {e}"); time.sleep(5)

if __name__=="__main__": main()
