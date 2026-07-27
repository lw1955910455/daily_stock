# -*- coding: utf-8 -*-
"""
A股全市场监控系统 - 全局配置
所有关键词、板块映射、邮件参数都集中在这里维护。
"""
import os

def mk_status(name, ok, count=0, detail=""):
    """构造一条结构化数据源状态,供邮件底部的"数据源状态"表格使用。"""
    return {"name": name, "ok": bool(ok), "count": int(count), "detail": detail or ""}

# ============ 运行参数 ============
# 回看窗口(小时):只处理最近 N 小时内发布的内容,避免跨次运行重复推送
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "8"))

# ============ 邮件配置(从环境变量/GitHub Secrets 读取) ============
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
MAIL_USER = os.environ.get("QQ_EMAIL_USER", "")            # 发件QQ邮箱
MAIL_AUTH_CODE = os.environ.get("QQ_EMAIL_AUTH_CODE", "")  # QQ邮箱SMTP授权码(不是QQ密码)
MAIL_TO = os.environ.get("MAIL_TO", "1955910455@qq.com")   # 收件人

# 本地调试:设置 DRY_RUN=1 时不发邮件,只生成 email_preview.html
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

# ============ 一、公告监控关键词 ============
ANNOUNCEMENT_KEYWORDS = [
    "减持", "增持", "回购", "收购", "重组", "股权激励", "重大资产重组",
    "业绩预增", "扭亏为盈", "净利润大幅增长", "业绩预告",
]

# 业绩驱动关键词(命中即打上【业绩驱动】标签)
PERFORMANCE_KEYWORDS = [
    "业绩预增", "扭亏为盈", "净利润大幅增长", "业绩预告",
    "净利润同比增长", "预计盈利", "业绩大幅增长",
]

# ============ 二、政策监控关键词 → 关联板块 ============
POLICY_KEYWORD_SECTORS = {
    "新能源":     ["光伏", "风电", "新能源车", "锂电池"],
    "数字经济":   ["云计算", "大数据", "数据要素"],
    "低空经济":   ["低空经济", "无人机", "eVTOL"],
    "设备更新":   ["工程机械", "机械设备", "工业母机"],
    "以旧换新":   ["家电", "汽车", "消费电子"],
    "人工智能":   ["AI应用", "算力", "CPO", "服务器"],
    "半导体":     ["芯片", "半导体设备", "存储芯片"],
    "生物医药":   ["创新药", "CXO", "医疗器械"],
    "军工":       ["国防军工", "军工电子", "航空航天"],
    "电网":       ["电网设备", "特高压", "智能电网"],
    "储能":       ["储能", "电池", "钠电池"],
    "充电桩":     ["充电桩", "汽车配套"],
    "智能制造":   ["机器人", "工业自动化", "工业母机"],
    "信创":       ["信创", "国产软件", "网络安全"],
    "国产替代":   ["半导体", "信创", "高端装备"],
    "碳中和":     ["绿电", "环保", "碳交易"],
    "碳达峰":     ["绿电", "环保", "碳交易"],
    "专精特新":   ["专精特新", "高端制造"],
    "新质生产力": ["科技创新", "高端制造", "未来产业"],
}
POLICY_KEYWORDS = list(POLICY_KEYWORD_SECTORS.keys())

# ============ 三、事件催化规则 → 利好板块 / 利空板块 ============
EVENT_RULES = [
    {
        "name": "电力需求激增",
        "keywords": ["电力需求激增", "用电量创新高", "用电负荷创新高", "电力供应紧张",
                     "迎峰度夏", "电网负荷", "限电"],
        "sectors": ["电力", "电网设备", "虚拟电厂", "储能"],
        "bearish_sectors": ["高耗能下游(化工/钢铁/有色)"],
    },
    {
        "name": "地缘冲突",
        "keywords": ["局部战争", "地缘冲突", "军事冲突", "空袭", "导弹袭击",
                     "宣布开战", "开火", "武装冲突", "袭击油田", "封锁海峡"],
        "sectors": ["军工", "油气", "黄金"],
        "bearish_sectors": ["航空机场", "航运", "出口链", "高估值成长股"],
    },
    {
        "name": "自然灾害",
        "keywords": ["自然灾害", "洪水", "洪涝", "地震", "极寒", "寒潮",
                     "台风", "暴雨", "干旱", "山火"],
        "sectors": ["应急物资", "水利建设", "农业"],
        "bearish_sectors": ["受灾地区旅游", "保险(赔付压力)", "当地农业短期"],
    },
    {
        "name": "重大科技突破",
        "keywords": ["重大科技突破", "重大突破", "技术突破", "首次实现",
                     "全球首个", "攻克", "里程碑式"],
        "sectors": ["科技前沿"],
        "bearish_sectors": ["被替代的传统产能(燃油车/旧技术)"],
    },
    {
        "name": "供需缺口/涨价",
        "keywords": ["供需缺口", "涨价", "提价", "调价", "供应紧张",
                     "库存告急", "缺货", "产能不足"],
        "sectors": ["上游资源", "周期品"],
        "bearish_sectors": ["下游制造", "消费品(成本传导)"],
    },
    {
        "name": "重大安全事故",
        "keywords": ["重大安全事故", "爆炸事故", "火灾事故", "矿难", "召回"],
        "sectors": ["安全生产", "替代供应商"],
        "bearish_sectors": ["涉事行业(化工/煤炭/食饮)", "同业(监管收紧)"],
    },
]

# ============ 三·b、政策利空关键词 → 利空板块(监管/收紧类政策) ============
POLICY_BEARISH_SECTORS = {
    "反垄断":      ["平台经济", "互联网巨头"],
    "集采":        ["医药(仿制药)", "高值耗材"],
    "环保限产":    ["高污染行业(水泥/钢铁/化工)"],
    "去产能":      ["落后产能", "过剩行业"],
    "退市":        ["ST股", "壳资源", "垃圾股"],
    "减持新规":    ["高减持压力个股"],
    "监管收紧":    ["房地产", "城投", "高杠杆行业"],
}

# ============ 四、国际动态关键词(中英文) → 关联板块 ============
INTL_KEYWORD_SECTORS = {
    "特朗普":   ["出口链", "黄金", "军工"],
    "美联储":   ["黄金", "券商", "人民币资产"],
    "加息":     ["银行", "黄金"],
    "降息":     ["券商", "地产", "黄金"],
    "关税":     ["出口链", "国产替代"],
    "英伟达":   ["算力", "AI硬件", "CPO"],
    "微软":     ["AI应用", "云计算"],
    "苹果":     ["消费电子", "果链"],
    "特斯拉":   ["新能源车", "机器人"],
    "三星":     ["存储芯片", "半导体"],
    "SK海力士": ["存储芯片", "半导体"],
    "博通":     ["ASIC芯片", "算力"],
}
# 英文别名 → 中文关键词
INTL_EN_ALIAS = {
    "trump": "特朗普", "federal reserve": "美联储", "fed ": "美联储",
    "rate hike": "加息", "rate cut": "降息", "tariff": "关税",
    "nvidia": "英伟达", "microsoft": "微软", "apple": "苹果",
    "tesla": "特斯拉", "samsung": "三星", "sk hynix": "SK海力士",
    "broadcom": "博通",
}
INTL_KEYWORDS = list(INTL_KEYWORD_SECTORS.keys())

# ============ 五、数据源地址 ============
# 政策源(国务院JSON/政策文件库/发改委列表页)在 fetch_policy.py 中定义
RSS_FEEDS = [
    ("BBC World",    "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Fox News",     "https://moxie.foxnews.com/google-publisher/latest.xml"),
    ("Fox Business", "https://moxie.foxnews.com/google-publisher/world.xml"),
    # 路透社官方RSS已停止服务,用 Google News RSS 聚合路透社内容替代
    ("Reuters(via GoogleNews)", "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en"),
]

# 请求头
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT = 20

# ============ 六、自动恢复 / 应急搜索配置 ============
# 连续多少次"全源失败"后,自动切换百度应急搜索模式
FAIL_THRESHOLD = int(os.environ.get("FAIL_THRESHOLD", "3"))
# 每次应急搜索最多发起的查询数(避免请求过多/超时)
EMERGENCY_MAX_QUERIES = int(os.environ.get("EMERGENCY_MAX_QUERIES", "16"))
# 百度搜索基础地址(桌面版;移动版作为降级)
BAIDU_SEARCH_URL = "https://www.baidu.com/s?ie=utf-8&wd={q}"
BAIDU_MOBILE_URL = "https://m.baidu.com/s?word={q}"
# 状态文件路径(跨次运行持久化失败计数 / 应急模式,由 GitHub Actions 提交回仓库)
STATE_FILE = os.environ.get("MONITOR_STATE_FILE",
                           os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        ".monitor_state.json"))
