# -*- coding: utf-8 -*-
"""
A股全市场监控系统 - 主入口
流程:抓取(公告/政策/快讯/RSS) → 分析(关键词/板块/个股) → 共振标注 → 邮件推送
健壮性:
  - 每个数据源成功/失败均记入"数据源状态"表格(邮件底部)
  - 程序崩溃自动发送"异常告警"邮件
  - 连续 FAIL_THRESHOLD 次"全源失败"自动切换百度应急搜索模式
  - 保留 workflow_dispatch 手动运行入口
用法:python monitor.py     (环境变量见 config.py / README.md)
"""
import sys
import os
import datetime as dt
from zoneinfo import ZoneInfo

from config import LOOKBACK_HOURS, FAIL_THRESHOLD
from a_stock_data import fetch_announcements
from fetch_policy import fetch_policies
from fetch_news import fetch_domestic_news, fetch_rss
from emergency import fetch_emergency
from analyzer import (load_stock_map, analyze_announcements, analyze_policies,
                      analyze_events, analyze_intl, analyze_perf_news,
                      build_resonance, build_sector_resonance)
from mailer import (render_html, render_heartbeat, send_mail, send_alert,
                    summarize_status)
from state_store import load_state, save_state

TZ = ZoneInfo("Asia/Shanghai")


def log(msg):
    print("[{}] {}".format(dt.datetime.now(TZ).strftime("%H:%M:%S"), msg), flush=True)


def _run():
    hours = LOOKBACK_HOURS

    # ---------- 0. 加载持久化状态(失败计数 / 应急模式) ----------
    state = load_state()
    state["runs"] = state.get("runs", 0) + 1
    forced = os.environ.get("FORCE_EMERGENCY") == "1"
    reset = os.environ.get("RESET_EMERGENCY") == "1"
    if reset:
        state["fail_count"] = 0
        log("收到 RESET_EMERGENCY,已重置失败计数。")
    # 连续失败达到阈值 → 进入应急模式(也支持手动强制)
    emergency_active = (state.get("fail_count", 0) >= FAIL_THRESHOLD) or forced
    if emergency_active:
        log("⚠️ 应急搜索模式已启用(连续失败 {} 次 / 强制={})。".format(
            state.get("fail_count", 0), forced))

    source_table = []

    # ---------- 1. 抓取 ----------
    log("抓取A股公告(近{}小时)...".format(hours))
    anns, st = fetch_announcements(hours)
    source_table.extend(st); log("公告:{} 条".format(len(anns)))

    log("抓取政策文件...")
    policies, pst = fetch_policies()
    source_table.extend(pst); log("政策:{} 条".format(len(policies)))

    log("抓取国内快讯...")
    dnews, dst = fetch_domestic_news(hours)
    source_table.extend(dst); log("国内快讯:{} 条".format(len(dnews)))

    log("抓取海外RSS...")
    rss, rst = fetch_rss(hours)
    source_table.extend(rst); log("海外RSS:{} 条".format(len(rss)))

    log("加载全A股票名单...")
    stock_map = load_stock_map()
    source_table.append({"name": "股票名单", "ok": bool(stock_map),
                         "count": len(stock_map),
                         "detail": "已加载" if stock_map else "加载失败(个股提取降级)"})

    # ---------- 1.5 应急搜索兜底 ----------
    em_items = []
    if emergency_active:
        log("应急搜索:百度关键词组合抓取中...")
        em_items, em_st = fetch_emergency(hours)
        source_table.extend(em_st)
        log("应急搜索命中:{} 条".format(len(em_items)))

    # ---------- 2. 分析 ----------
    # 应急结果并入新闻池(事件/国际/业绩)与政策池
    all_news = dnews + rss + em_items
    ann_hits = analyze_announcements(anns)
    policy_hits = analyze_policies(policies + em_items, stock_map)
    event_hits = analyze_events(all_news, stock_map)
    intl_hits = analyze_intl(all_news)
    perf_news_hits = analyze_perf_news(dnews + em_items, stock_map)

    log("命中:公告{} 政策{} 事件{} 国际{} 业绩新闻{}".format(
        len(ann_hits), len(policy_hits), len(event_hits),
        len(intl_hits), len(perf_news_hits)))

    # ---------- 3. 共振标注 ----------
    res = build_resonance(policy_hits, event_hits, ann_hits, perf_news_hits)
    sector_res = build_sector_resonance(policy_hits, event_hits)
    log("共振标的:{} 个;共振板块:{}".format(len(res), sector_res or "无"))

    # ---------- 4. 失败计数 / 应急模式持久化 ----------
    normal_items = len(anns) + len(policies) + len(dnews) + len(rss)
    if normal_items == 0:
        state["fail_count"] = state.get("fail_count", 0) + 1
        state["last_status"] = "failed"
    else:
        state["fail_count"] = 0
        state["last_status"] = "ok"
    # 应急模式在"连续失败达阈值"或手动强制时持续;常规源恢复后自动退出
    emergency_now = (state["fail_count"] >= FAIL_THRESHOLD) or forced
    state["emergency_mode"] = emergency_now
    save_state(state)
    log("状态已保存:连续失败={}, 应急模式={}".format(
        state["fail_count"], emergency_now))

    # ---------- 5. 邮件 ----------
    now = dt.datetime.now(TZ).strftime("%m-%d %H:%M")
    failed, ok_cnt, fail_cnt = summarize_status(source_table)
    total = (len(ann_hits) + len(policy_hits) + len(event_hits)
             + len(intl_hits) + len(perf_news_hits))

    # 主题前缀:应急模式 / 数据源失败告警
    prefix = ""
    if emergency_now:
        prefix += "【应急搜索模式】"
    if fail_cnt > 0:
        prefix += "⚠️{}个数据源失败 ".format(fail_cnt)

    if total == 0:
        subject = "{}【A股监控·心跳】{} 今日无新消息".format(prefix, now)
        html = render_heartbeat(source_table, hours, emergency_now)
    else:
        tri = sum(1 for r in res if len(r["drivers"]) >= 3)
        dual = len(res) - tri
        badge = ""
        if tri:
            badge = "🔥🔥🔥三重共振x{} ".format(tri)
        elif dual:
            badge = "🔥双轮驱动x{} ".format(dual)
        subject = "{}【A股监控】{} {}政策{} 事件{} 业绩{} 公告{}".format(
            prefix, now, badge, len(policy_hits), len(event_hits),
            len(perf_news_hits) + sum(1 for a in ann_hits if a["is_performance"]),
            len(ann_hits))
        html = render_html(res, sector_res, policy_hits, event_hits, ann_hits,
                           intl_hits, perf_news_hits, source_table, hours,
                           emergency_now)

    result = send_mail(subject, html)
    log(result)
    if fail_cnt > 0:
        log("⚠️ 以下数据源本次失败:{}".format("、".join(failed)))
    log("本轮监控完成。")
    return 0


def main():
    try:
        return _run()
    except Exception as e:
        import traceback as _tb
        tb = _tb.format_exc()
        log("‼️ 程序异常崩溃:{}".format(e))
        log(tb)
        # 记录失败,推进应急模式(连续崩溃也算失败)
        try:
            state = load_state()
            state["fail_count"] = state.get("fail_count", 0) + 1
            state["last_status"] = "crash"
            state["emergency_mode"] = state["fail_count"] >= FAIL_THRESHOLD
            save_state(state)
        except Exception:
            pass
        # 发送异常告警邮件(尽量送达)
        try:
            send_alert("{}".format(e))
        except Exception as mail_err:
            log("‼️ 异常告警邮件发送失败:{}".format(mail_err))
        return 1


if __name__ == "__main__":
    sys.exit(main())
