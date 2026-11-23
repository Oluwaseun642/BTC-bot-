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
def home(): return "OK V16.4 MAIN SPLIT - PILE RESET",200
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
def dynamic_qty_lev(price, bal):
    if bal < 5:
        return 0.001, 60
    if bal < 15:
        return 0.001, 40
    if bal < 50:
        q = 10.0 / 600.0
        return max(0.001, round(q,3)), 30
    if bal < 200:
        q = 20.0 / 600.0
        return max(0.001, round(q,3)), 20
    risk = bal * 0.02
    q = risk / 600.0
    return max(0.001, round(q,3)), 15
def main():
    keep_alive(); Thread(target=self_ping,daemon=True).start()
    print("[MAIN] V16.4 MAIN SPLIT started - CERT 75% + V12 DYNAMIC QTY + 60x <$5 + PILE RESET",flush=True)
    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"
    be_done=False; last_trade_close=0.0; in_calm=False; calm_start=0.0
    brain=PileupFlipBrain(); flip_history=[]
    wins=0; losses=0; bes=0
    while True:
        try:
            prev_in_pos=in_position; prev_side=side; prev_entry=entry
            st={"in_position":in_position,"side":side,"entry":entry,"qty":qty,"mode":mode}
            st=sync_position_from_bybit(bybit_get,st)
            in_position,side,entry,qty,mode=st["in_position"],st["side"],st["entry"],st["qty"],st["mode"]
            price_live, k1_live = get_price_and_candles()
            if not price_live or price_live==0:
                print("[MAIN] No live price, wait 5s",flush=True); time.sleep(5); continue
            sig=get_signal(price_live, None, k1_live)
            price=float(sig.get("price",0) or price_live or 0)
            if price==0: price=price_live
            k1=sig.get("k1_norm",[]) or k1_live or []
            candles=k1[-10:] if k1 else []
            direction=sig.get("direction","NONE"); cert=sig.get("cert",0)
            hunt_cert=sig.get("hunt_certainty",{}) or {}
            hunt_score=int(hunt_cert.get("score",0) or sig.get("hunt_cert",0) or 0)
            hunt_label=hunt_cert.get("label","NO_HUNT")
            liq=sig.get("liq_clusters",{}) or {}
            cvd=sig.get("cvd_live",{}) or {}
            cvd_agg=cvd.get("aggressive","NEUTRAL"); cvd_buy=float(cvd.get("buy_pct",50) or 50)
            pileup=sig.get("pileup",{}) or {}
            # --- PATCHED: PILE RESET - no carry over ---
            raw_up=min(int(pileup.get("pileup_up_count",0) or 0),3)
            raw_down=min(int(pileup.get("pileup_down_count",0) or 0),3)
            pile_allowed=bool(pileup.get("allowed", True))
            # If allowed=False, brain go reset both to 0
            if not pile_allowed:
                try: brain.reset_pile("allowed=False from data_engine")
                except Exception: pass
                pile_up=0; pile_down=0
            else:
                pile_up=raw_up; pile_down=raw_down
                # Track dir flip / $80 move - brain go auto-reset inside
                _pile_dir_for_track="UP" if pile_up>=pile_down else "DOWN" if pile_down>0 else None
                try:
                    if _pile_dir_for_track:
                        brain.track_pile(price, _pile_dir_for_track, max(pile_up,pile_down))
                except Exception: pass
                # If brain just reset, respect it
                if getattr(brain,"pile_reset",False):
                    pile_up=0; pile_down=0
            # Flip pile count = opposite side pile
            if side=="SHORT": pile_count=pile_up
            elif side=="LONG": pile_count=pile_down
            else: pile_count=max(pile_up,pile_down)
            pile_dir="LONG" if side=="SHORT" else "SHORT" if side=="LONG" else "NONE"
            # --- CLOSE COUNTING - FIXED W/L/BE ---
            if prev_in_pos and not in_position and prev_entry>0:
                pnl_close=(price-prev_entry) if prev_side=="LONG" else (prev_entry-price)
                if be_done:
                    bes+=1; print(f"[STATS] Close -> BE counted | W {wins} L {losses} BE {bes} pnl ${pnl_close:.0f}",flush=True)
                elif pnl_close>0:
                    wins+=1; print(f"[STATS] Close -> WIN counted | W {wins} L {losses} BE {bes} pnl ${pnl_close:.0f}",flush=True)
                elif pnl_close<0:
                    losses+=1; print(f"[STATS] Close -> LOSS counted | W {wins} L {losses} BE {bes} pnl ${pnl_close:.0f}",flush=True)
                be_done=False; last_trade_close=time.time()
            bal_now=get_balance() or 0
            total=max(1,wins+losses+bes)
            win_rate=round((wins/total)*100,1) if (wins+losses)>0 else 0
            print(f"[STATS] Bal ${bal_now:.2f} W {wins} L {losses} BE {bes} Win {win_rate}% | Price ${price:.0f} Dir {direction} Cert {cert}% Hunt {hunt_label} {hunt_score}/9 Pile Up {pile_up}/3 Down {pile_down}/3 InPos {in_position} {side or ''}",flush=True)
            if in_position and side and entry:
                pnl=(price-entry) if side=="LONG" else (entry-price)
                be_t=be_target_for(mode)
                if not be_done and pnl>=be_t:
                    print(f"[BE] {side} pnl ${pnl:.0f} >= BE ${be_t:.0f} - move SL to entry",flush=True); be_done=True
                if pile_dir!="NONE" and (pile_allowed or pile_count>=3):
                    try:
                        ok,reason,tdir=should_flip_to_pileup(brain,price,side,entry,pile_count,pile_dir,hunt_score,cvd_agg,cvd_buy,cert,direction,float(liq.get("total",0) or 0),k1,candles)
                    except TypeError:
                        ok,reason,tdir=should_flip_to_pileup(brain,price,side,entry,pile_count,pile_dir,hunt_score,cvd_agg,cvd_buy,cert,direction,float(liq.get("total",0) or 0))
                    print(f"[FLIP CHECK] {reason}",flush=True)
                    if ok and tdir:
                        print(f"[FLIP] Close {side} @ ${price:.1f}, open {tdir}",flush=True)
                        if TRADING and qty>0: close_position_market(side,qty)
                        try: brain.note_flip_used(tdir,price)
                        except Exception: pass
                        # After flip, reset pile - new trade, no old pile
                        try: brain.reset_pile("after flip - new trade")
                        except Exception: pass
                        in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; be_done=False; flip_history.append((time.time(),tdir,price)); last_trade_close=time.time()
                        time.sleep(5); continue
            else:
                if not in_calm:
                    in_calm=True; calm_start=time.time()
                if time.time()-calm_start<150:
                    time.sleep(5); continue
                if direction not in ("LONG","SHORT"):
                    time.sleep(5); continue
                if cert < 75:
                    print(f"[SKIP] Cert {cert}% < 75% - no entry",flush=True); time.sleep(5); continue
                if hunt_score < 2:
                    print(f"[SKIP] Hunt {hunt_score}/9 too low",flush=True); time.sleep(5); continue
                if not TRADING or time.time()-last_trade_close<=150:
                    time.sleep(5); continue
                bal=get_balance() or 0
                if bal < 2:
                    print(f"[SKIP] Bal ${bal:.2f} < $2 min - need $2 to trade 0.001 @60x",flush=True); time.sleep(10); continue
                q,lev=dynamic_qty_lev(price,bal)
                print(f"[ENTRY CHECK] Bal ${bal:.2f} -> Qty {q} Lev {lev}x Cert {cert}% Hunt {hunt_score}/9 Dir {direction}",flush=True)
                sl,tp=calc_sl_tp(direction,price,mode)
                set_isolated_margin("BTCUSDT",lev,direction)
                r=place_order(direction,q,sl,tp,price,lev)
                print(f"[ENTRY] {direction} {q} @ ${price:.1f} Lev {lev}x SL ${sl:.1f} TP ${tp:.1f} -> {r.get('retCode')} {r.get('retMsg')}",flush=True)
                if r.get("retCode")==0:
                    in_position=True; side=direction; entry=price; qty=q; be_done=False; in_calm=False
                    try: brain.reset_pile("after entry - new pile")
                    except Exception: pass
            time.sleep(5)
        except Exception as e:
            print(f"[MAIN] Loop error {e}\n{traceback.format_exc()}",flush=True); time.sleep(5)
if __name__=="__main__": main()
