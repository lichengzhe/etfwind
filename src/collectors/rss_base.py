"""RSS 采集器基类"""

import re
from datetime import datetime
from typing import Optional
from email.utils import parsedate_to_datetime

from loguru import logger

from src.models import NewsItem, NewsCategory, SourceType
from .base import BaseCollector


class RSSCollector(BaseCollector):
    """RSS 新闻采集器基类"""

    RSS_URL: str = ""
    SOURCE_NAME: str = ""
    SOURCE_TYPE: SourceType = SourceType.INTERNATIONAL
    LANGUAGE: str = "en"

    async def collect(self) -> list[NewsItem]:
        """采集 RSS 新闻"""
        if not self.RSS_URL:
            return []

        client = await self.get_client()
        try:
            response = await client.get(self.RSS_URL)
            response.raise_for_status()
            return self._parse_rss(response.text)
        except Exception as e:
            logger.error(f"{self.SOURCE_NAME} RSS 采集失败: {e}")
            return []

    def _sanitize_xml(self, xml_content: str) -> str:
        """清理不规范的 RSS XML（如未转义的 & 符号）"""
        # 将未转义的 & 替换为 &amp;，跳过已合法的实体引用
        return re.sub(r'&(?!(?:amp|lt|gt|apos|quot|#\d+|#x[0-9a-fA-F]+);)', '&amp;', xml_content)

    def _parse_rss(self, xml_content: str) -> list[NewsItem]:
        """解析 RSS XML"""
        import xml.etree.ElementTree as ET
        xml_content = self._sanitize_xml(xml_content)

        items = []
        try:
            root = ET.fromstring(xml_content)
            # 处理 RSS 2.0 格式
            for item in root.findall(".//item"):
                news = self._parse_item(item)
                if news:
                    items.append(news)
            # 处理 Atom 格式
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns):
                news = self._parse_atom_entry(entry, ns)
                if news:
                    items.append(news)
        except ET.ParseError as e:
            logger.error(f"RSS XML 解析失败: {e}")
        return items

    def _parse_item(self, item) -> Optional[NewsItem]:
        """解析 RSS item"""
        try:
            title = self._get_text(item, "title")
            if not title:
                return None

            content = self._get_text(item, "description") or ""
            link = self._get_text(item, "link")
            pub_date = self._get_text(item, "pubDate")

            published_at = None
            if pub_date:
                try:
                    published_at = parsedate_to_datetime(pub_date)
                except Exception:
                    pass

            return NewsItem(
                title=title[:200],
                content=content[:500],
                source=self.SOURCE_NAME,
                source_type=self.SOURCE_TYPE,
                url=link,
                published_at=published_at,
                category=NewsCategory.INTERNATIONAL,
                language=self.LANGUAGE,
            )
        except Exception as e:
            logger.debug(f"解析 RSS item 失败: {e}")
            return None

    def _parse_atom_entry(self, entry, ns) -> Optional[NewsItem]:
        """解析 Atom entry"""
        try:
            title_el = entry.find("atom:title", ns)
            title = title_el.text if title_el is not None else None
            if not title:
                return None

            content_el = entry.find("atom:summary", ns)
            content = content_el.text if content_el is not None else ""

            link_el = entry.find("atom:link", ns)
            link = link_el.get("href") if link_el is not None else None

            updated_el = entry.find("atom:updated", ns)
            published_at = None
            if updated_el is not None and updated_el.text:
                try:
                    published_at = datetime.fromisoformat(
                        updated_el.text.replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            return NewsItem(
                title=title[:200],
                content=content[:500] if content else "",
                source=self.SOURCE_NAME,
                source_type=self.SOURCE_TYPE,
                url=link,
                published_at=published_at,
                category=NewsCategory.INTERNATIONAL,
                language=self.LANGUAGE,
            )
        except Exception as e:
            logger.debug(f"解析 Atom entry 失败: {e}")
            return None

    def _get_text(self, element, tag: str) -> Optional[str]:
        """获取子元素文本"""
        child = element.find(tag)
        return child.text if child is not None else None
