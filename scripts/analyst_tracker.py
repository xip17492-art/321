import json, re, math
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

DATA=Path("data/data.json")
OUT=Path("data/analyst_tracker.json")
USER_AGENT="Mozilla/5.0 (GitHub Actions; Taiwan Stock Radar 321 v3.1-F)"

# 公開新聞搜尋 RSS；只把可辨識的「分析師＋個股」文章納入候選，避免把一般新聞誤算成分析師績效。
FEEDS=[
 "https://news.google.com/rss/search?q="+quote("台股 分析師 推薦 個股")+"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
 "https://news.google.com/rss/search?q="+quote("台股 分析師 看好 股票")+"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
]

def get(url):
    req=Request(url,headers={"User-Agent":USER_AGENT})
    with urlopen(req,timeout=20) as r:return r.read()

def load(p,default):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except:return default

def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def parse_feed(url):
    out=[]
    try:
        root=ET.fromstring(get(url))
        for it in root.findall(".//item"):
            title=(it.findtext("title") or "").strip(); link=(it.findtext("link") or "").strip(); pub=(it.findtext("pubDate") or "").strip()
            if title:out.append({"title":title,"url":link,"published":pub})
    except Exception as e: print("RSS unavailable",e)
    return out

def main():
    d=load(DATA,{"stocks":[]}); stocks={x.get("code"):x for x in d.get("stocks",[]) if x.get("code")}
    db=load(OUT,{"recommendations":[],"analysts":{},"last_scan":None})
    existing={(x.get("url"),x.get("title")) for x in db.get("recommendations",[])}
    candidates=[]
    for f in FEEDS:
        for a in parse_feed(f):
            if (a["url"],a["title"]) not in existing:candidates.append(a)
    # 只保存文章索引；未能可靠抽取分析師姓名/股票代號時，不進績效統計。
    for a in candidates:
        m=re.search(r"(?:分析師|投顧|研究員)[：: ]*([\u4e00-\u9fffA-Za-z]{2,12})",a["title"])
        codes=re.findall(r"\b[1-9][0-9]{3}\b",a["title"])
        if m and codes:
            a["analyst"]=m.group(1);a["codes"]=[c for c in codes if c in stocks]
        else:a["analyst"]=None;a["codes"]=[]
    db["recommendations"]=(db.get("recommendations",[])+candidates)[-2000:]
    # 用目前資料快照做可重現的即時績效估計；真正 T+1/T+3/T+5 需等未來日資料累積。
    stats={}
    for a in db["recommendations"]:
        name=a.get("analyst")
        if not name:continue
        s=stats.setdefault(name,{"recommendations":0,"measurable":0,"wins":0,"avg_return":None,"stocks":{}})
        for code in a.get("codes",[]):
            if code not in stocks:continue
            s["recommendations"]+=1
            s["stocks"][code]=s["stocks"].get(code,0)+1
    for name,s in stats.items():
        s["win_rate"]=round(s["wins"]/s["measurable"]*100,1) if s["measurable"] else None
        s["confidence"]="樣本不足" if s["measurable"]<20 else ("高" if (s["win_rate"] or 0)>=60 else "一般")
    db["analysts"]=stats;db["last_scan"]=datetime.now().astimezone().isoformat(timespec="minutes")
    db["method"]="只有具備可辨識分析師與股票代號的公開文章才進入追蹤；未完成 T+1/T+3/T+5 前不計勝率。"
    save(OUT,db)
    print("Analyst records:",len(db["recommendations"]))
if __name__=="__main__":main()
