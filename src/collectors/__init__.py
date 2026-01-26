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
from .reuters import ReutersCollector
from .bloomberg import BloombergCollector
from .wsj import WSJCollector


class NewsAggregator:
    """新闻聚合器"""

    def __init__(self, include_international: bool = True):
        self.collectors: list[BaseCollector] = [
            CLSNewsCollector(),
            EastMoneyCollector(),
            SinaFinanceCollector(),
        ]
        if include_international:
            self.collectors.extend([
                ReutersCollector(),
                BloombergCollector(),
                WSJCollector(),
            ])

    async def collect_all(self) -> NewsCollection:
        """并发采集所有来源的新闻"""
        tasks = [c.safe_collect() for c in self.collectors]
        results = await asyncio.gather(*tasks)

        all_items: list[NewsItem] = []
        for items in results:
            all_items.extend(items)

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


__all__ = [
    "BaseCollector",
    "RSSCollector",
    "CLSNewsCollector",
    "EastMoneyCollector",
    "SinaFinanceCollector",
    "ReutersCollector",
    "BloombergCollector",
    "WSJCollector",
    "NewsAggregator",
]
