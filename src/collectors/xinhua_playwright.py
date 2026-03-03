"""新华社 Playwright 采集器"""

import re
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup
from loguru import logger

from src.models import NewsItem, SourceType, NewsCategory
from .playwright_base import PlaywrightCollector


class XinhuaPlaywrightCollector(PlaywrightCollector):
    """新华社要闻采集器（Playwright）"""

    async def get_urls(self) -> list[str]:
        return [
            "https://www.news.cn/politics/",
            "https://www.news.cn/world/",
        ]

    async def parse_page(self, url: str, content: str) -> list[NewsItem]:
        soup = BeautifulSoup(content, "html.parser")
        items = []
        seen = set()
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)

        is_world = "world" in url
        category = NewsCategory.INTERNATIONAL if is_world else NewsCategory.MACRO

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            title = a_tag.get_text(strip=True)

            if not title or len(title) < 8 or title in seen:
                continue
            # 过滤非新闻链接
            if not re.search(r"news\.cn/.+/\d{8}/", href):
                continue

            seen.add(title)
            full_url = href if href.startswith("http") else f"https:{href}"

            items.append(NewsItem(
                title=title,
                source="新华社",
                source_type=SourceType.DOMESTIC,
                url=full_url,
                published_at=now,
                category=category,
                language="zh",
            ))

        return items[:20]
