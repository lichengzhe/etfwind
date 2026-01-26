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
    MarketOverview,
    FundAdvice,
    FundType,
    Sentiment,
    SectorAnalysis,
    PolicyInsight,
)
from .prompts import INVESTMENT_ANALYSIS_PROMPT


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
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["content"][0]["text"]
        result = self._parse_response(content)

        # 取前30条有链接的新闻作为来源
        news_with_url = [n for n in news.items[:30] if n.url]

        return InvestmentReport(
            period=period,
            market_overview=result["market_overview"],
            policy_insights=result["policy_insights"],
            sector_analyses=result["sector_analyses"],
            fund_advices=result["fund_advices"],
            news_sources=news_with_url,
        )

    def _format_news(self, news: NewsCollection) -> str:
        """格式化新闻内容"""
        lines = []
        for i, item in enumerate(news.items[:30], 1):
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
            "market_overview": self._parse_overview(data.get("market_overview", {})),
            "policy_insights": self._parse_policies(data.get("policy_insights", [])),
            "sector_analyses": self._parse_sectors(data.get("sector_analyses", [])),
            "fund_advices": self._parse_advices(data.get("fund_advices", [])),
        }

    def _parse_overview(self, data: dict) -> MarketOverview:
        """解析市场概览"""
        return MarketOverview(
            summary=data.get("summary", "暂无市场总结"),
            key_events=data.get("key_events", []),
            risk_factors=data.get("risk_factors", []),
        )

    def _parse_policies(self, data: list) -> list[PolicyInsight]:
        """解析政策解读"""
        policies = []
        for item in data:
            policies.append(PolicyInsight(
                title=item.get("title", ""),
                background=item.get("background", ""),
                impact=item.get("impact", ""),
                opportunity=item.get("opportunity", ""),
                risk=item.get("risk", ""),
                action=item.get("action", ""),
            ))
        return policies

    def _parse_sectors(self, data: list) -> list[SectorAnalysis]:
        """解析行业分析"""
        sentiment_map = {
            "看多": Sentiment.BULLISH,
            "看空": Sentiment.BEARISH,
            "观望": Sentiment.NEUTRAL,
        }
        sectors = []
        for item in data:
            sentiment = sentiment_map.get(item.get("sentiment"), Sentiment.NEUTRAL)
            sectors.append(SectorAnalysis(
                name=item.get("name", ""),
                sentiment=sentiment,
                heat=item.get("heat", 50),
                reason=item.get("reason", ""),
                related_news=item.get("related_news", []),
                key_stocks=item.get("key_stocks", []),
            ))
        return sectors

    def _parse_advices(self, data: list) -> list[FundAdvice]:
        """解析基金建议"""
        advices = []
        type_map = {
            "股票型": FundType.STOCK,
            "债券型": FundType.BOND,
            "混合型": FundType.MIXED,
            "指数/ETF": FundType.INDEX,
        }
        sentiment_map = {
            "看多": Sentiment.BULLISH,
            "看空": Sentiment.BEARISH,
            "观望": Sentiment.NEUTRAL,
        }

        for item in data:
            fund_type = type_map.get(item.get("fund_type"))
            sentiment = sentiment_map.get(item.get("sentiment"))
            if fund_type and sentiment:
                advices.append(
                    FundAdvice(
                        fund_type=fund_type,
                        sentiment=sentiment,
                        reason=item.get("reason", ""),
                        attention_points=item.get("attention_points", []),
                    )
                )
        return advices

    def _default_result(self) -> dict[str, Any]:
        """默认结果"""
        return {
            "market_overview": MarketOverview(
                summary="AI 分析暂时不可用",
                key_events=[],
                risk_factors=[],
            ),
            "policy_insights": [],
            "sector_analyses": [],
            "fund_advices": [],
        }
