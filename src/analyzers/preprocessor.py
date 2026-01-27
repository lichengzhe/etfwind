"""新闻预处理器 - 去重、过滤、合并"""

import re
from datetime import datetime, timezone, timedelta
from loguru import logger

from src.models import NewsItem


# 低价值关键词 - 这类新闻单独看价值低
LOW_VALUE_KEYWORDS = [
    # 人事变动
    "辞职", "辞去", "聘任", "任命", "离任",
    # 股权操作
    "质押", "解押", "解除质押", "冻结", "解冻",
    # 常规公告
    "回购进展", "增持计划", "减持计划", "股份变动",
    "注册资本", "章程修订", "董事会决议",
    "回购股份", "回购价格", "回购方案", "拟将回购",
    "询价转让", "询价申购", "募投项目", "变更部分",
    "审核状态", "已问询", "提交上市申请",
    # 低信息量
    "互动平台", "投资者问", "公司回应称",
    "不存在需要更正", "信息披露",
    # 个股公告（非重大）
    "原料药上市申请", "药品注册", "专利授权",
    "中标项目", "签订合同", "战略合作",
    "股东大会", "临时公告", "更正公告",
    "计划受托人", "公开市场上购买",
    # 处罚/禁止
    "被禁止参加", "行政处罚", "警示函",
    # 券商评级
    "维持", "目标价", "优于大市", "买入评级",
    "料香港", "料蒙牛", "推荐新鸿基",
    # 海外低相关
    "印度", "俄罗斯央行", "西班牙", "巴西",
    "乌克兰", "敖德萨", "日债",
    # 征求意见
    "征求意见稿", "公开征求意见",
]

# 高价值关键词 - 优先保留
HIGH_VALUE_KEYWORDS = [
    # 宏观
    "央行", "降息", "降准", "加息", "GDP", "CPI", "PMI",
    # 市场
    "涨停", "跌停", "暴涨", "暴跌", "创新高", "新低",
    "主力资金", "北向资金", "外资",
    # 政策
    "政策", "监管", "发改委", "证监会", "国务院",
    # 行业重大
    "芯片", "AI", "人工智能", "新能源", "光伏", "锂电",
    "贵金属", "黄金", "白银", "原油",
]

# 业绩预告关键词 - 合并处理
EARNINGS_KEYWORDS = [
    "净利润", "预增", "预减", "预亏", "扭亏",
    "业绩快报", "业绩预告", "同比增长", "同比下降",
]


def calc_similarity(title1: str, title2: str) -> float:
    """计算两个标题的 Jaccard 相似度"""
    def get_ngrams(text: str, n: int = 3) -> set:
        text = re.sub(r'[【】\[\]()（）：:，,。.！!？?]', '', text)
        return {text[i:i+n] for i in range(len(text) - n + 1)}

    set1 = get_ngrams(title1)
    set2 = get_ngrams(title2)

    if not set1 or not set2:
        return 0.0

    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def is_high_value(title: str) -> bool:
    """判断是否为高价值新闻"""
    return any(kw in title for kw in HIGH_VALUE_KEYWORDS)


def is_low_value(title: str) -> bool:
    """判断是否为低价值新闻"""
    return any(kw in title for kw in LOW_VALUE_KEYWORDS)


def is_earnings_news(title: str) -> bool:
    """判断是否为业绩预告类新闻"""
    return any(kw in title for kw in EARNINGS_KEYWORDS)


def deduplicate_news(items: list[NewsItem], threshold: float = 0.5) -> list[NewsItem]:
    """去重相似新闻，保留第一条"""
    if not items:
        return []

    unique = [items[0]]
    for item in items[1:]:
        is_dup = False
        for existing in unique:
            if calc_similarity(item.title, existing.title) > threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(item)

    return unique


def summarize_earnings(items: list[NewsItem]) -> str:
    """汇总业绩预告新闻"""
    if not items:
        return ""

    positive = []  # 预增/扭亏
    negative = []  # 预减/预亏

    for item in items:
        title = item.title
        # 提取公司名
        match = re.search(r'【?([^：:【】]+)[：:]', title)
        company = match.group(1) if match else title[:6]

        if any(kw in title for kw in ["预增", "扭亏", "同比增长"]):
            positive.append(company)
        elif any(kw in title for kw in ["预减", "预亏", "同比下降", "亏损"]):
            negative.append(company)

    parts = []
    if positive:
        parts.append(f"业绩预增: {', '.join(positive[:5])}等{len(positive)}家")
    if negative:
        parts.append(f"业绩预减: {', '.join(negative[:5])}等{len(negative)}家")

    return "; ".join(parts) if parts else f"今日{len(items)}家公司发布业绩预告"


def preprocess_news(items: list[NewsItem], hours: int = 6) -> dict:
    """
    预处理新闻列表

    返回:
        {
            "high_value": [...],  # 高价值新闻
            "earnings_summary": "...",  # 业绩预告汇总
            "stats": {...}  # 统计信息
        }
    """
    if not items:
        return {"high_value": [], "earnings_summary": "", "stats": {}}

    # 时间过滤
    beijing_tz = timezone(timedelta(hours=8))
    cutoff = datetime.now(beijing_tz) - timedelta(hours=hours)

    recent = []
    for item in items:
        if item.published_at is None:
            recent.append(item)
        else:
            pub_time = item.published_at
            if pub_time.tzinfo is None:
                pub_time = pub_time.replace(tzinfo=beijing_tz)
            if pub_time > cutoff:
                recent.append(item)

    # 分类：高价值优先，然后过滤低价值和业绩
    earnings = []
    low_value = []
    high_value = []

    for item in recent:
        title = item.title
        # 高价值关键词优先保留
        if is_high_value(title):
            high_value.append(item)
        elif is_earnings_news(title):
            earnings.append(item)
        elif is_low_value(title):
            low_value.append(item)
        else:
            # 其他新闻，长度>30才保留
            if len(title) > 30:
                high_value.append(item)

    # 去重高价值新闻
    high_value = deduplicate_news(high_value, threshold=0.5)

    # 汇总业绩预告
    earnings_summary = summarize_earnings(earnings)

    stats = {
        "total": len(items),
        "recent": len(recent),
        "high_value": len(high_value),
        "earnings": len(earnings),
        "low_value": len(low_value),
    }

    logger.info(f"预处理: {stats['total']}条 → {stats['high_value']}条高价值 + 业绩汇总")

    return {
        "high_value": high_value,
        "earnings_summary": earnings_summary,
        "stats": stats,
    }
