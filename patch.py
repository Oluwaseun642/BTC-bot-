from datetime import datetime, timezone
_SESSION_OPENS_MIN=[0,420,810]
def session_status(now=None):
    now=now or datetime.now(timezone.utc)
    mins=now.hour*60+now.minute
    for o in _SESSION_OPENS_MIN:
        to=(o-mins)%1440; since=(mins-o)%1440
        if to<=60: return True,False,f"SESSION COMING in {to}m - Get ready",to
        if since<=20: return False,True,f"SESSION JUST OPENED {since}m ago - Get ready",since
    return False,False,"NO SESSION AT HAND - Calm period",9999
