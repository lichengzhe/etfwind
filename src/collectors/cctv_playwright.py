"""央视新闻 Playwright 采集器"""

import re
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup
from loguru import logger

from src.models import NewsItem, SourceType, NewsCategory
from .playwright_base import PlaywrightCollector


class CCTVPlaywrightCollector(PlaywrightCollector):
    """央视新闻采集器（Playwright）"""

    async def get_urls(self) -> list[str]:
        return ["https://news.cctv.com/"]

    async def parse_page(self, url: str, content: str) -> list[NewsItem]:
        soup = BeautifulSoup(content, "html.parser")
        items = []
        seen = set()
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)

        for a_tag in soup.find_all("a", href=re.compile(r"https?://news\.cctv\.com/\d{4}/\d{2}/\d{2}/")):
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 8 or title in seen:
                continue

            seen.add(title)
            href = a_tag.get("href", "")

            items.append(NewsItem(
                title=title,
                source="央视新闻",
                source_type=SourceType.DOMESTIC,
                url=href,
                published_at=now,
                category=NewsCategory.MACRO,
                language="zh",
            ))

        return items[:20]
