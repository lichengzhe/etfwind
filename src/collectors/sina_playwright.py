"""新浪财经 7x24 Playwright 采集器"""

import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from loguru import logger

from src.models import NewsItem, SourceType
from .playwright_base import PlaywrightCollector


class SinaPlaywrightCollector(PlaywrightCollector):
    """新浪财经7x24快讯采集器（Playwright 版本）"""

    async def get_urls(self) -> list[str]:
        return ["https://finance.sina.com.cn/7x24/"]

    async def parse_page(self, url: str, content: str) -> list[NewsItem]:
        """解析新浪7x24页面"""
        soup = BeautifulSoup(content, "html.parser")
        items = []

        news_items = soup.select(".bd_i")

        for item in news_items[:30]:
            try:
                # 提取时间
                time_el = item.select_one(".bd_i_time_c")
                pub_time = None
                if time_el:
                    time_text = time_el.get_text(strip=True)
                    pub_time = self._parse_time(time_text)

                # 提取标题/内容
                content_el = item.select_one(".bd_i_txt_c a")
                title = content_el.get_text(strip=True) if content_el else ""

                # 提取链接
                news_url = url
                if content_el and content_el.get("href"):
                    news_url = content_el["href"]

                if not title or len(title) < 10:
                    continue

                items.append(NewsItem(
                    title=title,
                    content=title,
                    source="新浪7x24",
                    source_type=SourceType.DOMESTIC,
                    url=news_url,
                    published_at=pub_time,
                ))
            except Exception as e:
                logger.debug(f"解析新浪条目失败: {e}")
                continue

        return items

    def _parse_time(self, time_text: str) -> datetime:
        """解析时间文本 HH:MM:SS"""
        # 北京时间
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)

        match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", time_text)
        if match:
            hour, minute, second = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return now
