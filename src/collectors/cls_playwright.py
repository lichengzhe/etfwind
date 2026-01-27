"""财联社 Playwright 采集器 - 采集电报快讯"""

import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from loguru import logger

from src.models import NewsItem, SourceType
from .playwright_base import PlaywrightCollector


class CLSPlaywrightCollector(PlaywrightCollector):
    """财联社电报采集器（Playwright 版本）"""

    async def get_urls(self) -> list[str]:
        return ["https://www.cls.cn/telegraph"]

    async def parse_page(self, url: str, content: str) -> list[NewsItem]:
        """解析财联社电报页面"""
        soup = BeautifulSoup(content, "html.parser")
        items = []

        # 查找电报列表
        telegraphs = soup.select(".telegraph-list .telegraph-item, .telegraph-content-box")

        for tg in telegraphs[:30]:  # 最多30条
            try:
                # 提取标题/内容
                title_el = tg.select_one(".telegraph-title, .title, h3")
                content_el = tg.select_one(".telegraph-content, .content, p")

                title = ""
                if title_el:
                    title = title_el.get_text(strip=True)
                if not title and content_el:
                    title = content_el.get_text(strip=True)[:100]

                if not title or len(title) < 10:
                    continue

                # 提取时间
                time_el = tg.select_one(".telegraph-time, .time, time")
                pub_time = None
                if time_el:
                    time_text = time_el.get_text(strip=True)
                    pub_time = self._parse_time(time_text)

                items.append(NewsItem(
                    title=title,
                    content=title,
                    source="财联社电报",
                    source_type=SourceType.DOMESTIC,
                    url=url,
                    published_at=pub_time,
                ))
            except Exception as e:
                logger.debug(f"解析电报条目失败: {e}")
                continue

        return items

    def _parse_time(self, time_text: str) -> datetime:
        """解析时间文本"""
        now = datetime.now(timezone.utc)
        # 匹配 HH:MM 格式
        match = re.search(r"(\d{1,2}):(\d{2})", time_text)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return now
