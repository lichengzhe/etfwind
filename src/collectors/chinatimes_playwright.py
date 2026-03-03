"""中时新闻网 Playwright 采集器"""

import re
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup
from loguru import logger

from src.models import NewsItem, SourceType, NewsCategory
from .playwright_base import PlaywrightCollector


class ChinaTimesPlaywrightCollector(PlaywrightCollector):
    """中时新闻网热门新闻采集器（Playwright）"""

    async def get_urls(self) -> list[str]:
        return [
            "https://www.chinatimes.com/realtimenews/?chdtv",
        ]

    async def parse_page(self, url: str, content: str) -> list[NewsItem]:
        soup = BeautifulSoup(content, "html.parser")
        items = []
        seen = set()
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)

        # 中时新闻的文章链接格式
        for a_tag in soup.find_all("a", href=re.compile(r"chinatimes\.com/(realtimenews|newspapers|hottopic)")):
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 8 or title in seen:
                continue

            seen.add(title)
            href = a_tag.get("href", "")
            full_url = href if href.startswith("http") else f"https://www.chinatimes.com{href}"

            items.append(NewsItem(
                title=title,
                source="中時新聞網",
                source_type=SourceType.DOMESTIC,
                url=full_url,
                published_at=now,
                category=self._classify(title),
                language="zh-TW",
            ))

        return items[:30]

    def _classify(self, text: str) -> NewsCategory:
        if any(k in text for k in ["美", "日", "韓", "俄", "烏", "歐", "伊朗", "中東", "川普"]):
            return NewsCategory.INTERNATIONAL
        if any(k in text for k in ["台股", "央行", "經濟", "物價", "金管會"]):
            return NewsCategory.MACRO
        return NewsCategory.OTHER
