# -*- coding: utf-8 -*-
"""
应急搜索模块:
当连续多次"全源失败"后,主程序会进入应急搜索模式,
改用百度搜索关键词组合抓取新闻,作为数据源降级兜底。
返回结构与新闻条目一致 {source, title, content, url, time},
可直接喂给 analyzer 的 analyze_policies / analyze_events / analyze_perf_news。

注意:百度对自动化抓取有反爬,本模块为"尽力而为"——
能抓到就用,抓不到也不会让主流程崩溃(仅状态标记为失败)。
"""
import datetime as dt
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from config import (HEADERS, REQUEST_TIMEOUT, mk_status, POLICY_KEYWORDS,
                    EVENT_RULES, EMERGENCY_MAX_QUERIES, BAIDU_SEARCH_URL,
                    BAIDU_MOBILE_URL)

TZ = ZoneInfo("Asia/Shanghai")


def build_queries() -> list:
    """构造应急搜索关键词组合(政策×事件×业绩),限量避免超时。"""
    q = []
    for kw in POLICY_KEYWORDS[:12]:
        q.append("{} 最新政策 A股".format(kw))
    for rule in EVENT_RULES:
        q.append("{} 影响 A股 板块".format(rule["name"]))
    q += ["业绩预增 公告 A股", "扭亏为盈 公告", "重大资产重组 停牌"]
    # 去重并保持顺序
    seen, out = set(), []
    for x in q:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:EMERGENCY_MAX_QUERIES]


def _parse_results(resp_text: str) -> list:
    """从百度搜索结果页解析标题/链接(桌面版与移动版兼容)。"""
    soup = BeautifulSoup(resp_text, "lxml")
    items = []
    # 桌面版: <h3 class="t"> 内 <a> 标题
    for h3 in soup.select("h3.t"):
        a = h3.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title and href.startswith("http"):
            items.append({"title": title, "url": href})
    # 移动版兜底: <div class="result"> / <a class="title">
    if not items:
        for a in soup.select("a.title"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if title and href.startswith("http"):
                items.append({"title": title, "url": href})
    return items


def fetch_emergency(hours: int) -> tuple:
    """百度应急搜索。返回 (新闻条目列表, 状态字典列表)。"""
    queries = build_queries()
    items, statuses = [], []
    ok_url = 0
    for q in queries:
        try:
            resp = requests.get(BAIDU_SEARCH_URL.format(q=requests.utils.quote(q)),
                                 headers={**HEADERS,
                                          "Cookie": "BAIDUID=1:1; PSTM=1"},
                                 timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"
            found = _parse_results(resp.text)
            if not found:
                # 桌面版被反爬,试移动版
                resp = requests.get(BAIDU_MOBILE_URL.format(q=requests.utils.quote(q)),
                                     headers=HEADERS, timeout=REQUEST_TIMEOUT)
                resp.encoding = "utf-8"
                found = _parse_results(resp.text)
            for f in found:
                items.append({
                    "source": "应急搜索-百度",
                    "title": f["title"],
                    "content": "",
                    "url": f["url"],
                    "time": dt.datetime.now(TZ),
                })
                ok_url += 1
            statuses.append(mk_status("应急搜索-百度:{}".format(q[:12]), bool(found),
                                  len(found)))
        except Exception as e:
            statuses.append(mk_status("应急搜索-百度:{}".format(q[:12]),
                                  False, 0, str(e)[:60]))
    return items, statuses
