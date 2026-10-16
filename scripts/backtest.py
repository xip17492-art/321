import json, math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path("data/data.json")
OUT = Path("data/backtest.json")

def rsi(values, n=14):
    if len(values) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    g = sum(gains[-n:]) / n
    l = sum(losses[-n:]) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)

def pct(a, b):
    return None if a in (None, 0) or b is None else (b / a - 1) * 100

def classify(closes, vols, t):
    if t < 25:
        return None
    c = closes[t]
    ma20 = sum(closes[t-19:t+1]) / 20
    prev20_high = max(closes[t-20:t])
    avg5 = sum(vols[t-5:t]) / 5
    vr = vols[t] / avg5 if avg5 > 0 else None
    mom20 = pct(closes[t-20], c)
    rr = rsi(closes[:t+1], 14)
    if vr is None or mom20 is None or rr is None:
        return None
    breakout = (c >= prev20_high * 1.005) or (c > ma20 * 1.02 and vr >= 1.35)
    heat = 0
    heat += max(0, rr - 65) * 1.35
    heat += max(0, vr - 1.5) * 14
    heat += max(0, mom20 - 8) * 0.9
    heat = min(100, max(0, heat))
    if breakout and vr >= 1.5 and c > ma20 and mom20 > 0 and 50 <= rr <= 75 and heat < 75:
        tier = "A_強突破"
    elif breakout and vr >= 1.25 and c > ma20 and mom20 > 0 and heat < 80:
        tier = "B_突破確認"
    elif c > ma20 and mom20 > 0 and vr >= 1.10 and rr < 78 and heat < 80:
        tier = "C_起漲前"
    else:
        return None
    return {"tier": tier, "breakout": breakout, "volume_ratio": round(vr,3), "momentum20": round(mom20,2), "rsi": round(rr,1), "heat": round(heat,1)}

def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    stocks = d.get("stocks", [])
    events = []
    by_tier = {}
    by_score = {}
    for s in stocks:
        closes = [x for x in s.get("history_close", []) if isinstance(x, (int,float))]
        vols = [x for x in s.get("history_volume", []) if isinstance(x, (int,float))]
        dates = s.get("history_date", [])
        n = min(len(closes), len(vols))
        if n < 40:
            continue
        closes, vols = closes[-n:], vols[-n:]
        dates = dates[-n:] if len(dates) >= n else []
        for t in range(25, n-3):
            sig = classify(closes, vols, t)
            if not sig:
                continue
            future = closes[t+1:t+4]
            rets = [(v / closes[t] - 1) * 100 for v in future if closes[t]]
            if len(rets) < 3:
                continue
            hit = max(rets) >= 2
            close_win = rets[-1] >= 2
            stop = min(rets) <= -3
            outcome = {
                "hit_2pct_t3": hit,
                "close_2pct_t3": close_win,
                "stop_3pct_t3": stop,
                "max_return_t3": round(max(rets),2),
                "close_return_t3": round(rets[-1],2),
                "min_return_t3": round(min(rets),2)
            }
            e = {"code":s.get("code"),"name":s.get("name"),"date":dates[t] if t < len(dates) else None,**sig,**outcome}
            events.append(e)
            b = by_tier.setdefault(sig["tier"], {"samples":0,"hit":0,"close_win":0,"stop":0,"avg_max_return":0,"avg_close_return":0})
            b["samples"] += 1; b["hit"] += int(hit); b["close_win"] += int(close_win); b["stop"] += int(stop)
            b["avg_max_return"] += max(rets); b["avg_close_return"] += rets[-1]
            # A compact score bucket for later calibration/monitoring.
            proxy = 50
            proxy += 15 if sig["breakout"] else 0
            proxy += min(15, max(0, (sig["volume_ratio"]-1)*20))
            proxy += 8 if sig["momentum20"] > 0 else 0
            proxy += 7 if 50 <= sig["rsi"] <= 72 else 0
            proxy -= min(15, max(0, sig["heat"]-55))
            proxy = int(max(0,min(100,round(proxy/100*100))))
            bucket = f"{(proxy//10)*10}-{(proxy//10)*10+9}"
            q=by_score.setdefault(bucket,{"samples":0,"hit":0,"close_win":0})
            q["samples"]+=1;q["hit"]+=int(hit);q["close_win"]+=int(close_win)
    for b in by_tier.values():
        n=b["samples"]; b["hit_rate"]=round(b["hit"]/n*100,1); b["close_win_rate"]=round(b["close_win"]/n*100,1); b["stop_rate"]=round(b["stop"]/n*100,1)
        b["avg_max_return"]=round(b["avg_max_return"]/n,2); b["avg_close_return"]=round(b["avg_close_return"]/n,2)
    for b in by_score.values():
        n=b["samples"]; b["hit_rate"]=round(b["hit"]/n*100,1); b["close_win_rate"]=round(b["close_win"]/n*100,1)
    # Compare against the same universe without a signal, using the first 3 future closes.
    baseline=[]
    for s in stocks:
        c=[x for x in s.get("history_close",[]) if isinstance(x,(int,float))]
        for t in range(25,len(c)-3):
            rs=[(v/c[t]-1)*100 for v in c[t+1:t+4] if c[t]]
            if len(rs)==3: baseline.append(rs)
    baseline_hit=sum(max(r)>=2 for r in baseline)
    baseline_close=sum(r[-1]>=2 for r in baseline)
    OUT.write_text(json.dumps({
        "version":"1.0","generated_at":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="minutes"),
        "method":"歷史收盤＋成交量 walk-forward；每個訊號只使用當日及以前資料，T+3 不使用未來資料判斷訊號。",
        "events":len(events),"stocks_tested":sum(1 for s in stocks if len(s.get("history_close",[]))>=40),
        "baseline":{"samples":len(baseline),"hit_2pct_t3_rate":round(baseline_hit/len(baseline)*100,1) if baseline else None,"close_2pct_t3_rate":round(baseline_close/len(baseline)*100,1) if baseline else None},
        "tiers":by_tier,"score_buckets":by_score,
        "target":{"win_rate_target":60,"definition":"T+3 期間內任一收盤價相對訊號價達 +2% 為命中；此回測不等同未來保證。"},
        "recent_events":events[-200:]
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print("BACKTEST EVENTS:",len(events),"STOCKS:",sum(1 for s in stocks if len(s.get("history_close",[]))>=40))

if __name__=="__main__":
    main()
