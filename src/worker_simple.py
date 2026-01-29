"""简化版 Worker - 采集+分析，结果存JSON文件"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from loguru import logger

from src.config import settings
from src.collectors import NewsAggregator
from src.analyzers.realtime import analyze
from src.services.fund_service import fund_service

# 输出目录
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# 归档目录
ARCHIVE_DIR = DATA_DIR / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)


def archive_data(beijing_tz):
    """归档数据：当天保留，7天每天一份，1月每周一份，1年每月一份"""
    logger.info("=== 开始归档数据 ===")
    now = datetime.now(beijing_tz)
    today = now.strftime("%Y-%m-%d")

    # 归档 latest.json 到当天（含精简摘要）
    latest_file = DATA_DIR / "latest.json"
    if latest_file.exists():
        daily_file = ARCHIVE_DIR / f"latest_{today}.json"
        if not daily_file.exists():
            # 读取并添加摘要
            data = json.loads(latest_file.read_text())
            result = data.get("result", {})
            # FOTH Matrix 归档
            data["foth"] = {
                "facts": result.get("facts", [])[:5],
                "opinions": result.get("opinions", {}),
                "sectors": [
                    {"name": s["name"], "heat": s["heat"], "direction": s["direction"]}
                    for s in result.get("sectors", [])[:4]
                ],
                "market_view": result.get("market_view", ""),
                "commodity_cycle": result.get("commodity_cycle", {}),
            }
            daily_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            logger.info(f"✅ 归档成功: {daily_file.name}")
        else:
            logger.info(f"⏭️ 今日已归档: {daily_file.name}")
    else:
        logger.warning("⚠️ latest.json 不存在，跳过归档")

    # 清理旧归档
    cleanup_archives(now)


def cleanup_archives(now: datetime):
    """清理归档：7天内每天保留，30天内每周保留，1年内每月保留"""
    archive_files = sorted(ARCHIVE_DIR.glob("latest_*.json"))
    logger.info(f"📁 归档目录共 {len(archive_files)} 个文件")

    cleaned = 0
    for f in archive_files:
        # 解析日期
        try:
            date_str = f.stem.replace("latest_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        days_ago = (now.replace(tzinfo=None) - file_date).days

        # 7天内：全部保留
        if days_ago <= 7:
            continue

        # 7-30天：只保留周一
        if days_ago <= 30:
            if file_date.weekday() != 0:  # 不是周一
                f.unlink()
                logger.info(f"清理归档 {f.name}（非周一）")
            continue

        # 30天-1年：只保留每月1号
        if days_ago <= 365:
            if file_date.day != 1:  # 不是1号
                f.unlink()
                logger.info(f"清理归档 {f.name}（非月初）")
            continue

        # 超过1年：删除
        f.unlink()
        logger.info(f"清理归档 {f.name}（超过1年）")


def load_history(days: int = 7) -> list[dict]:
    """读取近N天的历史归档数据（FOTH Matrix）"""
    logger.info(f"=== 读取历史数据 (最近{days}天) ===")
    history = []

    archive_files = sorted(ARCHIVE_DIR.glob("latest_*.json"), reverse=True)
    logger.info(f"📁 找到 {len(archive_files)} 个归档文件")

    for f in archive_files[:days]:
        try:
            data = json.loads(f.read_text())
            date_str = f.stem.replace("latest_", "")
            result = data.get("result", {})

            # 新格式：FOTH
            foth = data.get("foth", {})
            if foth:
                history.append({"date": date_str, **foth})
                facts_count = len(foth.get("facts", []))
                logger.info(f"  ✅ {date_str}: {facts_count} facts (foth)")
                continue

            # 兼容旧格式
            if result.get("sectors"):
                history.append({
                    "date": date_str,
                    "facts": result.get("facts", result.get("key_events", [])),
                    "opinions": result.get("opinions", {}),
                    "sectors": [
                        {"name": s["name"], "heat": s["heat"], "direction": s["direction"]}
                        for s in result.get("sectors", [])[:4]
                    ],
                    "market_view": result.get("market_view", ""),
                })
                logger.info(f"  ✅ {date_str}: 从 result 提取")
            else:
                logger.info(f"  ⏭️ {date_str}: 无数据")
        except Exception as e:
            logger.warning(f"  ❌ 读取 {f.name} 失败: {e}")

    logger.info(f"📊 成功加载 {len(history)} 天历史数据")
    return history


def format_history_context(history: list[dict]) -> str:
    """格式化历史数据为 AI 上下文（FOTH Matrix）

    分离展示 Facts 和 Opinions，让 AI 独立判断
    """
    if not history:
        return ""

    lines = ["## 历史数据（FOTH Matrix）"]

    # History Facts
    lines.append("\n### History Facts（客观事件）")
    for h in history[:3]:
        facts = h.get("facts", [])
        if facts:
            lines.append(f"**{h['date']}**: {'; '.join(facts[:3])}")

    # History Opinions
    lines.append("\n### History Opinions（市场情绪）")
    for h in history[:3]:
        opinions = h.get("opinions", {})
        sectors = h.get("sectors", [])
        if opinions or sectors:
            sentiment = opinions.get("sentiment", "")
            hot_words = opinions.get("hot_words", [])
            sector_str = ", ".join(
                f"{s['name']}{'↑' if s['direction']=='利好' else '↓'}"
                for s in sectors[:3]
            )
            parts = []
            if sentiment:
                parts.append(sentiment)
            if hot_words:
                parts.append(f"热词:{','.join(hot_words[:3])}")
            if sector_str:
                parts.append(f"热点:{sector_str}")
            if parts:
                lines.append(f"**{h['date']}**: {' | '.join(parts)}")

    # History Commodity Cycle（商品周期）
    lines.append("\n### History Commodity Cycle（商品周期）")
    for h in history[:3]:
        cycle = h.get("commodity_cycle", {})
        if cycle:
            stage_name = cycle.get("stage_name", "")
            if stage_name:
                lines.append(f"**{h['date']}**: {stage_name}")

    return "\n".join(lines)


async def save_news(news_items, beijing_tz):
    """保存新闻列表"""
    aggregator_urls = [
        "https://www.jin10.com/",
        "https://wallstreetcn.com/live",
        "https://kuaixun.eastmoney.com/",
    ]
    news_list = [
        {
            "title": item.title,
            "source": item.source,
            "url": item.url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
        }
        for item in news_items
        if item.url and not any(item.url.startswith(agg) for agg in aggregator_urls)
    ]
    news_file = DATA_DIR / "news.json"
    news_file.write_text(json.dumps({
        "news": news_list,
        "updated_at": datetime.now(beijing_tz).isoformat(),
    }, ensure_ascii=False, indent=2))
    logger.info(f"新闻列表已保存到 {news_file}")


async def run():
    """运行采集和分析"""
    logger.info("=" * 50)
    logger.info("🚀 ETF风向标 - 开始运行")
    logger.info("=" * 50)

    # 采集
    logger.info("=== 第1步: 采集新闻 ===")
    agg = NewsAggregator(include_international=True, include_playwright=True)
    try:
        news = await agg.collect_all()
        source_stats = dict(Counter(item.source for item in news.items))
        logger.info(f"✅ 采集完成: {len(news.items)} 条新闻")
        for src, cnt in sorted(source_stats.items(), key=lambda x: -x[1]):
            logger.info(f"  - {src}: {cnt} 条")
    finally:
        await agg.close()

    # 新闻数量检查
    MIN_NEWS_COUNT = 20
    if len(news.items) < MIN_NEWS_COUNT:
        logger.warning(f"⚠️ 新闻数量不足 ({len(news.items)} < {MIN_NEWS_COUNT})，跳过分析")
        return None

    # 读取 sector_list（从 etf_master.json）
    logger.info("=== 第2步: 读取板块配置 ===")
    sector_list = None
    master_file = Path(__file__).parent.parent / "config" / "etf_master.json"
    if master_file.exists():
        try:
            master_data = json.loads(master_file.read_text())
            sector_list = master_data.get("sector_list", [])
            logger.info(f"✅ 读取到 {len(sector_list)} 个可选板块")
        except Exception as e:
            logger.warning(f"⚠️ 读取 etf_master.json 失败: {e}")
    else:
        logger.warning("⚠️ etf_master.json 不存在，使用默认板块")

    # 读取历史数据用于综合分析
    history = load_history(days=7)
    history_context = format_history_context(history)
    if history_context:
        logger.info(f"📜 历史上下文:\n{history_context}")

    # AI 分析
    logger.info("=== 第3步: AI 分析 ===")
    result = await analyze(news.items, sector_list=sector_list, history_context=history_context)

    # 检查分析结果是否有效
    output_file = DATA_DIR / "latest.json"
    beijing_tz = timezone(timedelta(hours=8))

    # 先归档当前数据
    archive_data(beijing_tz)

    # AI 分析结果无效时，不覆盖文件
    if not result or not result.get("sectors"):
        logger.error("❌ AI 分析结果为空，不覆盖历史数据")
        if output_file.exists():
            try:
                old_data = json.loads(output_file.read_text())
                result = old_data.get("result", {})
                logger.info("📂 使用历史分析结果")
            except Exception as e:
                logger.error(f"❌ 读取历史数据失败: {e}")
        await save_news(news.items, beijing_tz)
        logger.info("⚠️ 运行结束（分析失败）")
        return None

    # 分析成功
    sectors = result.get("sectors", [])
    logger.info(f"✅ AI 分析完成: {len(sectors)} 个板块")
    for s in sectors:
        logger.info(f"  - {s['name']}: {s['direction']} {'★'*s['heat']}")

    # 为每个板块匹配 ETF
    logger.info("=== 第4步: 匹配 ETF ===")
    await enrich_sectors_with_etfs(result)

    # 保存结果
    logger.info("=== 第5步: 保存结果 ===")
    output = {
        "result": result,
        "updated_at": datetime.now(beijing_tz).isoformat(),
        "news_count": len(news.items),
        "source_stats": source_stats,
    }

    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(f"✅ 分析结果已保存: {output_file}")

    # 保存新闻列表
    await save_news(news.items, beijing_tz)

    logger.info("=" * 50)
    logger.info("🎉 ETF风向标 - 运行完成")
    logger.info("=" * 50)

    return output


async def ai_map_to_master_sectors(
    ai_sectors: list[str], master_sectors: list[str]
) -> dict[str, list[str]]:
    """AI 将分析出的板块映射到 master 中的标准板块（可一对多）"""
    import httpx
    from src.config import settings

    prompt = f"""将左边的板块名映射到右边最相关的标准板块。

## 待映射板块
{', '.join(ai_sectors)}

## 标准板块列表
{', '.join(master_sectors)}

## 输出JSON
```json
{{
  "待映射板块": ["标准板块1", "标准板块2"],
  ...
}}
```

要求：
- 每个板块可映射1-3个相关标准板块
- 如"新能源车"可映射到["锂电池", "汽车"]
- 如"科技"可映射到["芯片", "软件", "人工智能"]
- 无法映射则返回空数组[]"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.claude_base_url.rstrip('/')}/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": settings.claude_model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}]
                },
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
    except Exception as e:
        logger.warning(f"AI板块映射失败: {e}")
        return {}


async def enrich_sectors_with_etfs(result: dict):
    """为每个板块匹配ETF（AI映射板块 + 按成交量取Top3）"""
    sectors = result.get("sectors", [])
    if not sectors:
        logger.warning("⚠️ 无板块数据，跳过ETF匹配")
        return

    # 读取 ETF 主数据
    master_file = Path(__file__).parent.parent / "config" / "etf_master.json"
    if not master_file.exists():
        logger.warning("⚠️ etf_master.json 不存在")
        return
    etf_master = json.loads(master_file.read_text())
    master_sectors = etf_master.get("sector_list", [])
    sector_index = etf_master.get("sectors", {})
    etfs_data = etf_master.get("etfs", {})
    logger.info(f"📊 ETF主数据: {len(etfs_data)} 个ETF, {len(master_sectors)} 个板块")

    # AI 将分析板块映射到 master 标准板块
    ai_sector_names = [s["name"] for s in sectors]
    logger.info(f"🤖 AI 映射板块: {ai_sector_names}")
    sector_mapping = await ai_map_to_master_sectors(ai_sector_names, master_sectors)

    if not sector_mapping:
        logger.warning("⚠️ AI映射失败，使用直接匹配")
        sector_mapping = {name: [name] if name in sector_index else [] for name in ai_sector_names}

    # 根据映射收集 ETF 代码（合并多个板块）
    sector_etf_codes: dict[str, list[str]] = {}
    for ai_name, master_names in sector_mapping.items():
        codes = []
        for m_name in master_names:
            if m_name in sector_index:
                codes.extend(sector_index[m_name])
        sector_etf_codes[ai_name] = codes
        if master_names:
            logger.info(f"  {ai_name} → {master_names}")

    # 收集所有需要查询的 ETF 代码
    codes_to_fetch = set()
    for codes in sector_etf_codes.values():
        codes_to_fetch.update(codes)

    if not codes_to_fetch:
        logger.warning("⚠️ 没有匹配到ETF代码")
        return

    # 批量获取ETF实时数据
    logger.info(f"📈 获取 {len(codes_to_fetch)} 个ETF实时数据")
    fund_data = await fund_service.batch_get_funds(list(codes_to_fetch))

    # 为每个板块添加ETF信息
    matched = 0
    for sector in sectors:
        sector_name = sector.get("name", "")
        codes = sector_etf_codes.get(sector_name, [])
        etfs = []
        for code in codes:
            if code in fund_data:
                etfs.append(fund_data[code])
        etfs.sort(key=lambda x: x.get("amount_yi", 0), reverse=True)
        sector["etfs"] = etfs[:3]
        if etfs:
            matched += 1
            logger.info(f"  ✅ {sector_name}: {', '.join(e['name'] for e in etfs[:3])}")

    logger.info(f"✅ ETF匹配完成: {matched}/{len(sectors)} 个板块")


if __name__ == "__main__":
    asyncio.run(run())
