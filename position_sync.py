import time
def sync_position_from_bybit(bybit_get_fn,st):
    try:
        j=bybit_get_fn("/v5/position/list",{"category":"linear","symbol":"BTCUSDT"})
        lst=j.get("result",{}).get("list",[])
        if not lst or float(lst[0].get("size",0))==0:
            if st.get("in_position"): st.update({"in_position":False,"side":None,"entry":0.0,"qty":0.0,"mode":"NORMAL"})
            return st
        p=lst[0]; size=float(p.get("size",0)); bs=p.get("side","")
        ent=float(p.get("entryPrice",0) or p.get("avgPrice",0) or 0)
        real="LONG" if bs=="Buy" else "SHORT" if bs=="Sell" else None
        if not real: return st
        if not st.get("in_position"):
            print(f"[SYNC] FOUND MANUAL: {real} {size} @ ${ent:.1f}",flush=True)
            st.update({"in_position":True,"side":real,"entry":ent,"qty":size,"synced_from_bybit":True,"synced_at":time.time()}); return st
        if st.get("side")!=real:
            print(f"[SYNC] SIDE CHANGE: {st.get('side')} -> {real} @ ${ent:.1f}",flush=True)
            st.update({"side":real,"entry":ent,"qty":size}); return st
        if abs(st.get("entry",0)-ent)>0.5 or abs(st.get("qty",0)-size)>0.0001: st.update({"entry":ent,"qty":size})
        return st
    except Exception as e:
        print(f"[SYNC] error {e}",flush=True); return st
