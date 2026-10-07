import json
import math
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path("data/data.json")
UA = "Mozilla/5.0 (GitHub Actions; Taiwan Stock Radar 321 v3.0)"

def get_json(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
    with urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8-sig"))

def num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").replace(" ", "").strip()
    if s in ("", "-", "--", "None", "null", "N/A"):
        return None
    try:
        return float(s)
    except Exception:
        return None

def sma(a, n):
    a = [x for x in a if x is not None]
    return sum(a[-n:]) / n if len(a) >= n else None

def rsi(a, n=14):
    a = [x for x in a if x is not None]
    if len(a) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(a)):
        d = a[i] - a[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    g, l = sum(gains[-n:]) / n, sum(losses[-n:]) / n
    if l == 0:
        return 100.0
    return 100 - (100 / (1 + g / l))

def pct(a, b):
    return None if a in (None, 0) or b is None else (b / a - 1) * 100

def pick_index(fields, *needles):
    for i, f in enumerate(fields):
        fs = str(f).lower().replace(" ", "")
        if all(str(n).lower().replace(" ", "") in fs for n in needles):
            return i
    return None

def twse_quotes():
    rows = get_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
    out = []
    for r in rows:
        c = str(r.get("Code", "")).strip()
        close = num(r.get("ClosingPrice"))
        if not (c.isdigit() and len(c) == 4 and close is not None):
            continue
        out.append({
            "code": c, "name": str(r.get("Name", "")).strip(), "market": "TWSE",
            "open": num(r.get("OpeningPrice")), "high": num(r.get("HighestPrice")),
            "low": num(r.get("LowestPrice")), "close": close,
            "volume": num(r.get("TradeVolume")), "change": num(r.get("Change"))
        })
    return out

def tpex_quotes():
    try:
        rows = get_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
    except Exception as e:
        print("TPEx unavailable:", e)
        return []
    out = []
    for r in rows:
        c = str(r.get("SecuritiesCompanyCode", "")).strip()
        close = num(r.get("Close"))
        if not (c.isdigit() and len(c) == 4 and close is not None):
            continue
        out.append({
            "code": c, "name": str(r.get("CompanyName", "")).strip(), "market": "TPEX",
            "open": num(r.get("Open")), "high": num(r.get("High")),
            "low": num(r.get("Low")), "close": close,
            "volume": num(r.get("TradingShares")), "change": None
        })
    return out

def twse_t86():
    d = datetime.now().strftime("%Y%m%d")
    try:
        j = get_json(f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALL&response=json")
        fields, rows = j.get("fields", []), j.get("data", [])
        code_i = pick_index(fields, "證券代號")
        total_i = pick_index(fields, "三大法人買賣超股數")
        foreign_i = pick_index(fields, "外陸資買賣超股數")
        trust_i = pick_index(fields, "投信買賣超股數")
        dealer_i = pick_index(fields, "自營商買賣超股數")
        out = {}
        for row in rows:
            if code_i is None or code_i >= len(row):
                continue
            c = str(row[code_i]).strip()
            out[c] = {
                "inst_net": num(row[total_i]) if total_i is not None and total_i < len(row) else None,
                "foreign_net": num(row[foreign_i]) if foreign_i is not None and foreign_i < len(row) else None,
                "trust_net": num(row[trust_i]) if trust_i is not None and trust_i < len(row) else None,
                "dealer_net": num(row[dealer_i]) if dealer_i is not None and dealer_i < len(row) else None
            }
        return out
    except Exception as e:
        print("T86 unavailable:", e)
        return {}

def twse_margin():
    d = datetime.now().strftime("%Y%m%d")
    try:
        j = get_json(f"https://www.twse.com.tw/exchangeReport/MI_MARGN?date={d}&response=json")
        fields, rows = j.get("fields", []), j.get("data", [])
        code_i = pick_index(fields, "證券代號")
        mb_i = pick_index(fields, "融資餘額")
        ms_i = pick_index(fields, "融券餘額")
        mbi = pick_index(fields, "融資買進")
        msi = pick_index(fields, "融券賣出")
        out = {}
        for row in rows:
            if code_i is None or code_i >= len(row):
                continue
            c = str(row[code_i]).strip()
            out[c] = {
                "margin_balance": num(row[mb_i]) if mb_i is not None and mb_i < len(row) else None,
                "short_balance": num(row[ms_i]) if ms_i is not None and ms_i < len(row) else None,
                "margin_buy": num(row[mbi]) if mbi is not None and mbi < len(row) else None,
                "short_sell": num(row[msi]) if msi is not None and msi < len(row) else None
            }
        return out
    except Exception as e:
        print("MI_MARGN unavailable:", e)
        return {}

def twse_lending():
    d = datetime.now().strftime("%Y%m%d")
    try:
        j = get_json(f"https://www.twse.com.tw/exchangeReport/TWT93U?date={d}&response=json")
        fields, rows = j.get("fields", []), j.get("data", [])
        code_i = pick_index(fields, "證券代號")
        bal_i = pick_index(fields, "借券賣出餘額")
        sell_i = pick_index(fields, "市場借券賣出")
        out = {}
        for row in rows:
            if code_i is None or code_i >= len(row):
                continue
            c = str(row[code_i]).strip()
            out[c] = {
                "lending_balance": num(row[bal_i]) if bal_i is not None and bal_i < len(row) else None,
                "lending_sell": num(row[sell_i]) if sell_i is not None and sell_i < len(row) else None
            }
        return out
    except Exception as e:
        print("TWT93U unavailable:", e)
        return {}

def twse_valuation():
    d = datetime.now().strftime("%Y%m%d")
    try:
        j = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={d}&selectType=ALL&response=json")
        fields, rows = j.get("fields", []), j.get("data", [])
        code_i = pick_index(fields, "證券代號")
        y_i = pick_index(fields, "殖利率")
        pe_i = pick_index(fields, "本益比")
        pb_i = pick_index(fields, "股價淨值比")
        out = {}
        for row in rows:
            if code_i is None or code_i >= len(row):
                continue
            c = str(row[code_i]).strip()
            out[c] = {
                "dividend_yield": num(row[y_i]) if y_i is not None and y_i < len(row) else None,
                "pe": num(row[pe_i]) if pe_i is not None and pe_i < len(row) else None,
                "pb": num(row[pb_i]) if pb_i is not None and pb_i < len(row) else None
            }
        return out
    except Exception as e:
        print("BWIBBU_d unavailable:", e)
        return {}

def twse_revenue():
    try:
        rows = get_json("https://openapi.twse.com.tw/v1/opendata/t187ap05_L")
        out = {}
        for r in rows:
            c = str(r.get("公司代號") or r.get("Code") or "").strip()
            if not c:
                continue
            yoy = None
            for k, v in r.items():
                ks = str(k)
                if "去年同月增減" in ks or "年增率" in ks or "YoY" in ks:
                    yoy = num(v)
                    if yoy is not None:
                        break
            cur = None
            for k, v in r.items():
                if "當月營收" in str(k) or str(k).lower() == "revenue":
                    cur = num(v)
                    if cur is not None:
                        break
            out[c] = {"revenue_yoy": yoy, "revenue": cur}
        return out
    except Exception as e:
        print("Revenue unavailable:", e)
        return {}

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, round(v)))

def main_force_score(x):
    vr = x.get("volume_ratio") or 1
    inst = x.get("inst_net")
    vol = x.get("volume") or 1
    inst_ratio = (inst / vol) if inst is not None else 0
    price = x.get("change") or 0
    s = 50 + min(25, max(-25, inst_ratio * 1000)) + min(15, max(-15, (vr - 1) * 12)) + min(10, max(-10, price * 1.5))
    return clamp(s)

def ai_probability(x):
    s = 0.0
    s += (x.get("score", 50) - 50) * 0.75
    s += (x.get("main_force_score", 50) - 50) * 0.35
    s += (x.get("inst_net") or 0) / max(x.get("volume") or 1, 1) * 120
    s += max(0, (x.get("revenue_yoy") or 0)) * 0.12
    s -= max(0, (x.get("overheat_score") or 0) - 70) * 0.55
    return round(1 / (1 + math.exp(-s / 18)) * 100, 1)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    oldmap = {x["code"]: x for x in old.get("stocks", []) if x.get("code")}
    quotes = twse_quotes() + tpex_quotes()
    if not quotes:
        raise RuntimeError("No market data returned")

    inst, margin, lending, valuation, revenue = twse_t86(), twse_margin(), twse_lending(), twse_valuation(), twse_revenue()
    result = []

    for x in quotes:
        prev = oldmap.get(x["code"], {})
        closes = list(prev.get("history_close", []))[-119:]
        vols = list(prev.get("history_volume", []))[-119:]
        if not closes or closes[-1] != x["close"]:
            closes.append(x["close"])
        if not vols or vols[-1] != (x.get("volume") or 0):
            vols.append(x.get("volume") or 0)

        ma5, ma20 = sma(closes, 5), sma(closes, 20)
        rr = rsi(closes, 14)
        pv = sma(vols[:-1], 5) if len(vols) >= 6 else None
        vr = (vols[-1] / pv) if pv and pv > 0 else None
        i = inst.get(x["code"], {})
        m = margin.get(x["code"], {})
        l = lending.get(x["code"], {})
        v = valuation.get(x["code"], {})
        rev = revenue.get(x["code"], {})

        score = 45
        if ma5 and x["close"] > ma5: score += 10
        if ma20 and x["close"] > ma20: score += 10
        if rr is not None:
            if 55 <= rr <= 72: score += 10
            elif rr > 80: score -= 8
        if vr is not None:
            if vr >= 1.8: score += 15
            elif vr >= 1.5: score += 10
            elif vr >= 1.2: score += 5
        if x.get("change") is not None and x["change"] >= 5: score += 5

        breakout = bool(ma20 and x["close"] > ma20 and x.get("high") and x["close"] >= x["high"] * 0.98)
        overheat = 0
        if rr is not None: overheat += max(0, rr - 65) * 1.35
        if vr is not None: overheat += max(0, vr - 1.5) * 14
        if x.get("change") is not None: overheat += max(0, x["change"] - 3) * 2.2
        if ma20 and ma20 > 0: overheat += max(0, (x["close"] / ma20 - 1) * 100) * 0.9
        overheat = clamp(overheat)

        row = {
            **x, "score": clamp(score), "ma5": ma5, "ma20": ma20, "rsi": rr,
            "volume_ratio": vr, "breakout": breakout,
            "risk": "high" if overheat >= 75 else ("low" if score >= 75 and overheat < 50 else "medium"),
            "strategy": "突破回測" if breakout and overheat < 70 else ("避免追高" if overheat >= 75 else ("量增觀察" if score >= 70 else "觀察")),
            "history_close": closes[-120:], "history_volume": vols[-120:],
            "inst_net": i.get("inst_net"), "foreign_net": i.get("foreign_net"),
            "trust_net": i.get("trust_net"), "dealer_net": i.get("dealer_net"),
            "margin_balance": m.get("margin_balance"), "short_balance": m.get("short_balance"),
            "margin_buy": m.get("margin_buy"), "short_sell": m.get("short_sell"),
            "lending_balance": l.get("lending_balance"), "lending_sell": l.get("lending_sell"),
            "dividend_yield": v.get("dividend_yield"), "pe": v.get("pe"), "pb": v.get("pb"),
            "revenue_yoy": rev.get("revenue_yoy"), "revenue": rev.get("revenue")
        }
        row["main_force_score"] = main_force_score(row)
        row["ai_probability_5d"] = ai_probability(row)
        row["ai_signal"] = "偏多" if row["ai_probability_5d"] >= 68 else ("中性" if row["ai_probability_5d"] >= 50 else "偏空")
        row["savings_score"] = clamp(
            35 + (row["dividend_yield"] or 0) * 5 +
            max(-10, min(20, (row["revenue_yoy"] or 0) * 0.4)) +
            (10 if (row["pb"] is not None and row["pb"] <= 1.2) else 0)
        )
        result.append(row)

    result.sort(key=lambda z: (z["score"], z.get("ai_probability_5d") or 0, z.get("main_force_score") or 0), reverse=True)
    payload = {
        "version": "3.0",
        "date": today,
        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "data_notes": {
            "main_force": "主力籌碼為量價＋法人推估，不等同逐家券商分點。",
            "ai": "AI預測為本機多因子統計模型，非保證獲利，也不是大型語言模型。",
            "realtime": "GitHub Pages 的日資料為盤後資料；盤中即時報價需由瀏覽器直接連接 TWSE MIS 或正式即時行情服務。"
        },
        "stocks": result
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("Updated", len(result), "stocks")

if __name__ == "__main__":
    main()
