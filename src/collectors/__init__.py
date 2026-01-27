"""采集器模块"""

import asyncio
from datetime import datetime

from loguru import logger

from src.models import NewsItem, NewsCollection
from .base import BaseCollector
from .cls_news import CLSNewsCollector
from .eastmoney import EastMoneyCollector
from .sina_finance import SinaFinanceCollector
from .rss_base import RSSCollector
from .cnbc import CNBCCollector
from .bloomberg import BloombergCollector
from .wsj import WSJCollector

# Playwright 采集器（可选）
_playwright_collectors = []
try:
    from .playwright_base import PlaywrightCollector, close_browser
    from .cls_playwright import CLSPlaywrightCollector
    from .sina_playwright import SinaPlaywrightCollector
    _playwright_collectors = [CLSPlaywrightCollector, SinaPlaywrightCollector]
except ImportError:
    close_browser = None
    pass


class NewsAggregator:
    """新闻聚合器"""

    def __init__(self, include_international: bool = True, include_playwright: bool = True):
        self.collectors: list[BaseCollector] = [
            CLSNewsCollector(),
            EastMoneyCollector(),
            SinaFinanceCollector(),
        ]
        if include_international:
            self.collectors.extend([
                CNBCCollector(),
                BloombergCollector(),
                WSJCollector(),
            ])
        # Playwright 采集器
        self.playwright_collectors = []
        if include_playwright and _playwright_collectors:
            self.playwright_collectors = [c() for c in _playwright_collectors]

    async def collect_all(self) -> NewsCollection:
        """并发采集所有来源的新闻"""
        # 普通采集器
        tasks = [c.safe_collect() for c in self.collectors]
        results = await asyncio.gather(*tasks)

        all_items: list[NewsItem] = []
        for items in results:
            all_items.extend(items)

        # Playwright 采集器（串行执行避免资源竞争）
        for pw_collector in self.playwright_collectors:
            try:
                pw_items = await pw_collector.safe_collect()
                all_items.extend(pw_items)
            except Exception as e:
                logger.warning(f"Playwright 采集失败: {e}")

        # 去重（按标题）
        seen_titles = set()
        unique_items = []
        for item in all_items:
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                unique_items.append(item)

        # 按时间排序（处理时区混合问题）
        def get_sort_key(x):
            if x.published_at is None:
                return datetime.min
            # 移除时区信息以便比较
            if x.published_at.tzinfo is not None:
                return x.published_at.replace(tzinfo=None)
            return x.published_at

        unique_items.sort(key=get_sort_key, reverse=True)

        logger.info(f"共采集 {len(unique_items)} 条去重新闻")

        return NewsCollection(items=unique_items)

    async def close(self):
        """关闭所有采集器"""
        for collector in self.collectors:
            await collector.close()
        # 关闭 Playwright 浏览器
        if close_browser:
            await close_browser()


__all__ = [
    "BaseCollector",
    "RSSCollector",
    "CLSNewsCollector",
    "EastMoneyCollector",
    "SinaFinanceCollector",
    "CNBCCollector",
    "BloombergCollector",
    "WSJCollector",
    "NewsAggregator",
]
