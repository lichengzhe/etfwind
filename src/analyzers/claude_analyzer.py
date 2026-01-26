"""Claude AI 分析器"""

import json
import re
from typing import Any

import httpx
from loguru import logger

from src.config import settings
from src.models import (
    NewsCollection,
    InvestmentReport,
    GlobalEvent,
    SectorOpportunity,
    PositionAdvice,
    PolicyInsight,
)
from .prompts import SYSTEM_PROMPT, INVESTMENT_ANALYSIS_PROMPT

MAX_NEWS_SOURCES = 20
MAX_NEWS_FOR_ANALYSIS = 30
MAX_RETRIES = 3


class ClaudeAnalyzer:
    """Claude 投资分析器"""

    def __init__(self):
        self.api_key = settings.claude_api_key
        self.base_url = settings.claude_base_url.rstrip("/")
        self.model = settings.claude_model

    async def analyze(
        self, news: NewsCollection, period: str
    ) -> InvestmentReport:
        """分析新闻并生成投资报告"""
        news_content = self._format_news(news)
        prompt = INVESTMENT_ANALYSIS_PROMPT.format(news_content=news_content)

        logger.info(f"开始 AI 分析，新闻数量: {news.count}")

        content = await self._call_api_with_retry(prompt)
        result = self._parse_response(content)

        news_with_url = [n for n in news.items[:MAX_NEWS_SOURCES] if n.url]

        return InvestmentReport(
            period=period,
            one_liner=result["one_liner"],
            market_emotion=result["market_emotion"],
            emotion_suggestion=result["emotion_suggestion"],
            global_events=result["global_events"],
            sector_opportunities=result["sector_opportunities"],
            policy_insights=result["policy_insights"],
            position_advices=result["position_advices"],
            risk_warnings=result["risk_warnings"],
            news_sources=news_with_url,
        )

    async def _call_api_with_retry(self, prompt: str) -> str:
        """调用 API，带重试机制"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/messages",
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                        },
                        json={
                            "model": self.model,
                            "max_tokens": 4096,
                            "system": SYSTEM_PROMPT,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["content"][0]["text"]
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                if e.response.status_code >= 500:
                    continue
                raise
            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"网络错误 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                continue
        logger.error(f"API 调用失败，已重试 {MAX_RETRIES} 次")
        raise last_error or Exception("API 调用失败")

    def _format_news(self, news: NewsCollection) -> str:
        """格式化新闻内容"""
        lines = []
        for i, item in enumerate(news.items[:MAX_NEWS_FOR_ANALYSIS], 1):
            time_str = ""
            if item.published_at:
                time_str = item.published_at.strftime("%H:%M")
            lines.append(f"{i}. [{item.source}] {time_str} {item.title}")
            if item.content and item.content != item.title:
                lines.append(f"   {item.content[:200]}")
        return "\n".join(lines)

    def _parse_response(self, content: str) -> dict[str, Any]:
        """解析 AI 响应"""
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return self._default_result()

        return {
            "one_liner": data.get("one_liner", "暂无建议"),
            "market_emotion": data.get("market_emotion", 50),
            "emotion_suggestion": data.get("emotion_suggestion", ""),
            "global_events": self._parse_events(data.get("global_events", [])),
            "sector_opportunities": self._parse_sectors(data.get("sector_opportunities", [])),
            "policy_insights": self._parse_policies(data.get("policy_insights", [])),
            "position_advices": self._parse_positions(data.get("position_advices", [])),
            "risk_warnings": data.get("risk_warnings", []),
        }

    def _parse_events(self, data: list) -> list[GlobalEvent]:
        """解析全球事件"""
        events = []
        for item in data:
            events.append(GlobalEvent(
                event=item.get("event", ""),
                region=item.get("region", ""),
                a_stock_impact=item.get("a_stock_impact", ""),
                affected_sectors=item.get("affected_sectors", []),
            ))
        return events

    def _parse_sectors(self, data: list) -> list[SectorOpportunity]:
        """解析板块机会"""
        sectors = []
        for item in data:
            sectors.append(SectorOpportunity(
                name=item.get("name", ""),
                signal=item.get("signal", "观望"),
                heat=item.get("heat", 50),
                crowding=item.get("crowding", 50),
                logic=item.get("logic", ""),
                contrarian_note=item.get("contrarian_note", ""),
                key_etf=item.get("key_etf", []),
            ))
        return sectors

    def _parse_policies(self, data: list) -> list[PolicyInsight]:
        """解析政策解读"""
        policies = []
        for item in data:
            policies.append(PolicyInsight(
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                investment_logic=item.get("investment_logic", ""),
                contrarian_view=item.get("contrarian_view", ""),
                action_suggestion=item.get("action_suggestion", ""),
                related_sectors=item.get("related_sectors", []),
            ))
        return policies

    def _parse_positions(self, data: list) -> list[PositionAdvice]:
        """解析仓位建议"""
        positions = []
        for item in data:
            positions.append(PositionAdvice(
                asset_type=item.get("asset_type", ""),
                current_position=item.get("current_position", "标配"),
                change=item.get("change", "持有"),
                reason=item.get("reason", ""),
            ))
        return positions

    def _default_result(self) -> dict[str, Any]:
        """默认结果"""
        return {
            "one_liner": "AI 分析暂时不可用",
            "market_emotion": 50,
            "emotion_suggestion": "",
            "global_events": [],
            "sector_opportunities": [],
            "policy_insights": [],
            "position_advices": [],
            "risk_warnings": [],
        }
