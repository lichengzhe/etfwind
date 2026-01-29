"""采集新闻模块 - 只负责采集，输出 news_raw.json"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from loguru import logger

from src.collectors import NewsAggregator

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


async def collect():
    """采集所有源的新闻"""
    logger.info("=" * 50)
    logger.info("开始采集新闻")
    logger.info("=" * 50)

    agg = NewsAggregator(include_international=True, include_playwright=True)
    try:
        news = await agg.collect_all()
        source_stats = dict(Counter(item.source for item in news.items))
        logger.info(f"采集完成: {len(news.items)} 条新闻")
        for src, cnt in sorted(source_stats.items(), key=lambda x: -x[1]):
            logger.info(f"  - {src}: {cnt} 条")
    finally:
        await agg.close()

    # 保存原始新闻
    beijing_tz = timezone(timedelta(hours=8))
    news_raw = {
        "items": [
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at.isoformat() if item.published_at else None,
            }
            for item in news.items
        ],
        "source_stats": source_stats,
        "collected_at": datetime.now(beijing_tz).isoformat(),
    }

    output_file = DATA_DIR / "news_raw.json"
    output_file.write_text(json.dumps(news_raw, ensure_ascii=False, indent=2))
    logger.info(f"保存到 {output_file}")

    return news_raw


if __name__ == "__main__":
    asyncio.run(collect())
