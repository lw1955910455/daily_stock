# -*- coding: utf-8 -*-
"""
新闻监控:
1. 国内快讯:财联社电报(主源) → 东方财富7x24(备源)
2. 海外新闻:BBC / Fox / 路透社(GoogleNews聚合) RSS
返回统一结构: {source, title, content, url, time(datetime|None)}
"""
import datetime as dt
import time as _time
from zoneinfo import ZoneInfo

import requests
import feedparser

from config import RSS_FEEDS, HEADERS, REQUEST_TIMEOUT, mk_status

TZ = ZoneInfo("Asia/Shanghai")


def _now():
    return dt.datetime.now(TZ)


# ---------------- 国内快讯 ----------------
def fetch_cls(hours: int) -> list:
    """财联社电报滚动快讯(接口需签名: sign = md5(sha1(排序后的query)))"""
    import hashlib
    from urllib.parse import urlencode
    cutoff = _now() - dt.timedelta(hours=hours)
    params = {"app": "CailianpressWeb", "category": "", "lastTime": "",
              "last_time": "", "os": "web", "refresh_type": "1",
              "rn": "50", "sv": "8.4.6"}
    qs = urlencode(sorted(params.items()))
    sign = hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()
    url = "https://www.cls.cn/v1/roll/get_roll_list?{}&sign={}".format(qs, sign)
    resp = requests.get(url, headers={**HEADERS, "Referer": "https://www.cls.cn/telegraph"},
                        timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    rows = ((resp.json().get("data") or {}).get("roll_data")) or []
    items = []
    for r in rows:
        t = dt.datetime.fromtimestamp(r.get("ctime", 0), TZ)
        if t < cutoff:
            continue
        items.append({
            "source": "财联社",
            "title": r.get("title") or (r.get("content") or "")[:50],
            "content": r.get("content") or "",
            "url": "https://www.cls.cn/detail/{}".format(r.get("id", "")),
            "time": t,
        })
    return items


def fetch_em_724(hours: int) -> list:
    """东方财富 7x24 快讯(财联社失败时的备源)"""
    cutoff = _now() - dt.timedelta(hours=hours)
    url = ("https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
           "?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=50&req_trace=1")
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    rows = ((resp.json().get("data") or {}).get("fastNewsList")) or []
    items = []
    for r in rows:
        try:
            t = dt.datetime.strptime(r["showTime"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
        except Exception:
            t = _now()
        if t < cutoff:
            continue
        items.append({
            "source": "东财7x24",
            "title": r.get("title") or (r.get("summary") or "")[:50],
            "content": r.get("summary") or "",
            "url": "https://kuaixun.eastmoney.com/",
            "time": t,
        })
    return items


def fetch_domestic_news(hours: int) -> tuple:
    """国内快讯统一入口(财联社→东财降级)。返回 (列表, 状态字典列表)"""
    try:
        data = fetch_cls(hours)
        if data:
            return data, [mk_status("快讯-财联社", True, len(data))]
        err = "财联社返回空"
    except Exception as e:
        err = "财联社失败: {}".format(str(e)[:60])
    try:
        data = fetch_em_724(hours)
        return data, [mk_status("快讯-财联社", False, 0, err),
                      mk_status("快讯-东财7x24(备源)", True, len(data))]
    except Exception as e2:
        return [], [mk_status("快讯-财联社", False, 0, err),
                    mk_status("快讯-东财7x24(备源)", False, 0, str(e2)[:60])]


# ---------------- 海外 RSS ----------------
def fetch_rss(hours: int) -> tuple:
    """BBC/Fox/路透社 RSS。返回 (列表, 状态列表)"""
    cutoff = _now() - dt.timedelta(hours=hours)
    items, status = [], []
    for name, feed_url in RSS_FEEDS:
        try:
            # feedparser 自己请求可能没UA,先用requests拿内容
            resp = requests.get(feed_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            cnt = 0
            for e in feed.entries[:40]:
                t = None
                for attr in ("published_parsed", "updated_parsed"):
                    st = getattr(e, attr, None)
                    if st:
                        t = dt.datetime.fromtimestamp(_time.mktime(st), dt.timezone.utc).astimezone(TZ)
                        break
                if t and t < cutoff:
                    continue
                items.append({
                    "source": name,
                    "title": getattr(e, "title", ""),
                    "content": getattr(e, "summary", "")[:300],
                    "url": getattr(e, "link", ""),
                    "time": t,
                })
                cnt += 1
            status.append(mk_status(name, True, cnt))
        except Exception as ex:
            status.append(mk_status(name, False, 0, str(ex)[:50]))
    return items, status
