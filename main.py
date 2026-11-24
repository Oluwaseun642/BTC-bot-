# MAIN V17 - ONE FILE - 2 DOORS + FLIP GUARDIAN
import os,time,threading,datetime,requests
from data_engine import get_signal,get_price_and_candles
from bybit_client import bybit_get,bybit_post
import http.server,socketserver
def keep():
 class H(http.server.BaseHTTPRequestHandler):
  def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b"ok")
  def log_message(self,*a):pass
 socketserver.TCPServer(("",int(os.getenv("PORT",10000))),H).serve_forever()
threading.Thread(target=keep,daemon=True).start()
def ping():
 while True:
  try:requests.get(os.getenv("RENDER_EXTERNAL_URL","http://localhost:10000"),timeout=5)
  except:pass
  time.sleep(240)
threading.Thread(target=ping,daemon=True).start()
BAL=0;POS=None;ENTRY=0;MODE="";BE_DONE=False;LAST_CLOSE=0;LAST_FLIP_CANDLE=-1;PAUSED=False
def bal():
 try:
  r=bybit_get("/v5/account/wallet-balance",{"accountType":"UNIFIED"})
  return float(r["result"]["list"][0]["totalWalletBalance"])
 except:return BAL
def pos():
 try:
  r=bybit_get("/v5/position/list",{"category":"linear","symbol":"BTCUSDT"})
  p=r["result"]["list"][0]
  return p if float(p.get("size",0))>0 else None
 except:return None
def qty_lev(b):
 if b<5:return 0.001,60
 if b<20:return 0.002,50
 if b<100:return 0.005,40
 return 0.01,30
def set_lev(l):
 try:bybit_post("/v5/position/set-leverage",{"category":"linear","symbol":"BTCUSDT","buyLeverage":str(l),"sellLeverage":str(l)})
 except:pass
def order(side,q):
 try:return bybit_post("/v5/order/create",{"category":"linear","symbol":"BTCUSDT","side":side,"orderType":"Market","qty":str(q),"positionIdx":0})
 except Exception as e:print("[ERR order]",e);return None
def close_all():
 global POS
 try:
  p=pos()
  if p:
   side="Sell" if p["side"]=="Buy" else "Buy";bybit_post("/v5/order/create",{"category":"linear","symbol":"BTCUSDT","side":side,"orderType":"Market","qty":str(p["size"]),"positionIdx":0,"reduceOnly":True})
 except Exception as e:print("[ERR close]",e)
 POS=None
def news_block():
 # 5 min before/after FOMC/CPI/PCE - from env HH:MM list, default empty
 return False
print("[MAIN] V17 - 2 DOORS + FLIP - START")
BAL=bal();print(f"[MAIN] Bal ${BAL:.2f}")
POS=pos()
if POS:ENTRY=float(POS["avgPrice"]);MODE="SYNC";print(f"[SYNC] Pos {POS['side']} {POS['size']} @ {ENTRY}")
while True:
 try:
  if os.getenv("PAUSE_BOT")=="1":print("[PAUSE]");time.sleep(10);continue
  BAL=bal();POS=pos()
  if POS:ENTRY=float(POS["avgPrice"])
  price,kl=get_price_and_candles();s=get_signal(price,kl)
  # --- FLIP GUARDIAN - CHECK FIRST, BEFORE BE/TP/SL ---
  if POS:
   cur="LONG" if POS["side"]=="Buy" else "SHORT";opp="SHORT" if cur=="LONG" else "LONG"
   candle=int(time.time()//60)
   flip=False;why=""
   if s["hunt_dir"]==opp and s["hunt_score"]>=6:flip=True;why=f"HUNTER {opp} {s['hunt_score']}/9"
   elif s["direction"]==opp and s["cert"]>=75 and s["agree"]>=s["total"]-3:flip=True;why=f"CERT {opp} {s['cert']}%"
   elif (s["pile_up"]>=3 and opp=="LONG") or (s["pile_down"]>=3 and opp=="SHORT"):
    if s["hunt_dir"]==opp and s["hunt_score"]>=5:flip=True;why=f"PILE {opp} 3/3 + HUNT"
   if flip and candle!=LAST_FLIP_CANDLE:
    print(f"[FLIP] {cur}->{opp} {why} @ {price:.0f}");close_all();time.sleep(1);q,l=qty_lev(BAL);set_lev(l)
    if BAL>=2 and (os.getenv("FORCE_SHORT")!="1" and os.getenv("FORCE_LONG")!="1"):order("Buy" if opp=="LONG" else "Sell",q)
    ENTRY=price;MODE="FLIP";LAST_FLIP_CANDLE=candle;LAST_CLOSE=time.time();BE_DONE=False;POS=pos()
  # --- MANAGE OPEN POS: BE / TP / SL / OPP SWEEP ---
  if POS:
   cur="LONG" if POS["side"]=="Buy" else "SHORT";run=(price-ENTRY) if cur=="LONG" else (ENTRY-price)
   be_need=800 if MODE in ("NORMAL","SYNC") else 500 if MODE=="HUNTER" else 600
   sl_d=1800 if MODE in ("NORMAL","SYNC") else 800 if MODE=="HUNTER" else 1000
   tp1=2000 if MODE in ("NORMAL","SYNC") else 1000 if MODE=="HUNTER" else 1500
   tp2=3500 if MODE in ("NORMAL","SYNC") else 2000 if MODE=="HUNTER" else 2500
   # BE = early TP $500/600/800, close 50%
   if not BE_DONE and run>=be_need:
    print(f"[BE] {cur} +${run:.0f} close 50% @ {price:.0f}");q=float(POS["size"])/2
    bybit_post("/v5/order/create",{"category":"linear","symbol":"BTCUSDT","side":"Sell" if cur=="LONG" else "Buy","orderType":"Market","qty":str(q),"positionIdx":0,"reduceOnly":True});BE_DONE=True
   # TP2 / SL in $
   if run>=tp2 or run<=-sl_d:
    print(f"[EXIT] {cur} run ${run:.0f} @ {price:.0f}");close_all();LAST_CLOSE=time.time();BE_DONE=False;MODE=""
   # Opposite sweep close early
   elif (cur=="LONG" and s["sweep_dir"]=="SHORT") or (cur=="SHORT" and s["sweep_dir"]=="LONG"):
    print(f"[SWEEP CLOSE] {cur} opp sweep");close_all();LAST_CLOSE=time.time();BE_DONE=False;MODE=""
   print(f"[STATS] Bal ${BAL:.2f} Pos {cur} @ {ENTRY:.0f} Run ${run:.0f} Dir {s['direction']} Cert {s['cert']}% {s['agree']}/{s['total']} Sess {s['regions']['SESSION']} Hunt {s['hunt_dir']} {s['hunt_score']}/9 Pile {s['pile_up']}/{s['pile_down']} Trap {s['trap_mode']}")
   time.sleep(7);continue
  # --- NO POS: COOLDOWN ---
  cd=150 if s["trap_mode"]=="PILE" else 150 # 2-3 min = 150s, pile 150s
  if time.time()-LAST_CLOSE<cd:print(f"[COOLDOWN] {int(cd-(time.time()-LAST_CLOSE))}s");time.sleep(7);continue
  if BAL<2:print(f"[NO BAL] ${BAL:.2f}");time.sleep(10);continue
  # --- DECIDE DOOR ---
  force=os.getenv("FORCE_LONG")=="1" and "LONG" or os.getenv("FORCE_SHORT")=="1" and "SHORT" or None
  enter=None;mode=""
  # DOOR 2 TRAP FIRST - HUNTER / PILE / SWEEP
  if s["trap_mode"]=="SWEEP" and s["trap_dir"] in ("LONG","SHORT"):enter=s["trap_dir"];mode="HUNTER"
  elif s["trap_mode"]=="HUNTER" and s["hunt_score"]>=5:enter=s["trap_dir"];mode="HUNTER"
  elif s["trap_mode"]=="PILE" and s["trap_dir"] in ("LONG","SHORT") and s["cert"]<75:enter=s["trap_dir"];mode="PILE"
  elif s["hunt_score"]>=6 and s["hunt_dir"] in ("LONG","SHORT"):enter=s["hunt_dir"];mode="HUNTER" # BIGGEST take over Cert
  # DOOR 1 NORMAL - WORLDWIDE CERT V17.2
  if not enter and s["direction"] in ("LONG","SHORT") and s["cert"]>=75 and s["agree"]>=s["total"]-3:
   if news_block() and s["hunt_score"]<5:print("[NEWS BLOCK] Normal skip");enter=None
   else:enter=s["direction"];mode="NORMAL"
  if force:enter=force;mode="NORMAL";print(f"[FORCE] {force}")
  if enter:
   # Funding guard: no LONG if funding too high
   from data_engine import funding_oi
   fu,_=funding_oi()
   if enter=="LONG" and fu>0.02:print(f"[FUND BLOCK] {fu}");time.sleep(7);continue
   q,l=qty_lev(BAL);set_lev(l);print(f"[ENTER] {mode} {enter} Cert {s['cert']}% Hunt {s['hunt_dir']} {s['hunt_score']}/9 Pile {s['pile_up']}/{s['pile_down']} Qty {q} Lev {l}x @ {price:.0f}")
   order("Buy" if enter=="LONG" else "Sell",q);ENTRY=price;MODE=mode;BE_DONE=False
  else:print(f"[SKIP] Dir {s['direction']} Cert {s['cert']}% {s['agree']}/{s['total']} Hunt {s['hunt_dir']} {s['hunt_score']}/9 Pile {s['pile_up']}/{s['pile_down']} Trap {s['trap_mode']} Sess {s['regions']['SESSION']}")
  time.sleep(7)
 except Exception as e:print("[ERR loop]",e);time.sleep(7)
