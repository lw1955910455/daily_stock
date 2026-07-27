# -*- coding: utf-8 -*-
"""
分析引擎:
1. 公告 → 命中关键词、识别业绩驱动
2. 政策 → 命中关键词、关联板块、提取提及个股 →【政策驱动】
3. 快讯/新闻 → 事件催化规则、关联板块、提取提及个股 →【事件驱动】
4. 国际动态 → 中英文关键词、关联板块
5. 共振标注:同一股票命中 政策/事件/业绩 中的
   任意两项 →【🔥共振标的(双轮驱动)】
   三项全中 →【🔥🔥🔥三重共振爆发标的】
"""
import re

import requests

from config import (ANNOUNCEMENT_KEYWORDS, PERFORMANCE_KEYWORDS,
                    POLICY_KEYWORD_SECTORS, POLICY_KEYWORDS,
                    EVENT_RULES, INTL_KEYWORD_SECTORS, INTL_EN_ALIAS,
                    HEADERS, REQUEST_TIMEOUT)

CODE_RE = re.compile(r"[（(](\d{6})(?:\.(?:SH|SZ|BJ))?[)）]")


# ---------------- 全市场股票名单(用于从新闻文本中识别个股) ----------------
def load_stock_map() -> dict:
    """东方财富全A列表 {name: code};失败返回空dict(不影响主流程)"""
    try:
        url = ("https://push2.eastmoney.com/api/qt/clist/get"
               "?pn=1&pz=8000&po=1&np=1&fltt=2&invt=2&fid=f12"
               "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
               "&fields=f12,f14")
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        rows = ((resp.json().get("data") or {}).get("diff")) or []
        m = {}
        for r in rows:
            name = (r.get("f14") or "").replace(" ", "")
            code = r.get("f12") or ""
            # 只用3字以上的名称做文本匹配,规避两字名误伤(如"中国""科技")
            if len(name) >= 3 and not name.startswith(("ST", "*ST", "N", "C")):
                m[name] = code
        return m
    except Exception:
        return {}


def extract_stocks(text: str, stock_map: dict) -> list:
    """从文本中提取 (name, code) 列表:6位代码 + 股票名匹配"""
    found = {}
    for m in CODE_RE.finditer(text):
        found[m.group(1)] = ("", m.group(1))
    if stock_map:
        for name, code in stock_map.items():
            if name in text:
                found[code] = (name, code)
    # 反查代码对应名称
    if stock_map:
        rev = {v: k for k, v in stock_map.items()}
        out = []
        for code, (name, c) in found.items():
            out.append((name or rev.get(c, ""), c))
        return out
    return list(found.values())


def _hit_keywords(text: str, keywords: list) -> list:
    return [k for k in keywords if k in text]


# ---------------- 各类分析 ----------------
def analyze_announcements(anns: list) -> list:
    """公告关键词过滤,返回命中列表,附 is_performance 标记"""
    hits = []
    for a in anns:
        kws = _hit_keywords(a["title"], ANNOUNCEMENT_KEYWORDS)
        if not kws:
            continue
        perf = _hit_keywords(a["title"], PERFORMANCE_KEYWORDS)
        hits.append({**a, "keywords": kws, "is_performance": bool(perf)})
    return hits


def analyze_policies(policies: list, stock_map: dict) -> list:
    hits = []
    for p in policies:
        kws = _hit_keywords(p["title"], POLICY_KEYWORDS)
        if not kws:
            continue
        sectors = sorted({s for k in kws for s in POLICY_KEYWORD_SECTORS[k]})
        stocks = extract_stocks(p["title"], stock_map)
        hits.append({**p, "keywords": kws, "sectors": sectors, "stocks": stocks})
    return hits


def analyze_events(news: list, stock_map: dict) -> list:
    """快讯/新闻按事件催化规则匹配"""
    hits = []
    for n in news:
        text = (n.get("title") or "") + " " + (n.get("content") or "")
        matched_rules, sectors, kws = [], set(), []
        for rule in EVENT_RULES:
            got = _hit_keywords(text, rule["keywords"])
            if got:
                matched_rules.append(rule["name"])
                sectors.update(rule["sectors"])
                kws.extend(got)
        if not matched_rules:
            continue
        stocks = extract_stocks(text, stock_map)
        hits.append({**n, "events": matched_rules, "keywords": kws,
                     "sectors": sorted(sectors), "stocks": stocks})
    return hits


def analyze_intl(news: list) -> list:
    """国际动态关键词(中英文)"""
    hits = []
    for n in news:
        text = (n.get("title") or "") + " " + (n.get("content") or "")
        low = " " + text.lower() + " "
        kws = set(_hit_keywords(text, list(INTL_KEYWORD_SECTORS.keys())))
        for en, zh in INTL_EN_ALIAS.items():
            if en in low:
                kws.add(zh)
        if not kws:
            continue
        sectors = sorted({s for k in kws for s in INTL_KEYWORD_SECTORS.get(k, [])})
        hits.append({**n, "keywords": sorted(kws), "sectors": sectors})
    return hits


def analyze_perf_news(news: list, stock_map: dict) -> list:
    """从新闻快讯中识别业绩信息(业绩预增/扭亏为盈等)"""
    hits = []
    for n in news:
        text = (n.get("title") or "") + " " + (n.get("content") or "")
        kws = _hit_keywords(text, PERFORMANCE_KEYWORDS)
        if not kws:
            continue
        stocks = extract_stocks(text, stock_map)
        # 提取具体业绩数字(增长率等)
        nums = re.findall(r"(?:增长|预增|增幅|同比[增减长]?[长加]?)\s*约?\s*(\d+(?:\.\d+)?%(?:[-~至]\d+(?:\.\d+)?%)?)", text)
        hits.append({**n, "keywords": kws, "stocks": stocks, "growth": nums[:3]})
    return hits


# ---------------- 共振标注(核心) ----------------
def build_resonance(policy_hits, event_hits, ann_hits, perf_news_hits) -> list:
    """
    汇总每只股票命中的驱动维度:
      policy   ← 政策文件/政策关键词快讯中被提及
      event    ← 事件催化快讯中被提及
      perf     ← 业绩类公告 或 业绩类新闻中被提及
    返回按驱动数降序的列表:
      [{name, code, drivers:{...}, level, evidence:[(维度,标题,url)]}]
    """
    book = {}  # key=code or name

    def _touch(name, code, driver, title, url):
        key = code or name
        if not key:
            return
        rec = book.setdefault(key, {"name": name, "code": code,
                                    "drivers": set(), "evidence": []})
        if name and not rec["name"]:
            rec["name"] = name
        rec["drivers"].add(driver)
        if len(rec["evidence"]) < 6:
            rec["evidence"].append((driver, title[:60], url))

    for p in policy_hits:
        for name, code in p.get("stocks", []):
            _touch(name, code, "政策驱动", p["title"], p["url"])
    for e in event_hits:
        for name, code in e.get("stocks", []):
            _touch(name, code, "事件驱动", e["title"], e["url"])
    for a in ann_hits:
        if a.get("is_performance"):
            _touch(a.get("name", ""), a.get("code", ""), "业绩驱动",
                   a["title"], a["url"])
    for pn in perf_news_hits:
        for name, code in pn.get("stocks", []):
            _touch(name, code, "业绩驱动", pn["title"], pn["url"])

    out = []
    for rec in book.values():
        n = len(rec["drivers"])
        if n < 2:
            continue
        rec["level"] = ("【🔥🔥🔥三重共振爆发标的】" if n >= 3
                        else "【🔥共振标的(双轮驱动)】")
        rec["drivers"] = sorted(rec["drivers"])
        out.append(rec)
    out.sort(key=lambda r: -len(r["drivers"]))
    return out


def build_sector_resonance(policy_hits, event_hits) -> list:
    """板块级共振:政策与事件同时利好的板块(个股共振的补充视角)"""
    ps = {s for p in policy_hits for s in p.get("sectors", [])}
    es = {s for e in event_hits for s in e.get("sectors", [])}
    return sorted(ps & es)
