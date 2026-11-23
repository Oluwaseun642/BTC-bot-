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
def home(): return "OK V16.6 MAIN SPLIT - 3 DOORS FIXED HUNT DIR",200
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
    if bal < 5: return 0.001, 60
    if bal < 15: return 0.001, 40
    if bal < 50:
        q = 10.0 / 600.0
        return max(0.001, round(q,3)), 30
    if bal < 200:
        q = 20.0 / 600.0
        return max(0.001, round(q,3)), 20
    risk = bal * 0.02
    q = risk / 600.0
    return max(0.001, round(q,3)), 15
def do_enter(direction, price, bal, mode_label):
    q,lev=dynamic_qty_lev(price,bal)
    print(f"[ENTRY CHECK] Bal ${bal:.2f} -> Qty {q} Lev {lev}x Dir {direction} Mode {mode_label}",flush=True)
    sl,tp=calc_sl_tp(direction,price,"NORMAL")
    set_isolated_margin("BTCUSDT",lev,direction)
    r=place_order(direction,q,sl,tp,price,lev)
    print(f"[ENTRY] {direction} {q} @ ${price:.1f} Lev {lev}x SL ${sl:.1f} TP ${tp:.1f} Mode {mode_label} -> {r.get('retCode')} {r.get('retMsg')}",flush=True)
    return r,q

def main():
    keep_alive(); Thread(target=self_ping,daemon=True).start()
    print("[MAIN] V16.6 - 3 DOORS | CERT 75% Worldwide | HUNTER flip_dir FIXED | PILE 3/3 Calm",flush=True)
    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"
    be_done=False; last_trade_close=0.0; in_calm=False; calm_start=0.0
    brain=PileupFlipBrain(); flip_history=[]
    wins=0; losses=0; bes=0; last_dir=None
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
            # --- FIXED: Hunt direction from data_engine V16.2 ---
            # data_engine gives: sig["flip_dir"] = LONG/SHORT/NONE, sig["flip_allowed"] bool
            # + hunt_cert["hunt_dir"] = UP_FIRST / DOWN_FIRST
            # UP_FIRST -> LONG (hunt shorts first, price go up), DOWN_FIRST -> SHORT
            _map={"UP_FIRST":"LONG","DOWN_FIRST":"SHORT","LONG":"LONG","SHORT":"SHORT"}
            _raw_hunt_dir = sig.get("flip_dir") or sig.get("hunt_trade_dir") or hunt_cert.get("hunt_dir") or "NONE"
            hunt_dir = _map.get(_raw_hunt_dir, "NONE")
            # Fallback: hunter_bias (LONG/SHORT/NEUTRAL) if flip_dir is NONE
            hunter_bias=sig.get("hunter_bias","NEUTRAL")
            if hunt_dir=="NONE" and hunter_bias in ("LONG","SHORT"): hunt_dir=hunter_bias
            flip_allowed=bool(sig.get("flip_allowed",False)); flip_reason=sig.get("flip_reason","")
            flip_dir=sig.get("flip_dir","NONE")
            sweep_done=bool(sig.get("sweep_done",False)); sweep_dir=sig.get("sweep_dir","NONE")
            hunt_ride=bool(sig.get("hunt_ride",False)); hunt_ride_dir=sig.get("hunt_ride_dir","NONE")
            # If sweep done, data_engine already set cert=85, direction=sweep_dir - honour am
            if sweep_done and sweep_dir in ("LONG","SHORT"):
                direction=sweep_dir; cert=max(cert,85.0)
                print(f"[SWEEP DONE] {sweep_dir} @ ${price:,.0f} - Cert forced 85% - ENTER IMMEDIATELY",flush=True)
            liq=sig.get("liq_clusters",{}) or {}
            cvd=sig.get("cvd_live",{}) or {}
            cvd_agg=cvd.get("aggressive","NEUTRAL"); cvd_buy=float(cvd.get("buy_pct",50) or 50)
            pileup=sig.get("pileup",{}) or {}
            raw_up=min(int(pileup.get("pileup_up_count",0) or 0),3)
            raw_down=min(int(pileup.get("pileup_down_count",0) or 0),3)
            pile_allowed=bool(pileup.get("allowed", True))
            if not pile_allowed:
                try: brain.reset_pile("allowed=False from data_engine")
                except Exception: pass
                pile_up=0; pile_down=0
            else:
                pile_up=raw_up; pile_down=raw_down
                _pd="UP" if pile_up>=pile_down else "DOWN" if pile_down>0 else None
                try:
                    if _pd: brain.track_pile(price, _pd, max(pile_up,pile_down))
                except Exception: pass
                if getattr(brain,"pile_reset",False): pile_up=0; pile_down=0
            if last_dir is not None and direction in ("LONG","SHORT") and direction != last_dir:
                pile_up=0; pile_down=0
                try: brain.reset_pile(f"direction change {last_dir}->{direction}")
                except Exception: pass
                print(f"[PILE] Reset - direction {last_dir} -> {direction} - 0/3",flush=True)
            if direction in ("LONG","SHORT"): last_dir=direction
            if not in_position:
                if pile_up>=3 and pile_up>=pile_down: flat_pile_dir="LONG"; flat_pile_count=pile_up
                elif pile_down>=3 and pile_down>=pile_up: flat_pile_dir="SHORT"; flat_pile_count=pile_down
                else: flat_pile_dir="NONE"; flat_pile_count=max(pile_up,pile_down)
            else: flat_pile_dir="NONE"; flat_pile_count=0
            if side=="SHORT": pile_count=pile_up
            elif side=="LONG": pile_count=pile_down
            else: pile_count=max(pile_up,pile_down)
            pile_dir="LONG" if side=="SHORT" else "SHORT" if side=="LONG" else "NONE"
            is_calm=(cert<75 and hunt_score<5)
            if prev_in_pos and not in_position and prev_entry>0:
                pnl_close=(price-prev_entry) if prev_side=="LONG" else (prev_entry-price)
                if be_done: bes+=1; print(f"[STATS] Close -> BE | W {wins} L {losses} BE {bes} pnl ${pnl_close:.0f}",flush=True)
                elif pnl_close>0: wins+=1; print(f"[STATS] Close -> WIN | W {wins} L {losses} BE {bes} pnl ${pnl_close:.0f}",flush=True)
                elif pnl_close<0: losses+=1; print(f"[STATS] Close -> LOSS | W {wins} L {losses} BE {bes} pnl ${pnl_close:.0f}",flush=True)
                be_done=False; last_trade_close=time.time(); mode="NORMAL"
            bal_now=get_balance() or 0
            total=max(1,wins+losses+bes)
            win_rate=round((wins/total)*100,1) if (wins+losses)>0 else 0
            print(f"[STATS] Bal ${bal_now:.2f} W {wins} L {losses} BE {bes} Win {win_rate}% | Price ${price:.0f} Dir {direction} Cert {cert}% Hunt {hunt_label} {hunt_score}/9 HuntDir {hunt_dir} Flip {flip_dir} FlipAllowed {flip_allowed} Pile Up {pile_up}/3 Down {pile_down}/3 FlatPile {flat_pile_dir} {flat_pile_count}/3 Calm {is_calm} Sweep {sweep_done} {sweep_dir} InPos {in_position} {side or ''} Mode {mode}",flush=True)
            if flip_allowed and flip_reason: print(f"[FLIP GATE] {flip_reason}",flush=True)
            if in_position and side and entry:
                pnl=(price-entry) if side=="LONG" else (entry-price)
                be_t=be_target_for(mode)
                if not be_done and pnl>=be_t: print(f"[BE] {side} pnl ${pnl:.0f} >= BE ${be_t:.0f}",flush=True); be_done=True
                if mode=="HUNTER" and hunt_score<2:
                    print(f"[FLIP BACK] Hunters done {hunt_score}/9 - close {side} hunter, flip back to NORMAL {direction}",flush=True)
                    if TRADING and qty>0: close_position_market(side,qty)
                    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; be_done=False; last_trade_close=time.time(); time.sleep(5); continue
                if mode=="PILE" and pile_count==0:
                    print(f"[PILE DONE] Pile reset 0/3 - close {side} pile, flip back to NORMAL {direction}",flush=True)
                    if TRADING and qty>0: close_position_market(side,qty)
                    in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; be_done=False; last_trade_close=time.time(); time.sleep(5); continue
                # --- BIG HUNTER OVERRIDE IN POSITION - BOTH SIDES, USE flip_allowed OR hunt_score>=5 ---
                if hunt_dir in ("LONG","SHORT") and hunt_dir!=side and (flip_allowed or hunt_score>=5):
                    print(f"[BIG HUNTER OVERRIDE] In {side} but Hunt {hunt_score}/9 {hunt_dir} override Cert {direction} - FLIP {side}->{hunt_dir} | {flip_reason}",flush=True)
                    if TRADING and qty>0: close_position_market(side,qty)
                    time.sleep(2)
                    bal=get_balance() or 0
                    if bal>=2 and TRADING:
                        r,q2=do_enter(hunt_dir,price,bal,"HUNTER")
                        if r.get("retCode")==0: in_position=True; side=hunt_dir; entry=price; qty=q2; mode="HUNTER"; be_done=False
                    else: in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"
                    time.sleep(5); continue
                if pile_dir!="NONE" and (pile_allowed or pile_count>=3):
                    try: ok,reason,tdir=should_flip_to_pileup(brain,price,side,entry,pile_count,pile_dir,hunt_score,cvd_agg,cvd_buy,cert,direction,float(liq.get("total",0) or 0),k1,candles)
                    except TypeError: ok,reason,tdir=should_flip_to_pileup(brain,price,side,entry,pile_count,pile_dir,hunt_score,cvd_agg,cvd_buy,cert,direction,float(liq.get("total",0) or 0))
                    print(f"[FLIP CHECK] {reason}",flush=True)
                    if ok and tdir:
                        print(f"[FLIP] Close {side} @ ${price:.1f}, open {tdir}",flush=True)
                        if TRADING and qty>0: close_position_market(side,qty)
                        try: brain.note_flip_used(tdir,price)
                        except Exception: pass
                        try: brain.reset_pile("after flip - new trade")
                        except Exception: pass
                        in_position=False; side=None; entry=0.0; qty=0.0; mode="NORMAL"; be_done=False; flip_history.append((time.time(),tdir,price)); last_trade_close=time.time(); time.sleep(5); continue
            else:
                if not in_calm: in_calm=True; calm_start=time.time()
                calm_passed=(time.time()-calm_start>=150) or (time.time()-last_trade_close>=150) or sweep_done
                if not TRADING: time.sleep(5); continue
                enter_dir=None; enter_mode=None
                # DOOR 1: NORMAL - Cert 75% LONG or SHORT
                if direction in ("LONG","SHORT") and cert>=75 and calm_passed: enter_dir=direction; enter_mode="NORMAL"
                # DOOR 2: BIG HUNTER - flip_dir / hunt_dir LONG or SHORT, flip_allowed OR score>=5
                elif hunt_dir in ("LONG","SHORT") and (flip_allowed or hunt_score>=5):
                    enter_dir=hunt_dir; enter_mode="HUNTER"
                    print(f"[BIG HUNTER] Hunt {hunt_score}/9 {hunt_dir} override/support Cert {direction} {cert}% FlipAllowed {flip_allowed} - enter hunter",flush=True)
                # DOOR 3: PILE BOUNCE - Calm + Pile 3/3 LONG or SHORT, Cert no block
                elif is_calm and flat_pile_dir in ("LONG","SHORT") and flat_pile_count>=3:
                    enter_dir=flat_pile_dir; enter_mode="PILE"
                    print(f"[PILE BOUNCE] Pile {flat_pile_count}/3 {flat_pile_dir} Calm - Cert {cert}% no block",flush=True)
                else:
                    if sweep_done: print(f"[SKIP] Sweep but no door? Dir {direction} Cert {cert}%",flush=True)
                    elif direction not in ("LONG","SHORT"): print(f"[SKIP] Dir NONE - no worldwide direction",flush=True)
                    elif cert<75 and hunt_score<5 and not (is_calm and flat_pile_count>=3): print(f"[SKIP] Cert {cert}% <75% + Hunt {hunt_score}/9 <5 + Pile {flat_pile_count}/3 <3 - all 3 doors closed",flush=True)
                    elif not calm_passed and cert>=75: print(f"[SKIP] NORMAL Cert {cert}% ok but CALM {int(time.time()-calm_start)}s/150s - wait",flush=True)
                    time.sleep(5); continue
                bal=get_balance() or 0
                if bal<2: print(f"[SKIP] Bal ${bal:.2f} < $2 min",flush=True); time.sleep(10); continue
                r,q=do_enter(enter_dir,price,bal,enter_mode)
                if r.get("retCode")==0:
                    in_position=True; side=enter_dir; entry=price; qty=q; be_done=False; in_calm=False; mode=enter_mode
                    try: brain.reset_pile("after entry - new pile")
                    except Exception: pass
            time.sleep(5)
        except Exception as e:
            print(f"[MAIN] Loop error {e}\n{traceback.format_exc()}",flush=True); time.sleep(5)
if __name__=="__main__": main()
