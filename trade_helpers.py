def be_target_for(mode): return 800.0 if mode=="NORMAL" else 600.0
def calc_sl_tp(side,entry,mode):
    sl_d,tp_d=(1000.0,1200.0) if mode=="HUNT" else (1200.0,1200.0)
    return (entry-sl_d,entry+tp_d) if side=="LONG" else (entry+sl_d,entry-tp_d)
def calc_atr(k1):
    if not k1 or len(k1)<15: return 0.0
    trs=[max(k1[i]["high"]-k1[i]["low"],abs(k1[i]["high"]-k1[i-1]["close"]),abs(k1[i]["low"]-k1[i-1]["close"])) for i in range(1,len(k1))]
    return sum(trs[-14:])/14 if trs else 0.0
