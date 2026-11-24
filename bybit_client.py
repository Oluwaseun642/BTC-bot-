# BYBIT CLIENT V17 - MAINNET - SIGN + RETRY 3x
import os,time,hmac,hashlib,requests
KEY=os.getenv("BYBIT_API_KEY","")
SEC=os.getenv("BYBIT_API_SECRET","")
BASE="https://api.bybit.com"
H={"Content-Type":"application/json"}
def _sign(q):
 ts=str(int(time.time()*1000));s=ts+KEY+"5000"+q
 return ts,hmac.new(SEC.encode(),s.encode(),hashlib.sha256).hexdigest()
def bybit_get(path,params=None):
 params=params or {};qs="&".join(f"{k}={v}" for k,v in params.items())
 ts,sig=_sign(qs);url=f"{BASE}{path}?{qs}" if qs else f"{BASE}{path}"
 for _ in range(3):
  try:
   r=requests.get(url,headers={**H,"X-BAPI-API-KEY":KEY,"X-BAPI-TIMESTAMP":ts,"X-BAPI-SIGN":sig,"X-BAPI-RECV-WINDOW":"5000"},timeout=5)
   if r.status_code==200:return r.json()
  except:time.sleep(1)
 return {"retCode":-1,"result":{}}
def bybit_post(path,data=None):
 import json;data=data or {};body=json.dumps(data)
 ts,sig=_sign(body)
 for _ in range(3):
  try:
   r=requests.post(BASE+path,headers={**H,"X-BAPI-API-KEY":KEY,"X-BAPI-TIMESTAMP":ts,"X-BAPI-SIGN":sig,"X-BAPI-RECV-WINDOW":"5000"},data=body,timeout=5)
   if r.status_code==200:return r.json()
  except:time.sleep(1)
 return {"retCode":-1,"result":{}}
