"""新闻预处理器 - 规则硬过滤 + AI精选"""

import asyncio
import os
import re
from loguru import logger

from src.models import NewsItem


# 硬过滤关键词 - 直接删除
HARD_FILTER = [
    "净利润", "预增", "预减", "预亏", "扭亏", "业绩快报", "业绩预告",
    "同比增长", "同比下降", "同比减少",
    "回购股份", "回购价格", "质押", "解押",
    "辞职", "辞去", "聘任", "任命",
    "询价转让", "询价申购", "IPO申请", "递交上市",
    "原料药上市", "药品注册", "专利授权",
]


def hard_filter(items: list[NewsItem]) -> list[NewsItem]:
    """规则硬过滤"""
    result = []
    for item in items:
        if not any(kw in item.title for kw in HARD_FILTER):
            result.append(item)
    logger.info(f"硬过滤: {len(items)}条 → {len(result)}条")
    return result


BATCH_FILTER_PROMPT = """从以下新闻中删除对ETF投资无价值的条目。

{news_list}

【必须删除】这些类型全部删掉：
1. 单个公司业绩预告（净利润增长/下降/预增/预亏/扭亏）
2. 个股公告（回购、质押、人事、合同、专利、询价、投资项目）
3. 个股涨停（除非标题明确说"XX板块"整体涨停）
4. 券商研报、目标价
5. 港股IPO
6. 海外小国数据

【保留】只保留：
- 宏观政策（央行、国务院、GDP/CPI/PMI）
- 行业整体趋势（存储涨价、光伏产能、芯片短缺等）
- 板块资金流向（北向资金、主力资金）
- 地缘重大（中美关税、制裁）
- 市场异常（暴涨暴跌、成交异常）

输出要删除的序号，用逗号分隔。如果都要保留，输出：无"""


async def filter_batch(client, items: list[NewsItem]) -> list[int]:
    """AI批量筛选，返回保留的索引"""
    news_list = "\n".join([
        f"{i+1}. {item.title[:80]}"
        for i, item in enumerate(items)
    ])

    try:
        model = os.getenv("CLAUDE_FILTER_MODEL", "claude-opus-4-5-20251101")
        response = await client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": BATCH_FILTER_PROMPT.format(news_list=news_list)
            }]
        )
        result = response.content[0].text.strip()

        if result == "无" or not result:
            return list(range(len(items)))  # 全保留

        # 解析要删除的序号
        delete_indices = set()
        for num in re.findall(r'\d+', result):
            idx = int(num) - 1
            if 0 <= idx < len(items):
                delete_indices.add(idx)

        # 返回保留的索引
        return [i for i in range(len(items)) if i not in delete_indices]
    except Exception as e:
        logger.warning(f"AI批量筛选失败: {e}")
        return list(range(len(items)))  # 失败时全保留


async def filter_news(items: list[NewsItem], batch_size: int = 30) -> list[NewsItem]:
    """规则硬过滤 + AI精选"""
    # 第一步：规则硬过滤
    filtered = hard_filter(items)

    if len(filtered) <= 50:
        return filtered

    # 第二步：AI精选（如果还是太多）
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(
        api_key=os.getenv("CLAUDE_API_KEY"),
        base_url=os.getenv("CLAUDE_BASE_URL"),
    )

    results = []
    total = len(filtered)

    for i in range(0, total, batch_size):
        batch = filtered[i:i+batch_size]
        indices = await filter_batch(client, batch)
        for idx in indices:
            results.append(batch[idx])
        logger.info(f"AI筛选: {i+len(batch)}/{total}, 本批保留{len(indices)}条")

    logger.info(f"最终: {len(items)}条 → {len(results)}条")
    return results


async def filter_single(client, title: str) -> bool:
    """AI判断单条新闻是否有价值"""
    try:
        response = await client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": FILTER_PROMPT.format(title=title)
            }]
        )
        result = response.content[0].text.strip()
        return result == "1"
    except Exception as e:
        logger.debug(f"AI筛选失败: {e}")
        return True  # 失败时保留


async def filter_news_batch(items: list[NewsItem], batch_size: int = 20) -> list[NewsItem]:
    """批量筛选新闻"""
    import os
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(
        api_key=os.getenv("CLAUDE_API_KEY"),
        base_url=os.getenv("CLAUDE_BASE_URL"),
    )

    results = []
    total = len(items)

    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        tasks = [filter_single(client, item.title) for item in batch]
        flags = await asyncio.gather(*tasks)

        for item, keep in zip(batch, flags):
            if keep:
                results.append(item)

        logger.info(f"筛选进度: {min(i+batch_size, total)}/{total}")

    logger.info(f"AI筛选: {total}条 → {len(results)}条")
    return results
