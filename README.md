# A股全市场监控系统

自动监控 **公告 / 政策 / 事件催化 / 业绩 / 国际动态** 五大维度,识别
【政策驱动】+【事件驱动】+【业绩驱动】共振标的,通过 QQ 邮箱定时推送。
部署在 GitHub Actions 云端,电脑关机不影响运行。

## 功能一览

| 模块 | 数据源 | 说明 |
|---|---|---|
| 公告监控 | 巨潮资讯(主源)→ 东方财富 → 新浪(自动降级) | 减持/增持/回购/收购/重组/股权激励/业绩预增/扭亏为盈等 |
| 政策监控 | 国务院 gov.cn、发改委 ndrc.gov.cn、工信部 miit.gov.cn | 新能源/数字经济/低空经济/人工智能/半导体等 19 个关键词,自动关联板块 |
| 事件催化 | 财联社快讯(→东财7x24降级)+ BBC/Fox/路透 RSS | 电力激增→电力/储能;地缘冲突→军工/油气/黄金;灾害→应急/水利/农业 等 |
| 业绩监测 | 公告 + 新闻双通道 | 识别业绩预增/扭亏为盈,并提取增长率数字 |
| 国际动态 | 海外 RSS + 国内快讯 | 特朗普/美联储/加息/降息/关税/英伟达/微软/苹果/特斯拉/三星/SK海力士/博通(中英文) |
| 共振标注 | 跨维度交叉 | 两项驱动 →【🔥共振标的(双轮驱动)】;三项 →【🔥🔥🔥三重共振爆发标的】,邮件置顶(优先级最高) |
| 心跳 | — | 无命中显示"今日无新消息",仍发心跳邮件,证明脚本存活 |
| 数据源状态 | 每源记录 | 邮件底部"数据源状态"表格:逐源标 ✅正常 / ❌失败 + 失败源名 + 原因 |
| 异常告警 | 全局捕获 | 程序崩溃时自动发"🚨异常告警"邮件,附错误堆栈 |
| 应急搜索 | 自动降级 | 连续 `FAIL_THRESHOLD`(默认3)次"全源失败"→ 切换百度关键词组合兜底,邮件标"【应急搜索模式】" |
| 手动触发 | workflow_dispatch | Actions 页面可手动 Run,并支持"强制应急""重置状态"两个开关 |

## 健壮性 / 自动恢复机制

1. **数据源状态日志**:每次运行,公告/政策/快讯/RSS/股票名单/应急搜索每个源都记录
   成功(`ok`)或失败(`detail` 含具体原因),邮件底部"🩺 数据源状态"以表格呈现,
   ❌ 行高亮标红,一眼看出**哪个源挂了**。
2. **异常捕获**:`main()` 外层 `try/except` 包裹;任何未预期异常都会触发
   `send_alert()` 发送"🚨异常告警"邮件(含错误信息 + 完整堆栈),同时把本次记为一次失败。
3. **连续失败 → 应急搜索**:用仓库里的 `.monitor_state.json` 持久化"连续失败次数"
   (GitHub Actions 无状态,工作流每次运行后把该文件提交回仓库实现跨次计数)。
   - 当 **常规数据源全部失败** 累计达 `FAIL_THRESHOLD`(默认 3)次,下一轮自动进入
     **百度关键词组合应急搜索模式**,在邮件顶部标注"【应急搜索模式】"。
   - 应急搜索是"尽力而为":能抓到就并入分析,抓不到只会在状态表标失败,**不会**让主流程崩溃。
   - 一旦常规源恢复(单轮拿到任意正常数据),失败计数清零,**自动退出**应急模式(自愈)。
4. **手动触发 / 调试开关**:`workflow_dispatch` 入口支持三个输入:
   - `lookback_hours`:回看窗口
   - `force_emergency`:强制本轮启用应急搜索(测试用)
   - `reset_state`:重置失败计数、立即退出应急模式

## 文件结构

```
a-stock-monitor/
├── monitor.py           # 主入口(含异常捕获 / 失败计数 / 应急触发)
├── config.py            # ★所有关键词/板块映射/邮箱配置/阈值(日常维护改这里)
├── a_stock_data.py      # 公告抓取工具包(巨潮→东财→新浪 三级降级)
├── fetch_policy.py      # 政策抓取(国务院/发改委/工信部)
├── fetch_news.py        # 快讯+RSS 抓取
├── emergency.py         # 百度应急搜索兜底(连续失败触发)
├── state_store.py       # 失败计数 / 应急模式 持久化(.monitor_state.json)
├── analyzer.py          # 关键词命中/板块关联/个股识别/共振标注
├── mailer.py            # QQ邮箱 HTML 邮件 + 心跳 + 异常告警 + 状态表
├── requirements.txt
├── .monitor_state.json  # 运行时生成的跨次状态(需提交进仓库!)
└── .github/workflows/monitor.yml   # 云端定时任务
```

## 部署到 GitHub Actions(5 步)

### 第 1 步:获取 QQ 邮箱 SMTP 授权码
1. 网页登录 QQ 邮箱 → 设置 → 账号 → 「POP3/IMAP/SMTP…服务」
2. 开启 **SMTP 服务**,按提示发短信验证
3. 得到一个 16 位**授权码**(注意:不是 QQ 密码),复制保存

### 第 2 步:创建 GitHub 仓库
1. 登录 GitHub → New repository
2. 仓库名任意(如 `a-stock-monitor`),**选择 Private(私有)**
3. 不要勾选任何初始化选项,创建

### 第 3 步:上传代码
在本目录打开终端执行(替换成你的用户名/仓库名):
```bash
git init
git add .
git commit -m "A股全市场监控系统"
git branch -M main
git remote add origin https://github.com/<你的用户名>/a-stock-monitor.git
git push -u origin main
```
(不会命令行也可以在 GitHub 网页上直接 "uploading an existing file" 把整个文件夹拖进去,
 注意 `.github` 文件夹必须一起上传)

### 第 4 步:配置 Secrets(邮箱凭证)
仓库页面 → Settings → Secrets and variables → **Actions** → New repository secret,添加两条:

发件凭据支持**两套**,任选其一配置即可(`mailer.py` 优先读前者,读不到则回退后者):

| Name | Value |
|---|---|
| `QQ_EMAIL_USER` | 你的发件 QQ 邮箱,如 `1955910455@qq.com` |
| `QQ_EMAIL_AUTH_CODE` | 第 1 步拿到的 16 位授权码 |
| 或 `EMAIL_SENDER` / `EMAIL_PASSWORD` | 回退凭据(同样是发件邮箱 + 授权码) |

### 第 5 步:启用并测试
1. 仓库页面 → **Actions** 标签 → 如提示则点 "I understand… enable them"
2. 左侧选 **A-Stock Market Monitor** → 右侧 **Run workflow** 手动跑一次
   (可展开 Options 填 `lookback_hours`、勾选 `force_emergency`/`reset_state` 做调试)
3. 约 1-2 分钟后查看 1955910455@qq.com 是否收到邮件 ✅

之后每天北京时间 **6:00 / 12:00 / 18:00 / 23:00** 自动运行(GitHub 定时任务
可能有 5-15 分钟排队延迟,属正常现象)。

> ⚠️ **重要**:`.monitor_state.json` 必须随代码一起提交进仓库(工作流会在每次
> 运行后自动把它提交回去)。如果只提交代码、不提交这个文件,失败计数每次都会
> 从 0 开始,"连续失败 3 次"的应急机制就永远不会触发。首次 push 时确保它已被跟踪即可。

## 本地测试(可选)

```bash
pip install -r requirements.txt

# 真实发送测试(mailer 现强制真实发送,不再写预览文件):
# 凭据任选一套,设置后直接运行即发送:
set QQ_EMAIL_USER=xxx@qq.com
set QQ_EMAIL_AUTH_CODE=十六位授权码
python monitor.py
# 或使用回退凭据:
set EMAIL_SENDER=xxx@qq.com
set EMAIL_PASSWORD=十六位授权码
python monitor.py
```

> 注:旧版的 `DRY_RUN=1` 预览模式已移除——`mailer.py` 现强制真实发送、
> 不再生成 `email_preview.html`。如需本地查看邮件排版,可临时把 `mailer.py` 顶部
> 的 `DRY_RUN = False` 改回读取(或单独写预览),但正式部署请保持强制发送。

## 日常维护

- **加关键词/改板块映射** → 只改 `config.py`,提交推送即可,下次运行自动生效
- **改运行时间** → 改 `.github/workflows/monitor.yml` 里的 cron(注意用 UTC,北京时间-8)
- **改收件人** → 改 monitor.yml 中的 `MAIL_TO`
- **排查问题** → 仓库 Actions 页面看运行日志;邮件末尾"数据源状态"一栏
  会显示每个数据源成功/失败情况

## 已知限制(诚实说明)

1. **政府网站反爬**:gov.cn / ndrc / miit 偶尔会拒绝海外服务器(GitHub Actions 在
   境外)的请求,失败时邮件"数据源状态"会标明,不影响其他模块。
2. **财联社接口**:非官方接口,若失效自动降级到东方财富 7x24 快讯。
3. **路透社**:官方 RSS 已停服,使用 Google News 聚合的路透社内容替代。
4. **共振识别口径**:政策/事件驱动需要新闻或政策文本中**明确提及个股名称/代码**
   才能落到个股;未提及个股时按"板块级共振"展示。这是为了避免把整个板块
   几百只股票都硬贴上"共振"造成噪音。
5. 本系统仅为信息聚合工具,不构成投资建议。
