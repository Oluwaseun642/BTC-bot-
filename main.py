import os,time,requests,traceback
from flask import Flask
from threading import Thread
from bybit_client import bybit_get,bybit_post,get_balance,get_dynamic_leverage,get_dynamic_qty,set_isolated_margin,place_order,close_position_market,SYMBOL
from trade_helpers import be_target_for,calc_sl_tp,calc_atr
from position_sync import sync_position_from_bybit
from pileup_brain import PileupFlipBrain,should_flip_to_pileup,_two_candles_confirm
from data_engine import get_signal,get_price_and_candles
app=Flask(__name__)
@app.route("/")
def home(): return "OK V16.3 MAIN SPLIT",200
@app.route("/health")
def health(): return "OK",200
def keep_alive(): Thread(target=lambda: app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")),threaded=True),daemon=True).start()
KEEP=os.getenv("RENDER_EXTERNAL_URL","") or os.getenv("KEEP_ALIVE_URL","")
TRADING=os.getenv("TRADING_ENABLED","1").strip()!="0"
def self_ping():
    while True:
        try:
            if KEEP: requests.get(KEEP.rstrip("/")+"/",timeout=10)
        except Exception: pass
        time.sleep(300)
def main():
    keep_alive(); Thread(target=self_ping,daemon=True).start()
    print("[MAIN] V16.3 MAIN SPLIT started",flush=True)
    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"
    be_done=False; last_trade_close=0.0; in_calm=False; calm_start=0.0
    brain=PileupFlipBrain(); flip_history=[]
    while True:
        try:
            st={"in_position":in_position,"side":side,"entry":entry,"qty":qty,"mode":mode}
            st=sync_position_from_bybit(bybit_get,st)
            in_position,side,entry,qty,mode=st["in_position"],st["side"],st["entry"],st["qty"],st["mode"]
            sig=get_signal(); price=float(sig.get("price",0) or 0)
            k1=sig.get("k1_norm",[]) or []
            candles=k1[-10:] if k1 else []
            votes=sig.get("votes",{}); direction=sig.get("direction","NONE"); cert=sig.get("cert",0)
            hunt=sig.get("hunt",{}); hunter=sig.get("hunter",{}); liq=hunter.get("liq",{})
            cvd=hunter.get("cvd",{}); cvd_agg=cvd.get("aggressive","NEUTRAL"); cvd_buy=float(cvd.get("buy_pct",50) or 50)
            pileup=sig.get("pileup",{}); pile_count=pileup.get("pileup_up_count",0) if side=="SHORT" else pileup.get("pileup_down_count",0)
            pile_dir="LONG" if side=="SHORT" else "SHORT"
            hunt_score=int(hunt.get("score",0) or 0)
            # --- IF IN POSITION: BE / PILE-UP FLIP ---
            if in_position and side and entry:
                pnl=(price-entry) if side=="LONG" else (entry-price)
                be_t=be_target_for(mode)
                if not be_done and pnl>=be_t:
                    print(f"[BE] {side} pnl ${pnl:.0f} >= BE ${be_t:.0f} - move SL to entry",flush=True); be_done=True
                # PILE-UP FLIP - servant + takeover, no blind wide-cert block
                if pileup.get("allowed") or pile_count>=3:
                    ok,reason,tdir=should_flip_to_pileup(brain,price,side,entry,pile_count,pile_dir,hunt_score,cvd_agg,cvd_buy,cert,direction,float(liq.get("total",0) or 0),k1,candles)
                    print(f"[FLIP CHECK] {reason}",flush=True)
                    if ok and tdir:
                        print(f"[FLIP] Close {side} @ ${price:.1f}, open {tdir}",flush=True)
                        if TRADING and qty>0: close_position_market(side,qty)
                        brain.note_flip_used(tdir,price); in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; be_done=False; flip_history.append((time.time(),tdir,price))
                        # Re-enter opposite as new trade below in next loop, no immediate double order to avoid flip-flop
                        time.sleep(5); continue
                # Normal close by TP/SL is handled by Bybit SL/TP. If Bybit says flat, sync go mark flat next loop.
            else:
                # --- FLAT: CALM 150s + NEW ENTRY ---
                if not in_calm:
                    in_calm=True; calm_start=time.time()
                if time.time()-calm_start<150:
                    time.sleep(5); continue
                if direction in ("LONG","SHORT") and TRADING and time.time()-last_trade_close>150:
                    bal=get_balance() or 0; q,lev=get_dynamic_qty(price,bal,30.0)
                    if q>0:
                        sl,tp=calc_sl_tp(direction,price,mode)
                        set_isolated_margin("BTCUSDT.P",lev,direction)
                        r=place_order(direction,q,sl,tp,price,lev)
                        print(f"[ENTRY] {direction} {q} @ ${price:.1f} SL ${sl:.1f} TP ${tp:.1f} -> {r.get('retCode')} {r.get('retMsg')}",flush=True)
                        if r.get("retCode")==0:
                            in_position=True; side=direction; entry=price; qty=q; be_done=False; in_calm=False
                # If signal say pile-up entry while flat, wait for next loop - no pile-up entry from flat to avoid flip-flop
            time.sleep(5)
        except Exception as e:
            print(f"[MAIN] Loop error {e}\n{traceback.format_exc()}",flush=True); time.sleep(5)
if __name__=="__main__": main()
