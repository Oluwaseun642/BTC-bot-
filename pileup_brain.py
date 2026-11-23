import time
try:
    from pileup_patch import pileup_gate_for_main
except Exception:
    def pileup_gate_for_main(k1,count,score,cvd_flip,cert,cert_drop,move_against):
        if count<3: return False,f"Pile count {count}/3 <3",None
        if score<4: return False,f"Hunt {score} <4",None
        if not cvd_flip: return False,"CVD no flip",None
        return True,"Servant gate OK - pile 3/3 + hunt + CVD flip",None
try:
    from hunter_takeover import is_hunter_takeover
except Exception:
    def is_hunter_takeover(score,liq_total,cvd_buy,cert_dir,move_against):
        if score>=6 and liq_total>=500000:
            return True,f"Takeover fallback - hunt {score}/9 liq ${liq_total:.0f}"
        return False,"No takeover"

class PileupFlipBrain:
    def __init__(self):
        self.flip_locked=False; self.flip_block_until=0.0; self.void_price=0.0
        # PATCHED: pile reset tracking - so score no go carry over
        self.last_pile_price=0.0
        self.last_pile_dir=None
        self.pile_count=0
        self.pile_reset=True

    def reset_pile(self, reason="allowed=False"):
        # PATCHED: Called by main.py when pileup allowed=False
        # Clear old pile, no carry over to next trade
        self.last_pile_price=0.0
        self.last_pile_dir=None
        self.pile_count=0
        self.pile_reset=True
        self.void_price=0.0
        print(f"[PILE] Reset - {reason} - counts cleared 0/3, no carry over",flush=True)

    def track_pile(self, price, pile_dir, count):
        # PATCHED: Track pile so we know when e reset
        # If direction flip, reset. If price move $80+ away, reset.
        if pile_dir is None:
            if not self.pile_reset:
                self.reset_pile("pile_dir=None")
            return 0
        if self.last_pile_dir is not None and pile_dir != self.last_pile_dir:
            self.reset_pile(f"dir flip {self.last_pile_dir} -> {pile_dir}")
            # After reset, start new pile with current count
            self.last_pile_dir=pile_dir; self.last_pile_price=price; self.pile_count=count; self.pile_reset=False
            return count
        if self.last_pile_price and abs(price - self.last_pile_price) >= 80:
            self.reset_pile(f"price moved ${abs(price-self.last_pile_price):.0f} >= $80 from pile ${self.last_pile_price:.0f}")
            self.last_pile_dir=pile_dir; self.last_pile_price=price; self.pile_count=count; self.pile_reset=False
            return count
        # Same pile continues
        self.last_pile_dir=pile_dir
        if not self.last_pile_price: self.last_pile_price=price
        self.pile_count=count; self.pile_reset=False
        return count

    def check_and_reset(self, price, pile_dir, allowed):
        # PATCHED: main.py go call this every loop
        # If allowed=False -> reset to 0/3
        if not allowed:
            if not self.pile_reset:
                self.reset_pile("allowed=False from data_engine")
            return 0
        return self.track_pile(price, pile_dir, self.pile_count)

    def note_flip_used(self,dir,price):
        self.flip_locked=True; self.flip_block_until=time.time()+90
        print(f"[FLIP] Used {dir} @ ${price:.1f} - locked 90s",flush=True)

    def can_flip_now(self):
        if self.flip_locked and time.time()>=self.flip_block_until:
            self.flip_locked=False
        if self.flip_locked: return False,"Flip locked - already flipped, wait 90s"
        if time.time()<self.flip_block_until: return False,"Flip blocked 90s"
        return True,"OK"

    def is_repile_certain(self,price,side,entry,count,expected,target,liq,ob,cvd_agg,score):
        if count<3: return False,f"Repile: Count {count}/3 <3"
        if expected<80: return False,f"Repile: Expected ${expected:.0f} < $80 - too close"
        if expected>3000: return False,f"Repile: Expected ${expected:.0f} > $3000 - too far"
        if score<3: return False,f"Repile: Hunt {score} <3"
        return True,f"Repile Certain - count 3/3, move ${expected:.0f}, hunt {score}"

def _two_candles_confirm(candles,dir):
    if not candles or len(candles)<2: return False,"No 2 candles"
    a,b=candles[-2],candles[-1]
    try:
        a_close=float(a.get("close",0) if isinstance(a,dict) else a); a_open=float(a.get("open",0) if isinstance(a,dict) else a)
        b_close=float(b.get("close",0) if isinstance(b,dict) else b); b_open=float(b.get("open",0) if isinstance(b,dict) else b)
    except Exception:
        return False,"Candles format wahala"
    if dir=="LONG": return (b_close>b_open and a_close>a_open),"2 candles LONG" if (b_close>b_open and a_close>a_open) else "2 candles no confirm LONG"
    return (b_close<b_open and a_close<a_open),"2 candles SHORT" if (b_close<b_open and a_close<a_open) else "2 candles no confirm SHORT"

def should_flip_to_pileup(brain,price,side,entry,count,pile_dir,score,cvd_agg,cvd_buy,cert,cert_dir,liq_total,k1=None,candles=None):
    if k1 is None: k1=[]
    if candles is None: candles=[]
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
