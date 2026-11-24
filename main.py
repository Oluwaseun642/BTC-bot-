# MAIN V19.2 - DEBUG + PRICE FIX
import os,time,threading,traceback
from http.server import BaseHTTPRequestHandler,HTTPServer
from bybit_client import bybit_get,bybit_post
from data_engine import get_signal,get_price_and_candles

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}",flush=True)
def env(k,d="0"): return os.getenv(k,d)
def bal():
 r=bybit_get("/v5/account/wallet-balance",{"accountType":"UNIFIED","coin":"USDT"})
 try: return float(r["result"]["list"][0]["coin"][0]["walletBalance"])
 except: return 0
def pos():
 r=bybit_get("/v5/position/list",{"category":"linear","symbol":"BTCUSDT"})
 try:
  l=r["result"]["list"]; return l[0] if l and float(l[0]["size"])>0 else None
 except: return None
def qty_lev(b): return 0.001,60
def set_lev(l): bybit_post("/v5/position/set-leverage",{"category":"linear","symbol":"BTCUSDT","buyLeverage":str(l),"sellLeverage":str(l)})
def order(side,q): return bybit_post("/v5/order/create",{"category":"linear","symbol":"BTCUSDT","side":side,"orderType":"Market","qty":str(q)})
def close_all():
 p=pos()
 if p: order("Sell" if p["side"]=="Buy" else "Buy",p["size"])

class H(BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200);self.end_headers();self.wfile.write(b"ok")
 def log_message(self,*a): pass
threading.Thread(target=lambda:HTTPServer(("0.0.0.0",int(os.getenv("PORT","10000"))),H).serve_forever(),daemon=True).start()
def ping():
 import requests
 while True:
  try: requests.get(os.getenv("RENDER_EXTERNAL_URL","http://localhost:10000"),timeout=5)
  except: pass
  time.sleep(60)
threading.Thread(target=ping,daemon=True).start()

def _num(x):
  try:
    if isinstance(x, (list, tuple)): return float(x[0]) if len(x)>0 else 0
    if isinstance(x, dict): return float(x.get("close", x.get("c", x.get("price", 0))))
    return float(x)
  except: return 0
def _candle(c):
  try:
    if isinstance(c, dict):
      return _num(c.get("high", c.get("h", 0))), _num(c.get("low", c.get("l", 0))), _num(c.get("close", c.get("c", 0)))
    if isinstance(c, (list, tuple)):
      if len(c)==1 and isinstance(c[0], (list, tuple, dict)): return _candle(c[0])
      return _num(c[2]) if len(c)>2 else 0, _num(c[3]) if len(c)>3 else 0, _num(c[4]) if len(c)>4 else 0
    return 0,0,0
  except: return 0,0,0
def get_vol(candles, price):
  try:
    if not candles or len(candles)<55: return 0,0,0
    parsed=[_candle(c) for c in candles[-55:]]
    ranges=[h-l for h,l,cl in parsed if h>0 and l>0]
    if len(ranges)<55: return 0,0,0
    avg_50=sum(ranges[:-5])/50; avg_5=sum(ranges[-5:])/5
    vol_ratio=avg_5/avg_50 if avg_50>0 else 0
    price_5_ago=parsed[-6][2] or price
    velocity=abs(price-price_5_ago)/price_5_ago*100 if price_5_ago>0 else 0
    hr=int(time.strftime("%H")); sess_boost=1.15 if hr in (8,9,10,13,14,15) else 1.0
    return round(vol_ratio,2), round(velocity,3), round(vol_ratio*sess_boost,2)
  except Exception as e:
    print(f"[VOL-ERR] {e}", flush=True); return 0,0,0

BAL=bal(); ENTRY=0; MODE=""; BE_DONE=False; LAST_CLOSE=0
VOL_DEAD_START=0; FLIPS_TODAY=0; LAST_FLIP_DAY=""; LAST_CERT_DIR=""
log(f"START V19.2 VOL-ONLY Bal ${BAL:.2f}")

while True:
 try:
  if env("PAUSE_BOT")=="1": time.sleep(7); continue
  raw_price,candles=get_price_and_candles()
  # FIX: price fit be list/dict, force am to float
  price=_num(raw_price)
  if price==0:
    log(f"[DEBUG] raw_price type={type(raw_price)} value={str(raw_price)[:200]} candles type={type(candles)} len={len(candles) if hasattr(candles,'__len__') else 'no-len'} first={str(candles[0])[:300] if candles else 'empty'}")
    time.sleep(7); continue
  s=get_signal(candles)
  vol_ratio,velocity,vol_score=get_vol(candles,price)
  BAL=bal(); P=pos()
  today=time.strftime("%Y-%m-%d")
  if today!=LAST_FLIP_DAY: LAST_FLIP_DAY=today; FLIPS_TODAY=0
  VOL_HIGH = vol_score>=1.35 and velocity>=0.12
  VOL_DEAD = vol_score<1.15 and velocity<0.08
  cert_dir=s.get("direction",""); cert=s.get("cert",0)
  hunt_dir=s.get("hunt_dir",""); hunt_score=s.get("hunt_score",0)
  IS_HUNTER = hunt_dir!="" and cert_dir!="" and hunt_dir!=cert_dir and hunt_score>=7
  if not P:
   enter=None; why=""
   if VOL_HIGH and IS_HUNTER: enter=hunt_dir; MODE="HUNTER"; why=f"HUNTER {hunt_dir} {hunt_score}/9 vs Cert {cert_dir} Vol {vol_score} Vel {velocity}%"
   elif VOL_HIGH and hunt_score>=7 and hunt_dir in ("LONG","SHORT"): enter=hunt_dir; MODE="HUNTER"; why=f"VOL-FLIP HUNT {hunt_dir} {hunt_score}/9 Vol {vol_score} Vel {velocity}%"
   elif VOL_HIGH and cert>=70 and cert_dir in ("LONG","SHORT"): enter=cert_dir; MODE="NORMAL"; why=f"CERT {cert_dir} {cert:.0f}% Vol {vol_score} Vel {velocity}%"
   elif env("FORCE_LONG")=="1": enter="LONG"; MODE="FORCE"
   elif env("FORCE_SHORT")=="1": enter="SHORT"; MODE="FORCE"
   if enter and time.time()-LAST_CLOSE>60:
    q,l=qty_lev(BAL); set_lev(l); order("Buy" if enter=="LONG" else "Sell",q)
    ENTRY=float(price); BE_DONE=False; VOL_DEAD_START=0; LAST_CERT_DIR=cert_dir
    log(f"[ENTER] {enter} {MODE} @ {price:.0f} {why}")
   else:
    if not VOL_HIGH: log(f"[WAIT-VOL] Bal ${BAL:.2f} Price {price:.0f} Cert {cert_dir} {cert:.0f}% Hunt {hunt_dir} {hunt_score}/9 Hunter? {IS_HUNTER} Vol {vol_score} Vel {velocity}% - Dead, no trade")
    else: log(f"[STATS] Bal ${BAL:.2f} NoPos Price {price:.0f} Cert {cert_dir} {cert:.0f}% Hunt {hunt_dir} {hunt_score}/9 Hunter? {IS_HUNTER} Vol {vol_score} Vel {velocity}%")
   time.sleep(7); continue
  if ENTRY==0: ENTRY=float(P["avgPrice"])
  cur="LONG" if P["side"]=="Buy" else "SHORT"; opp="SHORT" if cur=="LONG" else "LONG"
  run=(float(price)-float(ENTRY)) if cur=="LONG" else (float(ENTRY)-float(price))
  be_need=500 if MODE=="HUNTER" else 800
  if not BE_DONE and run>=be_need:
   close_all(); time.sleep(1); q,l=qty_lev(BAL); set_lev(l); order("Buy" if cur=="LONG" else "Sell",q)
   ENTRY=float(price); BE_DONE=True; log(f"[BE] {cur} @ {price:.0f} Run ${run:.0f}")
  sl_need=800 if MODE=="HUNTER" else 1800
  if run<=-sl_need:
   log(f"[SL] {cur} @ {price:.0f} Run ${run:.0f}"); close_all(); LAST_CLOSE=time.time(); ENTRY=0; VOL_DEAD_START=0; time.sleep(7); continue
  if run>=2000:
   log(f"[TP2] {cur} @ {price:.0f} Run ${run:.0f}"); close_all(); LAST_CLOSE=time.time(); ENTRY=0; VOL_DEAD_START=0; time.sleep(7); continue
  flip=False; why=""
  if VOL_HIGH and run<200 and time.time()-LAST_CLOSE>600 and FLIPS_TODAY<3:
   if cert_dir==opp and cert>=80: flip=True; why=f"CERT-FLIP Worldwide {opp} {cert:.0f}% Vol {vol_score}"
   elif IS_HUNTER and hunt_dir==opp: flip=True; why=f"HUNTER-FLIP Session {opp} {hunt_score}/9 vs Worldwide {cert_dir} Vol {vol_score} Vel {velocity}%"
   elif hunt_dir==opp and hunt_score>=7: flip=True; why=f"VOL-FLIP Hunt {opp} {hunt_score}/9 Vol {vol_score} Vel {velocity}%"
  if flip:
   log(f"[FLIP] {cur}->{opp} {why} @ {price:.0f} Run ${run:.0f}"); close_all(); time.sleep(1); q,l=qty_lev(BAL); set_lev(l); order("Buy" if opp=="LONG" else "Sell",q)
   ENTRY=float(price); MODE="HUNTER"; BE_DONE=False; LAST_CLOSE=time.time(); FLIPS_TODAY+=1; VOL_DEAD_START=0; LAST_CERT_DIR=cert_dir
   time.sleep(7); continue
  if VOL_DEAD:
   if VOL_DEAD_START==0: VOL_DEAD_START=time.time(); log(f"[VOL-DIE] Pos {cur} @{ENTRY:.0f} Run ${run:.0f} Vol {vol_score} Vel {velocity}% - Hold 2 min")
   elif time.time()-VOL_DEAD_START>=120:
    log(f"[TP-DEAD-VOL] {cur} @ {price:.0f} Run ${run:.0f} Vol dead 2min - TP here"); close_all(); LAST_CLOSE=time.time(); ENTRY=0; VOL_DEAD_START=0; time.sleep(7); continue
   else:
    left=int(120-(time.time()-VOL_DEAD_START)); log(f"[HOLD-NO-VOL] Pos {cur} @{ENTRY:.0f} Run ${run:.0f} Vol {vol_score} Vel {velocity}% - {left}s to TP")
   time.sleep(7); continue
  else:
   if VOL_DEAD_START!=0: log(f"[VOL-BACK] Pos {cur} Vol {vol_score} Vel {velocity}% - Vol continue")
   VOL_DEAD_START=0
   log(f"[STATS] Bal ${BAL:.2f} Pos {cur} @{ENTRY:.0f} Run ${run:.0f} Price {price:.0f} Cert {cert_dir} {cert:.0f}% Hunt {hunt_dir} {hunt_score}/9 Hunter? {IS_HUNTER} Vol {vol_score} Vel {velocity}% Flips {FLIPS_TODAY}/3")
  time.sleep(7)
 except Exception as e:
  log(f"[ERR] {e}"); traceback.print_exc(); time.sleep(7)
