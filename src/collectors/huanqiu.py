"""环球网新闻采集器"""

import re
from datetime import datetime, date, timezone, timedelta

from bs4 import BeautifulSoup
from loguru import logger

from src.models import NewsItem, NewsCategory
from .base import BaseCollector


class HuanqiuCollector(BaseCollector):
    """环球网首页新闻采集器

    抓取 huanqiu.com 首页要闻，解析标题和链接。
    """

    PAGE_URL = "https://www.huanqiu.com/"

    async def collect(self) -> list[NewsItem]:
        client = await self.get_client()
        response = await client.get(self.PAGE_URL, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        items: list[NewsItem] = []
        seen = set()

        for a_tag in soup.find_all("a", href=re.compile(r"https?://\w+\.huanqiu\.com/article/")):
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 8 or title in seen:
                continue
            seen.add(title)

            url = a_tag.get("href", "")
            beijing_tz = timezone(timedelta(hours=8))
            now = datetime.now(beijing_tz)

            items.append(NewsItem(
                title=title,
                source="环球网",
                url=url,
                published_at=now,
                category=self._classify(title),
                language="zh",
            ))

        return items[:30]

    def _classify(self, text: str) -> NewsCategory:
        if any(k in text for k in ["美国", "日本", "俄", "欧洲", "英国", "伊朗", "中东", "联合国"]):
            return NewsCategory.INTERNATIONAL
        if any(k in text for k in ["经济", "GDP", "贸易", "金融"]):
            return NewsCategory.MACRO
        return NewsCategory.OTHER
