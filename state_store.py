# -*- coding: utf-8 -*-
"""
运行状态持久化:
- fail_count    连续"全源失败"次数(用于触发应急搜索)
- emergency_mode 当前是否处于应急搜索模式
- runs / last_run / last_status  运行统计
GitHub Actions 无状态,本文件由工作流在每次运行后提交回仓库,实现跨次计数。
本地运行(DRY_RUN)同样读写该文件,不影响。
"""
import json
import os
import datetime as dt
from zoneinfo import ZoneInfo

from config import STATE_FILE

TZ = ZoneInfo("Asia/Shanghai")


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            st = json.load(f)
        if not isinstance(st, dict):
            raise ValueError("bad state")
        st.setdefault("fail_count", 0)
        st.setdefault("emergency_mode", False)
        st.setdefault("runs", 0)
        st.setdefault("last_run", "")
        st.setdefault("last_status", "")
        return st
    except Exception:
        return {"fail_count": 0, "emergency_mode": False,
                "runs": 0, "last_run": "", "last_status": ""}


def save_state(state: dict) -> bool:
    state["last_run"] = dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
