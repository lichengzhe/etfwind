"""后台 Worker 进程：定时采集新闻并触发增量分析"""

import asyncio
from datetime import date, datetime, timedelta, timezone

from loguru import logger

from src.collectors import NewsAggregator
from src.analyzers import IncrementalAnalyzer
from src.utils.timezone import today_beijing
from src.web.database import (
    init_db,
    store_news_batch,
    get_daily_report,
    get_daily_report_raw,
    finalize_daily_report,
)

# 配置
COLLECT_INTERVAL = 600  # 10分钟
MIN_NEWS_FOR_UPDATE = 1  # 最少新增新闻数触发更新
MIN_UPDATE_INTERVAL = 300  # 最少更新间隔（秒）5分钟


async def collect_and_store() -> list[int]:
    """采集新闻并存储，返回新增ID列表"""
    aggregator = NewsAggregator(include_international=True)
    try:
        collection = await aggregator.collect_all()

        # 转换为字典列表
        news_dicts = []
        for item in collection.items:
            news_dicts.append({
                "title": item.title,
                "content": item.content,
                "source": item.source,
                "source_type": item.source_type.value if hasattr(item.source_type, 'value') else str(item.source_type),
                "url": item.url,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "language": item.language,
                "summary_zh": item.summary_zh,
            })

        new_ids = await store_news_batch(news_dicts)
        logger.info(f"新增 {len(new_ids)} 条新闻")
        return new_ids
    finally:
        await aggregator.close()


async def should_update(new_ids: list[int]) -> bool:
    """判断是否需要触发更新"""
    if len(new_ids) < MIN_NEWS_FOR_UPDATE:
        return False

    report = await get_daily_report_raw()
    if not report:
        return True

    last_updated = report.get("last_updated")
    if not last_updated:
        return True

    if isinstance(last_updated, str):
        # last_updated 是 UTC ISO 格式字符串
        try:
            last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        except ValueError:
            # 如果解析失败，返回 True 触发更新
            return True

    elapsed = (datetime.now(timezone.utc) - last_updated).total_seconds()
    return elapsed >= MIN_UPDATE_INTERVAL


async def check_and_finalize_yesterday():
    """检查并归档昨日报告"""
    yesterday = today_beijing() - timedelta(days=1)
    report = await get_daily_report(yesterday)
    if report and not report.get("is_finalized"):
        await finalize_daily_report(yesterday)
        logger.info(f"已归档 {yesterday} 的报告")


async def run_cycle():
    """运行一个采集周期"""
    try:
        # 1. 采集新闻
        new_ids = await collect_and_store()

        # 2. 判断是否需要更新
        if await should_update(new_ids):
            logger.info("触发增量分析...")
            analyzer = IncrementalAnalyzer()
            await analyzer.analyze_new_news(new_ids)

        # 3. 每日归档检查
        await check_and_finalize_yesterday()

    except Exception as e:
        logger.error(f"Worker 周期错误: {e}")


async def main():
    """Worker 主循环"""
    logger.info("Worker 启动...")
    await init_db()

    while True:
        await run_cycle()
        logger.info(f"等待 {COLLECT_INTERVAL} 秒...")
        await asyncio.sleep(COLLECT_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
