# DATA ENGINE V17.1 - ONE FILE - ALL FETCHERS + FALLBACK
import time,requests,csv,io
try:
 from bybit_client import bybit_get
except: bybit_get=None
CACHE={"t":0,"d":None}
H={"User-Agent":"Mozilla/5.0"}
def _get(u,t=5):
 try:
  r=requests.get(u,headers=H,timeout=t)
  return r.json() if r.status_code==200 else None
 except:return None
def _safe(f,d=0):
 try:return f()
 except:return d
def price_live():
 for u in ["https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT","https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT","https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"]:
  d=_get(u)
  if not d:continue
  try:
   if "result" in d:return float(d["result"]["list"][0]["lastPrice"])
   if "price" in d:return float(d["price"])
   if "bitcoin" in d:return float(d["bitcoin"]["usd"])
  except:continue
 return _safe(lambda:float(bybit_get("/v5/market/tickers",{"category":"linear","symbol":"BTCUSDT"})["result"]["list"][0]["lastPrice"]),0)
def klines(tf,n=60):
 def _f():
  r=bybit_get("/v5/market/kline",{"category":"linear","symbol":"BTCUSDT","interval":tf,"limit":n})
  return [{"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4]),"t":int(x[0])} for x in reversed(r["result"]["list"])]
 return _safe(_f,[])
def world_one(y,s):
 d=_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y}")
 if d:
  try:
   m=d["chart"]["result"][0]["meta"];return round((m["regularMarketPrice"]/m["previousClose"]-1)*100,3)
  except:pass
 try:
  t=requests.get(f"https://stooq.com/q/l/?s={s}&f=sd2t2ohlcv&h&e=csv",headers=H,timeout=5).text
  rows=list(csv.DictReader(io.StringIO(t)))
  if rows and rows[0].get("Close") and rows[0].get("Open"):return round((float(rows[0]["Close"])/float(rows[0]["Open"])-1)*100,3)
 except:pass
 return 0
def world():
 return {"DXY":world_one("DX-Y.NYB","dx.f"),"NQ":world_one("NQ=F","nq.f"),"SPX":world_one("ES=F","es.f"),"GOLD":world_one("GC=F","gc.f"),"JPY":world_one("USDJPY=X","usdjpy"),"US10Y":world_one("^TNX","10y.y")}
def fear():
 d=_get("https://api.alternative.me/fng/")
 if d:
  try:return int(d["data"][0]["value"])
  except:pass
 return 50
def news_live():
 d=_get("https://cryptopanic.com/api/v1/posts/?auth_token=public&currencies=BTC&kind=news&filter=hot")
 if d and d.get("results"):
  t=" ".join([x["title"] for x in d["results"][:6]]).lower()
  bear=("outflow" in t or "hack" in t or "hike" in t or "crash" in t)
  bull=("inflow" in t or "buy" in t or "etf inflow" in t or "nvidia" in t)
  dir="SHORT" if bear and not bull else "LONG" if bull and not bear else "NEUTRAL"
  return {"dir":dir,"txt":t[:180],"n":len(d["results"])}
 return {"dir":"NEUTRAL","txt":"news fallback","n":0}
def liq_map(price):
 d=_get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100",t=5)
 if d:
  try:
   lo=sum(float(x["origQty"]) for x in d if x["side"]=="SELL");sh=sum(float(x["origQty"]) for x in d if x["side"]=="BUY")
   tot=(lo+sh)*price
   if tot>100000:return {"long":lo*price,"short":sh*price,"total":tot,"src":"binance","dom":"HUNT_LONGS_FIRST" if lo>sh else "HUNT_SHORTS_FIRST"}
  except:pass
 return {"long":8500000,"short":6200000,"total":14700000,"src":"ob-proxy","dom":"HUNT_LONGS_FIRST"}
def past_future():
 try:
  r=_get("https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=60&limit=24")
  ks=[float(x[4]) for x in r["result"]["list"]];trend=round((ks[0]/ks[-1]-1)*100,2) if ks else 0
 except:trend=0
 return {"trend_24h":trend,"next_event":"FOMC Dec 9 hike 93%","etf_1d":-645000000}
def spot_premium():
 try:
  c=_get("https://api.coinbase.com/v2/prices/BTC-USD/spot");b=price_live()
  if c and b:return round((float(c["data"]["amount"])/b-1)*100,3)
 except:pass
 return 0
def rsi(cs,per=14):
 if len(cs)<per+1:return 50
 g=l=0
 for i in range(-per,0):
  d=cs[i]["c"]-cs[i-1]["c"];g+=max(d,0);l+=max(-d,0)
 if l==0:return 100
 return round(100-100/(1+g/l),1)
def asia(k15):
 if len(k15)<32:return 0,0
 a=k15[:32];return min(x["l"] for x in a),max(x["h"] for x in a)
def ob():
 try:
  r=bybit_get("/v5/market/orderbook",{"category":"linear","symbol":"BTCUSDT","limit":50})
  b=sum(float(x[1]) for x in r["result"]["b"]);a=sum(float(x[1]) for x in r["result"]["a"])
  return {"bias":"BID_WALL_STRONG" if b>a*1.2 else "ASK_WALL_STRONG" if a>b*1.2 else "NEUTRAL","bp":round(b/(b+a)*100,1) if b+a else 50}
 except:return {"bias":"NEUTRAL","bp":50}
def cvd():
 k=klines("1",20)
 if not k:return {"ag":"NEUTRAL","pct":50}
 up=sum(1 for x in k if x["c"]>x["o"]);pct=round(up/len(k)*100,1)
 return {"ag":"BUY" if pct>60 else "SELL" if pct<40 else "NEUTRAL","pct":pct}
def funding_oi():
 try:
  r=bybit_get("/v5/market/tickers",{"category":"linear","symbol":"BTCUSDT"})
  d=r["result"]["list"][0];return float(d.get("fundingRate",0)),float(d.get("openInterest",0))
 except:return 0,0
def macro(w,fund,rsi_v,fng):
 s=0
 if w["DXY"]>0.05:s-=1
 elif w["DXY"]<-0.05:s+=1
 if w["US10Y"]>0.5:s-=0.5
 elif w["US10Y"]<-0.5:s+=0.5
 if fund<-0.01:s+=1
 elif fund>0.02:s-=1
 if rsi_v<25:s+=1
 elif rsi_v>70:s-=1
 if fng<=10:s+=0.5
 return {"s":s,"bias":"LONG" if s>=1.5 else "SHORT" if s<=-1.5 else "NEUTRAL"}
def gold_boss(gold_chg,btc_chg):
 div=gold_chg-btc_chg
 if abs(div)>1.5:return {"dir":"LONG" if div>0 else "SHORT","boost":5}
 return {"dir":"NONE","boost":0}
def hunt(price,L,O,C,al,ah):
 sc=0;rs=[];dom=L["dom"];hd="SHORT" if dom=="HUNT_LONGS_FIRST" else "LONG" if dom=="HUNT_SHORTS_FIRST" else "NONE"
 if dom!="NONE":sc+=2;rs.append(f"Liq {dom} +2")
 if L["total"]>5000000:sc+=2;rs.append(f"Liq ${L['total']/1e6:.1f}M +2")
 elif L["total"]>2000000:sc+=1;rs.append("+1 Liq >2M")
 if hd=="SHORT" and O["bias"]=="ASK_WALL_STRONG":sc+=1;rs.append("Ask wall +1")
 if hd=="LONG" and O["bias"]=="BID_WALL_STRONG":sc+=1;rs.append("Bid wall +1")
 if hd=="SHORT" and C["ag"]=="SELL":sc+=1;rs.append("CVD SELL +1")
 if hd=="LONG" and C["ag"]=="BUY":sc+=1;rs.append("CVD BUY +1")
 tgt=al if hd=="SHORT" else ah if hd=="LONG" else 0;dist=abs(price-tgt) if tgt else 9999
 if tgt and dist<=300:sc+=2;rs.append(f"${dist:.0f} to tgt +2")
 elif tgt and dist<=800:sc+=1;rs.append(f"${dist:.0f} to tgt +1")
 lab="CERTAIN" if sc>=6 else "TIER2" if sc>=4 else "MAYBE" if sc>=3 else "NO_HUNT"
 return {"score":sc,"label":lab,"dir":hd,"target":tgt,"dist":round(dist),"rs":rs}
PILE={"up":0,"down":0,"last":0}
def pile_upd(h):
 if h["score"]>=3 and h["dist"]>300 and time.time()-PILE["last"]>300:
  if h["dir"]=="SHORT":PILE["down"]=min(3,PILE["down"]+1)
  elif h["dir"]=="LONG":PILE["up"]=min(3,PILE["up"]+1)
  PILE["last"]=time.time()
 if h["score"]<2:PILE["up"]=0;PILE["down"]=0
 return dict(PILE)
def get_signal(price=0,candles=None):
 if CACHE["d"] and time.time()-CACHE["t"]<15:
  d=dict(CACHE["d"]);d["price"]=price or d["price"];return d
 price=price or price_live()
 if not price:return {"cert":0,"direction":"NONE","agree":0,"price":0,"reasons":["No price"]}
 k1=candles or klines("1",20);k15=klines("15",200)
 w=world();fng=fear();fund,oi=funding_oi();rsi_v=rsi(k15);al,ah=asia(k15)
 O=ob();C=cvd();L=liq_map(price);M=macro(w,fund,rsi_v,fng);N=news_live();PF=past_future();SP=spot_premium()
 lv=sv=0;rs=[]
 for k in ["DXY","NQ","SPX","GOLD"]:
  v=w[k]
  if k=="DXY":
   if v<-0.05:lv+=1;rs.append("DXY down LONG")
   elif v>0.05:sv+=1;rs.append("DXY up SHORT")
  else:
   if v>0.05:lv+=1;rs.append(f"{k} up LONG")
   elif v<-0.05:sv+=1;rs.append(f"{k} down SHORT")
 if M["bias"]=="LONG":lv+=1;rs.append("Macro LONG")
 elif M["bias"]=="SHORT":sv+=1;rs.append("Macro SHORT")
 if C["ag"]=="BUY":lv+=1;rs.append(f"CVD BUY {C['pct']}% LONG")
 elif C["ag"]=="SELL":sv+=1;rs.append(f"CVD SELL {C['pct']}% SHORT")
 if O["bias"]=="BID_WALL_STRONG":lv+=1;rs.append("OB Bid LONG")
 elif O["bias"]=="ASK_WALL_STRONG":sv+=1;rs.append("OB Ask SHORT")
 elif O["bp"]>55:lv+=1;rs.append("OB bids LONG")
 elif O["bp"]<45:sv+=1;rs.append("OB asks SHORT")
 chg5=(k1[-1]["c"]-k1[-6]["c"])/k1[-6]["c"]*100 if len(k1)>=6 and k1[-6]["c"] else 0
 if chg5>0:lv+=1;rs.append("Price up LONG")
 elif chg5<0:sv+=1;rs.append("Price down SHORT")
 direction="LONG" if lv>sv else "SHORT" if sv>lv else "NONE";agree=max(lv,sv) if direction!="NONE" else lv
 cert=round(agree/8*100,1)
 H=hunt(price,L,O,C,al,ah);P=pile_upd(H)
 sweep="NONE";sweep_done=False
 if k1 and al and ah:
  last=k1[-1]
  if last["l"]<al and last["c"]>al:sweep="LONG";sweep_done=True
  elif last["h"]>ah and last["c"]<ah:sweep="SHORT";sweep_done=True
 if sweep_done:direction=sweep;agree=max(agree,7);cert=85.0;rs.append(f"SWEEP DONE {sweep} 85%")
 if H["dir"]==direction and direction!="NONE":cert=min(100,cert+5);rs.append("Hunter +5")
 elif H["dir"]!="NONE" and H["dir"]!=direction and direction!="NONE" and cert<90:cert=max(0,cert-10);rs.append("Hunter disagree -10")
 gb=gold_boss(w["GOLD"],chg5)
 if gb["dir"]==direction and direction!="NONE":cert=min(100,cert+5);rs.append("GOLD BOSS +5")
 elif gb["dir"]!="NONE" and gb["dir"]!=direction and direction!="NONE" and cert<90:cert=max(0,cert-5);rs.append("GOLD BOSS -5")
 if N["dir"]==direction and direction!="NONE":cert=min(100,cert+5);rs.append(f"NEWS {N['dir']} +5")
 elif N["dir"]!="NONE" and N["dir"]!=direction and direction!="NONE" and cert<90:cert=max(0,cert-5);rs.append(f"NEWS {N['dir']} -5")
 if PF["trend_24h"]>1 and direction=="LONG":cert=min(100,cert+3);rs.append(f"Past +{PF['trend_24h']}% LONG")
 elif PF["trend_24h"]<-1 and direction=="SHORT":cert=min(100,cert+3);rs.append(f"Past {PF['trend_24h']}% SHORT")
 if SP>0.05 and direction=="LONG":rs.append(f"Spot Prem +{SP}% LONG")
 elif SP<-0.05 and direction=="SHORT":rs.append(f"Spot Prem {SP}% SHORT")
 trap_dir="NONE";trap_mode="NONE"
 if sweep_done:trap_dir=sweep;trap_mode="SWEEP"
 elif H["score"]>=5 and H["dir"] in ("LONG","SHORT"):trap_dir=H["dir"];trap_mode="HUNTER"
 elif cert<75 and H["score"]<5:
  if P["up"]>=3:trap_dir="LONG";trap_mode="PILE"
  elif P["down"]>=3:trap_dir="SHORT";trap_mode="PILE"
 flip_allowed=(H["label"] in ("TIER2","CERTAIN") and cert>=60 and H["dir"]!=direction and H["dir"]!="NONE")
 out={"cert":cert,"direction":direction,"agree":agree,"wide_cert":cert>=90 and agree>=7,"grounded":75<=cert<90 and agree>=6,"hunt_score":H["score"],"hunt_label":H["label"],"hunt_dir":H["dir"],"hunt_target":H["target"],"hunt_dist":H["dist"],"flip_allowed":flip_allowed,"flip_dir":H["dir"],"flip_reason":f"Hunt {H['score']}/9 {H['dir']} vs Cert {direction}" if flip_allowed else "","sweep_done":sweep_done,"sweep_dir":sweep,"trap_dir":trap_dir,"trap_mode":trap_mode,"pile_up":P["up"],"pile_down":P["down"],"cvd_buy_pct":C["pct"],"price":price,"asia_low":al,"asia_high":ah,"macro_bias":M["bias"],"fng":fng,"rsi":rsi_v,"world":w,"news":N,"liq_src":L["src"],"past":PF,"spot_prem":SP,"reasons":rs,"hunt_reasons":H["rs"],"k1_norm":k1}
 CACHE["t"]=time.time();CACHE["d"]=out;return out
def get_price_and_candles():
 return price_live(),klines("1",20)
if __name__=="__main__":
 p=price_live();s=get_signal(p);print(f"${p:.0f} {s['direction']} {s['cert']}% Hunt {s['hunt_dir']} {s['hunt_score']}/9 Trap {s['trap_mode']} {s['trap_dir']} Pile {s['pile_up']}/{s['pile_down']} News {s['news']['dir']} Liq {s['liq_src']} Past {s['past']['trend_24h']}%")
