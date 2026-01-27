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

## 输出JSON
```json
{{
  "market_view": "🎯 市场状态一句话（20字内）",
  "narrative": "市场全景分析（200字，主要矛盾、资金流向、情绪、趋势，适当emoji）",
  "sectors": [
    {{
      "name": "芯片",
      "heat": 5,
      "direction": "利好",
      "analysis": "板块深度分析（80-100字，包含：驱动因素、产业链影响、资金态度、短期展望）",
      "news": [
        "🔥 美光涨5%创新高 → 存储芯片涨价周期确认，国产替代加速"
      ]
    }}
  ],
  "risk_level": "中"
}}
```

## 要求
- sectors 最多6个，按热度和重要性排序
- name 必须是：芯片/半导体/人工智能/通信/机器人/光伏/新能源/新能源车/锂电池/军工/医药/创新药/证券/银行/房地产/白酒/消费/农业/黄金/贵金属/有色/煤炭/钢铁/石油/恒生科技/港股/游戏/传媒/电力/互联网/汽车/家电/环保
- heat: 1-5星热度（5=极热，基于新闻数量、事件重要性、市场关注度）
- direction: 利好/利空/中性
- analysis: 深度分析，信息量要足，包含逻辑链条
- news: 1-3条，格式"📰 消息 → 解读"，消息和解读在一行
- risk_level: 低/中/高
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


async def analyze(items: list[NewsItem]) -> dict:
    """AI分析新闻"""
    base_url = settings.claude_base_url.rstrip("/")
    api_key = settings.claude_api_key
    model = settings.claude_model

    news_list = "\n".join([
        f"{i+1}. [{item.source}] {item.title}"
        for i, item in enumerate(items)
    ])

    prompt = ANALYSIS_PROMPT.format(count=len(items), news_list=news_list)

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

        return json.loads(text)
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
