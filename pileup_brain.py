import time
from pileup_patch import pileup_gate_for_main
from hunter_takeover import is_hunter_takeover
class PileupFlipBrain:
    def __init__(self): self.flip_locked=False; self.flip_block_until=0.0; self.void_price=0.0
    def note_flip_used(self,dir,price): self.flip_locked=True; self.flip_block_until=time.time()+90; print(f"[FLIP] Used {dir} @ ${price:.1f}",flush=True)
    def can_flip_now(self):
        if self.flip_locked: return False,"Flip locked - already flipped"
        if time.time()<self.flip_block_until: return False,"Flip blocked 90s"
        return True,"OK"
    def is_repile_certain(self,price,side,entry,count,expected,target,liq,ob,cvd_agg,score):
        if count<3: return False,f"Repile: Count {count}/3 <3"
        if expected<80: return False,f"Repile: Expected ${expected:.0f} < $80 - too close"  # WAS 150, NOW 80
        if expected>3000: return False,f"Repile: Expected ${expected:.0f} > $3000 - too far"
        if score<3: return False,f"Repile: Hunt {score} <3"
        return True,f"Repile Certain - count 3/3, move ${expected:.0f}, hunt {score}"
def _two_candles_confirm(candles,dir):
    if not candles or len(candles)<2: return False,"No 2 candles"
    a,b=candles[-2],candles[-1]
    if dir=="LONG": return (b["close"]>b["open"] and a["close"]>a["open"]),"2 candles LONG" if (b["close"]>b["open"] and a["close"]>a["open"]) else "2 candles no confirm LONG"
    return (b["close"]<b["open"] and a["close"]<a["open"]),"2 candles SHORT" if (b["close"]<b["open"] and a["close"]<a["open"]) else "2 candles no confirm SHORT"
def should_flip_to_pileup(brain,price,side,entry,count,pile_dir,score,cvd_agg,cvd_buy,cert,cert_dir,liq_total,k1,candles):
    can,why=brain.can_flip_now()
    if not can: return False,why,None
    if count<3: return False,f"Flip: Count {count}/3 <3",None
    if score<4: return False,f"Flip: Hunt {score} <4",None
    cvd_flip=(side=="SHORT" and cvd_agg=="BUY") or (side=="LONG" and cvd_agg=="SELL")
    move_against=abs(price-entry) if entry else 0; cert_drop=cert<75
    takeover,tk=is_hunter_takeover(score,liq_total,cvd_buy,cert_dir,move_against)
    if takeover:
        ok,w2=_two_candles_confirm(candles,pile_dir)
        if not ok: return False,f"Flip takeover but {w2}",None
        return True,f"FLIP TAKEOVER - {tk}",pile_dir
    can_p,pr,_=pileup_gate_for_main(k1,count,score,cvd_flip,cert,cert_drop,move_against)
    if not can_p: return False,f"Flip blocked - {pr}",None
    ok,w2=_two_candles_confirm(candles,pile_dir)
    if not ok: return False,f"Flip servant but {w2}",None
    return True,f"FLIP SERVANT - {pr}",pile_dir
