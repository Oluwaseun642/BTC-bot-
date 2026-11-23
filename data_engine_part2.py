# DATA ENGINE V16.2 - PART 2/3 - HUNTER + PILE-UP PATCHED
from data_engine_part1 import _safe_get,_safe_get_text,_now,get_world,get_session,get_hunt_window,get_funding,get_fear,get_open_interest,get_asia_range,calc_rsi,yahoo_price_1h
import time
from xml.etree import ElementTree as ET
# --- PILE-UP PATCHED: Session 60/20, Calm 600/0.7%, Servant + Takeover ---
_PILEUP_OPENS=[0,420,810]
def check_session_reopening_soon(now=None):
    now=now or _now(); mins=now.hour*60+now.minute
    for o in _PILEUP_OPENS:
        to=(o-mins)%1440; since=(mins-o)%1440
        if to<=60: return True,f"Session opens in {to}m - Pile-Up OFF"
        if since<=20: return True,f"Session just opened {since}m ago - Pile-Up OFF"
    return False,"Calm - no session - Pile-Up ON"
def is_volatility_low_and_steady(k1):
    if not k1 or len(k1)<6: return False,"No candles - Pile-Up OFF"
    l6=k1[-6:]; chg=abs(l6[-1]["close"]-l6[0]["close"]); rng=max(c["high"] for c in l6)-min(c["low"] for c in l6); last=l6[-1]; wick=(last["high"]-last["low"])/last["close"]*100 if last["close"] else 999
    if chg>=1000: return False,f"Vol HIGH move ${chg:.0f} >= $1000 - Pile-Up OFF"
    if rng>=600: return False,f"Vol HIGH range ${rng:.0f} >= $600 - Pile-Up OFF"
    if wick>=0.7: return False,f"Vol HIGH wick {wick:.2f}% >=0.7% - Pile-Up OFF"
    return True,f"Vol LOW+Steady range ${rng:.0f} move ${chg:.0f} wick {wick:.2f}% - Pile-Up ON"
def is_pileup_allowed(hunt_score=0,k1=None,wide_cert=False,cert=0,cvd_flip=False,cert_drop=False,move_against=0,liq_total=0,cvd_buy=50,cert_dir="NONE"):
    # Takeover bypasses Calm + Session
    if hunt_score>=6 and liq_total>=5000000 and move_against>=800:
        if (cert_dir=="SHORT" and cvd_buy>=60) or (cert_dir=="LONG" and cvd_buy<=40): return True,f"TAKEOVER bypass - Score {hunt_score} Liq ${liq_total:,.0f} Move ${move_against:.0f}"
    if wide_cert and not cvd_flip and not cert_drop and move_against<300: return False,f"Servant HOLD - Boss still {cert}% - no flip"
    if hunt_score>=6: return True,"Big Hunt 6+ bypass Lock1"
    reopening,reason=check_session_reopening_soon()
    if reopening: return False,f"Lock1 - {reason}"
    vol_ok,vol=is_volatility_low_and_steady(k1 or [])
    if not vol_ok: return False,vol
    return True,f"Lock1+Vol OK - {reason} | {vol}"
_pileup_state={"up":{"count":0,"disappear_streak":0,"prev_liq":None,"prev_score":None,"prev_cvd_buy_pct":None,"active":False},"down":{"count":0,"disappear_streak":0,"prev_liq":None,"prev_score":None,"prev_cvd_buy_pct":None,"active":False}}
def _pileup_update_one(st,is_piling,is_dis):
    if is_dis:
        st["disappear_streak"]+=1
        if st["disappear_streak"]>=3: st["count"]=0; st["active"]=False; st["disappear_streak"]=0
        return st
    st["disappear_streak"]=0
    if is_piling:
        st["count"]+=1
        if st["count"]>=3: st["active"]=True
    return st
def decay_pileup_by_1(dir_against):
    k="up" if dir_against=="UP" else "down"; st=_pileup_state[k]
    if st["count"]>0:
        st["count"]=max(0,st["count"]-1)
        if st["count"]<3: st["active"]=False
    return st["count"]
def reset_pileup(dir_against):
    k="up" if dir_against=="UP" else "down"; _pileup_state[k]={"count":0,"disappear_streak":0,"prev_liq":None,"prev_score":None,"prev_cvd_buy_pct":None,"active":False}
def update_pileup(hunt_cert,liq,cvd,price_chg_5=0.0):
    try:
        score=int(hunt_cert.get("score",0) or 0); hunt_dir=hunt_cert.get("hunt_dir","NONE"); long_liq=float(liq.get("long_liq",0) or 0); short_liq=float(liq.get("short_liq",0) or 0); cvd_buy=float(cvd.get("buy_pct",50.0) or 50.0); cvd_agg=str(cvd.get("aggressive","NEUTRAL"))
        up=_pileup_state["up"]; down=_pileup_state["down"]
        up_piling=(hunt_dir=="UP_FIRST") or (up["prev_liq"] is not None and short_liq>up["prev_liq"]*1.10) or (up["prev_cvd_buy_pct"] is not None and cvd_buy>up["prev_cvd_buy_pct"]+2) or (price_chg_5>=0 and (hunt_dir=="UP_FIRST" or cvd_agg=="BUY"))
        up_dis=(score<3 and hunt_dir!="UP_FIRST" and cvd_agg in ("SELL","NEUTRAL") and ((up["prev_liq"] is not None and short_liq<up["prev_liq"]*0.95) or (up["count"]>0 and score<=2)))
        _pileup_update_one(up,up_piling,up_dis); up["prev_liq"]=short_liq; up["prev_score"]=score; up["prev_cvd_buy_pct"]=cvd_buy
        down_piling=(hunt_dir=="DOWN_FIRST") or (down["prev_liq"] is not None and long_liq>down["prev_liq"]*1.10) or (down["prev_cvd_buy_pct"] is not None and cvd_buy<down["prev_cvd_buy_pct"]-2) or (price_chg_5<=0 and (hunt_dir=="DOWN_FIRST" or cvd_agg=="SELL"))
        down_dis=(score<3 and hunt_dir!="DOWN_FIRST" and cvd_agg in ("BUY","NEUTRAL") and ((down["prev_liq"] is not None and long_liq<down["prev_liq"]*0.95) or (down["count"]>0 and score<=2)))
        _pileup_update_one(down,down_piling,down_dis); down["prev_liq"]=long_liq; down["prev_score"]=score; down["prev_cvd_buy_pct"]=cvd_buy
        return {"pileup_up":bool(up["active"]),"pileup_up_count":int(up["count"]),"pileup_down":bool(down["active"]),"pileup_down_count":int(down["count"])}
    except Exception as e: return {"pileup_up":False,"pileup_up_count":0,"pileup_down":False,"pileup_down_count":0,"error":str(e)}
_void_memory={"up":None,"down":None}
def remember_void(dir_against,target,liq_at,ob_wall):
    k="up" if dir_against=="UP" else "down"; _void_memory[k]={"price":float(target),"liq_at_level":float(liq_at or 0),"ob_wall_usd":float(ob_wall or 0),"touched":False}
def check_void_eaten_live(dir_against,price,liq_now,ob_now,k1):
    k="up" if dir_against=="UP" else "down"; void=_void_memory.get(k)
    if not void or not void.get("price"): return False,"No void remembered"
    target=void["price"]
    if not k1: return False,"No candles"
    last=k1[-1]; touched=(last["high"]>=target) if dir_against=="UP" else (last["low"]<=target)
    if touched: void["touched"]=True
    if not void["touched"]: return False,f"Void ${target:,.0f} not touched"
    closed_back=(last["close"]<target) if dir_against=="UP" else (last["close"]>target)
    if not closed_back: return False,f"Price still beyond void ${target:,.0f}"
    liq_gone=void["liq_at_level"]>0 and liq_now is not None and float(liq_now)<void["liq_at_level"]*0.30
    ob_gone=void["ob_wall_usd"]>0 and ob_now is not None and float(ob_now)<void["ob_wall_usd"]*0.30
    if liq_gone or ob_gone: return True,f"Void Eaten Live - ${target:,.0f} touched, close back, liq/OB gone"
    return False,f"Void ${target:,.0f} touched+close back, but liq/OB still live"
def is_pileup_done(dir_against,price,liq_now,ob_now,k1,hunt_score,cvd_agg,cert_against=False):
    void_eaten,void_reason=check_void_eaten_live(dir_against,price,liq_now,ob_now,k1); confirms=[]
    if void_eaten: confirms.append("Void Eaten Live")
    if hunt_score<3: confirms.append(f"Score drop {hunt_score}<3")
    if dir_against=="UP" and cvd_agg=="SELL": confirms.append("CVD flip BUY->SELL vs UP")
    if dir_against=="DOWN" and cvd_agg=="BUY": confirms.append("CVD flip SELL->BUY vs DOWN")
    if cert_against: confirms.append("Cert 85%+ against pile-up")
    if len(confirms)>=2: return True,f"Pile-Up Done - {'; '.join(confirms)}"
    return False,f"Pile-Up NOT Done - {void_reason} | Confirms: {', '.join(confirms) if confirms else 'none'}"
def get_liq_clusters(price,k1=None):
    if not price: return {"long_liq":0,"short_liq":0,"total":0,"dominant":"UNKNOWN","hunt_dir":"NONE","imbalance_pct":0.0,"src":"NO-PRICE","thresh":1.4,"long_1pct":0,"short_1pct":0,"long_2pct":0,"short_2pct":0}
    long_liq=0.0; short_liq=0.0; src="LIVE-FAIL"
    try:
        j=_safe_get("https://fapi.binance.com/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=100")
        if isinstance(j,list) and len(j)>0:
            for x in j:
                sz=float(x.get("origQty",0))*float(x.get("price",price))
                if x.get("side")=="SELL": long_liq+=sz
                elif x.get("side")=="BUY": short_liq+=sz
            if long_liq+short_liq>0: src="Binance-LIVE"
    except: pass
    if src=="LIVE-FAIL":
        try:
            j=_safe_get("https://api.bybit.com/v5/market/liquidation?category=linear&symbol=BTCUSDT&limit=50")
            if j:
                for x in j.get("result",{}).get("list",[]):
                    sz=float(x.get("size",0))*float(x.get("price",price))
                    if x.get("side")=="Sell": long_liq+=sz
                    elif x.get("side")=="Buy": short_liq+=sz
                if long_liq+short_liq>0: src="Bybit-LIVE"
        except: pass
    if src=="LIVE-FAIL": long_liq,short_liq=500000.0,500000.0; src="Proxy-50-50-BALANCED"
    total=long_liq+short_liq; hunt_active,_=get_hunt_window(); thresh=1.3 if hunt_active else 1.4
    if total>0:
        if long_liq>short_liq*thresh: dominant="HUNT_LONGS_FIRST"; hunt_dir="DOWN_FIRST"
        elif short_liq>long_liq*thresh: dominant="HUNT_SHORTS_FIRST"; hunt_dir="UP_FIRST"
        else: dominant="BALANCED"; hunt_dir="NONE"
        imb=round((long_liq-short_liq)/total*100,1)
    else: dominant="UNKNOWN"; hunt_dir="NONE"; imb=0.0
    return {"long_liq":round(long_liq,0),"short_liq":round(short_liq,0),"total":round(total,0),"dominant":dominant,"hunt_dir":hunt_dir,"imbalance_pct":imb,"src":src,"thresh":thresh,"long_1pct":round(long_liq*0.4,0),"short_1pct":round(short_liq*0.4,0),"long_2pct":round(long_liq*0.7,0),"short_2pct":round(short_liq*0.7,0)}
def _parse_ob(bids,asks,src):
    bb=max(bids,key=lambda x: float(x[1])*float(x[0])) if bids else [0,0]; aa=max(asks,key=lambda x: float(x[1])*float(x[0])) if asks else [0,0]
    bwp=float(bb[0]); bwu=float(bb[1])*bwp; awp=float(aa[0]); awu=float(aa[1])*awp; bv=sum(float(x[1])*float(x[0]) for x in bids); av=sum(float(x[1])*float(x[0]) for x in asks); total=bv+av; bp=(bv/total*100) if total else 50.0
    bias="BID_WALL_STRONG" if bwu>awu*1.8 else "ASK_WALL_STRONG" if awu>bwu*1.8 else "BALANCED"
    return {"bid_wall_price":bwp,"bid_wall_usd":round(bwu,0),"ask_wall_price":awp,"ask_wall_usd":round(awu,0),"bid_vol":round(bv,0),"ask_vol":round(av,0),"buy_pressure":round(bp,1),"cluster_bias":bias,"src":src}
def get_ob_clusters(price):
    try:
        j=_safe_get("https://api.bybit.com/v5/market/orderbook?category=linear&symbol=BTCUSDT&limit=50")
        if j: return _parse_ob(j["result"]["b"],j["result"]["a"],"Bybit-LIVE")
    except: pass
    try:
        j=_safe_get("https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=50")
        if j: return _parse_ob(j["bids"],j["asks"],"Binance-LIVE")
    except: pass
    return {"bid_wall_price":0,"bid_wall_usd":0,"ask_wall_price":0,"ask_wall_usd":0,"bid_vol":0,"ask_vol":0,"buy_pressure":50.0,"cluster_bias":"UNKNOWN","src":"LIVE-FAIL"}
def get_cvd_live():
    try:
        j=_safe_get("https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=200")
        if j:
            lst=j["result"]["list"]; bv=sum(float(x.get("size",0)) for x in lst if x.get("side")=="Buy"); sv=sum(float(x.get("size",0)) for x in lst if x.get("side")=="Sell")
            if bv+sv>0:
                bp=bv/(bv+sv)*100; agg="BUY" if bp>55 else "SELL" if bp<45 else "NEUTRAL"; return {"cvd":round(bv-sv,3),"buy_vol":round(bv,3),"sell_vol":round(sv,3),"buy_pct":round(bp,1),"aggressive":agg,"src":"Bybit-Trades-LIVE"}
    except: pass
    return {"cvd":0.0,"buy_vol":0,"sell_vol":0,"buy_pct":50.0,"aggressive":"NEUTRAL","src":"LIVE-FAIL"}
def get_spot_premium():
    try:
        cb=_safe_get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        if cb:
            cb_p=float(cb["price"])
            for url,parse in [("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",lambda j: float(j["price"])),("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP",lambda j: float(j["data"][0]["last"]))]:
                j=_safe_get(url)
                if not j: continue
                bn_p=parse(j); prem=cb_p-bn_p; bias="SPOT_BUYING" if prem>50 else "SPOT_SELLING" if prem<-50 else "NEUTRAL"; return {"coinbase":cb_p,"binance":bn_p,"premium_usd":round(prem,1),"premium_pct":round(prem/bn_p*100,4) if bn_p else 0,"bias":bias,"src":"Coinbase-LIVE"}
    except: pass
    return {"coinbase":0,"binance":0,"premium_usd":0,"premium_pct":0,"bias":"UNKNOWN","src":"LIVE-FAIL"}
def get_spread_score(price,spot,funding):
    prem=spot.get("premium_usd",0) if spot else 0; cbp=spot.get("coinbase",0) if spot else 0; cb_bybit=(cbp-price) if cbp and price else 0; score=0; reasons=[]
    if prem>=100: score+=2; reasons.append(f"Spot prem +${prem:.0f} +2")
    elif prem>=50: score+=1; reasons.append(f"Spot prem +${prem:.0f} +1")
    elif prem<=-100: score-=2; reasons.append(f"Spot prem ${prem:.0f} -2")
    elif prem<=-50: score-=1; reasons.append(f"Spot prem ${prem:.0f} -1")
    if cb_bybit>=150: score+=2; reasons.append(f"Coinbase-Bybit +${cb_bybit:.0f} +2")
    elif cb_bybit>=80: score+=1; reasons.append(f"Coinbase-Bybit +${cb_bybit:.0f} +1")
    elif cb_bybit<=-150: score-=2; reasons.append(f"Coinbase-Bybit ${cb_bybit:.0f} -2")
    elif cb_bybit<=-80: score-=1; reasons.append(f"Coinbase-Bybit ${cb_bybit:.0f} -1")
    crowded=False
    if funding is not None and funding>0.05 and score>0: score-=1; crowded=True; reasons.append("Funding crowded LONG -1")
    if funding is not None and funding<-0.03 and score<0: score+=1; crowded=True; reasons.append("Funding crowded SHORT +1")
    bias="LONG" if score>=3 else "SHORT" if score<=-3 else "LONG_WEAK" if score>0 else "SHORT_WEAK" if score<0 else "NEUTRAL"
    return {"score":score,"bias":bias,"spot_premium_usd":round(prem,1),"coinbase":round(cbp,1),"coinbase_bybit_spread":round(cb_bybit,1),"crowded":crowded,"reasons":reasons}
_gold_state={"break_active":False,"resolve_since":0,"break_candles":0,"last_break_ts":0}
def get_gold_5m_series():
    try:
        for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
            j=_safe_get(f"{base}/v8/finance/chart/GC=F?range=1d&interval=5m")
            if j:
                res=j["chart"]["result"][0]; q=res["indicators"]["quote"][0]; closes=[c for c in q.get("close",[]) if c is not None]; highs=[h for h in q.get("high",[]) if h is not None]; lows=[l for l in q.get("low",[]) if l is not None]
                if len(closes)>=4: return closes,highs,lows
    except: pass
    return [],[],[]
def get_gold_boss(gold_day,btc_15m,funding,oi_chg):
    closes,highs,lows=get_gold_5m_series(); gold_15m=0.0; gold_1h=0.0; wick=0.0; wick_active=False
    if len(closes)>=4:
        if closes[-4]: gold_15m=round((closes[-1]-closes[-4])/closes[-4]*100,3)
        if len(closes)>=13 and closes[-13]: gold_1h=round((closes[-1]-closes[-13])/closes[-13]*100,3)
    if highs and lows and closes and closes[-1]: wick=round((highs[-1]-lows[-1])/closes[-1]*100,3); wick_active=wick>0.5
    is_break=False; div=0.0; break_dir="NONE"; tier="NONE"
    if gold_15m!=0 and btc_15m!=0:
        if (gold_15m>0 and btc_15m<0) or (gold_15m<0 and btc_15m>0):
            div=round(abs(gold_15m-btc_15m),3); tier="TIER1_IGNORE" if div<=0.3 else "TIER2_HOLD_WATCH" if div<=0.8 else "TIER3_BIG_BREAK"; is_break=div>0.3
            if is_break: break_dir="BTC_UP_GOLD_DOWN" if btc_15m>0 else "BTC_DOWN_GOLD_UP"
    now=time.time()
    if is_break:
        if not _gold_state["break_active"]: _gold_state["break_active"]=True; _gold_state["break_candles"]=1; _gold_state["last_break_ts"]=now
        elif now-_gold_state["last_break_ts"]>=240: _gold_state["break_candles"]+=1; _gold_state["last_break_ts"]=now
        _gold_state["resolve_since"]=0
    elif _gold_state["break_active"]: _gold_state["break_active"]=False; _gold_state["resolve_since"]=now; _gold_state["break_candles"]=0
    confirm_ok=False; wait=0
    if not is_break and _gold_state["resolve_since"]>0:
        el=now-_gold_state["resolve_since"]
        if el>=120 and not wick_active: confirm_ok=True
        else: wait=max(0,int(120-el))
    elif not is_break: confirm_ok=True
    flip_to="LONG" if _gold_state["break_candles"]>=3 and is_break and break_dir=="BTC_UP_GOLD_DOWN" else "SHORT" if _gold_state["break_candles"]>=3 and is_break else "NONE"
    boss_boost=0; boss_dir="NONE"; boss_reasons=[]
    if not is_break:
        if gold_15m<-0.05 and btc_15m<-0.05: boss_dir="SHORT"; boss_boost=15 if abs(gold_day)>=2.0 else 10 if abs(gold_day)>=1.0 else 5; boss_reasons.append(f"GOLD BOSS SHORT +{boss_boost}% | GOLD day {gold_day:.2f}% + GOLD 15m {gold_15m:.2f}% + BTC 15m {btc_15m:.2f}%")
        elif gold_15m>0.05 and btc_15m>0.05: boss_dir="LONG"; boss_boost=15 if abs(gold_day)>=2.0 else 10 if abs(gold_day)>=1.0 else 5; boss_reasons.append(f"GOLD BOSS LONG +{boss_boost}% | GOLD day {gold_day:.2f}% + GOLD 15m {gold_15m:.2f}% + BTC 15m {btc_15m:.2f}%")
    dom_boost=0; dom_dir="NONE"; dom_reasons=[]
    if gold_day<-1.0 and oi_chg>0.1 and funding is not None and funding>0.02: dom_dir="SHORT"; dom_boost=10; dom_reasons.append(f"DOMINANCE SHORT +10% | GOLD {gold_day:.2f}% + OI +{oi_chg:.2f}% + Funding +{funding:.4f}%")
    elif gold_day>1.0 and oi_chg>0.1 and funding is not None and funding<-0.01: dom_dir="LONG"; dom_boost=10; dom_reasons.append(f"DOMINANCE LONG +10% | GOLD +{gold_day:.2f}% + OI +{oi_chg:.2f}% + Funding {funding:.4f}%")
    return {"gold_15m":gold_15m,"gold_1h":gold_1h,"gold_day":gold_day,"btc_15m":round(btc_15m,3),"wick_pct":wick,"wick_active":wick_active,"is_break":is_break,"divergence":div,"break_dir":break_dir,"break_tier":tier,"break_candles":_gold_state["break_candles"],"confirm_ok":confirm_ok,"confirm_wait":wait,"resolve_since":_gold_state["resolve_since"],"flip_to":flip_to,"boss_boost":boss_boost,"boss_dir":boss_dir,"boss_reasons":boss_reasons,"dom_boost":dom_boost,"dom_dir":dom_dir,"dom_reasons":dom_reasons}
def get_funding_cascade(funding,oi_chg=0.0,price_chg_5=0.0):
    risk="NONE"; reason=""
    if funding>0.02 and oi_chg>0.1 and price_chg_5<0: risk="CASCADE_DOWN"; reason=f"Funding +{funding:.4f}% crowded LONG + OI up + price down"
    elif funding>0.05: risk="CASCADE_DOWN"; reason=f"Funding +{funding:.4f}% extreme LONG"
    elif funding<-0.01 and oi_chg>0.1 and price_chg_5>0: risk="CASCADE_UP"; reason=f"Funding {funding:.4f}% crowded SHORT + OI up + price up"
    elif funding<-0.03: risk="CASCADE_UP"; reason=f"Funding {funding:.4f}% extreme SHORT"
    return {"funding":funding,"risk":risk,"reason":reason,"oi_chg_5m":oi_chg,"price_chg_5m":round(price_chg_5,3)}
_BEAR=["hike","hawkish","outflow","sue","lawsuit","tariff","ban","hack","selloff","sell-off","dump","crash","recession","inflation","probe","fraud","liquidat","bearish","fear","war","sanction","default"]; _BULL=["cut","dovish","inflow","approve","approval","etf","adopt","bullish","rally","surge","accumulat","buy","partnership","launch","upgrade","record","boom"]
_news_cache={"time":0,"data":None}
def _score_headlines(heads):
    bear=bull=0
    for h in heads[:25]:
        t=h.lower(); b=sum(1 for w in _BEAR if w in t); u=sum(1 for w in _BULL if w in t)
        if b>u: bear+=1
        elif u>b: bull+=1
    if bear>=4 and bear>bull*2: return -2,f"News bearish {bear} vs bullish {bull}",bear,bull
    if bull>=4 and bull>bear*2: return 2,f"News bullish {bull} vs bearish {bear}",bear,bull
    if bear>bull: return -1,f"News bearish {bear} vs bullish {bull}",bear,bull
    if bull>bear: return 1,f"News bullish {bull} vs bearish {bear}",bear,bull
    return 0,"News neutral",bear,bull
def _fetch_headlines():
    heads=[]
    for q in ["bitcoin","BTC","Federal Reserve","ETF","tariff"]:
        try:
            j=_safe_get(f"https://query1.finance.yahoo.com/v1/finance/search?q={q}&newsCount=5")
            if isinstance(j,dict) and j.get("news"):
                for n in j["news"]: heads.append(str(n.get("title","")))
        except: pass
    try:
        txt=_safe_get_text("https://www.coindesk.com/arc/outboundfeeds/rss/",timeout=5)
        if txt:
            root=ET.fromstring(txt)
            for it in root.findall(".//item")[:15]: heads.append(it.findtext("title",""))
    except: pass
    try:
        txt=_safe_get_text("https://cointelegraph.com/rss",timeout=5)
        if txt:
            root=ET.fromstring(txt)
            for it in root.findall(".//item")[:15]: heads.append(it.findtext("title",""))
    except: pass
    return [h for h in heads if h][:40]
def get_news_live(world,price_chg_1h=0.0,cvd_agg="NEUTRAL",btc_move_1h=0.0):
    if _news_cache["data"] is not None and time.time()-_news_cache["time"]<60: base=dict(_news_cache["data"])
    else:
        heads=_fetch_headlines(); hs,hr,bear,bull=_score_headlines(heads); base={"headline_score":hs,"headline_reason":hr,"bear_count":bear,"bull_count":bull,"headlines":heads[:8]}; _news_cache["time"]=time.time(); _news_cache["data"]=base
    spx=world.get("SPX",0); nq=world.get("NQ",0); dxy=world.get("DXY",0); gold=world.get("GOLD",0); oil=world.get("OIL",0); num=0; num_reasons=[]
    if spx<=-1.0: num-=1; num_reasons.append(f"SPX day {spx:.2f}% risk-off -1")
    elif spx>=1.0: num+=1; num_reasons.append(f"SPX day +{spx:.2f}% risk-on +1")
    if nq<=-1.5: num-=1; num_reasons.append(f"NQ day {nq:.2f}% -1")
    elif nq>=1.5: num+=1; num_reasons.append(f"NQ day +{nq:.2f}% +1")
    if dxy>=0.5: num-=1; num_reasons.append(f"DXY day +{dxy:.2f}% headwind -1")
    elif dxy<=-0.5: num+=1; num_reasons.append(f"DXY day {dxy:.2f}% tailwind +1")
    if gold>=1.0 and spx<0: num-=1; num_reasons.append(f"GOLD +{gold:.2f}% + SPX down risk-off -1")
    if oil>=2.0 and spx<0: num-=1; num_reasons.append(f"OIL +{oil:.2f}% + SPX down shock -1")
    price_agree=(btc_move_1h>0 and cvd_agg=="BUY") or (btc_move_1h<0 and cvd_agg=="SELL") or abs(btc_move_1h)<0.1
    h_score=base["headline_score"]
    if h_score!=0 and not price_agree: h_eff=0; h_note="Headline ignored - price/CVD disagree"
    else: h_eff=h_score; h_note=base["headline_reason"]
    total=max(-2,min(2,h_eff+(1 if num>=2 else -1 if num<=-2 else 0)))
    if num>=2 and total<0: total=0
    if num<=-2 and total>0: total=0
    direction="SHORT" if total<0 else "LONG" if total>0 else "NEUTRAL"
    return {"score":total,"direction":direction,"headline_score":h_score,"headline_score_eff":h_eff,"headline_note":h_note,"numbers_score":num,"numbers_reasons":num_reasons,"bear_count":base["bear_count"],"bull_count":base["bull_count"],"headlines":base["headlines"],"src":"Yahoo+CoinDesk+CoinTelegraph"}
def news_booster(news,direction,base_cert,all_agree=False):
    if direction=="NONE" or base_cert<65: return 0,"No news boost - base cert <65% or no direction"
    if not all_agree: return 0,"News no boost - certainties NOT all agree, news ignored (no block)"
    if news.get("direction")==direction and news.get("score",0)!=0: return 10,f"NEWS BOOSTER +10% | News {news['direction']} {news['score']} backs {direction} | {news.get('headline_note','')}"
    return 0,"News no boost - disagree or neutral, ignored (no block)"
