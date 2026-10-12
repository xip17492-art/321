import json
import math
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
import subprocess

OUT = Path("data/data.json")
UA = "Mozilla/5.0 (GitHub Actions; Taiwan Stock Radar 321 v3.2)"

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

def returns(a, n):
    a = [x for x in a if x is not None]
    return pct(a[-n-1], a[-1]) if len(a) >= n + 1 else None

def stdev_pct(a, n=20):
    a = [x for x in a if x is not None]
    if len(a) < n + 1:
        return None
    rs = []
    for i in range(len(a)-n, len(a)):
        prev, cur = a[i-1], a[i]
        if prev not in (None, 0):
            rs.append(cur / prev - 1)
    if len(rs) < n:
        return None
    mean = sum(rs) / len(rs)
    return (sum((r - mean) ** 2 for r in rs) / len(rs)) ** 0.5 * math.sqrt(252) * 100

def median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m-1] + vals[m]) / 2

def percentile_rank(vals, value):
    vals = sorted(v for v in vals if v is not None)
    if value is None or not vals:
        return None
    if len(vals) == 1:
        return 100.0
    lo = sum(1 for v in vals if v < value)
    eq = sum(1 for v in vals if v == value)
    return round((lo + 0.5 * eq) / len(vals) * 100, 1)

def percentile_value(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    idx = max(0, min(len(vals)-1, int(round((len(vals)-1) * p))))
    return vals[idx]

def business_days_between(start, end):
    try:
        from datetime import date, timedelta
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        if b <= a:
            return 0
        return sum(1 for i in range((b-a).days) if (a + timedelta(days=i)).weekday() < 5)
    except Exception:
        return 0

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
    """Heuristic bullishness score (0-100), not a calibrated probability."""
    s = 0.0
    s += (x.get("score", 50) - 50) * 0.75
    s += (x.get("main_force_score", 50) - 50) * 0.35
    s += (x.get("inst_net") or 0) / max(x.get("volume") or 1, 1) * 120
    s += max(0, (x.get("revenue_yoy") or 0)) * 0.12
    s -= max(0, (x.get("overheat_score") or 0) - 70) * 0.55
    return round(1 / (1 + math.exp(-s / 18)) * 100, 1)

def twse_bulk_history(calendar_days=100):
    """Backfill recent daily OHLCV for all listed stocks from TWSE's date-aware historical endpoint.
    This is only used when the saved history is too short; later runs remain incremental.
    """
    from datetime import date, timedelta
    from time import sleep

    end = date.today()
    start = end - timedelta(days=calendar_days)
    collected = {}
    current = start
    while current <= end:
        if current.weekday() < 5:
            ds = current.strftime("%Y%m%d")
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ds}&type=ALLBUT0999&response=json"
            try:
                payload = get_json(url)
                fields = None
                rows = None
                # TWSE has returned both flat dataN/fieldsN pairs and nested tables:[{fields,data}] payloads.
                candidates = []
                def collect_tables(node):
                    if isinstance(node, dict):
                        candidate_fields = node.get("fields")
                        candidate_rows = node.get("data")
                        if isinstance(candidate_fields, list) and isinstance(candidate_rows, list):
                            candidates.append((candidate_fields, candidate_rows))
                        for child in node.values():
                            if isinstance(child, (dict, list)):
                                collect_tables(child)
                    elif isinstance(node, list):
                        for child in node:
                            if isinstance(child, (dict, list)):
                                collect_tables(child)
                collect_tables(payload)
                # Keep compatibility with the flat fieldsN/dataN response format.
                for key, value in payload.items():
                    if not str(key).startswith("data") or not (isinstance(value, list) and value and isinstance(value[0], list)):
                        continue
                    suffix = str(key)[4:]
                    candidate_fields = payload.get("fields" + suffix)
                    if isinstance(candidate_fields, list):
                        candidates.append((candidate_fields, value))
                for candidate_fields, candidate_rows in candidates:
                    fs = [str(x).replace(" ", "") for x in candidate_fields]
                    if any("證券代號" in x for x in fs) and any("收盤價" in x for x in fs) and candidate_rows:
                        fields, rows = candidate_fields, candidate_rows
                        break
                if fields and rows:
                    code_i = pick_index(fields, "證券代號")
                    close_i = pick_index(fields, "收盤價")
                    volume_i = pick_index(fields, "成交股數")
                    if code_i is not None and close_i is not None:
                        for row in rows:
                            if max(code_i, close_i) >= len(row):
                                continue
                            code = str(row[code_i]).strip()
                            close = num(row[close_i])
                            if not (code.isdigit() and len(code) == 4 and close is not None):
                                continue
                            volume = num(row[volume_i]) if volume_i is not None and volume_i < len(row) else 0
                            collected.setdefault(code, []).append((current.isoformat(), close, volume or 0))
            except Exception as e:
                print(f"TWSE history skipped {ds}: {e}")
            sleep(0.12)
        current += timedelta(days=1)
    for code, bars in collected.items():
        bars.sort(key=lambda z: z[0])
        collected[code] = bars[-90:]
    print(f"TWSE historical backfill: {len(collected)} symbols")
    return collected


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

    # Backfill when most saved records have not yet accumulated enough sessions for 20/60-day factors.
    history_lengths = [len(x.get("history_close", [])) for x in old.get("stocks", []) if x.get("history_close")]
    if len(history_lengths) < max(100, int(len(quotes) * 0.25)) or (history_lengths and median(history_lengths) < 90):
        bulk_history = twse_bulk_history(calendar_days=100)
    else:
        bulk_history = {}

    inst, margin, lending, valuation, revenue = twse_t86(), twse_margin(), twse_lending(), twse_valuation(), twse_revenue()
    result = []

    for x in quotes:
        prev = oldmap.get(x["code"], {})
        closes = list(prev.get("history_close", []))[-251:]
        vols = list(prev.get("history_volume", []))[-251:]
        # Historical bulk data is date-sorted and replaces shorter locally accumulated history.
        # Keep the most recent 90 sessions; 60D momentum and the 20D volatility/liquidity factors can then calculate.
        hist_bars = bulk_history.get(x["code"], [])
        if len(hist_bars) > len(closes):
            closes = [b[1] for b in hist_bars][-251:]
            vols = [b[2] for b in hist_bars][-251:]
        # TWSE Change 是價差金額，統一換算成漲跌幅，避免以金額誤判百分比門檻。
        raw_change = x.get("change")
        # 優先使用交易所當日價差推算前收，避免同日重跑時拿已更新的收盤價當前收。
        if raw_change is not None:
            prior_close = x["close"] - raw_change
        elif closes:
            prior_close = closes[-2] if len(closes) >= 2 and closes[-1] == x["close"] else closes[-1]
        else:
            prior_close = None
        if prior_close not in (None, 0):
            x["change"] = round((x["close"] / prior_close - 1) * 100, 2)
        else:
            x["change"] = None
        if not closes or closes[-1] != x["close"]:
            closes.append(x["close"])
        if not vols or vols[-1] != (x.get("volume") or 0):
            vols.append(x.get("volume") or 0)

        ma5, ma20 = sma(closes, 5), sma(closes, 20)
        rr = rsi(closes, 14)
        mom5 = returns(closes, 5)
        mom20 = returns(closes, 20)
        mom60 = returns(closes, 60)
        vol20 = stdev_pct(closes, 20)
        high_window = closes[-252:] if len(closes) >= 252 else closes[-120:]
        high_52w = max(high_window) if high_window else None
        high_52w_distance = pct(high_52w, x["close"]) if high_52w else None
        high_52w_lookback = min(len(high_window), 252)
        turnover20 = None
        if len(closes) >= 20 and len(vols) >= 20:
            pairs = [(c or 0) * (v or 0) for c, v in zip(closes[-20:], vols[-20:])]
            turnover20 = sum(pairs) / len(pairs)
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
        if x.get("change") is not None:
            if x["change"] >= 5: score += 8
            elif x["change"] >= 3: score += 5
        if i.get("inst_net") is not None and i.get("inst_net") > 0: score += 4

        prev20 = closes[-21:-1] if len(closes) >= 21 else []
        prev20_high = max(prev20) if prev20 else None
        breakout_base = bool(
            ma20 and (
                (prev20_high is not None and x["close"] >= prev20_high * 1.005) or
                (x["close"] > ma20 * 1.02 and vr is not None and vr >= 1.35)
            ) and (x.get("change") is None or x.get("change") >= -1.0)
        )
        # 從近60個交易日找局部高點，使用最近兩個較低高點外推下降壓力線。
        trend_closes = closes[-60:]
        pivot_highs = []
        for pi in range(2, len(trend_closes) - 2):
            ph = trend_closes[pi]
            if ph >= max(trend_closes[pi-2:pi]) and ph >= max(trend_closes[pi+1:pi+3]):
                pivot_highs.append((pi, ph))
        descending_line = None
        if len(pivot_highs) >= 2:
            p1, p2 = pivot_highs[-2], pivot_highs[-1]
            if p2[1] < p1[1] and p2[0] > p1[0]:
                slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
                descending_line = p2[1] + slope * (len(trend_closes) - 1 - p2[0])
        trendline_breakout = bool(
            descending_line is not None and ma20 is not None and
            x["close"] > descending_line * 1.005 and x["close"] > ma20
        )
        above_month_line = bool(ma20 is not None and x["close"] > ma20)
        breakout = bool(breakout_base or trendline_breakout)
        overheat = 0
        if rr is not None: overheat += max(0, rr - 65) * 1.35
        if vr is not None: overheat += max(0, vr - 1.5) * 14
        if x.get("change") is not None: overheat += max(0, x["change"] - 3) * 2.2
        if ma20 and ma20 > 0: overheat += max(0, (x["close"] / ma20 - 1) * 100) * 0.9
        overheat = clamp(overheat)

        row = {
            **x, "score": clamp(score), "overheat_score": overheat, "ma5": ma5, "ma20": ma20, "rsi": rr,
            "volume_ratio": vr, "breakout": breakout,
            "breakout_base": breakout_base, "trendline_breakout": trendline_breakout,
            "descending_trendline_price": round(descending_line, 3) if descending_line is not None else None,
            "above_month_line": above_month_line,
            "technical_setup": "下降趨勢線突破＋站上月線" if trendline_breakout else ("站上月線" if above_month_line else "月線下方"),
            "risk": "high" if overheat >= 75 else ("low" if score >= 75 and overheat < 50 else "medium"),
            "strategy": "突破回測" if breakout and overheat < 70 else ("避免追高" if overheat >= 75 else ("量增觀察" if score >= 70 else "觀察")),
            "history_close": closes[-252:], "history_volume": vols[-252:],
            "momentum_5d": mom5, "momentum_20d": mom20, "momentum_60d": mom60,
            "volatility_20d": vol20, "high_52w": high_52w,
            "high_52w_distance": high_52w_distance,
            "high_52w_lookback": high_52w_lookback,
            "avg_turnover_20d": turnover20,
            "history_date": (list(prev.get("history_date", [])) + [today])[-120:],
            "inst_net": i.get("inst_net"), "foreign_net": i.get("foreign_net"),
            "trust_net": i.get("trust_net"), "dealer_net": i.get("dealer_net"),
            "margin_balance": m.get("margin_balance"), "short_balance": m.get("short_balance"),
            "margin_buy": m.get("margin_buy"), "short_sell": m.get("short_sell"),
            "lending_balance": l.get("lending_balance"), "lending_sell": l.get("lending_sell"),
            "dividend_yield": v.get("dividend_yield"), "pe": v.get("pe"), "pb": v.get("pb"),
            "revenue_yoy": rev.get("revenue_yoy"), "revenue": rev.get("revenue")
        }
        # If a public endpoint is temporarily empty (weekend/holiday/API outage), retain the
        # last known value instead of replacing it with null. Expose carried fields for transparency.
        carried = []
        for field in ("inst_net", "foreign_net", "trust_net", "dealer_net", "margin_balance", "short_balance", "margin_buy", "short_sell", "lending_balance", "lending_sell", "dividend_yield", "pe", "pb", "revenue_yoy", "revenue"):
            if row.get(field) is None and prev.get(field) is not None:
                row[field] = prev[field]
                carried.append(field)
        row["carried_forward_fields"] = carried
        row["data_quality_note"] = "部分籌碼/基本面欄位沿用前次有效值" if carried else "欄位依本次資料源回傳；仍請確認來源日期"
        row["main_force_score"] = main_force_score(row)
        row["ai_probability_5d"] = ai_probability(row)
        row["ai_estimate_type"] = "heuristic_bullishness_score_not_calibrated_probability"
        row["ai_signal"] = "偏多" if row["ai_probability_5d"] >= 68 else ("中性" if row["ai_probability_5d"] >= 50 else "偏空")
        row["savings_score"] = clamp(
            35 + (row["dividend_yield"] or 0) * 5 +
            max(-10, min(20, (row["revenue_yoy"] or 0) * 0.4)) +
            (10 if (row["pb"] is not None and row["pb"] <= 1.2) else 0)
        )
        result.append(row)

    # 3.2 公開研究因子層：動能、52週高點距離、20日波動、流動性與市場相對強弱。
    # 市場基準採全市場截面中位數，避免額外依賴單一指數 API；不使用未來資料。
    market_mom20 = median([x.get("momentum_20d") for x in result])
    market_mom60 = median([x.get("momentum_60d") for x in result])
    liq_values = [x.get("avg_turnover_20d") for x in result]
    liquidity_floor = percentile_value(liq_values, 0.20)
    for x in result:
        x["market_momentum_20d"] = market_mom20
        x["market_momentum_60d"] = market_mom60
        x["relative_strength_20d"] = (x.get("momentum_20d") - market_mom20) if x.get("momentum_20d") is not None and market_mom20 is not None else None
        x["relative_strength_60d"] = (x.get("momentum_60d") - market_mom60) if x.get("momentum_60d") is not None and market_mom60 is not None else None
        x["liquidity_floor_20d"] = liquidity_floor
        # Require at least NT$30 million average daily turnover over 20 sessions by default.
        # This keeps thinly traded stocks out of the actionable radar ranking.
        x["liquidity_min_turnover"] = 30000000
        x["liquidity_ok"] = bool(x.get("avg_turnover_20d") is not None and x["avg_turnover_20d"] >= 30000000)
        x["market_regime"] = "偏多" if market_mom20 is not None and market_mom20 >= 2 else ("偏空" if market_mom20 is not None and market_mom20 <= -2 else "中性")

    # 產業鏈標籤：只對常見台股代號/名稱做保守分類，未知者不猜測。
    sector_codes = {
        "半導體": {"2330","2454","3711","3443","5274","3529","3661","6510","6533","晶圓","封測","IC設計"},
        "AI伺服器／ODM": {"2317","2382","3231","6669","緯創","廣達","英業達","鴻海","技嘉","華碩"},
        "PCB／載板": {"3037","8046","3189","2368","4958","欣興","南電","景碩","臻鼎","華通"},
        "散熱": {"3017","3324","3653","2421","雙鴻","奇鋐","健策","建準"},
        "電源／重電": {"2308","2301","1519","1503","1513","台達電","光寶科","華城","士電"},
        "光通訊": {"3081","4979","6442","3163","3363","波若威","新復興","光聖"},
        "記憶體": {"2408","2344","8299","2337","4967","南亞科","華邦電","群聯","十銓"},
        "機器人／自動化": {"2049","1590","2395","6166","直得","上銀","所羅門"},
        "金融": {"2881","2882","2884","2886","2891","2892","2883","2885"},
        "航運": {"2603","2609","2615","2618","2637","2606"},
        "生技醫療": {"6547","4743","6472","4162","6446","藥華藥","晶碩"},
        "汽車／電動車": {"2207","2231","1513","1536","裕日車","和大","貿聯"},
        "塑化／原物料": {"1301","1303","1326","6505","台塑","南亞","台化","台塑化"}
    }
    def classify_sector(stock):
        code, name = str(stock.get("code", "")), str(stock.get("name", ""))
        for sector, keys in sector_codes.items():
            if code in keys or any(k in name for k in keys if not k.isdigit()):
                return sector
        return "其他／未分類"
    for stock in result:
        stock["industry_chain"] = classify_sector(stock)
    sector_stats = {}
    for stock in result:
        sector = stock["industry_chain"]
        s = sector_stats.setdefault(sector, {"industry_chain": sector, "count": 0, "change_sum": 0.0, "change_n": 0, "up": 0, "down": 0, "flat": 0})
        s["count"] += 1
        ch = stock.get("change")
        if ch is not None:
            s["change_sum"] += ch
            s["change_n"] += 1
            if ch > 0: s["up"] += 1
            elif ch < 0: s["down"] += 1
            else: s["flat"] += 1
    industry_chains = []
    for s in sector_stats.values():
        s["avg_change_pct"] = round(s["change_sum"] / s["change_n"], 2) if s["change_n"] else None
        del s["change_sum"], s["change_n"]
        industry_chains.append(s)
    industry_chains.sort(key=lambda s: (s["avg_change_pct"] is not None, s["avg_change_pct"] or -999), reverse=True)

    m5 = [x.get("momentum_5d") for x in result]
    m20 = [x.get("momentum_20d") for x in result]
    m60 = [x.get("momentum_60d") for x in result]
    h52 = [x.get("high_52w_distance") for x in result]
    rel20 = [x.get("relative_strength_20d") for x in result]
    vol20s = [x.get("volatility_20d") for x in result]
    liq20 = [x.get("avg_turnover_20d") for x in result]
    for x in result:
        vol_rank = 100 - percentile_rank(vol20s, x.get("volatility_20d")) if x.get("volatility_20d") is not None else None
        parts = [
            (percentile_rank(m5, x.get("momentum_5d")), 0.12),
            (percentile_rank(m20, x.get("momentum_20d")), 0.23),
            (percentile_rank(m60, x.get("momentum_60d")), 0.18),
            (percentile_rank(h52, x.get("high_52w_distance")), 0.16),
            (percentile_rank(rel20, x.get("relative_strength_20d")), 0.16),
            (vol_rank, 0.10),
            (percentile_rank(liq20, x.get("avg_turnover_20d")), 0.05)
        ]
        usable = [(r,w) for r,w in parts if r is not None]
        x["factor_coverage"] = round(sum(w for _,w in usable), 2)
        x["research_factor_score"] = round(sum(r*w for r,w in usable) / max(sum(w for _,w in usable), 0.01), 1)
        base_score = x.get("score") or 0
        x["score_pre_factor"] = base_score
        x["score"] = clamp(base_score * 0.72 + x["research_factor_score"] * 0.28)
        x["factor_liquidity_pass"] = bool(x.get("liquidity_ok"))
        x["factor_signal"] = "動能＋相對強勢" if (x.get("momentum_20d") or 0) > 0 and (x.get("relative_strength_20d") or 0) > 0 else ("趨勢觀察" if (x.get("momentum_60d") or 0) > 0 else "弱勢")
        x["radar_eligible"] = bool(x.get("liquidity_ok")) and x.get("factor_coverage", 0) >= 0.70
    # 3.1-F 自適應權重：用已結算推薦的條件成功率微調下一輪排序；樣本少於 10 不調整，避免過度擬合。
    rec_path = Path("data/recommendation_history.json")
    try: recdb_pre = json.loads(rec_path.read_text(encoding="utf-8"))
    except Exception: recdb_pre = {"days":[]}
    # Deduplicate before both adaptive weighting and validation so old repeated runs do not bias either.
    unique_pre = {}
    for day_pre in recdb_pre.get("days", []):
        if day_pre.get("date"):
            unique_pre[day_pre["date"]] = day_pre
    recdb_pre["days"] = [unique_pre[k] for k in sorted(unique_pre)][-120:]
    settled_pre=[p for d0 in recdb_pre.get("days",[]) for p in d0.get("top10",[]) if p.get("status") in ("win","loss")]
    factors={k:[0,0] for k in ("ai","breakout","chips","inst","low_heat")}
    for p in settled_pre:
        win=1 if p.get("status")=="win" else 0
        for k,yes in (("ai",(p.get("ai_probability_5d") or 0)>=68),("breakout",bool(p.get("breakout"))),("chips",(p.get("main_force_score") or 0)>=70),("inst",bool(p.get("inst_net")) and p.get("inst_net")>0),("low_heat",True)):
            if yes:factors[k][0]+=win;factors[k][1]+=1
    adaptive=[]
    for x in result:
        bonus=0
        for k,yes in (("ai",(x.get("ai_probability_5d") or 0)>=68),("breakout",bool(x.get("breakout"))),("chips",(x.get("main_force_score") or 0)>=70),("inst",bool(x.get("inst_net")) and x.get("inst_net")>0),("low_heat",(x.get("overheat_score") or 100)<70)):
            w,n0=factors[k]
            if n0>=10: bonus += max(-5,min(5,(w/n0-0.5)*10)) if yes else 0
        eligibility_bonus = 4 if x.get("radar_eligible") else -8
        x["adaptive_bonus"]=round(bonus,2)
        x["adaptive_score"]=round((x.get("score") or 0)+bonus+eligibility_bonus,2)
        x["radar_eligibility_bonus"] = eligibility_bonus
        adaptive.append(x)
    result.sort(key=lambda z: (z.get("radar_eligible", False), z.get("adaptive_score",z["score"]), z.get("ai_probability_5d") or 0, z.get("main_force_score") or 0), reverse=True)

    # 3.1-F：每日 Top 10 與歷史績效回饋。以「推薦後 +2%」作為成功事件，避免把單日大漲誤當成模型勝率。
    rec_path = Path("data/recommendation_history.json")
    try: recdb = json.loads(rec_path.read_text(encoding="utf-8"))
    except Exception: recdb = {"days": [], "model": {}}
    # Repair historical duplicate dates created by repeated manual/scheduled runs.
    # Keep the latest snapshot for each date; settlement below will recalculate open picks.
    dedup_days = {}
    for old_day in recdb.get("days", []):
        dkey = old_day.get("date")
        if dkey:
            dedup_days[dkey] = old_day
    recdb["days"] = [dedup_days[k] for k in sorted(dedup_days)][-120:]
    current = {x["code"]: x for x in result}
    for day in recdb.get("days", []):
        for pick in day.get("top10", []):
            if pick.get("status") == "open" and pick.get("code") in current:
                now = current[pick["code"]].get("close"); entry = pick.get("entry")
                if now is not None and entry not in (None, 0):
                    ret = (now / entry - 1) * 100
                    age = business_days_between(day.get("date", today), today)
                    pick["last_return"] = round(ret,2)
                    pick["t_plus_3_business_days"] = age
                    if age >= 3:
                        pick["status"] = "win" if ret >= 2 else "loss"
                        pick["settled_return"] = round(ret,2)
    today_top = []
    for rank,x in enumerate(result[:10],1):
        today_top.append({
            "rank":rank,"code":x["code"],"name":x.get("name"),"entry":x.get("close"),
            "score":x.get("score"),"ai_probability_5d":x.get("ai_probability_5d"),
            "main_force_score":x.get("main_force_score"),"breakout":x.get("breakout"),
            "momentum_5d":x.get("momentum_5d"),"momentum_20d":x.get("momentum_20d"),
            "momentum_60d":x.get("momentum_60d"),"volatility_20d":x.get("volatility_20d"),
            "high_52w_distance":x.get("high_52w_distance"),
            "relative_strength_20d":x.get("relative_strength_20d"),
            "avg_turnover_20d":x.get("avg_turnover_20d"),
            "liquidity_ok":x.get("liquidity_ok"),"research_factor_score":x.get("research_factor_score"),
            "market_regime":x.get("market_regime"),"reason":x.get("strategy"),"status":"open"
        })
    # One record per calendar date: rerunning the workflow replaces today's snapshot,
    # rather than inflating the recommendation sample size and win-rate statistics.
    recdb["days"] = [d for d in recdb.get("days", []) if d.get("date") != today]
    recdb.setdefault("days", []).append({"index": 0, "date": today, "top10": today_top})
    recdb["days"] = recdb["days"][-120:]
    for idx, day in enumerate(recdb["days"], 1):
        day["index"] = idx
    settled=[p for d0 in recdb["days"] for p in d0.get("top10",[]) if p.get("status") in ("win","loss")]
    wins=sum(p.get("status")=="win" for p in settled); total=len(settled)
    factor_defs = {
        "momentum_20d": lambda p: (p.get("momentum_20d") or 0) > 0,
        "momentum_60d": lambda p: (p.get("momentum_60d") or 0) > 0,
        "relative_strength_20d": lambda p: (p.get("relative_strength_20d") or 0) > 0,
        "near_52w_high": lambda p: p.get("high_52w_distance") is not None and p.get("high_52w_distance") >= -10,
        "low_volatility_20d": lambda p: p.get("volatility_20d") is not None and p.get("volatility_20d") <= 45,
        "liquidity_filter": lambda p: bool(p.get("liquidity_ok")),
        "research_factor_score_60+": lambda p: (p.get("research_factor_score") or 0) >= 60
    }
    factor_validation={}
    for name, cond in factor_defs.items():
        hits=[p for p in settled if cond(p)]
        hw=sum(p.get("status")=="win" for p in hits)
        factor_validation[name]={"samples":len(hits),"wins":hw,"win_rate":round(hw/len(hits)*100,1) if hits else None,"avg_return":round(sum(p.get("settled_return",0) for p in hits)/len(hits),2) if hits else None}
    recdb["factor_validation"]=factor_validation
    recdb["model"]={"measured":total,"wins":wins,"win_rate":round(wins/total*100,1) if total else None,"target":60,"target_reached":bool(total>=20 and wins/total>=0.6) if total else False,"definition":"T+3 期間內相對推薦價達 +2% 視為成功；至少 20 個已結算樣本才判定是否達 60%。"}
    rec_path.parent.mkdir(parents=True,exist_ok=True); rec_path.write_text(json.dumps(recdb,ensure_ascii=False),encoding="utf-8")
    payload = {
        "version": "3.3",
        "industry_chains": industry_chains,
        "date": today,
        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "data_notes": {
            "main_force": "主力籌碼為量價＋法人推估，不等同逐家券商分點。",
            "ai": "AI欄位目前是手工設計多因子公式轉換的偏多分數（0-100），不是經歷史回測校準的真實上漲機率；不保證獲利。",
            "realtime": "GitHub Pages 的日資料為盤後資料；盤中即時報價需由瀏覽器直接連接 TWSE MIS 或正式即時行情服務。",
            "recommendation_engine": "每日只保留一份推薦快照；重跑同日會更新當日紀錄而不增加樣本數。Top 10 以 T+3 期間內是否達 +2% 追蹤；因子驗證只使用已結算樣本。",
            "factor_engine": "3.3 新增產業鏈漲幅、下降趨勢線突破＋站上月線判定，並修正每日漲跌幅換算；保留 5/20/60 日動能、52週高點距離（資料不足時以近120日代理）、20日年化波動度、20日平均成交金額流動性過濾、全市場截面中位數相對強弱。流動性過濾影響推薦池，不刪除總表。"
        },
        "stocks": result
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("Updated", len(result), "stocks")
    try:
        subprocess.run(["python", "scripts/analyst_tracker.py"], check=False)
    except Exception as e:
        print("Analyst tracker unavailable:", e)

if __name__ == "__main__":
    main()
