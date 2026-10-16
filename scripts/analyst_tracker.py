import json, re, email.utils
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

DATA=Path("data/data.json")
OUT=Path("data/analyst_tracker.json")
USER_AGENT="Mozilla/5.0 (GitHub Actions; Taiwan Stock Radar 321 v3.5)"
FEEDS=[
 "https://news.google.com/rss/search?q="+quote("台股 分析師 推薦 個股")+"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
 "https://news.google.com/rss/search?q="+quote("台股 分析師 看好 股票")+"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
]
GENERIC={"看好","點名","推薦","揭","曝光","喊","表示","指出","分析","這檔","股票","最推薦","資深","證券","財經","專家","不要","避免","預估","認為","提醒","建議"}

def get(url):
    req=Request(url,headers={"User-Agent":USER_AGENT})
    with urlopen(req,timeout=20) as r:return r.read()

def load(p,default):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except:return default

def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def parse_feed(url):
    out=[]
    try:
        root=ET.fromstring(get(url))
        for it in root.findall(".//item"):
            title=(it.findtext("title") or "").strip()
            link=(it.findtext("link") or "").strip()
            pub=(it.findtext("pubDate") or "").strip()
            if title: out.append({"title":title,"url":link,"published":pub})
    except Exception as e: print("RSS unavailable",e)
    return out

def parse_analyst(title):
    m=re.search(r"(?:分析師|研究員|投顧)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z]{2,8})",title)
    if not m:return None
    name=m.group(1)
    if name in GENERIC or any(x in name for x in GENERIC):return None
    if len(name)>5 and not re.search(r"[A-Za-z]",name):return None
    return name

def pub_date(s):
    try:return email.utils.parsedate_to_datetime(s).date()
    except:return None

def t3_return(stock, article_date):
    dates=stock.get("history_date",[])
    closes=stock.get("history_close",[])
    pairs=[(d,c) for d,c in zip(dates,closes) if isinstance(d,str) and isinstance(c,(int,float))]
    if not pairs:return None
    idx=None
    for i,(d,c) in enumerate(pairs):
        if d>=article_date.isoformat():
            idx=i; break
    if idx is None or idx+3>=len(pairs):return None
    entry=pairs[idx][1]
    future=[pairs[idx+j][1] for j in (1,2,3)]
    if entry in (None,0):return None
    return round((future[-1]/entry-1)*100,2)

def main():
    d=load(DATA,{"stocks":[]})
    stockmap={str(x.get("code")):x for x in d.get("stocks",[]) if x.get("code")}
    db=load(OUT,{"recommendations":[],"analysts":{},"last_scan":None})
    existing={(x.get("url"),x.get("title")) for x in db.get("recommendations",[])}
    candidates=[]
    for f in FEEDS:
        for a in parse_feed(f):
            if (a["url"],a["title"]) not in existing:candidates.append(a)
    for a in candidates:
        a["analyst"]=parse_analyst(a["title"])
        a["codes"]=[c for c in re.findall(r"(?<!\d)[1-9]\d{3}(?!\d)",a["title"]) if c in stockmap]
        pd=pub_date(a.get("published",""))
        a["article_date"]=pd.isoformat() if pd else None
    db["recommendations"]=(db.get("recommendations",[])+candidates)[-2000:]
    # Re-parse historical records so old false matches are removed and results never duplicate.
    for a in db["recommendations"]:
        a["analyst"]=parse_analyst(a.get("title",""))
        a["codes"]=[code for code in re.findall(r"(?<!\d)[1-9]\d{3}(?!\d)",a.get("title","")) if code in stockmap]
        pd=pub_date(a.get("published",""))
        a["article_date"]=pd.isoformat() if pd else a.get("article_date")
        a["results"]=[]

    stats={}
    for a in db["recommendations"]:
        name=a.get("analyst"); ad=a.get("article_date")
        if not name or not ad: continue
        try: day=datetime.fromisoformat(ad).date()
        except: continue
        s=stats.setdefault(name,{"recommendations":0,"measurable":0,"wins":0,"avg_return":None,"stocks":{}})
        for code in a.get("codes",[]):
            s["recommendations"]+=1
            s["stocks"][code]=s["stocks"].get(code,0)+1
            ret=t3_return(stockmap.get(code,{}),day)
            if ret is not None:
                s["measurable"]+=1
                s["wins"]+=int(ret>=2)
                a.setdefault("results",[]).append({"code":code,"t3_return":ret,"win":ret>=2})
    for name,s in stats.items():
        measurable=[r["t3_return"] for a in db["recommendations"] if a.get("analyst")==name for r in a.get("results",[])]
        s["avg_return"]=round(sum(measurable)/len(measurable),2) if measurable else None
        s["win_rate"]=round(s["wins"]/s["measurable"]*100,1) if s["measurable"] else None
        s["confidence"]="樣本不足" if s["measurable"]<20 else ("高" if (s["win_rate"] or 0)>=60 else "一般")
    db["analysts"]=stats
    db["last_scan"]=datetime.now().astimezone().isoformat(timespec="minutes")
    db["method"]="僅接受明確可辨識的分析師姓名＋存在於當期股票資料的4位代號；以文章日期後第3個交易日收盤相對報酬計算，未完成T+3不計入勝率。"
    save(OUT,db)
    print("Analyst records:",len(db["recommendations"]),"named analysts:",len(stats))

if __name__=="__main__":main()
