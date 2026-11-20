# ============================================================
# MAIN.PY V15.9 - HUNTER VETO POWER / HUNT RIDE
# KEEP FROM V15.7: Flask + Self-Ping, X-BAPI Auth, _safe_json,
#   Balance Fallback, Position Sync, Dynamic Lev/Qty, Isolated
# NEW V15.9: BE=CLOSE Normal $800 / Hunt $600, TP Backup $1200,
#   Hunt SL $1000 / Normal SL $1200, Hunt Ride -> Hunt Done -> Normal,
#   First Aid V15.9, 1-Min Hold + Re-Check, News Booster Only
# REMOVE: hunter_wait block, news_wait block, pause block,
#   BE $500 -> Lock $20, TP $1500, dead duplicates
# ============================================================
import os, time, threading, hmac, hashlib, json
from datetime import datetime, timezone
import requests

# --- V13 KEEP-ALIVE: Flask + Self-Ping ---
try:
    from flask import Flask
    _flask_app = Flask(__name__)
    @_flask_app.route("/")
    def _health(): return "BOT ALIVE V15.9 - HUNT RIDE + BE CLOSE", 200
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
    print("✅ Data Engine Connected V15.9", flush=True)
    HAS_DE = True
except Exception as e:
    DE = None; HAS_DE = False
    print(f"❌ Data Engine NOT Found: {e}", flush=True)

BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "").strip()
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
SYMBOL = "BTCUSDT"; CATEGORY = "linear"; BASE_URL = "https://api.bybit.com"

# --- V15.9 NUMBERS: BE = CLOSE ---
NORMAL_BE_USD = 800.0; HUNT_BE_USD = 600.0
NORMAL_TP_USD = 1200.0; HUNT_TP_USD = 1200.0
NORMAL_SL_USD = 1200.0; HUNT_SL_USD = 1000.0
CERT_MIN = 75.0; CERT_HUNT = 85.0; MAX_DAILY_LOSS = 50.0
RECHECK_HOLD_SEC = 60
QTY_BASE = 0.010; QTY_STEP = 0.005; QTY_MIN = 0.001; REAL_MAX_QTY = 0.100
FEE_RATE = 0.0006
balance = 0.0; leverage = 25
in_position = False; side = None; entry = 0.0; qty = 0.0
mode = "NORMAL"  # NORMAL or HUNT_RIDE
daily_pnl = 0.0; wins = 0; losses = 0; breakevens = 0
recheck_until = 0; recheck_dir = None; recheck_mode = None

def log(msg): print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)
def tg(msg):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

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
    if mode_ == "HUNT_RIDE":
        sl_dist, tp_dist = HUNT_SL_USD, HUNT_TP_USD
    else:
        sl_dist, tp_dist = NORMAL_SL_USD, NORMAL_TP_USD
    if side_ == "LONG": return (round(price-sl_dist,1), round(price+tp_dist,1))
    return (round(price+sl_dist,1), round(price-tp_dist,1))

def be_target_for(mode_):
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
    default = {"cert":0,"direction":"NONE","agree":0,"hunt_soon":False,"hunt_cert":0,"news_critical":False,"news_wait":0,"pause_long":False,"pause_short":False,"pause_reason":"","hunter_score":0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_ride_dir":"NONE","hunt_done":False,"hunt_state":{},"sweep_done":False,"sweep_dir":"NONE","first_aid":False,"first_aid_action":"NONE","first_aid_reason":"","hunt_certainty":{"score":0,"label":"NO_HUNT","hunt_dir":"NONE"},"spread":{},"spread_score":0,"spread_bias":"NEUTRAL","spread_boost":0,"news":{"score":0,"direction":"NEUTRAL"},"news_boost":0}
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

def main():
    global in_position, side, entry, qty, mode, daily_pnl, wins, losses, breakevens, recheck_until, recheck_dir, recheck_mode
    log("V15.9 HUNT RIDE | ISOLATED | Normal BE $800 CLOSE / Hunt BE $600 CLOSE | TP Backup $1200 | Normal SL $1200 / Hunt SL $1000 | First Aid ON | Hunt Done -> Normal | 1-Min Recheck ON | News Booster Only")
    log(f"DEBUG KEY LEN {len(BYBIT_API_KEY)} START {BYBIT_API_KEY[:4]}**** | SECRET LEN {len(BYBIT_API_SECRET)}")
    tg("🤖 <b>BTC Bot V15.9 STARTED</b>\nISOLATED | Hunt Ride ON\nNormal BE $800 CLOSE\nHunt BE $600 CLOSE\nTP Backup $1200\nNormal SL $1200 / Hunt SL $1000\nFirst Aid ON | Hunt Done -> Normal\n1-Min Recheck ON | News Booster Only")
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
            hunter_score=v.get("hunter_score",0); hunter_bias=v.get("hunter_bias","NEUTRAL")
            hunt_ride_sig=v.get("hunt_ride",False); hunt_ride_dir=v.get("hunt_ride_dir","NONE")
            hunt_done=v.get("hunt_done",False); hunt_state=v.get("hunt_state",{}) or {}
            spot_prem=v.get("spot_premium_usd",0); fc=v.get("funding_cascade",{}) or {}; liq_c=v.get("liq_clusters",{}) or {}
            sweep_done=v.get("sweep_done",False); sweep_dir=v.get("sweep_dir","NONE")
            first_aid=v.get("first_aid",False); first_aid_action=v.get("first_aid_action","NONE"); first_aid_reason=v.get("first_aid_reason","")
            hunt_cert=v.get("hunt_certainty",{}) or {}; spread=v.get("spread",{}) or {}
            spread_score=v.get("spread_score",0); spread_bias=v.get("spread_bias","NEUTRAL"); spread_boost=v.get("spread_boost",0)
            news=v.get("news",{}) or {}; news_boost=v.get("news_boost",0)

            # --- 1-MIN RECHECK HOLD: After BE Close, hold 60s, then re-evaluate ---
            if not in_position and recheck_until>0 and time.time()<recheck_until:
                log(f"⏳ RECHECK HOLD {int(recheck_until-time.time())}s | Waiting to see if {recheck_dir} can still run another ${NORMAL_BE_USD if recheck_mode=='NORMAL' else HUNT_BE_USD:.0f} | Cert {cert}% Hunter {hunt_cert.get('score',0)}/9 News {news.get('direction')} {news.get('score')}")
                continue
            if not in_position and recheck_until>0 and time.time()>=recheck_until:
                # Hold done - decide: re-enter if cert still 75%+ OR hunter still 6/9+
                can_reenter = False; re_dir = recheck_dir; re_mode = recheck_mode
                if re_mode=="HUNT_RIDE" and hunt_ride_sig and hunt_ride_dir==re_dir:
                    can_reenter=True; log(f"✅ RECHECK: Hunt still privilege Hunter {hunt_cert.get('score',0)}/9 - Re-enter Hunt Ride {re_dir}")
                elif re_mode=="HUNT_RIDE" and hunt_done:
                    # Hunt done -> go Normal instead of Hunt Ride
                    re_dir=direction; re_mode="NORMAL"; can_reenter=(direction in ("LONG","SHORT") and cert>=CERT_MIN); log(f"✅ RECHECK: Hunt Done -> Switch to Normal {re_dir} Cert {cert}%")
                elif re_mode=="NORMAL" and direction==re_dir and cert>=CERT_MIN:
                    can_reenter=True; log(f"✅ RECHECK: Normal still strong Cert {cert}% {direction} - Re-enter for another $800")
                elif re_mode=="NORMAL" and hunt_ride_sig:
                    re_dir=hunt_ride_dir; re_mode="HUNT_RIDE"; can_reenter=True; log(f"✅ RECHECK: Hunt now vital - Switch to Hunt Ride {re_dir}")
                else:
                    log(f"❌ RECHECK: No re-entry Cert {cert}% {direction} Hunter {hunt_cert.get('score',0)}/9 - Wait")
                recheck_until=0; recheck_dir=None; recheck_mode=None
                if not can_reenter: continue
                # Fall through to entry below with re_dir / re_mode
                direction=re_dir
                # Use re_mode for entry
                enter_mode=re_mode
                enter_dir=re_dir
                # Skip normal hunt/normal priority logic, go straight to entry check
                qty_preview=get_dynamic_qty(price, get_dynamic_leverage())
                if qty_preview==0: continue
                sl,tp=calc_sl_tp(price,enter_dir,enter_mode)
                order_side="Buy" if enter_dir=="LONG" else "Sell"
                log(f"🚀 RE-ENTER {enter_dir} [{enter_mode}] | Price ${price:.0f} Qty {qty_preview} | SL ${sl:.0f} TP ${tp:.0f} BE ${be_target_for(enter_mode):.0f} CLOSE | Cert {cert}%")
                tg(f"🚀 <b>RE-ENTER {enter_dir} [{enter_mode}]</b>\nPrice ${price:.0f}\nQty {qty_preview}\nSL ${sl:.0f} TP ${tp:.0f}\nBE ${be_target_for(enter_mode):.0f} CLOSE\nCert {cert}%")
                r=place_order(order_side,qty_preview,sl,tp)
                if r.get("retCode",1)==0:
                    in_position=True; side=enter_dir; entry=price; qty=qty_preview; mode=enter_mode
                continue

            if in_position:
                profit_move=(price-entry) if side=="LONG" else (entry-price)
                be_target=be_target_for(mode)
                # --- BE = CLOSE: Once BE hit, close, collect quick profit, start 1-min recheck ---
                if profit_move>=be_target:
                    log(f"🎯 BE CLOSE {mode} | Move ${profit_move:.0f} >= ${be_target:.0f} | Closing {side} @ ${price:.0f} for quick profit")
                    if close_position_market("BE_CLOSE"):
                        _record_close(price, profit_move, "BE_CLOSE", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                        # Start 1-min recheck: can we run another BE?
                        recheck_until=time.time()+RECHECK_HOLD_SEC; recheck_dir=side; recheck_mode=mode
                        in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
                    else: log("BE CLOSE FAILED - retry next loop")
                    continue
                # --- FIRST AID V15.9: Hunt Ride fail, Cert takeover -> close Hunt Ride, enter Normal immediately ---
                if mode=="HUNT_RIDE" and first_aid and direction in ("LONG","SHORT") and direction!=side:
                    log(f"🚨 FIRST AID IN HUNT RIDE: {first_aid_reason} | Our Hunt {side} @ ${entry:.0f} Price ${price:.0f} Move ${profit_move:.0f} -> Close Hunt, Enter Normal {direction}")
                    tg(f"🚨 <b>FIRST AID</b>\n{first_aid_reason}\nClosing Hunt {side} @ ${price:.0f}\nEnter Normal {direction}")
                    if close_position_market("FIRST_AID"):
                        _record_close(price, profit_move, "FIRST_AID", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                        in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
                        # Immediately enter Normal - fall through to entry logic below with direction
                        # Do not set recheck, enter now
                    else: log("FIRST AID CLOSE FAILED - retry"); continue
                    # Continue to entry logic in same loop (do not continue)
                elif mode=="HUNT_RIDE" and hunt_done:
                    # --- HUNT DONE: Close Hunt Ride, enter Normal immediately ---
                    log(f"✅ HUNT DONE IN POSITION: Hunter drop, price back inside -> Close Hunt {side} @ ${price:.0f} Move ${profit_move:.0f}, Enter Normal {direction}")
                    tg(f"✅ <b>HUNT DONE</b>\nClosing Hunt {side} @ ${price:.0f}\nEnter Normal {direction}")
                    if close_position_market("HUNT_DONE"):
                        _record_close(price, profit_move, "HUNT_DONE", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                        in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance()
                    else: log("HUNT DONE CLOSE FAILED - retry"); continue
                    # Fall through to Normal entry
                elif get_position() is None:
                    # SL / TP hit on exchange (Bybit closed it)
                    sl,tp=calc_sl_tp(entry,side,mode)
                    _record_close(price, profit_move, "SL_TP_EXCHANGE", cert, atr, hunter_score, hunter_bias, spread_score, spread_bias)
                    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; get_balance(); continue
                else:
                    # Still holding - log
                    sl,tp=calc_sl_tp(entry,side,mode)
                    log(f"HOLDING [{mode}] {side} Entry ${entry:.0f} Price ${price:.0f} Move ${profit_move:.0f} | SL ${sl:.0f} BE CLOSE ${be_target:.0f} TP Backup ${tp:.0f} | W{wins} L{losses} BE{breakevens} | HuntDone {hunt_done} FirstAid {first_aid} News {news.get('direction')} {news.get('score')} Boost {news_boost}%")
                    # If we just closed via FirstAid/HuntDone above, we fell through - if still in_position, skip entry
                    if in_position: continue

            # --- NOT IN POSITION: Entry Logic ---
            lev=get_dynamic_leverage(); qty_preview=get_dynamic_qty(price,lev)
            log(f"Price ${price:.0f} | ATR {atr:.0f} | {direction} Cert {cert}% Agree {agree}/8 | Bal ${balance:.2f} | Sweep {sweep_done} {sweep_dir} | FirstAid {first_aid} {first_aid_action}")
            log(f"HUNTER {hunter_bias} {hunter_score} | Hunt {hunt_cert.get('label','?')} {hunt_cert.get('score',0)}/9 {hunt_cert.get('hunt_dir','')} Type {hunt_state.get('hunt_type','')} State {hunt_state.get('state','')} | HuntRide {hunt_ride_sig} {hunt_ride_dir} HuntDone {hunt_done} | Liq Long ${liq_c.get('long_liq',0):,.0f} Short ${liq_c.get('short_liq',0):,.0f} ({liq_c.get('dominant','?')}) | Spot ${spot_prem:.0f} | CVD {v.get('cvd_live',{}).get('buy_pct',50)}% | Funding {fc.get('risk','NONE')}")
            log(f"SPREAD {spread_bias} Score {spread_score} Boost {spread_boost}% | NEWS {news.get('direction')} {news.get('score')} Boost {news_boost}% | {news.get('headline_note','')}")
            if first_aid_reason: log(f"🚨 FIRST AID: {first_aid_reason}")
            log(f"Qty {qty_preview} Lev {lev}x | Normal BE $800 CLOSE SL $1200 TP $1200 | Hunt BE $600 CLOSE SL $1000 TP $1200 | W{wins} L{losses} BE{breakevens} PnL ${daily_pnl:.2f}")
            if daily_pnl<=-MAX_DAILY_LOSS: log(f"🛑 DAILY LOSS LIMIT ${daily_pnl:.2f}"); time.sleep(60); continue
            # V15.9: News NEVER blocks, Hunter NEVER blocks, Gold NEVER blocks - only Cert decides
            # Priority: 1) Hunt Ride if hunt_ride True, 2) Normal if cert >=75, 3) Sweep = Normal immediately
            enter_dir=None; enter_mode="NORMAL"
            if sweep_done and direction in ("LONG","SHORT"):
                enter_dir=direction; enter_mode="NORMAL"; log(f"⚡ SWEEP ENTER {enter_dir} @ ${price:.0f} - No bounce wait")
            elif hunt_ride_sig and hunt_ride_dir in ("LONG","SHORT"):
                # Hunt Ride: follow hunters, opposite to normal - high cert only, no timeout, no max limit
                enter_dir=hunt_ride_dir; enter_mode="HUNT_RIDE"; log(f"🏹 HUNT RIDE ENTER {enter_dir} | Hunter {hunt_cert.get('score',0)}/9 {hunt_cert.get('hunt_dir')} target ${hunt_cert.get('target',0):,.0f} Normal {direction} Cert {cert}% - Ride hunters, BE $600 CLOSE")
            elif direction in ("LONG","SHORT") and cert>=CERT_MIN:
                enter_dir=direction; enter_mode="NORMAL"; log(f"✅ NORMAL ENTER {enter_dir} Cert {cert}% >= {CERT_MIN}%")
            elif direction!="NONE":
                log(f"⏳ Cert {cert}% < {CERT_MIN}% - No trade | HuntRide {hunt_ride_sig} Sweep {sweep_done}")
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
            else: log(f"Order failed: {r}")
        except Exception as e: log(f"MAIN LOOP ERROR: {e}"); time.sleep(5)

if __name__=="__main__": main()
