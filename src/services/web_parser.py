"""AI 网页内容解析服务"""

import json
from typing import Optional
from loguru import logger
from anthropic import AsyncAnthropic

from src.config import settings


class WebParser:
    """使用 AI 解析网页内容"""

    def __init__(self):
        self.client = AsyncAnthropic(
            api_key=settings.claude_api_key,
            base_url=settings.claude_base_url,
        )
        self.model = "claude-3-5-haiku-20241022"

    async def extract_news(self, html: str, source: str) -> list[dict]:
        """从 HTML 中提取新闻列表"""
        # 截取前 50000 字符避免超长
        html_truncated = html[:50000] if len(html) > 50000 else html

        prompt = f"""从以下网页 HTML 中提取财经新闻列表。

要求：
1. 提取所有新闻标题和摘要
2. 过滤广告和无关内容
3. 返回 JSON 数组格式

返回格式：
[{{"title": "新闻标题", "summary": "简短摘要"}}]

网页来源：{source}
HTML 内容：
{html_truncated}"""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            # 提取 JSON
            return self._parse_json(text)
        except Exception as e:
            logger.warning(f"AI 解析网页失败: {e}")
            return []

    def _parse_json(self, text: str) -> list[dict]:
        """从文本中提取 JSON"""
        import re
        # 尝试找到 JSON 数组
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return []


web_parser = WebParser()
