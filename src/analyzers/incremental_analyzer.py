"""增量分析器"""

import json
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from loguru import logger

from src.config import settings
from src.utils.timezone import today_beijing
from src.web.database import (
    get_daily_report,
    get_news_by_ids,
    get_market_summaries,
    upsert_daily_report,
    batch_upsert_focus_events,
)
from .prompts import (
    SYSTEM_PROMPT,
    INVESTMENT_ANALYSIS_PROMPT,
    INCREMENTAL_ANALYSIS_PROMPT,
)


class IncrementalAnalyzer:
    """增量分析器：支持实时更新当日报告"""

    def __init__(self):
        self.api_key = settings.claude_api_key
        self.base_url = settings.claude_base_url.rstrip("/")
        self.model = settings.claude_model

    async def analyze_new_news(
        self,
        new_news_ids: list[int],
        force_full: bool = False,
    ) -> dict:
        """分析新增新闻，更新当日报告"""
        today = today_beijing()

        # 获取现有报告
        existing_report = await get_daily_report(today)

        # 获取新增新闻
        new_news = await get_news_by_ids(new_news_ids)
        if not new_news:
            logger.info("没有新增新闻需要分析")
            return existing_report or {}

        # 获取历史上下文
        history_context = await self._get_history_context()

        # 决定是全量分析还是增量分析
        if not existing_report or force_full:
            result = await self._full_analysis(new_news, history_context)
        else:
            result = await self._incremental_analysis(
                existing_report, new_news, history_context
            )

        # 更新新闻ID列表
        existing_ids = existing_report.get("news_ids", []) if existing_report else []
        all_news_ids = list(set(existing_ids + new_news_ids))
        result["news_ids"] = all_news_ids
        result["report_date"] = today.isoformat()

        # 保存焦点事件到独立表（瀑布流累积）
        focus_events = result.get("focus_events", [])
        if focus_events:
            await batch_upsert_focus_events(focus_events)
            logger.info(f"已保存 {len(focus_events)} 个焦点事件")

        # 保存更新
        await upsert_daily_report(result)
        logger.info(f"报告已更新，版本: {result.get('version', 1)}")

        return result

    async def _get_history_context(self) -> str:
        """获取压缩后的历史上下文"""
        summaries = await get_market_summaries()
        if not summaries:
            return "暂无历史数据"

        context_parts = []
        for s in summaries[:4]:  # 最多4条
            period = s.get("period_type", "")
            summary = s.get("summary", "")[:100]
            context_parts.append(f"[{period}] {summary}")

        return "\n".join(context_parts) if context_parts else "暂无历史数据"

    def _format_news(self, news_list: list[dict]) -> str:
        """格式化新闻列表，包含URL供AI引用"""
        lines = []
        for i, item in enumerate(news_list[:30], 1):
            source = item.get("source", "")
            title = item.get("title", "")
            url = item.get("url", "")
            # 英文新闻使用中文摘要
            if item.get("language") == "en" and item.get("summary_zh"):
                title = item.get("summary_zh")
            # 格式：序号. [来源] 标题 | URL
            if url:
                lines.append(f"{i}. [{source}] {title} | {url}")
            else:
                lines.append(f"{i}. [{source}] {title}")
        return "\n".join(lines)

    async def _full_analysis(
        self, news_list: list[dict], history_context: str
    ) -> dict:
        """全量分析"""
        news_content = self._format_news(news_list)
        prompt = INVESTMENT_ANALYSIS_PROMPT.format(news_content=news_content)

        content = await self._call_api(prompt)
        return self._parse_response(content)

    async def _incremental_analysis(
        self,
        existing_report: dict,
        new_news: list[dict],
        history_context: str,
    ) -> dict:
        """增量分析"""
        # 格式化现有报告
        existing_summary = json.dumps({
            "one_liner": existing_report.get("one_liner"),
            "market_emotion": existing_report.get("market_emotion"),
            "focus_events_count": len(existing_report.get("focus_events", [])),
        }, ensure_ascii=False)

        new_news_content = self._format_news(new_news)

        prompt = INCREMENTAL_ANALYSIS_PROMPT.format(
            existing_report=existing_summary,
            new_news=new_news_content,
            history_context=history_context,
        )

        content = await self._call_api(prompt)
        return self._parse_response(content)

    async def _call_api(self, prompt: str) -> str:
        """调用 Claude API"""
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "max_tokens": 16384,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    def _parse_response(self, content: str) -> dict:
        """解析 AI 响应"""
        import re

        # 尝试提取 JSON 块
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content

        # 清理常见的 JSON 格式问题
        json_str = json_str.strip()
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        # 修复截断的 JSON - 尝试补全
        if json_str.count('{') > json_str.count('}'):
            json_str += '}' * (json_str.count('{') - json_str.count('}'))
        if json_str.count('[') > json_str.count(']'):
            json_str += ']' * (json_str.count('[') - json_str.count(']'))

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            # 尝试截取到最后一个完整的事件
            try:
                last_brace = json_str.rfind('}')
                if last_brace > 0:
                    truncated = json_str[:last_brace+1]
                    # 补全可能缺失的括号
                    truncated += ']' * (truncated.count('[') - truncated.count(']'))
                    truncated += '}' * (truncated.count('{') - truncated.count('}'))
                    data = json.loads(truncated)
                    logger.info("使用截断后的 JSON 解析成功")
                else:
                    return self._default_result()
            except:
                logger.debug(f"原始响应: {content[:500]}...")
                return self._default_result()

        return {
            "one_liner": data.get("one_liner", "暂无建议"),
            "market_emotion": data.get("market_emotion", 50),
            "market_narrative": data.get("market_narrative", ""),
            "emotion_suggestion": data.get("emotion_suggestion", ""),
            "focus_events": data.get("focus_events", []),
            "position_advices": data.get("position_advices", []),
            "risk_warnings": data.get("risk_warnings", []),
        }

    def _default_result(self) -> dict:
        """默认结果"""
        return {
            "one_liner": "AI 分析暂时不可用",
            "market_emotion": 50,
            "market_narrative": "",
            "emotion_suggestion": "",
            "focus_events": [],
            "position_advices": [],
            "risk_warnings": [],
        }
