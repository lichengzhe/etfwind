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

    # 归档 latest.json 到当天
    latest_file = DATA_DIR / "latest.json"
    if latest_file.exists():
        daily_file = ARCHIVE_DIR / f"latest_{today}.json"
        if not daily_file.exists():
            import shutil
            shutil.copy(latest_file, daily_file)
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

        days_ago = (now - file_date).days

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
    """读取近N天的历史归档数据"""
    logger.info(f"=== 读取历史数据 (最近{days}天) ===")
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    history = []

    archive_files = sorted(ARCHIVE_DIR.glob("latest_*.json"), reverse=True)
    logger.info(f"📁 找到 {len(archive_files)} 个归档文件")
    for f in archive_files[:days]:
        try:
            data = json.loads(f.read_text())
            date_str = f.stem.replace("latest_", "")
            result = data.get("result", {})
            if result.get("sectors"):
                history.append({
                    "date": date_str,
                    "market_view": result.get("market_view", ""),
                    "sectors": [
                        {"name": s["name"], "heat": s["heat"], "direction": s["direction"]}
                        for s in result.get("sectors", [])
                    ]
                })
                logger.info(f"  ✅ {date_str}: {len(result['sectors'])} 个板块")
            else:
                logger.info(f"  ⏭️ {date_str}: 无板块数据")
        except Exception as e:
            logger.warning(f"  ❌ 读取 {f.name} 失败: {e}")

    logger.info(f"📊 成功加载 {len(history)} 天历史数据")
    return history


def format_history_context(history: list[dict]) -> str:
    """格式化历史数据为 AI 上下文"""
    if not history:
        return ""

    lines = ["## 近期历史分析（供参考）"]
    for h in history[:5]:  # 最多5天
        sectors_str = ", ".join([
            f"{s['name']}({'↑' if s['direction']=='利好' else '↓' if s['direction']=='利空' else '-'}{'★'*s['heat']})"
            for s in h["sectors"][:4]
        ])
        lines.append(f"- {h['date']}: {h['market_view']} | {sectors_str}")

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

    # 读取 sector_list（从 etf_master.json）
    logger.info("=== 第2步: 读取板块配置 ===")
    sector_list = None
    etf_file = DATA_DIR / "etf_master.json"
    if etf_file.exists():
        try:
            etf_data = json.loads(etf_file.read_text())
            sector_list = etf_data.get("sector_list", [])
            logger.info(f"✅ 读取到 {len(sector_list)} 个可选板块")
        except Exception as e:
            logger.warning(f"⚠️ 读取 sector_list 失败: {e}")
    else:
        logger.warning("⚠️ etf_master.json 不存在，使用默认板块")

    # 读取历史数据用于综合分析
    history = load_history(days=7)
    history_context = format_history_context(history)

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
        await fetch_etf_map()
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

    # 生成 ETF 板块映射（每天一次）
    await fetch_etf_map()

    logger.info("=" * 50)
    logger.info("🎉 ETF风向标 - 运行完成")
    logger.info("=" * 50)

    return output


async def enrich_sectors_with_etfs(result: dict):
    """为每个板块匹配交易量最大的3个ETF"""
    sectors = result.get("sectors", [])
    if not sectors:
        logger.warning("⚠️ 无板块数据，跳过ETF匹配")
        return

    # 获取板块->ETF映射
    sector_map = await fund_service.get_sector_etf_map()
    if not sector_map:
        logger.warning("⚠️ 无法获取板块映射")
        return
    logger.info(f"📊 板块映射: {len(sector_map)} 个板块")

    # 板块名映射（AI输出 -> ETF板块）
    sector_alias = {
        "新能源车": "锂电池", "新能源": "光伏", "创新药": "医药",
        "贵金属": "黄金", "券商": "证券",
        "芯片/半导体": "芯片", "半导体": "芯片",
    }

    # 收集需要查询的ETF代码
    codes_to_fetch = set()
    sector_etf_mapping = {}

    for sector in sectors:
        sector_name = sector.get("name", "")
        # 先尝试别名映射
        lookup_name = sector_alias.get(sector_name, sector_name)
        for key, etfs in sector_map.items():
            if key in lookup_name or lookup_name in key:
                codes = [code for code, name in etfs[:3]]
                sector_etf_mapping[sector_name] = codes
                codes_to_fetch.update(codes)
                break

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
        codes = sector_etf_mapping.get(sector_name, [])
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


async def fetch_etf_map(force: bool = False):
    """生成 ETF Master 数据文件（每周一更新，或强制更新）"""
    etf_file = DATA_DIR / "etf_master.json"
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)

    # 检查是否需要更新（每周一，或强制更新）
    if not force and etf_file.exists():
        try:
            data = json.loads(etf_file.read_text())
            last_update = data.get("updated_at", "")[:10]
            last_date = datetime.fromisoformat(last_update)
            # 如果上次更新在本周一之后，跳过
            days_since_monday = now.weekday()
            this_monday = (now - timedelta(days=days_since_monday)).date()
            if last_date.date() >= this_monday:
                logger.info(f"ETF Master 本周已更新（{last_update}），跳过")
                return
        except Exception:
            pass

    logger.info("生成 ETF Master 数据...")
    try:
        fund_service._etf_cache_time = 0
        master = await fund_service.build_etf_master(min_amount_yi=5.0)

        if not master.get("etfs"):
            logger.warning("未获取到ETF数据")
            return

        output = {
            **master,
            "updated_at": now.isoformat(),
        }
        etf_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        logger.info(f"ETF Master 已保存，共 {len(master['etfs'])} 个ETF")
    except Exception as e:
        logger.warning(f"生成 ETF Master 失败: {e}")


if __name__ == "__main__":
    asyncio.run(run())
