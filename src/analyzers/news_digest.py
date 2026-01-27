"""新闻聚合分析器 - 一次性喂给 Opus 全部新闻"""

import os
import json
from loguru import logger
from anthropic import AsyncAnthropic

from src.models import NewsItem


DIGEST_PROMPT = """你是A股ETF投资分析师。以下是今日采集的全部财经新闻，请提取对ETF投资有价值的信号。

## 新闻列表
{news_list}

## 任务
从上述新闻中提取：

1. **板块信号**：哪些板块利好/利空，依据是什么
2. **宏观事件**：央行政策、GDP/CPI数据、重大政策
3. **行业趋势**：供需变化、价格涨跌、产能情况
4. **资金动向**：北向资金、主力资金、板块资金流
5. **地缘风险**：中美关系、关税、制裁、战争

## 输出格式
```json
{
  "bullish_sectors": [
    {"sector": "存储芯片", "reason": "三星SK海力士涨价，存储短缺持续2-3年", "confidence": "高"}
  ],
  "bearish_sectors": [
    {"sector": "锂电池", "reason": "多家锂电公司预亏，行业产能过剩", "confidence": "中"}
  ],
  "macro_events": [
    {"event": "南京推电子房票", "impact": "地产政策边际放松"}
  ],
  "market_signals": [
    {"signal": "白银暴涨9%", "implication": "避险情绪升温"}
  ],
  "key_news_indices": [1, 5, 12, 23, 45]
}
```

注意：
- 业绩预告要聚合看：多家同行业公司预增/预亏反映行业趋势
- key_news_indices 是最重要的新闻序号（最多20条）
- 只输出JSON，不要其他内容"""


async def digest_news(items: list[NewsItem]) -> dict:
    """一次性分析全部新闻，提取板块信号"""
    client = AsyncAnthropic(
        api_key=os.getenv("CLAUDE_API_KEY"),
        base_url=os.getenv("CLAUDE_BASE_URL"),
    )

    # 构建新闻列表
    news_list = "\n".join([
        f"{i+1}. [{item.source}] {item.title}"
        for i, item in enumerate(items)
    ])

    logger.info(f"开始分析 {len(items)} 条新闻")

    try:
        response = await client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101"),
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": DIGEST_PROMPT.format(news_list=news_list)
            }]
        )

        result_text = response.content[0].text.strip()
        # 提取 JSON
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        result = json.loads(result_text)
        logger.info(f"分析完成: {len(result.get('bullish_sectors', []))}个利好, "
                   f"{len(result.get('bearish_sectors', []))}个利空")
        return result

    except Exception as e:
        logger.error(f"新闻分析失败: {e}")
        return {}
