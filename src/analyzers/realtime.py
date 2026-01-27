"""简化版投资分析 - 无数据库，实时分析"""

import asyncio
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger
import httpx

from src.models import NewsItem
from src.collectors import NewsAggregator


# 全局缓存
_cache = {
    "result": None,
    "updated_at": None,
    "news_count": 0,
}

ANALYSIS_PROMPT = """你是A股ETF投资分析师。分析以下财经新闻，输出投资参考。

## 新闻（共{count}条）
{news_list}

## 输出要求
```json
{{
  "market_view": "当前市场状态一句话总结（20字内）",
  "narrative": "市场全景分析（150字，包含主要矛盾、情绪、趋势）",
  "sectors": [
    {{"name": "存储芯片", "direction": "利好", "reason": "涨价+短缺", "etf": "芯片ETF(512760)"}},
    {{"name": "锂电池", "direction": "利空", "reason": "多家预亏", "etf": "锂电池ETF(159840)"}}
  ],
  "events": [
    {{"title": "白银暴涨9%", "analysis": "避险情绪升温...", "suggestion": "持有者可减仓"}}
  ],
  "risk_level": "中"
}}
```

注意：
- sectors 最多6个，按重要性排序
- events 最多5个重要事件
- 业绩预告要聚合看行业趋势
- risk_level: 低/中/高
"""


async def collect_news() -> list[NewsItem]:
    """采集所有源的新闻"""
    agg = NewsAggregator(include_international=True, include_playwright=True)
    try:
        news = await agg.collect_all()
        return news.items
    finally:
        await agg.close()


async def analyze(items: list[NewsItem]) -> dict:
    """AI分析新闻"""
    base_url = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com")
    api_key = os.getenv("CLAUDE_API_KEY")
    model = os.getenv("CLAUDE_MODEL", "claude-opus-4-5")

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
    items = await collect_news()
    logger.info(f"采集到 {len(items)} 条新闻")

    logger.info("开始AI分析...")
    result = await analyze(items)

    beijing_tz = timezone(timedelta(hours=8))
    _cache = {
        "result": result,
        "updated_at": datetime.now(beijing_tz),
        "news_count": len(items),
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
