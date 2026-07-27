# -*- coding: utf-8 -*-
"""
邮件模块:QQ邮箱 SMTP(SSL 465)发送 HTML 汇总邮件
- 共振标的汇总置顶(优先级最高)
- 数据源状态表格(清楚标出哪个源挂了)
- 无新内容时发送心跳邮件(显示"今日无新消息")
- 程序崩溃时发送"异常告警"邮件
- DRY_RUN=1 时只写 email_preview.html 不发送
"""
import smtplib
import datetime as dt
import traceback as _tb
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from zoneinfo import ZoneInfo

from config import (SMTP_HOST, SMTP_PORT, MAIL_USER, MAIL_AUTH_CODE,
                    MAIL_TO, DRY_RUN)

TZ = ZoneInfo("Asia/Shanghai")

CSS = """
<style>
body{font-family:'Microsoft YaHei',Arial,sans-serif;font-size:14px;color:#222;
     max-width:860px;margin:0 auto;padding:12px;}
h2{font-size:16px;border-left:4px solid #c0392b;padding-left:8px;margin:22px 0 8px;}
.resonance{background:#fff3f0;border:2px solid #e74c3c;border-radius:8px;
           padding:12px;margin-bottom:8px;}
.res-item{margin:8px 0;padding:8px;background:#fff;border-radius:6px;}
.lv3{color:#c0392b;font-weight:bold;}
.lv2{color:#e67e22;font-weight:bold;}
table{border-collapse:collapse;width:100%;}
td,th{border:1px solid #ddd;padding:6px 8px;font-size:13px;vertical-align:top;}
th{background:#f5f5f5;text-align:left;}
.tag{display:inline-block;background:#eef;border-radius:4px;padding:0 6px;
     margin:0 3px 2px 0;font-size:12px;color:#334;}
.sector{background:#e8f6ef;color:#1e7d4f;}
.time{color:#888;font-size:12px;}
.src{color:#888;font-size:12px;}
a{color:#1a5fb4;text-decoration:none;}
.status{background:#f8f8f8;border-radius:6px;padding:8px;font-size:12px;color:#666;}
.hb{background:#eef7ff;border:1px solid #9cc3e5;border-radius:8px;padding:14px;}
.emg{background:#fff4e5;border:2px solid #e69500;border-radius:8px;padding:10px;margin:8px 0;font-weight:bold;}
.st tr.ok{background:#f0fff4;}
.st tr.fail{background:#fff0f0;}
.st td .ok{color:#1e7d4f;font-weight:bold;}
.st td .fail{color:#c0392b;font-weight:bold;}
.alert{background:#fff0f0;border:2px solid #c0392b;border-radius:8px;padding:14px;}
.alert pre{white-space:pre-wrap;font-size:12px;background:#fff;padding:8px;border-radius:6px;max-height:300px;overflow:auto;}
</style>
"""


def _tags(lst, cls="tag"):
    return "".join('<span class="tag {}">{}</span>'.format(cls, x) for x in lst)

def _stock_str(stocks):
    return "、".join("{}({})".format(n or "?", c or "?") for n, c in stocks) if stocks else ""

def summarize_status(source_table: list) -> tuple:
    """返回 (失败源名列表, 成功数, 失败数)"""
    failed = [s.get("name", "?") for s in source_table if not s.get("ok")]
    ok = sum(1 for s in source_table if s.get("ok"))
    return failed, ok, len(failed)

def render_status_table(source_table: list) -> str:
    rows = []
    for s in source_table:
        ok = s.get("ok")
        badge = '<span class="ok">✅ 正常</span>' if ok else '<span class="fail">❌ 失败</span>'
        cls = "ok" if ok else "fail"
        rows.append("<tr class='{}'><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            cls, s.get("name", ""), badge, s.get("count", 0), s.get("detail", "") or "-"))
    if not rows:
        return "<div class='status'>（无状态记录）</div>"
    return ("<table class='st'><tr><th>数据源</th><th>状态</th><th>条数</th><th>说明</th></tr>"
            + "".join(rows) + "</table>")

def render_html(res, sector_res, policy_hits, event_hits, ann_hits,
                intl_hits, perf_news_hits, source_table, hours, emergency=False) -> str:
    now = dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    parts = [CSS, "<h1 style='font-size:18px'>A股全市场监控日报 <span class='time'>{}(近{}小时)</span></h1>".format(now, hours)]
    if emergency:
        parts.append("<div class='emg'>⚠️ 已进入【应急搜索模式】:常规数据源连续失败,本邮件部分内容由百度搜索关键词组合兜底,仅供参考。</div>")

    # ===== 共振标的汇总(置顶·优先级最高) =====
    parts.append("<h2>🔥 共振标的汇总(优先级最高 · 置顶)</h2>")
    if res:
        parts.append('<div class="resonance">')
        for r in res:
            lv = "lv3" if len(r["drivers"]) >= 3 else "lv2"
            ev = "".join('<div class="time">▸【{}】<a href="{}">{}</a></div>'.format(d, u, t)
                         for d, t, u in r["evidence"])
            parts.append(
                '<div class="res-item"><span class="{}">{}</span> '
                '<b>{}({})</b> 驱动:{}{}</div>'.format(
                    lv, r["level"], r["name"] or "?", r["code"] or "?",
                    _tags(r["drivers"]), ev))
        parts.append("</div>")
    else:
        parts.append("<p class='time'>本时段暂无满足双轮/三重共振条件的个股。</p>")
    if sector_res:
        parts.append("<p><b>板块级共振</b>(政策+事件同时利好):{}</p>".format(
            _tags(sector_res, "tag sector")))

    # ===== 政策监测 =====
    parts.append("<h2>📜 政策监测({}条命中)</h2>".format(len(policy_hits)))
    if policy_hits:
        parts.append("<table><tr><th>来源</th><th>政策文件</th><th>关键词</th><th>关联板块</th></tr>")
        for p in policy_hits:
            parts.append("<tr><td>{}<br><span class='time'>{}</span></td>"
                         "<td><a href='{}'>{}</a>{}</td><td>{}</td><td>{}</td></tr>".format(
                             p["source"], p.get("date", ""), p["url"], p["title"],
                             ("<br><span class='time'>提及:{}</span>".format(_stock_str(p["stocks"]))
                              if p.get("stocks") else ""),
                             _tags(p["keywords"]), _tags(p["sectors"], "tag sector")))
        parts.append("</table>")
    else:
        parts.append("<p class='time'>无命中。</p>")

    # ===== 事件催化 =====
    parts.append("<h2>⚡ 事件催化监测({}条命中)</h2>".format(len(event_hits)))
    if event_hits:
        parts.append("<table><tr><th>来源/时间</th><th>快讯</th><th>事件类型</th><th>利好板块</th></tr>")
        for e in event_hits:
            t = e["time"].strftime("%m-%d %H:%M") if e.get("time") else ""
            parts.append("<tr><td>{}<br><span class='time'>{}</span></td>"
                         "<td><a href='{}'>{}</a>{}</td><td>{}</td><td>{}</td></tr>".format(
                             e["source"], t, e["url"], e["title"],
                             ("<br><span class='time'>提及:{}</span>".format(_stock_str(e["stocks"]))
                              if e.get("stocks") else ""),
                             _tags(e["events"]), _tags(e["sectors"], "tag sector")))
        parts.append("</table>")
    else:
        parts.append("<p class='time'>无命中。</p>")

    # ===== 业绩监测 =====
    perf_anns = [a for a in ann_hits if a.get("is_performance")]
    parts.append("<h2>📈 业绩监测(公告{}条 / 新闻{}条)</h2>".format(
        len(perf_anns), len(perf_news_hits)))
    if perf_anns or perf_news_hits:
        parts.append("<table><tr><th>股票</th><th>标题</th><th>关键词/业绩数据</th></tr>")
        for a in perf_anns:
            parts.append("<tr><td>{}({})</td><td><a href='{}'>{}</a>"
                         "<br><span class='time'>{}</span></td><td>{}</td></tr>".format(
                             a["name"], a["code"], a["url"], a["title"],
                             a["time"].strftime("%m-%d %H:%M"), _tags(a["keywords"])))
        for pn in perf_news_hits:
            g = " 数据:{}".format("、".join(pn["growth"])) if pn.get("growth") else ""
            parts.append("<tr><td>{}</td><td><a href='{}'>{}</a>"
                         "<br><span class='src'>{}</span></td><td>{}{}</td></tr>".format(
                             _stock_str(pn.get("stocks", [])) or "-",
                             pn["url"], pn["title"], pn["source"],
                             _tags(pn["keywords"]), g))
        parts.append("</table>")
    else:
        parts.append("<p class='time'>无命中。</p>")

    # ===== 公告监测 =====
    other_anns = [a for a in ann_hits if not a.get("is_performance")]
    parts.append("<h2>📋 公告监测({}条命中)</h2>".format(len(other_anns)))
    if other_anns:
        parts.append("<table><tr><th>股票</th><th>公告标题</th><th>关键词</th></tr>")
        for a in other_anns[:120]:
            parts.append("<tr><td>{}({})</td><td><a href='{}'>{}</a>"
                         "<br><span class='time'>{}</span></td><td>{}</td></tr>".format(
                             a["name"], a["code"], a["url"], a["title"],
                             a["time"].strftime("%m-%d %H:%M"), _tags(a["keywords"])))
        parts.append("</table>")
    else:
        parts.append("<p class='time'>无命中。</p>")

    # ===== 国际动态 =====
    parts.append("<h2>🌍 国际动态({}条命中)</h2>".format(len(intl_hits)))
    if intl_hits:
        parts.append("<table><tr><th>来源</th><th>新闻</th><th>关键词</th><th>关联板块</th></tr>")
        for n in intl_hits[:40]:
            parts.append("<tr><td>{}</td><td><a href='{}'>{}</a></td>"
                         "<td>{}</td><td>{}</td></tr>".format(
                             n["source"], n["url"], n["title"],
                             _tags(n["keywords"]), _tags(n["sectors"], "tag sector")))
        parts.append("</table>")
    else:
        parts.append("<p class='time'>无命中。</p>")

    # ===== 数据源状态 =====
    parts.append("<h2>🩺 数据源状态(本邮件数据来源)</h2>")
    parts.append(render_status_table(source_table))
    return "".join(parts)

def render_heartbeat(source_table, hours, emergency=False) -> str:
    now = dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    parts = [CSS]
    if emergency:
        parts.append("<div class='emg'>⚠️ 已进入【应急搜索模式】:常规数据源连续失败,本邮件由百度搜索关键词组合兜底,仅供参考。</div>")
    parts.append("<div class='hb'><h2 style='border:none'>💓 心跳:监控脚本运行正常</h2>"
                "<p><b>今日无新消息</b> —— {} 完成一次扫描(近{}小时),各监控维度均无关键词命中。</p>"
                "<p class='time'>脚本仍在正常运行,无需担心;如有数据源失败会在下方标注。</p>"
                "<h2 style='border:none'>🩺 数据源状态</h2>{}</div>".format(
                    now, hours, render_status_table(source_table)))
    return "".join(parts)

def render_alert(error_msg: str, tb_text: str = "") -> str:
    now = dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    return (CSS +
            "<div class='alert'><h2 style='border:none;color:#c0392b'>🚨 异常告警:A股监控脚本崩溃</h2>"
            "<p>时间:{}</p>"
            "<p>错误信息:<b>{}</b></p>"
            "<p>脚本本次运行未正常完成,请检查运行环境 / 代码 / 网络。下方为堆栈:</p>"
            "<pre>{}</pre></div>".format(now, error_msg, (tb_text or _tb.format_exc())))

def send_mail(subject: str, html: str) -> str:
    if DRY_RUN or not MAIL_USER or not MAIL_AUTH_CODE:
        with open("email_preview.html", "w", encoding="utf-8") as f:
            f.write(html)
        return ("DRY_RUN 或未配置邮箱:已写入 email_preview.html(未发送)。"
                if DRY_RUN else "未配置 QQ_EMAIL_USER/QQ_EMAIL_AUTH_CODE:已写入 email_preview.html。")
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("A股监控机器人", MAIL_USER))
    msg["To"] = MAIL_TO
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.login(MAIL_USER, MAIL_AUTH_CODE)
        s.sendmail(MAIL_USER, [MAIL_TO], msg.as_string())
    return "邮件已发送至 " + MAIL_TO

def send_alert(error_msg: str) -> str:
    """崩溃时发送异常告警邮件(与正常邮件共用 SMTP 配置)。"""
    html = render_alert(error_msg)
    subject = "🚨【异常告警】A股监控脚本崩溃 - " + dt.datetime.now(TZ).strftime("%m-%d %H:%M")
    return send_mail(subject, html)
