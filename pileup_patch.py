from session_patch import session_status
def is_market_calm_for_pileup(k1):
    if not k1 or len(k1)<6: return False,"No candles"
    l6=k1[-6:]; chg=abs(l6[-1]["close"]-l6[0]["close"])
    rng=max(c["high"] for c in l6)-min(c["low"] for c in l6)
    last=l6[-1]; wick=(last["high"]-last["low"])/last["close"]*100 if last["close"] else 999
    if chg>=1000: return False,f"Not calm - move ${chg:.0f} >= $1000"
    if rng>=600: return False,f"Not calm - range ${rng:.0f} >= $600"
    if wick>=0.7: return False,f"Not calm - wick {wick:.2f}% >=0.7%"
    return True,f"Calm - range ${rng:.0f}, move ${chg:.0f}, wick {wick:.2f}%"
def pileup_can_override(count,score,cvd_flip,cert,cert_drop,move_against):
    if count<3: return False,f"Servant: Count {count}/3 <3"
    if score<4: return False,f"Servant: Hunt {score} <4"
    if cert>=90 and not cvd_flip and not cert_drop: return False,f"Servant: Boss still {cert}% - HOLD, no flip-flop"
    if cert_drop: return True,f"Servant CAN FLIP: Boss drop below 75% ({cert}%)"
    if cvd_flip: return True,"Servant CAN FLIP: CVD flip - real hunters"
    if move_against>=300: return True,f"Servant CAN FLIP: Move ${move_against:.0f} against us"
    return False,"Servant: Boss still strong"
def pileup_gate_for_main(k1,count,score,cvd_flip,cert,cert_drop,move_against):
    coming,opened,msg,_=session_status()
    if coming or opened: return False,f"Pile-up OFF - {msg} - Wait, get ready",msg
    calm,cm=is_market_calm_for_pileup(k1)
    if not calm: return False,f"Pile-up OFF - {cm}",msg
    ok,rs=pileup_can_override(count,score,cvd_flip,cert,cert_drop,move_against)
    if not ok: return False,f"Pile-up OFF - {rs}",msg
    return True,f"Pile-up ON - Calm + No Session + {rs}",msg
