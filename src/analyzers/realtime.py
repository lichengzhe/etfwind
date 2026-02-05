"""简化版投资分析 - 无数据库，实时分析"""

import asyncio
from datetime import datetime, timezone, timedelta
from collections import Counter
from loguru import logger
from src.config import settings
from src.models import NewsItem
from src.collectors import NewsAggregator
from src.services.ai_client import AIClient, AIRequest, parse_json_with_repair


# 全局缓存
_cache = {
    "result": None,
    "updated_at": None,
    "news_count": 0,
    "source_stats": {},  # 各来源采集统计
}

# 定时任务控制
_scheduler_task = None

ANALYSIS_PROMPT = """你是A股ETF投资分析师，专注板块轮动和ETF配置建议。

## 核心交易理念（必须遵守）

### 1. 板块轮动规律
- 政策驱动 > 业绩驱动 > 资金驱动
- 主线板块持续性强，跟风板块一日游
- 板块见顶信号：龙头滞涨、补涨股活跃

### 2. ETF配置原则
- 趋势确立后介入，不抄底不追高
- 板块热度≥4且方向利好时可关注
- 连续利空或热度骤降时回避

### 3. 风险识别要点
- 🚨 政策利空（监管、限制、处罚）
- 🚨 行业景气下行（业绩预亏、产能过剩）
- 🚨 资金出逃（北向大幅流出、主力减仓）

## 新闻数据（共{count}条）
{news_list}

{history_context}

## 可选板块
{sector_list}

## 商品周期规律
黄金→白银→铜→石油→农产品（依次传导，领涨品种切换表示周期演进）

## 输出JSON
```json
{{
  "market_view": "🎯 一句话核心结论（25字内，直接说今天该关注什么）",
  "summary": "市场综述（200字）：融合关键事实与趋势，用emoji标注重点",
  "sentiment": "偏乐观/偏悲观/分歧/平淡",
  "sectors": [
    {{
      "name": "板块名（从可选板块选）",
      "heat": 5,
      "direction": "利好/利空/中性",
      "confidence": 80,
      "analysis": "板块分析（80字）：包含驱动因素+风险提示",
      "signal": "🟢买入/🟡观望/🔴回避"
    }}
  ],
  "risk_alerts": ["风险1：具体描述", "风险2：具体描述"],
  "opportunity_hints": ["机会1：具体描述", "机会2：具体描述"],
  "commodity_cycle": {{
    "stage": 2,
    "stage_name": "白银跟涨期",
    "leader": "gold/silver/copper/oil/corn",
    "analysis": "周期分析（30字）"
  }}
}}
```

## 输出要求
1. market_view: 一句话说清今日主线，有操作指引性
2. sectors: 最多6个板块，按热度排序
   - signal: 基于热度+方向+风险综合判断
   - confidence: 0-100 分，代表信号把握度
3. risk_alerts: 今日需警惕的2-3个风险点
4. opportunity_hints: 今日值得关注的2-3个机会
5. commodity_cycle.leader: 当前领涨商品（用于前端高亮）
6. 重要：JSON字符串中禁止使用中文引号""，只用英文引号或不用引号
"""


async def collect_news() -> tuple[list[NewsItem], dict]:
    """采集所有源的新闻，返回 (新闻列表, 来源统计)"""
    agg = NewsAggregator(include_international=True, include_playwright=True)
    try:
        news = await agg.collect_all()
        # 统计各来源数量
        stats = Counter(item.source for item in news.items)
        return news.items, dict(stats)
    finally:
        await agg.close()


async def analyze(items: list[NewsItem], sector_list: list[str] = None, history_context: str = "") -> dict:
    """AI分析新闻

    Args:
        items: 新闻列表
        sector_list: 可选板块列表（从 etf_master.json 读取）
        history_context: 历史分析上下文（用于趋势对比）
    """
    news_list = "\n".join([
        f"{i+1}. [{item.source}] {item.title}"
        for i, item in enumerate(items)
    ])

    # 默认板块列表（与 etf_master.json 同步，含常用别名）
    if not sector_list:
        sector_list = [
            # 科技
            "芯片", "半导体", "人工智能", "软件", "通信", "机器人", "互联网",
            # 新能源
            "光伏", "新能源", "锂电池", "新能源车",
            # 金融
            "证券", "银行", "券商",
            # 消费
            "白酒", "消费", "医药", "创新药", "家电", "汽车",
            # 周期
            "黄金", "贵金属", "有色", "煤炭", "钢铁", "石油", "化工",
            # 其他
            "军工", "农业", "房地产", "电力", "环保",
            "恒生科技", "港股", "游戏", "传媒",
        ]

    sector_str = "/".join(sector_list)
    prompt = ANALYSIS_PROMPT.format(
        count=len(items),
        news_list=news_list,
        history_context=history_context,
        sector_list=sector_str
    )

    try:
        client = AIClient()
        text = await client.send(AIRequest(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            timeout=120,
            model=settings.claude_model,
        ))
        return parse_json_with_repair(text, fix_newlines=True)
    except Exception as e:
        logger.error(f"分析失败: {e}")
        return {}


async def refresh() -> dict:
    """刷新分析结果"""
    global _cache

    logger.info("开始采集新闻...")
    items, source_stats = await collect_news()
    logger.info(f"采集到 {len(items)} 条新闻: {source_stats}")

    logger.info("开始AI分析...")
    result = await analyze(items)

    beijing_tz = timezone(timedelta(hours=8))
    _cache = {
        "result": result,
        "updated_at": datetime.now(beijing_tz),
        "news_count": len(items),
        "source_stats": source_stats,
    }

    logger.info("分析完成")
    return result


def get_cache() -> dict:
    """获取缓存的分析结果"""
    return _cache


async def get_or_refresh(max_age_minutes: int = 60) -> dict:
    """获取结果，过期则刷新"""
    global _cache

    if _cache["result"] is None:
        return await refresh()

    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    age = now - _cache["updated_at"]

    if age.total_seconds() > max_age_minutes * 60:
        return await refresh()

    return _cache["result"]


async def _scheduler_loop(interval_minutes: int = 30):
    """定时刷新循环"""
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            logger.info(f"定时刷新开始 (间隔 {interval_minutes} 分钟)")
            await refresh()
        except asyncio.CancelledError:
            logger.info("定时任务已取消")
            break
        except Exception as e:
            logger.error(f"定时刷新失败: {e}")


def start_scheduler(interval_minutes: int = 30):
    """启动定时任务"""
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduler_loop(interval_minutes))
        logger.info(f"定时任务已启动，间隔 {interval_minutes} 分钟")


def stop_scheduler():
    """停止定时任务"""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("定时任务已停止")
