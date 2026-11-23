def is_hunter_takeover(score,liq_total,cvd_buy,cert_dir,move_against):
    if score<6: return False,f"No takeover - Hunt {score}/9 <6"
    if liq_total<5000000: return False,f"No takeover - Liq ${liq_total:,.0f} < $5M"
    if cert_dir=="SHORT" and cvd_buy<60: return False,f"No takeover - Cert SHORT but CVD BUY {cvd_buy}% <60%"
    if cert_dir=="LONG" and cvd_buy>40: return False,f"No takeover - Cert LONG but CVD BUY {cvd_buy}% >40%"
    if move_against<800: return False,f"No takeover - Move ${move_against:.0f} < $800"
    return True,f"HUNTER TAKEOVER! Score {score}/9, Liq ${liq_total:,.0f}, CVD {cvd_buy}%, Move ${move_against:.0f} vs {cert_dir}"
