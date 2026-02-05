"""分析新闻模块 - 读取 news_raw.json，调用 worker_simple 分析"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from loguru import logger

from src.models import NewsItem
from src.config import settings
from src.worker_simple import (
    DATA_DIR, ARCHIVE_DIR,
    archive_data, load_history, format_history_context,
    enrich_sectors_with_etfs, save_news, build_sector_trends, update_review,
)
from src.analyzers.realtime import analyze
from src.notify import send_wechat_message, format_analysis_message


def load_news_raw() -> tuple[list[NewsItem], dict]:
    """从 news_raw.json 加载新闻"""
    raw_file = DATA_DIR / "news_raw.json"
    if not raw_file.exists():
        logger.warning("news_raw.json 不存在")
        return [], {}

    data = json.loads(raw_file.read_text())
    items = []
    for item in data.get("items", []):
        news_item = NewsItem(
            title=item["title"],
            source=item["source"],
            url=item.get("url", ""),
        )
        if item.get("published_at"):
            news_item.published_at = datetime.fromisoformat(item["published_at"])
        items.append(news_item)

    return items, data.get("source_stats", {})


async def run():
    """运行分析"""
    logger.info("=" * 50)
    logger.info("开始分析新闻")
    logger.info("=" * 50)

    beijing_tz = timezone(timedelta(hours=8))

    # 加载新闻
    items, source_stats = load_news_raw()
    if len(items) < 20:
        logger.warning(f"新闻不足 ({len(items)} < 20)")
        return

    logger.info(f"加载 {len(items)} 条新闻")

    # 归档旧数据
    archive_data(beijing_tz)

    # 加载历史
    history = load_history(days=7)
    history_context = format_history_context(history)
    if history_context:
        logger.info(f"📜 历史上下文:\n{history_context}")

    # 读取板块列表
    master_file = Path(__file__).parent.parent / "config" / "etf_master.json"
    sector_list = None
    if master_file.exists():
        master = json.loads(master_file.read_text())
        sector_list = master.get("sector_list", [])

    # AI 分析
    logger.info("AI 分析中...")
    result = await analyze(items, sector_list=sector_list, history_context=history_context)

    if not result or not result.get("sectors"):
        logger.error("分析失败")
        return

    logger.info(f"分析完成: {len(result['sectors'])} 个板块")

    # 匹配 ETF
    await enrich_sectors_with_etfs(result)

    # 构建7日趋势
    sector_trends = build_sector_trends(history, result.get("sectors", []))
    logger.info(f"构建趋势: {len(sector_trends)} 个板块")

    # 信号复盘
    review = await update_review(result, beijing_tz)

    # 过热预警（P1）：基于热度、方向、置信度的轻量规则
    overheat = None
    try:
        sectors = result.get("sectors", [])
        hot = [
            s for s in sectors
            if s.get("direction") == "利好"
            and s.get("heat", 0) >= 4
            and s.get("confidence", 0) >= 80
        ]
        if len(hot) >= 3:
            overheat = {
                "level": "过热",
                "note": "高热度板块过多，注意追高风险",
                "count": len(hot),
            }
        elif len(hot) == 2:
            overheat = {
                "level": "偏热",
                "note": "热点集中，注意高位波动",
                "count": len(hot),
            }
    except Exception:
        overheat = None

    # 保存结果
    output = {
        "result": result,
        "sector_trends": sector_trends,
        "review": review,
        "overheat": overheat,
        "updated_at": datetime.now(beijing_tz).isoformat(),
        "news_count": len(items),
        "source_stats": source_stats,
    }
    output_file = DATA_DIR / "latest.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(f"保存: {output_file}")

    # 保存新闻列表
    await save_news(items, beijing_tz)

    # 企业微信推送
    if settings.wechat_webhook_url:
        logger.info("发送企业微信推送...")
        message = format_analysis_message(output)
        await send_wechat_message(settings.wechat_webhook_url, message)

    logger.info("分析完成")


if __name__ == "__main__":
    asyncio.run(run())
