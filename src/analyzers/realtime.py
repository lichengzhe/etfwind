"""简化版投资分析 - 无数据库，实时分析"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from collections import Counter
from loguru import logger
import httpx

from src.config import settings
from src.models import NewsItem
from src.collectors import NewsAggregator


# 全局缓存
_cache = {
    "result": None,
    "updated_at": None,
    "news_count": 0,
    "source_stats": {},  # 各来源采集统计
}

# 定时任务控制
_scheduler_task = None

ANALYSIS_PROMPT = """你是A股ETF投资分析师，分析新闻并输出投资参考。

## 新闻（共{count}条）
{news_list}

{history_context}

## 可选板块
{sector_list}

## 输出JSON
```json
{{
  "market_view": "🎯 市场状态一句话（20字内）",
  "summary": "📊 市场综述（200-250字）：融合关键事实与趋势分析，用📈📉💰🔥等emoji标注重点数据和转折，如「📈金价突破5500美元创新高」「🔥机器人板块订单放量」。行文流畅，一气呵成。",
  "sentiment": "偏乐观",
  "sectors": [
    {{
      "name": "芯片",
      "heat": 5,
      "direction": "利好",
      "analysis": "板块分析（80字）"
    }}
  ]
}}
```

## 要求
- market_view: 一句话概括今日市场主线
- summary: 综合分析，包含3-5个关键事实+趋势判断，用emoji突出重点
- sentiment: 整体情绪（偏乐观/偏悲观/分歧/平淡）
- sectors: 最多6个，按热度排序，name必须从"可选板块"中选择
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
    base_url = settings.claude_base_url.rstrip("/")
    api_key = settings.claude_api_key
    model = settings.claude_model

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
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"].strip()

        # 提取 JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        # 尝试解析，失败则修复常见问题
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            import re
            logger.warning(f"JSON 解析失败，尝试修复: {e}")
            # 修复：中文引号替换
            text = text.replace('"', '"').replace('"', '"')
            # 修复：移除尾部逗号
            text = re.sub(r',(\s*[}\]])', r'\1', text)
            # 修复：字符串内的换行（更彻底的方法）
            def fix_newlines(m):
                return m.group(0).replace('\n', ' ').replace('\r', '')
            text = re.sub(r'"[^"]*"', fix_newlines, text)
            try:
                return json.loads(text)
            except json.JSONDecodeError as e2:
                logger.error(f"修复后仍失败: {e2}")
                logger.error(f"问题文本片段: {text[max(0,e2.pos-50):e2.pos+50]}")
                raise
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
