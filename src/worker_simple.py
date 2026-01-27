"""简化版 Worker - 采集+分析，结果存JSON文件"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from loguru import logger

from src.config import settings
from src.collectors import NewsAggregator
from src.analyzers.realtime import analyze

# 输出目录 - 放到 src/web/data 避免被 volume 覆盖
DATA_DIR = Path(__file__).parent / "web" / "data"
DATA_DIR.mkdir(exist_ok=True)


async def run():
    """运行采集和分析"""
    logger.info("开始采集新闻...")

    # 采集
    agg = NewsAggregator(include_international=True, include_playwright=True)
    try:
        news = await agg.collect_all()
        source_stats = dict(Counter(item.source for item in news.items))
        logger.info(f"采集到 {len(news.items)} 条新闻: {source_stats}")
    finally:
        await agg.close()

    # AI 分析
    logger.info("开始 AI 分析...")
    result = await analyze(news.items)

    # 保存结果
    beijing_tz = timezone(timedelta(hours=8))
    output = {
        "result": result,
        "updated_at": datetime.now(beijing_tz).isoformat(),
        "news_count": len(news.items),
        "source_stats": source_stats,
    }

    output_file = DATA_DIR / "latest.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(f"结果已保存到 {output_file}")

    return output


if __name__ == "__main__":
    asyncio.run(run())
