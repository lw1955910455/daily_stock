# -*- coding: utf-8 -*-
"""
政策监控:
1. 国务院最新政策  → gov.cn 官方 JSON(ZUIXINZHENGCE.json)
2. 国家政策文件库  → sousuo.www.gov.cn 检索接口
   - 国务院文件(zhengcelibrary_gw)
   - 部门文件(zhengcelibrary_bm):覆盖发改委、工信部、财政部等全部部委
3. 发改委通知公告  → ndrc.gov.cn 列表页 HTML(直抓)
4. 工信部文件发布  → 页面为JS渲染无法直抓,由"部门文件库"覆盖
逐源容错,任何一个失败不影响其他源。
返回统一结构: {source, title, url, date(str)}
"""
import re
import json
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import HEADERS, REQUEST_TIMEOUT, mk_status

DATE_RE = re.compile(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})")

# 仍用HTML直抓的列表页(结构简单、可稳定解析)
HTML_SOURCES = [
    ("发改委-通知公告", "https://www.ndrc.gov.cn/xxgk/zcfb/tz/index.html",
     "https://www.ndrc.gov.cn/xxgk/zcfb/tz/"),
    ("发改委-发改委令", "https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/index.html",
     "https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/"),
]


def _fetch_gov_zuixin() -> list:
    """国务院'最新政策'官方JSON"""
    url = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    rows = json.loads(resp.text.strip())
    return [{"source": "国务院-最新政策",
             "title": r.get("TITLE", ""),
             "url": r.get("URL", ""),
             "date": r.get("DOCRELPUBTIME", "")}
            for r in rows if r.get("TITLE")][:30]


def _fetch_policy_library(lib_type: str, source: str) -> list:
    """国家政策文件库检索接口 lib_type: zhengcelibrary_gw(国务院) / zhengcelibrary_bm(部委)"""
    url = ("https://sousuo.www.gov.cn/search-gov/data?t={}&q=&timetype=timeqb"
           "&mintime=&maxtime=&sort=pubtime&sortType=1&searchfield=title"
           "&pcodeJiguan=&childtype=&subchildtype=&tsbq=&pubtimeyear=&puborg="
           "&pcodeYear=&pcodeNum=&filetype=&p=1&n=30&inpro=&bmfl=&dup=&orpro="
           ).format(lib_type)
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    rows = ((resp.json().get("searchVO") or {}).get("listVO")) or []
    out = []
    for r in rows:
        title = re.sub(r"<[^>]+>", "", r.get("title") or "")
        org = r.get("puborg") or ""
        out.append({"source": "{}[{}]".format(source, org) if org else source,
                    "title": title,
                    "url": r.get("url") or "",
                    "date": (r.get("pubtimeStr") or "").replace(".", "-")})
    return out


def _parse_list_page(html: str, base: str, source: str) -> list:
    """通用HTML列表页解析"""
    soup = BeautifulSoup(html, "lxml")
    items, seen = [], set()
    for li in soup.find_all(["li", "tr", "dd"]):
        a = li.find("a", href=True)
        if a is None:
            continue
        title = a.get_text(strip=True)
        href = a["href"].strip()
        if len(title) < 10 or href.startswith(("javascript", "#")):
            continue
        m = DATE_RE.search(li.get_text(" ", strip=True))
        date = "{}-{:02d}-{:02d}".format(
            int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else ""
        key = title[:40]
        if key in seen:
            continue
        seen.add(key)
        items.append({"source": source, "title": title,
                      "url": urljoin(base, href), "date": date})
    return items[:30]


def fetch_policies() -> tuple:
    """抓取全部政策源。返回 (条目列表, 状态说明列表)"""
    all_items, status = [], []

    tasks = [
        ("国务院-最新政策", _fetch_gov_zuixin),
        ("政策库-国务院文件", lambda: _fetch_policy_library("zhengcelibrary_gw", "政策库-国务院")),
        ("政策库-部门文件(含发改委/工信部/财政部)",
         lambda: _fetch_policy_library("zhengcelibrary_bm", "政策库-部委")),
    ]
    for name, fn in tasks:
        try:
            items = fn()
            all_items.extend(items)
            status.append(mk_status(name, True, len(items)))
        except Exception as e:
            status.append(mk_status(name, False, 0, str(e)[:60]))

    for source, url, base in HTML_SOURCES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding
            items = _parse_list_page(resp.text, base, source)
            all_items.extend(items)
            status.append(mk_status(source, True, len(items)))
        except Exception as e:
            status.append(mk_status(source, False, 0, str(e)[:60]))

    # 按标题去重(不同源可能收录同一文件)
    seen, dedup = set(), []
    for it in all_items:
        key = it["title"][:40]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(it)
    return dedup, status
