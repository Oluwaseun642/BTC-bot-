# DATA ENGINE V16.2 - PART 3/3 - HUNT + get_signal PATCHED
from data_engine_part1 import get_world,get_session,get_hunt_window,get_funding,get_fear,get_open_interest,get_asia_range,calc_rsi,yahoo_price_1h,get_price_live,get_klines
from data_engine_part2 import get_liq_clusters,get_ob_clusters,get_cvd_live,get_spot_premium,get_spread_score,get_gold_boss,get_funding_cascade,get_news_live,news_booster,update_pileup,is_pileup_allowed
import time
def get_market_against_btc(world,direction,price_chg_5):
    if direction not in ("LONG","SHORT"): return {"against_count":0,"total":5,"is_against":False,"reasons":[]}
    dxy=world.get("DXY",0); nq=world.get("NQ",0); spx=world.get("SPX",0); gold=world.get("GOLD",0); against=0; reasons=[]
    if direction=="SHORT":
        if dxy<0: against+=1; reasons.append("DXY down vs SHORT")
        if nq>0: against+=1; reasons.append("NQ up vs SHORT")
        if spx>0: against+=1; reasons.append("SPX up vs SHORT")
        if gold>0: against+=1; reasons.append("GOLD up vs SHORT")
        if price_chg_5>=0: against+=1; reasons.append("Price holding vs SHORT")
    else:
        if dxy>0: against+=1; reasons.append("DXY up vs LONG")
        if nq<0: against+=1; reasons.append("NQ down vs LONG")
        if spx<0: against+=1; reasons.append("SPX down vs LONG")
        if gold<0: against+=1; reasons.append("GOLD down vs LONG")
        if price_chg_5<=0: against+=1; reasons.append("Price holding vs LONG")
    return {"against_count":against,"total":5,"is_against":against>=2,"reasons":reasons}
def get_hunt_certainty(price,liq,obc,cvd,fc,a_low,a_high):
    score=0; reasons=[]; hunt_dir="NONE"; target=0.0
    if liq.get("dominant")=="HUNT_LONGS_FIRST": hunt_dir="DOWN_FIRST"; target=a_low if a_low else price-800; score+=2; reasons.append("Liq Longs > Shorts +2")
    elif liq.get("dominant")=="HUNT_SHORTS_FIRST": hunt_dir="UP_FIRST"; target=a_high if a_high else price+800; score+=2; reasons.append("Liq Shorts > Longs +2")
    if liq.get("total",0)>5000000: score+=2; reasons.append(f"Liq ${liq['total']:,.0f} > $5M +2")
    elif liq.get("total",0)>2000000: score+=1; reasons.append(f"Liq ${liq['total']:,.0f} > $2M +1")
    if hunt_dir=="DOWN_FIRST" and obc.get("cluster_bias")=="ASK_WALL_STRONG": score+=1; reasons.append("Ask wall + hunt down +1")
    elif hunt_dir=="UP_FIRST" and obc.get("cluster_bias")=="BID_WALL_STRONG": score+=1; reasons.append("Bid wall + hunt up +1")
    if hunt_dir=="DOWN_FIRST" and cvd.get("aggressive")=="SELL": score+=1; reasons.append("CVD SELL + hunt down +1")
    elif hunt_dir=="UP_FIRST" and cvd.get("aggressive")=="BUY": score+=1; reasons.append("CVD BUY + hunt up +1")
    if target:
        dist=abs(price-target)
        if dist<=300: score+=2; reasons.append(f"Price ${dist:.0f} from target +2 - CLOSE TO HUNT")
        elif dist<=800: score+=1; reasons.append(f"Price ${dist:.0f} from target +1")
    if hunt_dir=="DOWN_FIRST" and fc.get("risk")=="CASCADE_DOWN": score+=1; reasons.append("Funding cascade DOWN +1")
    elif hunt_dir=="UP_FIRST" and fc.get("risk")=="CASCADE_UP": score+=1; reasons.append("Funding cascade UP +1")
    label="CERTAIN" if score>=6 else "TIER2" if score>=4 else "MAYBE" if score>=3 else "NO_HUNT"; dist=abs(price-target) if target else 9999; size_label="GOOD" if dist<=1200 else "SL_DANGER"
    return {"score":score,"label":label,"hunt_dir":hunt_dir,"target":target,"distance":round(dist,0),"size_label":size_label,"reasons":reasons}
def get_hunt_state(hunt_cert,price,a_low,a_high,k1,world,cvd=None,obc=None):
    session=get_session(); hunt_active,_=get_hunt_window(); countries_align=(world.get("DXY",0)!=0 and world.get("NQ",0)!=0 and world.get("SPX",0)!=0); hunt_type="SESSIONAL" if (hunt_active and countries_align) else "NORMAL_DAY"; score=hunt_cert.get("score",0)
    state="CERTAINLY_VITAL" if score>=6 else "TIER2_COMING" if score>=4 else "MAYBE_LOW" if score>=3 else "NOT_VITAL"; hunt_done=False; done=[]
    if k1 and len(k1)>=2 and a_low and a_high:
        last=k1[-1]
        if hunt_cert.get("hunt_dir")=="UP_FIRST" and last["high"]>a_high and last["close"]<a_high: done.append("Wick above Asia High, close back inside")
        if hunt_cert.get("hunt_dir")=="DOWN_FIRST" and last["low"]<a_low and last["close"]>a_low: done.append("Wick below Asia Low, close back inside")
    if score<3: done.append(f"Hunter score drop {score}/9")
    if len(done)>=1 and score<3: hunt_done=True
    exh=[]; exhausted=False
    if 3<=score<=4: exh.append(f"Score fading {score}/9")
    if cvd is not None:
        if hunt_cert.get("hunt_dir")=="UP_FIRST" and cvd.get("aggressive")=="SELL": exh.append("CVD flip to SELL vs UP hunt")
        if hunt_cert.get("hunt_dir")=="DOWN_FIRST" and cvd.get("aggressive")=="BUY": exh.append("CVD flip to BUY vs DOWN hunt")
    if k1 and len(k1)>=1 and a_low and a_high:
        last=k1[-1]
        if hunt_cert.get("hunt_dir")=="UP_FIRST" and last["high"]>a_high and last["close"]<a_high: exh.append("Wick above Asia High, close back")
        if hunt_cert.get("hunt_dir")=="DOWN_FIRST" and last["low"]<a_low and last["close"]>a_low: exh.append("Wick below Asia Low, close back")
    if len(exh)>=2: exhausted=True
    return {"state":state,"hunt_type":hunt_type,"session":session,"hunt_active":hunt_active,"hunt_done":hunt_done,"done_reasons":done,"exhausted":exhausted,"exh_reasons":exh}
def get_fake_wide(k1,a_low,a_high):
    if not k1 or len(k1)<6 or not a_low or not a_high: return "NONE","",0.0
    last=k1[-1]; prev=k1[-6]
    if not prev["close"]: return "NONE","",0.0
    chg5=(last["close"]-prev["close"])/prev["close"]*100; move=abs(last["close"]-prev["close"])
    if chg5<=-1.5 and last["low"]<a_low and last["close"]>a_low: return "FAKE_DUMP",f"Wide Fake Dump {chg5:.2f}% ${move:.0f} wick below Asia Low, close inside -> Bounce LONG",move
    if chg5>=1.5 and last["high"]>a_high and last["close"]<a_high: return "FAKE_PUMP",f"Wide Fake Pump +{chg5:.2f}% ${move:.0f} wick above Asia High, close inside -> Bounce SHORT",move
    return "NONE","",move
def get_flip_gate(hunt_cert,flip_dir,direction,cert,agree,market_against,is_sessional):
    wide=(cert>=90 and agree>=7); grounded=(cert>=75 and cert<90 and agree>=6); run_needed=3000 if is_sessional else 800
    if flip_dir=="NONE" or flip_dir==direction: return False,"",wide,grounded,run_needed
    if wide: return False,f"WIDE CERT {cert}% - Go Normal {direction}, ignore TIER2",wide,grounded,run_needed
    if hunt_cert.get("label") in ("TIER2","CERTAIN") and grounded and market_against.get("is_against"):
        dist=hunt_cert.get("distance",0)
        if dist>=run_needed or hunt_cert.get("label")=="CERTAIN": return True,f"TIER2+2 CONFIRM: Market against {market_against.get('reasons')} + Grounded {cert}% + Run {dist:.0f} >= {run_needed}",wide,grounded,run_needed
        return False,f"TIER2 but run {dist:.0f} < {run_needed} - NO FLIP",wide,grounded,run_needed
    return False,f"TIER2 but confirm fail: grounded={grounded} against={market_against.get('is_against')} - PAUSE",wide,grounded,run_needed
def get_hunter_live(price,k1,funding,spot,oi,oi_chg,price_chg_5,a_low=0,a_high=0,world=None):
    try:
        liq=get_liq_clusters(price,k1); obc=get_ob_clusters(price); cvd=get_cvd_live(); fc=get_funding_cascade(funding,oi_chg,price_chg_5); hunt_cert=get_hunt_certainty(price,liq,obc,cvd,fc,a_low,a_high); hunt_active,hunt_session=get_hunt_window(); score=0.0; reasons=[]
        if liq["dominant"]=="HUNT_LONGS_FIRST": score-=1.5; reasons.append(f"Liq Longs ${liq['long_liq']:,.0f} > Shorts ${liq['short_liq']:,.0f}")
        elif liq["dominant"]=="HUNT_SHORTS_FIRST": score+=1.5; reasons.append(f"Liq Shorts ${liq['short_liq']:,.0f} > Longs ${liq['long_liq']:,.0f}")
        if fc["risk"]=="CASCADE_DOWN": score-=2; reasons.append(f"Funding cascade DOWN: {fc['reason']}")
        elif fc["risk"]=="CASCADE_UP": score+=2; reasons.append(f"Funding cascade UP: {fc['reason']}")
        if obc["cluster_bias"]=="BID_WALL_STRONG": score+=1; reasons.append(f"OB Bid wall ${obc['bid_wall_usd']:,.0f}")
        elif obc["cluster_bias"]=="ASK_WALL_STRONG": score-=1; reasons.append(f"OB Ask wall ${obc['ask_wall_usd']:,.0f}")
        if cvd["aggressive"]=="BUY" and cvd["buy_pct"]>60: score+=1; reasons.append(f"CVD BUY {cvd['buy_pct']}%")
        elif cvd["aggressive"]=="SELL" and cvd["buy_pct"]<40: score-=1; reasons.append(f"CVD SELL {cvd['buy_pct']}%")
        if spot["bias"]=="SPOT_BUYING": score+=1; reasons.append(f"Spot +${spot['premium_usd']:.0f}")
        elif spot["bias"]=="SPOT_SELLING": score-=1; reasons.append(f"Spot ${spot['premium_usd']:.0f}")
        if oi_chg>0.1 and price_chg_5>0: score+=0.5; reasons.append("OI up + price up")
        elif oi_chg>0.1 and price_chg_5<0: score-=0.5; reasons.append("OI up + price down")
        elif oi_chg<-0.1 and price_chg_5>0: score+=0.5; reasons.append("OI down + price up")
        elif oi_chg<-0.1 and price_chg_5<0: score-=0.5; reasons.append("OI down + price down")
        hunter_bias="LONG" if score>=1.5 else "SHORT" if score<=-1.5 else "NEUTRAL"; hunt_ride=hunt_cert["label"] in ("CERTAIN","TIER2") and hunt_cert["size_label"]=="GOOD" and hunter_bias!="NEUTRAL"; hunt_state=get_hunt_state(hunt_cert,price,a_low,a_high,k1,world or {},cvd,obc); fake_type,fake_reason,fake_move=get_fake_wide(k1,a_low,a_high); pileup=update_pileup(hunt_cert,liq,cvd,price_chg_5)
        # PATCHED: no blind wide_cert veto here. MAIN decides Servant/Takeover. DE only reports counts.
        pileup_allowed,pileup_reason=is_pileup_allowed(hunt_cert.get("score",0),k1,False,0,False,False,0,float(liq.get("total",0) or 0),float(cvd.get("buy_pct",50)),"NONE")
        pileup["allowed"]=pileup_allowed; pileup["allowed_reason"]=pileup_reason; pileup["pileup_up_effective"]=bool(pileup.get("pileup_up") and pileup_allowed); pileup["pileup_down_effective"]=bool(pileup.get("pileup_down") and pileup_allowed)
        return {"hunter_score":round(score,2),"hunter_bias":hunter_bias,"hunt_ride":hunt_ride,"hunt_state":hunt_state,"reasons":reasons,"liq":liq,"ob_clusters":obc,"cvd_live":cvd,"spot":spot,"funding_cascade":fc,"oi":oi,"hunt_certainty":hunt_cert,"hunt_active":hunt_active,"hunt_session":hunt_session,"fake_type":fake_type,"fake_reason":fake_reason,"fake_move":fake_move,"pileup":pileup}
    except Exception as e: return {"hunter_score":0.0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_state":{"state":"NOT_VITAL","hunt_type":"NORMAL_DAY","hunt_done":False,"done_reasons":[],"exhausted":False,"exh_reasons":[]},"reasons":[f"Hunter error {e}"],"liq":{},"ob_clusters":{},"cvd_live":{},"spot":spot,"funding_cascade":{},"oi":oi,"hunt_certainty":{"score":0,"label":"NO_HUNT","hunt_dir":"NONE","target":0,"distance":9999,"size_label":"GOOD","reasons":[]},"hunt_active":False,"hunt_session":get_session(),"fake_type":"NONE","fake_reason":"","fake_move":0,"pileup":{"allowed":False,"allowed_reason":f"error {e}","pileup_up":False,"pileup_up_count":0,"pileup_down":False,"pileup_down_count":0,"pileup_up_effective":False,"pileup_down_effective":False}}
def get_sweep(price,k15,k1,liq_clusters=None):
    a_low,a_high=get_asia_range(k15)
    if liq_clusters: ll=liq_clusters.get("long_liq",0); sl=liq_clusters.get("short_liq",0)
    else:
        c=get_liq_clusters(price,k1); ll=c["long_liq"]; sl=c["short_liq"]
    sweep_done=False; sweep_dir="NONE"; hunt="NEUTRAL"
    if a_low and a_high and k1:
        last=k1[-1]
        if last["low"]<a_low and last["close"]>a_low: hunt="LONG"; sweep_done=True; sweep_dir="LONG"
        elif last["high"]>a_high and last["close"]<a_high: hunt="SHORT"; sweep_done=True; sweep_dir="SHORT"
    return hunt,a_low,a_high,ll,sl,sweep_done,sweep_dir
def get_macro_brain(price,k1,k15,funding=0.0):
    try:
        dxy_p,dxy_d,dxy_1h=yahoo_price_1h("DX-Y.NYB"); _,_,jpy_1h=yahoo_price_1h("USDJPY=X"); _,tnx_d,_=yahoo_price_1h("^TNX"); fng,_=get_fear(); rsi=calc_rsi(k15[-60:] if k15 else [],14); score=0.0; det=[]
        if dxy_1h is not None:
            if dxy_1h>0.2: score-=2; det.append(f"DXY 1h +{dxy_1h:.2f}% SHORT+2")
            elif dxy_1h<-0.5: score+=2; det.append(f"DXY 1h {dxy_1h:.2f}% LONG+2")
            if dxy_p and dxy_p>102.5: score-=1; det.append("DXY>102.5 SHORT+1")
        if jpy_1h is not None:
            if jpy_1h<-1.5: score+=2; det.append("USDJPY -1.5% LONG+2")
            elif jpy_1h<-0.8: score+=1; det.append("USDJPY dropping LONG+1")
        if tnx_d is not None and tnx_d>0.5: score-=1; det.append("US10Y up SHORT+1")
        if funding<-0.01: score+=1; det.append("Funding shorts crowded LONG+1")
        elif funding>0.02: score-=1; det.append("Funding high SHORT+1")
        if rsi<25: score+=1; det.append(f"RSI {rsi} oversold LONG+1")
        elif rsi>70: score-=1; det.append("RSI overbought SHORT+1")
        if fng<=10: score+=0.5; det.append(f"Fear {fng} bounce risk")
        bias="SHORT" if score<=-1.5 else "LONG" if score>=1.5 else "NEUTRAL"; alert="PAUSE_SHORT" if (dxy_1h is not None and dxy_1h<=-0.5) or (jpy_1h is not None and jpy_1h<=-0.8) else None
        return {"score":score,"bias":bias,"alert":alert,"dxy_1h":dxy_1h,"jpy_1h":jpy_1h,"funding":funding,"fng":fng,"rsi":rsi,"details":det}
    except Exception as e: return {"score":0.0,"bias":"NEUTRAL","alert":None,"error":str(e)}
_last_signal={"time":0,"data":None}
def _macro_vote(bias): return (1,0) if bias=="LONG" else (0,1) if bias=="SHORT" else (0,0)
def _ob_vote(obc):
    bp=obc.get("buy_pressure",50)
    if obc.get("cluster_bias")=="BID_WALL_STRONG": return 1,0,"OB Bid Wall LONG"
    if obc.get("cluster_bias")=="ASK_WALL_STRONG": return 0,1,"OB Ask Wall SHORT"
    if bp>55: return 1,0,"Orderbook bids LONG"
    if bp<45: return 0,1,"Orderbook asks SHORT"
    return 0,0,""
def get_signal(price,atr=None,candles=None):
    global _last_signal
    if _last_signal["data"] is not None and (time.time()-_last_signal["time"])<15:
        cached=dict(_last_signal["data"]); cached["price"]=price; return cached
    try:
        if not price or price==0:
            price,_=get_price_live()
            if price==0: return {"cert":0,"direction":"NONE","agree":0,"wide_cert":False,"grounded_cert":False,"hunt_soon":False,"hunt_cert":0,"cvd_buy_pct":50,"price":0,"hunter_score":0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_done":False,"hunt_exhausted":False,"sweep_done":False,"sweep_dir":"NONE","hunt_certainty":{"score":0,"label":"NO_HUNT"},"spread":{"score":0,"bias":"NEUTRAL"},"gold_boss":{},"news":{},"flip_allowed":False,"flip_dir":"NONE","fake_type":"NONE","pileup":{"allowed":False,"pileup_up":False,"pileup_up_count":0,"pileup_down":False,"pileup_down_count":0,"pileup_up_effective":False,"pileup_down_effective":False}}
        k1=candles if candles and len(candles)>=5 else get_klines("1",20); k1_norm=[{"open":float(k.get("open",0)),"high":float(k.get("high",0)),"low":float(k.get("low",0)),"close":float(k.get("close",0)),"volume":float(k.get("volume",1)),"time":int(k.get("time",0))} for k in k1]; k15=get_klines("15",200); world=get_world(); funding,_=get_funding(); spot=get_spot_premium(); oi=get_open_interest()
        price_chg_5=(k1_norm[-1]["close"]-k1_norm[-6]["close"])/k1_norm[-6]["close"]*100 if len(k1_norm)>=6 and k1_norm[-6]["close"] else 0; price_chg_1h=(k1_norm[-1]["close"]-k1_norm[0]["close"])/k1_norm[0]["close"]*100 if k1_norm and k1_norm[0]["close"] else 0
        macro_brain=get_macro_brain(price,k1_norm,k15,funding); a_low_tmp,a_high_tmp=get_asia_range(k15); hunter=get_hunter_live(price,k1_norm,funding,spot,oi,oi.get("chg_5m",0),price_chg_5,a_low_tmp,a_high_tmp,world); hunt,a_low,a_high,ll,sl,sweep_done,sweep_dir=get_sweep(price,k15,k1_norm,hunter.get("liq")); obc=hunter.get("ob_clusters",{}); cvd_live=hunter.get("cvd_live",{}); fc=hunter.get("funding_cascade",{}); hunt_cert=hunter.get("hunt_certainty",{"score":0,"label":"NO_HUNT","hunt_dir":"NONE","target":0,"distance":9999,"size_label":"GOOD","reasons":[]}); hunt_active=hunter.get("hunt_active",False); spread=get_spread_score(price,spot,funding); news=get_news_live(world,price_chg_1h,cvd_live.get("aggressive","NEUTRAL"),price_chg_1h)
        long_votes=0; short_votes=0; total_voters=8; reasons=[]
        for key in ["DXY","NQ","SPX"]:
            v=world.get(key,0)
            if key=="DXY":
                if v<-0.05: long_votes+=1; reasons.append("DXY down LONG")
                elif v>0.05: short_votes+=1; reasons.append("DXY up SHORT")
            else:
                if v>0.05: long_votes+=1; reasons.append(f"{key} up LONG")
                elif v<-0.05: short_votes+=1; reasons.append(f"{key} down SHORT")
        gold=world.get("GOLD",0)
        if gold>0.05: long_votes+=1; reasons.append("GOLD up LONG")
        elif gold<-0.05: short_votes+=1; reasons.append("GOLD down SHORT")
        oi_chg=oi.get("chg_5m",0); macro_l,macro_s=_macro_vote(macro_brain.get("bias"))
        if oi_chg>0.1 and price_chg_5<0: long_votes+=1; reasons.append("OI up + price down LONG")
        elif oi_chg>0.1 and price_chg_5>0: long_votes+=1; reasons.append("OI up + price up LONG")
        elif oi_chg<-0.1 and price_chg_5<0: short_votes+=1; reasons.append("OI down + price down SHORT")
        else: long_votes+=macro_l; short_votes+=macro_s
        if hunt=="LONG": long_votes+=1; reasons.append("Sweep LONG")
        elif hunt=="SHORT": short_votes+=1; reasons.append("Sweep SHORT")
        cvd_agg=cvd_live.get("aggressive","NEUTRAL"); cvd_buy_pct=cvd_live.get("buy_pct",50.0)
        if cvd_agg=="BUY": long_votes+=1; reasons.append(f"CVD BUY {cvd_buy_pct}% LONG")
        elif cvd_agg=="SELL": short_votes+=1; reasons.append(f"CVD SELL {cvd_buy_pct}% SHORT")
        ob_l,ob_s,ob_r=_ob_vote(obc); long_votes+=ob_l; short_votes+=ob_s
        if ob_r and ob_r not in reasons: reasons.append(ob_r)
        if long_votes>short_votes: direction="LONG"; agree=long_votes
        elif short_votes>long_votes: direction="SHORT"; agree=short_votes
        else: direction="NONE"; agree=long_votes
        cert=round((agree/total_voters)*100,1) if total_voters else 0
        if macro_brain.get("bias")==direction and direction!="NONE": cert=min(100,cert+5)
        hunter_bias=hunter.get("hunter_bias","NEUTRAL"); hunter_score=hunter.get("hunter_score",0); wide_cert=(cert>=90 and agree>=7); grounded_cert=(cert>=75 and cert<90 and agree>=6)
        if hunter_bias==direction and direction!="NONE": cert=min(100,cert+5); reasons.append(f"Hunter agrees {hunter_bias} +5")
        elif hunter_bias!="NEUTRAL" and hunter_bias!=direction and direction!="NONE" and not wide_cert: cert=max(0,cert-10); reasons.append(f"Hunter disagrees {hunter_bias} vs {direction} -10")
        elif wide_cert: reasons.append(f"WIDE CERT {cert}% - Hunter {hunter_bias} ignored, hunters cannot dare")
        market_against=get_market_against_btc(world,direction,price_chg_5) if direction!="NONE" else {"against_count":0,"total":5,"is_against":False,"reasons":[]}; hunt_state=hunter.get("hunt_state",{}); is_sessional=(hunt_state.get("hunt_type")=="SESSIONAL"); hunt_dir_map={"UP_FIRST":"LONG","DOWN_FIRST":"SHORT"}; hunt_trade_dir=hunt_dir_map.get(hunt_cert.get("hunt_dir","NONE"),"NONE"); flip_allowed,flip_reason,wide_cert2,grounded_cert2,run_needed=get_flip_gate(hunt_cert,hunt_trade_dir,direction,cert,agree,market_against,is_sessional); wide_cert=wide_cert2; grounded_cert=grounded_cert2; spread_boost=0
        if direction!="NONE" and spread.get("bias") in ("LONG","SHORT"):
            spread_dir=spread["bias"]
            if spread_dir==direction and (hunter_bias==direction or macro_brain.get("bias")==direction): spread_boost=10; cert=min(100,cert+10); reasons.append(f"SPREAD BOOSTER +10% | Spread {spread_dir} {spread['score']} | Spot +${spread['spot_premium_usd']:.0f} | Coinbase-Bybit +${spread['coinbase_bybit_spread']:.0f}")
            elif spread_dir!=direction and spread.get("score",0)!=0: spread_boost=-5; cert=max(0,cert-5); reasons.append(f"SPREAD WARNING -5% | Spread {spread_dir} vs {direction} | Spot ${spread['spot_premium_usd']:.0f}")
        all_agree=(agree>=7); news_boost,news_boost_reason=news_booster(news,direction,cert,all_agree)
        if news_boost>0: cert=min(100,cert+news_boost); reasons.append(news_boost_reason)
        else: reasons.append(f"News {news.get('direction')} {news.get('score')} - {news_boost_reason} (ignored, no block)")
        hunt_boost=0
        if hunt_trade_dir!="NONE" and news.get("direction")==hunt_trade_dir and news.get("score",0)!=0 and all_agree: hunt_boost=1; reasons.append(f"NEWS BOOST HUNT +1 | News {news['direction']} backs hunt {hunt_trade_dir}")
        if sweep_done: direction=sweep_dir; agree=max(agree,7); cert=85.0; reasons.append(f"SWEEP DONE {sweep_dir} @ ${price:,.0f} - ENTER IMMEDIATELY"); wide_cert=False; grounded_cert=True
        hunt_soon=False; hunt_cert_score=hunt_cert.get("score",0)
        if hunt_cert["label"] in ("CERTAIN","TIER2") and hunt_active and not sweep_done: hunt_soon=True
        hunt_ride_active=False; hunt_ride_dir="NONE"
        if hunter.get("hunt_ride") and not sweep_done:
            if hunt_cert.get("hunt_dir")=="UP_FIRST": hunt_ride_dir="LONG"
            elif hunt_cert.get("hunt_dir")=="DOWN_FIRST": hunt_ride_dir="SHORT"
            if hunt_ride_dir!="NONE": hunt_ride_active=True; reasons.append(f"HUNT RIDE {hunt_ride_dir} | Hunter {hunt_cert['score']}/9 {hunt_state.get('hunt_type')} {hunt_cert['hunt_dir']} target ${hunt_cert['target']:,.0f} BE $600 close SL $1000 TP $1200")
        hunt_done=bool(hunt_state.get("hunt_done",False)); hunt_exhausted=bool(hunt_state.get("exhausted",False))
        if hunt_done: reasons.append(f"HUNT DONE: {'; '.join(hunt_state.get('done_reasons',[]))} -> Enter Normal {direction} immediately")
        if hunt_exhausted: reasons.append(f"HUNT EXHAUSTED: {'; '.join(hunt_state.get('exh_reasons',[]))} -> Flip back with little profit to Normal {direction}")
        btc_chg_15m_calc=(k1_norm[-1]["close"]-k1_norm[-16]["close"])/k1_norm[-16]["close"]*100 if len(k1_norm)>=16 and k1_norm[-16]["close"] else price_chg_5; gold_boss=get_gold_boss(gold,btc_chg_15m_calc,funding,oi_chg); gold_boss_boost=0
        if gold_boss["boss_dir"]==direction and direction!="NONE": gold_boss_boost+=gold_boss["boss_boost"]; cert=min(100,cert+gold_boss["boss_boost"]); reasons.extend(gold_boss["boss_reasons"])
        if gold_boss["dom_dir"]==direction and direction!="NONE": gold_boss_boost+=gold_boss["dom_boost"]; cert=min(100,cert+gold_boss["dom_boost"]); reasons.extend(gold_boss["dom_reasons"])
        if gold_boss["boss_dir"]!="NONE" and gold_boss["boss_dir"]!=direction and direction!="NONE" and not wide_cert: cert=max(0,cert-5); reasons.append(f"GOLD BOSS WARNING -5% | GOLD BOSS {gold_boss['boss_dir']} vs {direction}")
        if gold_boss["is_break"]:
            reasons.append(f"GOLD {gold_boss['break_tier']} WARNING - No Block, Cert Decides | GOLD 15m {gold_boss['gold_15m']:.2f}% vs BTC 15m {gold_boss['btc_15m']:.2f}% div {gold_boss['divergence']:.2f}%")
            if gold_boss["flip_to"]!="NONE": reasons.append(f"GOLD BREAK FLIP {gold_boss['break_candles']} candles -> Follow BTC {gold_boss['flip_to']} (Info only)")
        else:
            if gold_boss["resolve_since"]>0 and not gold_boss["confirm_ok"]: reasons.append(f"GOLD BREAK RESOLVED, 2min confirm {gold_boss['confirm_wait']}s left - Warning only, No Block")
            elif gold_boss["wick_active"] and direction!="NONE": reasons.append(f"GOLD WICK WARNING {gold_boss['wick_pct']:.2f}% - No Block, trade if cert strong")
        from data_engine_part1 import get_pre_entry
        pre_active,pre_name,pre_note=get_pre_entry(); fake_type=hunter.get("fake_type","NONE"); fake_reason=hunter.get("fake_reason",""); fake_move=hunter.get("fake_move",0); pileup=hunter.get("pileup",{})
        # PATCHED: No Lock2 veto. Servant: report counts, MAIN decides. Wide Cert just says Go Normal, not block pile-up forever.
        if wide_cert and pileup: reasons.append(f"PILE-UP REPORT - WIDE CERT {cert}% Go Normal, but Servant check still on | Up {pileup.get('pileup_up_count',0)}/3 Down {pileup.get('pileup_down_count',0)}/3")
        elif pileup and (pileup.get("pileup_up_effective") or pileup.get("pileup_down_effective")): reasons.append(f"PILE-UP ACTIVE - {pileup.get('allowed_reason','')} | Up {pileup.get('pileup_up_count',0)}/3 Down {pileup.get('pileup_down_count',0)}/3 - Main.py Part 2 go decide flip")
        result={"cert":cert,"direction":direction,"agree":agree,"wide_cert":wide_cert,"grounded_cert":grounded_cert,"hunt_soon":hunt_soon,"hunt_cert":hunt_cert_score,"cvd_buy_pct":cvd_buy_pct,"price":price,"reasons":reasons,"news_reason":news.get("headline_note",""),"macro_bias":macro_brain.get("bias"),"session":get_session(),"liq_long":ll,"liq_short":sl,"hunter_score":hunter_score,"hunter_bias":hunter_bias,"hunt_ride":hunt_ride_active,"hunt_ride_dir":hunt_ride_dir,"hunt_ride_boost":hunt_boost,"hunt_state":hunt_state,"hunt_done":hunt_done,"hunt_exhausted":hunt_exhausted,"hunter_reasons":hunter.get("reasons",[]),"liq_clusters":hunter.get("liq",{}),"ob_clusters":obc,"cvd_live":cvd_live,"spot_premium":spot,"spot_premium_usd":spot.get("premium_usd",0),"funding_cascade":fc,"oi":oi,"sweep_done":sweep_done,"sweep_dir":sweep_dir,"hunt_certainty":hunt_cert,"hunt_active":hunt_active,"hunt_session":hunter.get("hunt_session",get_session()),"asia_low":a_low,"asia_high":a_high,"spread":spread,"spread_score":spread.get("score",0),"spread_bias":spread.get("bias","NEUTRAL"),"spread_boost":spread_boost,"gold_boss":gold_boss,"gold_boss_boost":gold_boss_boost,"news":news,"news_boost":news_boost,"price_chg_1h":round(price_chg_1h,3),"flip_allowed":flip_allowed,"flip_reason":flip_reason,"flip_dir":hunt_trade_dir,"market_against":market_against,"run_needed":run_needed,"fake_type":fake_type,"fake_reason":fake_reason,"fake_move":fake_move,"pre_entry":{"active":pre_active,"name":pre_name,"note":pre_note},"pileup":pileup,"k1_norm":k1_norm}
        _last_signal={"time":time.time(),"data":result}; return result
    except Exception as e:
        print(f"get_signal Error: {e}",flush=True); return {"cert":0,"direction":"NONE","agree":0,"wide_cert":False,"grounded_cert":False,"hunt_soon":False,"hunt_cert":0,"cvd_buy_pct":50,"price":price,"hunter_score":0,"hunter_bias":"NEUTRAL","hunt_ride":False,"hunt_ride_dir":"NONE","hunt_done":False,"hunt_exhausted":False,"sweep_done":False,"sweep_dir":"NONE","hunt_certainty":{"score":0,"label":"NO_HUNT"},"spread":{"score":0,"bias":"NEUTRAL"},"gold_boss":{},"news":{"score":0,"direction":"NEUTRAL"},"flip_allowed":False,"flip_dir":"NONE","fake_type":"NONE","pileup":{"allowed":False,"pileup_up":False,"pileup_up_count":0,"pileup_down":False,"pileup_down_count":0,"pileup_up_effective":False,"pileup_down_effective":False}}
def get_price_and_candles():
    p,_=get_price_live(); k1=get_klines("1",20); return p,k1
if __name__=="__main__":
    price,src=get_price_live(); sig=get_signal(price,200,get_klines("1",20)); print(f"Price ${price:.0f} [{src}] Signal: {sig['direction']} Cert {sig['cert']}% Wide {sig.get('wide_cert')} Hunter {sig['hunter_bias']} {sig['hunter_score']} HuntRide {sig.get('hunt_ride')} {sig.get('hunt_ride_dir')} PileUp Up {sig.get('pileup',{}).get('pileup_up_count')}/3 Down {sig.get('pileup',{}).get('pileup_down_count')}/3 Allowed {sig.get('pileup',{}).get('allowed')}")
