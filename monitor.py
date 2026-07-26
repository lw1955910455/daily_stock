import requests, smtplib, feedparser, os
from email.mime.text import MIMEText
from datetime import datetime

KEYWORDS = ['减持','增持','回购','收购','重组','股权激励','重大资产重组']
MACRO = ['特朗普','美联储','加息','降息','关税','地缘冲突','原油','黄金','美元指数',
         '英伟达','NVIDIA','微软','Microsoft','苹果','Apple','特斯拉','Tesla',
         '三星','Samsung','SK海力士','博通','Broadcom','并购','收购','战略合作','合资']
MAPPING = {
    '英伟达': '半导体（北方华创、中微公司）', 'NVIDIA': '半导体（北方华创、中微公司）',
    '微软': 'AI算力（浪潮信息、中科曙光）', 'Microsoft': 'AI算力（浪潮信息、中科曙光）',
    '苹果': '消费电子（立讯精密、长电科技）', 'Apple': '消费电子（立讯精密、长电科技）',
    '特斯拉': '新能源车（比亚迪、宁德时代）', 'Tesla': '新能源车（比亚迪、宁德时代）',
    '三星': '存储芯片（兆易创新）', 'Samsung': '存储芯片（兆易创新）',
    'SK海力士': 'HBM（雅克科技、华海诚科）', '博通': '半导体（澜起科技）',
    'Broadcom': '半导体（澜起科技）'
}

def get_notices():
    url = f'https://data.eastmoney.com/notices/getData.ashx?type=all&date={datetime.now().strftime("%Y-%m-%d")}&pageSize=100'
    try:
        data = requests.get(url, timeout=30, headers={'User-Agent':'Mozilla/5.0'}).json()
        res = []
        for item in data.get('data', []):
            t = item.get('title', '')
            for kw in KEYWORDS:
                if kw in t:
                    res.append(f"{item.get('name','')}({item.get('code','')}) {t}")
                    break
        return res if res else ['暂无公告']
    except Exception as e:
        return [f'公告抓取失败: {e}']

def get_news():
    feeds = ['http://feeds.bbci.co.uk/news/world/rss.xml', 'https://feeds.feedburner.com/foxnews/latest']
    articles = []
    for url in feeds:
        try:
            for e in feedparser.parse(url).entries[:15]:
                t = e.get('title', '') + ' ' + e.get('summary', '')
                if any(kw.lower() in t.lower() for kw in MACRO):
                    articles.append(e.get('title', ''))
        except:
            continue
    return articles

def analyze(news_list):
    res = []
    for title in news_list:
        for company, stocks in MAPPING.items():
            if company.lower() in title.lower():
                res.append(f"📰 {title}\n   → 关联A股：{stocks}")
                break
    return res

notices = get_notices()
impacts = analyze(get_news())

body = f"=== A股公告（{datetime.now().strftime('%Y-%m-%d %H:%M')}）===\n"
body += "\n".join(notices)
body += "\n\n=== 国际新闻影响分析 ===\n"
body += "\n".join(impacts) if impacts else "暂无直接影响"

sender = os.environ.get('EMAIL_SENDER')
pwd = os.environ.get('EMAIL_PASSWORD')
receiver = os.environ.get('EMAIL_RECEIVERS')
if sender and pwd and receiver:
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'全市场监控 {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    msg['From'] = sender
    msg['To'] = receiver
    smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
    smtp.login(sender, pwd)
    smtp.sendmail(sender, [receiver], msg.as_string())
    smtp.quit()
    print('✅ 邮件发送成功')
else:
    print('❌ 邮箱配置缺失')
    print(body)
