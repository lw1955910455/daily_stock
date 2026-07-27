# -*- coding: utf-8 -*-
"""
a-stock-data 工具包:A股公告抓取
主源:巨潮资讯(cninfo)
降级:东方财富 → 新浪财经
返回统一结构: {code, name, title, url, time(datetime, Asia/Shanghai)}
"""
import re
import datetime as dt
from zoneinfo import ZoneInfo

import requests

from config import HEADERS, REQUEST_TIMEOUT, mk_status

TZ = ZoneInfo("Asia/Shanghai")


def _now():
    return dt.datetime.now(TZ)


# ---------------- 主源:巨潮资讯 ----------------
def fetch_cninfo(hours: int) -> list:
    """巨潮资讯历史公告接口,沪深两市,近 hours 小时"""
    cutoff = _now() - dt.timedelta(hours=hours)
    date_range = "{}~{}".format(
        (cutoff - dt.timedelta(days=1)).strftime("%Y-%m-%d"),
        _now().strftime("%Y-%m-%d"),
    )
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    results = []
    for column in ("szse", "sse"):
        for page in range(1, 6):  # 每市场最多5页x30条
            data = {
                "pageNum": page, "pageSize": 30, "column": column,
                "tabName": "fulltext", "plate": "", "stock": "",
                "searchkey": "", "secid": "", "category": "", "trade": "",
                "seDate": date_range, "sortName": "", "sortType": "",
                "isHLtitle": "true",
            }
            resp = requests.post(
                url, data=data, timeout=REQUEST_TIMEOUT,
                headers={**HEADERS, "Referer": "http://www.cninfo.com.cn/"},
            )
            resp.raise_for_status()
            js = resp.json()
            anns = js.get("announcements") or []
            if not anns:
                break
            stop = False
            for a in anns:
                t = dt.datetime.fromtimestamp(a["announcementTime"] / 1000, TZ)
                if t < cutoff:
                    stop = True
                    continue
                title = re.sub(r"<[^>]+>", "", a.get("announcementTitle") or "")
                results.append({
                    "code": a.get("secCode") or "",
                    "name": (a.get("secName") or "").replace(" ", ""),
                    "title": title,
                    "url": "http://static.cninfo.com.cn/" + (a.get("adjunctUrl") or ""),
                    "time": t,
                })
            if stop or not js.get("hasMore"):
                break
    return results


# ---------------- 备源1:东方财富 ----------------
def fetch_eastmoney(hours: int) -> list:
    cutoff = _now() - dt.timedelta(hours=hours)
    results = []
    for page in range(1, 6):
        url = ("https://np-anotice-stock.eastmoney.com/api/security/ann"
               "?sr=-1&page_size=100&page_index={}&ann_type=A"
               "&client_source=web&f_node=0&s_node=0".format(page))
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        items = (resp.json().get("data") or {}).get("list") or []
        if not items:
            break
        stop = False
        for it in items:
            try:
                t = dt.datetime.strptime(
                    it["notice_date"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
            except Exception:
                continue
            if t < cutoff:
                stop = True
                continue
            codes = it.get("codes") or [{}]
            results.append({
                "code": codes[0].get("stock_code", ""),
                "name": codes[0].get("short_name", ""),
                "title": it.get("title") or "",
                "url": "https://data.eastmoney.com/notices/detail/{}/{}.html".format(
                    codes[0].get("stock_code", ""), it.get("art_code", "")),
                "time": t,
            })
        if stop:
            break
    return results


# ---------------- 备源2:新浪财经 ----------------
def fetch_sina(hours: int) -> list:
    """新浪公司公告列表页(HTML),尽力解析"""
    from bs4 import BeautifulSoup
    cutoff = _now() - dt.timedelta(hours=hours)
    url = ("https://vip.stock.finance.sina.com.cn/corp/view/vCB_BulletinGather.php")
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.encoding = "gbk"
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    today = _now().strftime("%Y-%m-%d")
    for tr in soup.select("table tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        a = tds[1].find("a") or tds[0].find("a")
        if not a:
            continue
        date_text = tds[-1].get_text(strip=True)
        m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", date_text)
        d = m.group(1) if m else today
        try:
            t = dt.datetime.strptime(d, "%Y-%m-%d").replace(
                hour=9, tzinfo=TZ)
        except Exception:
            t = _now()
        if t.date() < cutoff.date():
            continue
        name = tds[0].get_text(strip=True)
        results.append({
            "code": "",
            "name": name if len(name) <= 8 else "",
            "title": a.get_text(strip=True),
            "url": a.get("href") or "",
            "time": t,
        })
    return results


def fetch_announcements(hours: int) -> tuple:
    """
    统一入口:主源巨潮,失败自动降级东财→新浪。
    返回 (公告列表, 数据源状态字典列表)
    """
    sources = [("巨潮资讯(主源)", fetch_cninfo),
               ("东方财富(备源)", fetch_eastmoney),
               ("新浪财经(备源)", fetch_sina)]
    statuses = []
    for name, fn in sources:
        try:
            data = fn(hours)
            if data:
                statuses.append(mk_status("公告-{}".format(name), True, len(data)))
                return data, statuses
            statuses.append(mk_status("公告-{}".format(name), False, 0,
                                      "返回空,已尝试降级" if statuses else "返回空"))
        except Exception as e:
            statuses.append(mk_status("公告-{}".format(name), False, 0,
                                      str(e)[:80]))
    return [], statuses
