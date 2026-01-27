"""Playwright 网页采集器基类"""

from abc import abstractmethod
from typing import Optional
from loguru import logger

from src.models import NewsItem

# Playwright 延迟导入，避免未安装时报错
_playwright = None
_browser = None


async def get_browser():
    """获取共享的浏览器实例"""
    global _playwright, _browser
    if _browser is None:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
    return _browser


async def close_browser():
    """关闭浏览器"""
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


class PlaywrightCollector:
    """Playwright 网页采集器基类"""

    def __init__(self, timeout: float = 30000):
        self.timeout = timeout  # 毫秒

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def get_urls(self) -> list[str]:
        """返回要采集的 URL 列表"""
        pass

    @abstractmethod
    async def parse_page(self, url: str, content: str) -> list[NewsItem]:
        """解析页面内容，返回新闻列表"""
        pass

    async def fetch_page(self, url: str) -> Optional[str]:
        """使用 Playwright 获取页面内容"""
        try:
            browser = await get_browser()
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=self.timeout)
                await page.wait_for_load_state("networkidle", timeout=10000)
                content = await page.content()
                return content
            finally:
                await page.close()
        except Exception as e:
            logger.warning(f"{self.name} 获取页面失败 {url}: {e}")
            return None

    async def collect(self) -> list[NewsItem]:
        """采集新闻"""
        items = []
        urls = await self.get_urls()

        for url in urls:
            content = await self.fetch_page(url)
            if content:
                try:
                    page_items = await self.parse_page(url, content)
                    items.extend(page_items)
                except Exception as e:
                    logger.warning(f"{self.name} 解析页面失败 {url}: {e}")

        return items

    async def safe_collect(self) -> list[NewsItem]:
        """安全采集，捕获异常"""
        try:
            items = await self.collect()
            logger.info(f"{self.name} 采集到 {len(items)} 条新闻")
            return items
        except Exception as e:
            logger.error(f"{self.name} 采集失败: {e}")
            return []
