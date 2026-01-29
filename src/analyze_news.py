"""分析新闻模块 - 读取 news_raw.json，输出 latest.json"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from loguru import logger

from src.config import settings
from src.analyzers.realtime import analyze
from src.services.fund_service import fund_service
from src.models import NewsItem

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR = DATA_DIR / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)


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


def load_history(days: int = 7) -> list[dict]:
    """读取历史归档"""
    history = []
    archive_files = sorted(ARCHIVE_DIR.glob("latest_*.json"), reverse=True)
    for f in archive_files[:days]:
        try:
            data = json.loads(f.read_text())
            date_str = f.stem.replace("latest_", "")
            foth = data.get("foth", {})
            if foth:
                history.append({"date": date_str, **foth})
        except Exception as e:
            logger.warning(f"读取 {f.name} 失败: {e}")
    return history


def format_history_context(history: list[dict]) -> str:
    """格式化历史上下文"""
    if not history:
        return ""
    lines = ["## 历史数据（FOTH Matrix）"]
    lines.append("\n### History Facts")
    for h in history[:3]:
        facts = h.get("facts", [])
        if facts:
            lines.append(f"**{h['date']}**: {'; '.join(facts[:3])}")
    lines.append("\n### History Opinions")
    for h in history[:3]:
        opinions = h.get("opinions", {})
        sectors = h.get("sectors", [])
        if opinions or sectors:
            sentiment = opinions.get("sentiment", "")
            sector_str = ", ".join(
                f"{s['name']}{'↑' if s['direction']=='利好' else '↓'}"
                for s in sectors[:3]
            )
            parts = [p for p in [sentiment, sector_str] if p]
            if parts:
                lines.append(f"**{h['date']}**: {' | '.join(parts)}")
    return "\n".join(lines)


def archive_data(beijing_tz):
    """归档当天数据"""
    today = datetime.now(beijing_tz).strftime("%Y-%m-%d")
    latest_file = DATA_DIR / "latest.json"
    daily_file = ARCHIVE_DIR / f"latest_{today}.json"

    if latest_file.exists() and not daily_file.exists():
        data = json.loads(latest_file.read_text())
        result = data.get("result", {})
        data["foth"] = {
            "facts": result.get("facts", [])[:5],
            "opinions": result.get("opinions", {}),
            "sectors": [
                {"name": s["name"], "heat": s["heat"], "direction": s["direction"]}
                for s in result.get("sectors", [])[:4]
            ],
            "market_view": result.get("market_view", ""),
        }
        daily_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        logger.info(f"归档: {daily_file.name}")


async def enrich_sectors_with_etfs(result: dict):
    """为板块匹配 ETF（复用 worker_simple 的逻辑）"""
    from src.worker_simple import ai_map_to_master_sectors

    sectors = result.get("sectors", [])
    if not sectors:
        return

    master_file = Path(__file__).parent.parent / "config" / "etf_master.json"
    if not master_file.exists():
        return

    etf_master = json.loads(master_file.read_text())
    master_sectors = etf_master.get("sector_list", [])
    sector_index = etf_master.get("sectors", {})

    ai_sector_names = [s["name"] for s in sectors]
    mapping = await ai_map_to_master_sectors(ai_sector_names, master_sectors)

    sector_etf_codes = {}
    for ai_name, master_names in mapping.items():
        codes = []
        for m_name in master_names:
            if m_name in sector_index:
                codes.extend(sector_index[m_name])
        sector_etf_codes[ai_name] = codes

    all_codes = set()
    for codes in sector_etf_codes.values():
        all_codes.update(codes)

    if all_codes:
        fund_data = await fund_service.batch_get_funds(list(all_codes))
        for sector in sectors:
            codes = sector_etf_codes.get(sector["name"], [])
            etfs = [fund_data[c] for c in codes if c in fund_data]
            etfs.sort(key=lambda x: x.get("amount_yi", 0), reverse=True)
            sector["etfs"] = etfs[:3]


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

    # 保存结果
    output = {
        "result": result,
        "updated_at": datetime.now(beijing_tz).isoformat(),
        "news_count": len(items),
        "source_stats": source_stats,
    }
    output_file = DATA_DIR / "latest.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(f"保存: {output_file}")

    # 保存新闻列表
    news_list = [
        {"title": item.title, "source": item.source, "url": item.url,
         "published_at": item.published_at.isoformat() if item.published_at else None}
        for item in items if item.url
    ]
    news_file = DATA_DIR / "news.json"
    news_file.write_text(json.dumps({
        "news": news_list,
        "updated_at": datetime.now(beijing_tz).isoformat(),
    }, ensure_ascii=False, indent=2))

    logger.info("分析完成")


if __name__ == "__main__":
    asyncio.run(run())
