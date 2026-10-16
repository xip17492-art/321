import json, math, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

OUT=Path("data/market_bottom.json")
UA="Mozilla/5.0 (GitHub Actions; Taiwan Stock Radar 3.6)"

def get_json(url, timeout=30):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/plain,*/*"})
    with urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","ignore"))

def yahoo_taiex():
    now=int(datetime.now(timezone.utc).timestamp())
    start=int((datetime.now(timezone.utc)-timedelta(days=30*365+10)).timestamp())
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?period1={start}&period2={now}&interval=1d&events=history&includeAdjustedClose=true"
    j=get_json(url,45)
    r=(j.get("chart",{}).get("result") or [None])[0]
    if not r: raise RuntimeError("Yahoo TAIEX history unavailable")
    ts=r.get("timestamp",[]); q=r.get("indicators",{}).get("quote",[{}])[0]
    closes=q.get("close",[])
    bars=[]
    for t,c in zip(ts,closes):
        if c is None: continue
        bars.append((datetime.fromtimestamp(t,timezone.utc).date().isoformat(),float(c)))
    if len(bars)<250: raise RuntimeError("TAIEX history too short")
    return bars

def parse_margin_total(j):
    tables=j.get("tables",[]) if isinstance(j,dict) else []
    for t in tables:
        fields=t.get("fields",[]); rows=t.get("data",[])
        if not fields or not rows: continue
        mi=next((i for i,x in enumerate(fields) if "融資今日餘額" in str(x)),None)
        ni=next((i for i,x in enumerate(fields) if str(x) in ("證券代號","代號")),None)
        namei=next((i for i,x in enumerate(fields) if str(x)=="名稱"),None)
        if mi is None: continue
        # Prefer the official aggregate row; otherwise sum numeric rows.
        for row in rows:
            label=str(row[ni]).strip() if ni is not None and ni<len(row) else ""
            name=str(row[namei]).strip() if namei is not None and namei<len(row) else ""
            if label in ("合計","總計") or name in ("合計","總計"):
                try:return float(str(row[mi]).replace(",",""))
                except: pass
        vals=[]
        for row in rows:
            try: vals.append(float(str(row[mi]).replace(",","")))
            except: pass
        if vals:return sum(vals)
    return None

def recent_margin():
    out=[]
    d=datetime.now().date()
    for k in range(42):
        day=d-timedelta(days=k)
        if day.weekday()>=5: continue
        ds=day.strftime("%Y%m%d")
        try:
            j=get_json(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ds}&selectType=ALL&response=json",30)
            v=parse_margin_total(j)
            if v is not None: out.append((day.isoformat(),v))
        except Exception as e:
            print("margin",ds,"unavailable",e)
        if len(out)>=22: break
        time.sleep(1.7)
    return list(reversed(out))

def pct(a,b):
    return None if a in (None,0) or b is None else (b/a-1)*100

def rsi(closes,n=14):
    if len(closes)<=n:return None
    g=l=0.0
    for i in range(len(closes)-n,len(closes)):
        d=closes[i]-closes[i-1]
        g+=max(d,0);l+=max(-d,0)
    if l==0:return 100.0
    return 100-100/(1+(g/n)/(l/n))

def drawdown_series(bars):
    peak=-1;peak_date=None;arr=[]
    for d,c in bars:
        if c>peak: peak=c;peak_date=d
        arr.append((d,c,(c/peak-1)*100,peak,peak_date))
    return arr

def top_drawdowns(bars,min_drop=-10):
    dd=drawdown_series(bars)
    episodes=[]; active=None
    for d,c,x,p,pd in dd:
        if x<=min_drop:
            if active is None: active={"peak_date":pd,"peak":p,"trough_date":d,"trough":c,"mdd":x}
            active["trough_date"]=d;active["trough"]=c;active["mdd"]=min(active["mdd"],x)
        elif active:
            active["recovery_date"]=d
            episodes.append(active);active=None
    if active:episodes.append(active)
    # Merge nearby episodes is intentionally avoided: the signal needs the actual peak-to-trough event.
    return sorted(episodes,key=lambda x:x["mdd"])[:8]

def fear_greed(latest, bars, margin):
    closes=[x[1] for x in bars]
    dd=drawdown_series(bars)[-1][2]
    r=rsi(closes)
    r5=pct(closes[-6],closes[-1]) if len(closes)>=6 else None
    r20=pct(closes[-21],closes[-1]) if len(closes)>=21 else None
    # 0 = calm/greedy? We expose fear directly, then greed=100-fear.
    fear=0
    fear += min(45,max(0,(-dd)/35*45))
    fear += min(20,max(0,(-r5 if r5 is not None else 0)/15*20))
    fear += min(15,max(0,(-r20 if r20 is not None else 0)/25*15))
    if r is not None: fear += min(10,max(0,(45-r)/20*10))
    margin_wash=None
    if len(margin)>=2:
        vals=[v for _,v in margin]
        peak=max(vals[-min(20,len(vals)):])
        margin_wash=(vals[-1]/peak-1)*100 if peak else None
        if margin_wash is not None: fear += min(20,max(0,(-margin_wash)/15*20))
    fear=round(min(100,max(0,fear)),1)
    greed=round(100-fear,1)
    return fear,greed,dd,r,r5,r20,margin_wash

def bottom_signal(dd, margin_wash, rsi14, r5):
    # The thresholds are deliberately conservative and are not a claim that liquidation equals the exact bottom.
    score=0
    score += min(45,max(0,(-dd)/35*45))
    if margin_wash is not None: score += min(30,max(0,(-margin_wash)/15*30))
    if rsi14 is not None: score += min(15,max(0,(45-rsi14)/20*15))
    if r5 is not None: score += min(10,max(0,(-r5)/12*10))
    score=round(min(100,score),1)
    if score>=80 and dd<=-25 and (margin_wash is None or margin_wash<=-10): tier="🔥 極端恐慌／分批重手"
    elif score>=65 and dd<=-20 and (margin_wash is None or margin_wash<=-7): tier="🟢 強抄底區／分批加碼"
    elif score>=45 and dd<=-15: tier="🟡 開始抄底／小額分批"
    elif score>=30 and dd<=-10: tier="🔵 觀察區／等待融資減肥"
    else: tier="⚪ 非抄底區"
    return score,tier

def main():
    bars=yahoo_taiex()
    margin=recent_margin()
    dd=drawdown_series(bars)
    latest_date,latest_close=bars[-1]
    fear,greed,current_dd,r14,r5,r20,margin_wash=fear_greed(latest_close,bars,margin)
    score,tier=bottom_signal(current_dd,margin_wash,r14,r5)
    top=top_drawdowns(bars,-10)
    # Reference events are kept as a sanity-check layer; the live calculation above remains data-driven.
    reference=[
      {"event":"2000 網路泡沫","mdd_pct":-67.18},
      {"event":"2008 金融海嘯","mdd_pct":-57.51},
      {"event":"2020 新冠股災","mdd_pct":-29.86}
    ]
    recovery=round((1/(1+current_dd/100)-1)*100,1) if current_dd<0 else 0
    data={
      "version":"3.6","generated_at":datetime.now().astimezone().isoformat(timespec="minutes"),
      "source":"TAIEX daily history via Yahoo Finance chart API; margin via TWSE MI_MARGN official report",
      "latest":{"date":latest_date,"close":latest_close,"drawdown_pct":round(current_dd,2),"rsi14":None if r14 is None else round(r14,1),"return_5d_pct":None if r5 is None else round(r5,2),"return_20d_pct":None if r20 is None else round(r20,2),"recovery_needed_pct":recovery},
      "fear_greed":{"fear_index":fear,"greed_index":greed,"label":"極度恐慌" if fear>=80 else "恐慌" if fear>=60 else "中性偏恐慌" if fear>=45 else "中性" if fear>=35 else "貪婪" if greed>=65 else "極度貪婪"},
      "margin":{"observations":len(margin),"latest_balance":margin[-1][1] if margin else None,"washout_from_20d_peak_pct":None if margin_wash is None else round(margin_wash,2),"series":[{"date":d,"balance":v} for d,v in margin]},
      "bottom_signal":{"score":score,"tier":tier,"rule":"歷史回撤＋RSI＋5日跌幅＋融資餘額高點回落綜合；融資餘額快速下降只視為去槓桿/強制賣壓代理，不等於真正爆倉金額。"},
      "drawdown_reference":reference,
      "largest_drawdowns":top,
      "data_coverage":{"days":len(bars),"start":bars[0][0],"end":bars[-1][0],"window_years":round(len(bars)/252,1)}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("MARKET BOTTOM:",tier,"score",score,"DD",round(current_dd,2),"margin washout",margin_wash,"days",len(bars),"margin obs",len(margin))

if __name__=="__main__": main()
