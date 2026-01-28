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


async def run():
    """运行采集和分析"""
    logger.info("开始采集新闻...")

    # 采集
    agg = NewsAggregator(include_international=True, include_playwright=True)
    try:
        news = await agg.collect_all()
        source_stats = dict(Counter(item.source for item in news.items))
        logger.info(f"采集到 {len(news.items)} 条新闻: {source_stats}")
    finally:
        await agg.close()

    # 读取 sector_list（从 etf_master.json）
    sector_list = None
    etf_file = DATA_DIR / "etf_master.json"
    if etf_file.exists():
        try:
            etf_data = json.loads(etf_file.read_text())
            sector_list = etf_data.get("sector_list", [])
            logger.info(f"读取到 {len(sector_list)} 个板块")
        except Exception as e:
            logger.warning(f"读取 sector_list 失败: {e}")

    # AI 分析（传入 sector_list 约束）
    logger.info("开始 AI 分析...")
    result = await analyze(news.items, sector_list=sector_list)

    # 为每个板块匹配 ETF
    await enrich_sectors_with_etfs(result)

    # 保存结果
    beijing_tz = timezone(timedelta(hours=8))
    output = {
        "result": result,
        "updated_at": datetime.now(beijing_tz).isoformat(),
        "news_count": len(news.items),
        "source_stats": source_stats,
    }

    output_file = DATA_DIR / "latest.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(f"结果已保存到 {output_file}")

    # 保存原始新闻列表（过滤聚合页面，只保留有具体文章URL的新闻）
    # 聚合页面通常是首页或列表页，不是具体文章
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
        for item in news.items
        if item.url and not any(item.url.startswith(agg) for agg in aggregator_urls)
    ]
    news_file = DATA_DIR / "news.json"
    news_file.write_text(json.dumps({
        "news": news_list,
        "updated_at": datetime.now(beijing_tz).isoformat(),
    }, ensure_ascii=False, indent=2))
    logger.info(f"新闻列表已保存到 {news_file}")

    # 生成 ETF 板块映射（每天一次）
    await fetch_etf_map()

    return output


async def enrich_sectors_with_etfs(result: dict):
    """为每个板块匹配交易量最大的3个ETF"""
    sectors = result.get("sectors", [])
    if not sectors:
        return

    # 获取板块->ETF映射
    sector_map = await fund_service.get_sector_etf_map()
    if not sector_map:
        logger.warning("无法获取板块映射")
        return

    # 收集需要查询的ETF代码
    codes_to_fetch = set()
    sector_etf_mapping = {}

    for sector in sectors:
        sector_name = sector.get("name", "")
        for key, etfs in sector_map.items():
            if key in sector_name or sector_name in key:
                codes = [code for code, name in etfs[:3]]
                sector_etf_mapping[sector_name] = codes
                codes_to_fetch.update(codes)
                break

    if not codes_to_fetch:
        logger.info("没有匹配到ETF代码")
        return

    # 批量获取ETF实时数据
    logger.info(f"获取 {len(codes_to_fetch)} 个ETF数据")
    fund_data = await fund_service.batch_get_funds(list(codes_to_fetch))

    # 为每个板块添加ETF信息
    for sector in sectors:
        sector_name = sector.get("name", "")
        codes = sector_etf_mapping.get(sector_name, [])
        etfs = []
        for code in codes:
            if code in fund_data:
                etfs.append(fund_data[code])
        # 按成交额排序
        etfs.sort(key=lambda x: x.get("amount_yi", 0), reverse=True)
        sector["etfs"] = etfs[:3]

    logger.info("板块ETF匹配完成")


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
