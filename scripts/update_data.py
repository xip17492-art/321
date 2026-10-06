import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
OUT=Path("data/data.json"); UA="Mozilla/5.0 (GitHub Actions; Taiwan Stock Radar 321)"
def get_json(url):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/plain,*/*"})
    with urlopen(req,timeout=45) as r:return json.loads(r.read().decode("utf-8-sig"))
def num(v):
    if v is None:return None
    s=str(v).replace(",","").replace(" ","").strip()
    if s in ("","-","--","None","null"):return None
    try:return float(s)
    except:return None
def sma(a,n):return sum(a[-n:])/n if len(a)>=n else None
def rsi(a,n=14):
    if len(a)<=n:return None
    g=l=0
    for d in [a[i]-a[i-1] for i in range(1,len(a))][-n:]:g+=max(d,0);l+=max(-d,0)
    return 100.0 if l==0 else 100-(100/(1+g/l))
def twse_quotes():
    rows=get_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL");out=[]
    for r in rows:
        c=str(r.get("Code","")).strip();close=num(r.get("ClosingPrice"))
        if not(c.isdigit() and len(c)==4 and close is not None):continue
        out.append({"code":c,"name":str(r.get("Name","")).strip(),"market":"TWSE","open":num(r.get("OpeningPrice")),"high":num(r.get("HighestPrice")),"low":num(r.get("LowestPrice")),"close":close,"volume":num(r.get("TradeVolume")),"change":num(r.get("Change"))})
    return out
def tpex_quotes():
    try:rows=get_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
    except Exception as e:print("TPEx unavailable:",e);return []
    out=[]
    for r in rows:
        c=str(r.get("SecuritiesCompanyCode","")).strip();close=num(r.get("Close"))
        if not(c.isdigit() and len(c)==4 and close is not None):continue
        out.append({"code":c,"name":str(r.get("CompanyName","")).strip(),"market":"TPEX","open":num(r.get("Open")),"high":num(r.get("High")),"low":num(r.get("Low")),"close":close,"volume":num(r.get("TradingShares")),"change":None})
    return out
def twse_inst():
    d=datetime.now().strftime("%Y%m%d")
    for u in [f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALLBUT0999&response=json",f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALL&response=json"]:
        try:
            j=get_json(u);fields=j.get("fields",[]);data=j.get("data",[]);idx={f:i for i,f in enumerate(fields)}
            def ix(*names):
                for n in names:
                    if n in idx:return idx[n]
            ic=ix("è­å¸ä»£è");a=ix("å¤é¸è³è²·è³£è¶è¡æ¸(ä¸å«å¤è³èªçå)");b=ix("æä¿¡è²·è³£è¶è¡æ¸");c=ix("èªçåè²·è³£è¶è¡æ¸");out={}
            for row in data:
                if ic is None:continue
                code=str(row[ic]).strip();vals=[]
                for i in (a,b,c):
                    if i is not None and i<len(row):vals.append(num(row[i]) or 0)
                if vals:out[code]=sum(vals)
            if out:return out
        except Exception as e:print("TWSE T86 unavailable:",e)
    return {}
def main():
    today=datetime.now().strftime("%Y-%m-%d");old={}
    if OUT.exists():
        try:old=json.loads(OUT.read_text(encoding="utf-8"))
        except:old={}
    oldmap={x["code"]:x for x in old.get("stocks",[]) if x.get("code")};quotes=twse_quotes()+tpex_quotes()
    if not quotes:raise RuntimeError("No market data returned")
    inst=twse_inst();result=[]
    for x in quotes:
        prev=oldmap.get(x["code"],{});closes=list(prev.get("history_close",[]))[-59:]+[x["close"]];vols=list(prev.get("history_volume",[]))[-59:]+[x.get("volume") or 0]
        ma5=sma(closes,5);ma20=sma(closes,20);rr=rsi(closes,14);pv=sma(vols[:-1],5) if len(vols)>=6 else None;vr=vols[-1]/pv if pv else None;score=45
        if ma5 and x["close"]>ma5:score+=10
        if ma20 and x["close"]>ma20:score+=10
        if rr is not None:
            if 55<=rr<=72:score+=10
            elif rr>80:score-=8
        if vr is not None:
            if vr>=1.8:score+=15
            elif vr>=1.5:score+=10
            elif vr>=1.2:score+=5
        if x.get("change") is not None and x["change"]>=5:score+=5
        score=max(0,min(100,round(score)));breakout=bool(ma20 and x["close"]>ma20 and x.get("high") and x["close"]>=x["high"]*0.98);risk="high" if rr is not None and rr>=82 else ("low" if score>=75 and (rr is None or rr<75) else "medium")
        result.append({**x,"score":score,"ma5":ma5,"ma20":ma20,"rsi":rr,"volume_ratio":vr,"inst_net":inst.get(x["code"]),"breakout":breakout,"risk":risk,"strategy":"çªç ´åæ¸¬" if breakout else ("éå¢è§å¯" if score>=70 else "è§å¯"),"history_close":closes,"history_volume":vols})
    result.sort(key=lambda z:(z["score"],z.get("volume_ratio") or 0),reverse=True);payload={"date":today,"updated_at":datetime.now().astimezone().isoformat(timespec="minutes"),"stocks":result};OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8");print("Updated",len(result),"stocks")
if __name__=="__main__":main()
