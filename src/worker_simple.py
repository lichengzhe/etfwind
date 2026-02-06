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

# 信号复盘数据
REVIEW_FILE = DATA_DIR / "review.json"


def _parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def _days_between(now: datetime, date_str: str) -> int | None:
    d = _parse_date(date_str)
    if not d:
        return None
    return (now.replace(tzinfo=None) - d).days


def _pick_trading_index(dates: list[str], entry_date: str) -> int | None:
    """选择不早于 entry_date 的第一个交易日索引"""
    for i, d in enumerate(dates):
        if d >= entry_date:
            return i
    return None


def load_review_data() -> dict:
    if REVIEW_FILE.exists():
        try:
            return json.loads(REVIEW_FILE.read_text())
        except Exception:
            pass
    return {"signals": []}


def save_review_data(data: dict):
    REVIEW_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


async def update_review(result: dict, beijing_tz) -> dict:
    """更新信号复盘数据并返回汇总指标"""
    data = load_review_data()
    signals: list[dict] = data.get("signals", [])

    now = datetime.now(beijing_tz)

    # 添加今日信号（只记录买入信号）
    today = now.strftime("%Y-%m-%d")
    sectors = result.get("sectors", [])
    today_entries = []
    for sector in sectors:
        etfs = sector.get("etfs") or []
        if not etfs:
            continue
        code = etfs[0].get("code")
        price = etfs[0].get("price")
        if not code or price is None:
            continue
        signal_text = sector.get("signal", "")
        if "买入" not in signal_text:
            continue
        today_entries.append({
            "date": today,
            "sector": sector.get("name"),
            "type": "overall",
            "signal": signal_text,
            "etf_code": code,
            "entry_price": price,
        })

    if today_entries:
        signals.extend(today_entries)

    data["signals"] = signals
    data["updated_at"] = now.isoformat()
    save_review_data(data)

    # 计算复盘指标（1/3/7/20 交易日）
    horizons = [1, 3, 7, 20]
    summary = {
        "as_of": now.isoformat(),
        "horizons": {},
        "benchmark": {"name": "沪深300", "secid": "1.000300"},
    }

    benchmark_kline = await fund_service.get_kline_date_map(secid="1.000300")
    bench_dates = [d for d, _ in benchmark_kline]
    bench_closes = [c for _, c in benchmark_kline]

    codes = list({s.get("etf_code") for s in signals if s.get("etf_code")})
    code_to_kline: dict[str, list[tuple[str, float]]] = {}
    if codes:
        sem = asyncio.Semaphore(5)

        async def fetch_kline(c: str):
            async with sem:
                return await fund_service.get_kline_date_map(code=c)

        results = await asyncio.gather(*(fetch_kline(c) for c in codes))
        code_to_kline = dict(zip(codes, results))

    for h in horizons:
        returns = []
        excess = []
        for s in signals:
            entry_date = s.get("date", "")
            code = s.get("etf_code")
            kline = code_to_kline.get(code, [])
            if not kline:
                continue
            dates = [d for d, _ in kline]
            closes = [c for _, c in kline]
            idx = _pick_trading_index(dates, entry_date)
            if idx is None:
                continue
            exit_idx = idx + h
            if exit_idx >= len(closes):
                continue
            entry = closes[idx]
            exit_price = closes[exit_idx]
            ret = (exit_price - entry) / entry * 100
            returns.append(ret)

            if bench_dates and bench_closes:
                bidx = _pick_trading_index(bench_dates, entry_date)
                if bidx is not None and bidx + h < len(bench_closes):
                    bret = (bench_closes[bidx + h] - bench_closes[bidx]) / bench_closes[bidx] * 100
                    excess.append(ret - bret)
        if returns:
            win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
            avg_ret = sum(returns) / len(returns)
            summary["horizons"][str(h)] = {
                "count": len(returns),
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_ret, 2),
                "avg_excess": round(sum(excess) / len(excess), 2) if excess else 0,
            }
        else:
            summary["horizons"][str(h)] = {"count": 0, "win_rate": 0, "avg_return": 0, "avg_excess": 0}

    return summary


def archive_data(beijing_tz):
    """归档数据：只保存板块趋势指标，用于7日趋势展示"""
    logger.info("=== 开始归档数据 ===")
    now = datetime.now(beijing_tz)
    today = now.strftime("%Y-%m-%d")

    latest_file = DATA_DIR / "latest.json"
    if latest_file.exists():
        daily_file = ARCHIVE_DIR / f"latest_{today}.json"
        if not daily_file.exists():
            data = json.loads(latest_file.read_text())
            result = data.get("result", {})
            # 归档：保存趋势和摘要数据
            archive = {
                "date": today,
                "sectors": {
                    s["name"]: {"dir": s["direction"], "heat": s["heat"]}
                    for s in result.get("sectors", [])
                },
                "sentiment": result.get("sentiment", ""),
                "market_view": result.get("market_view", ""),
                "summary": result.get("summary", ""),
            }
            daily_file.write_text(json.dumps(archive, ensure_ascii=False, indent=2))
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
    """读取近N天的历史归档数据（简化版：只读取板块趋势）"""
    logger.info(f"=== 读取历史数据 (最近{days}天) ===")
    history = []

    archive_files = sorted(ARCHIVE_DIR.glob("latest_*.json"), reverse=True)
    logger.info(f"📁 找到 {len(archive_files)} 个归档文件")

    for f in archive_files[:days]:
        try:
            data = json.loads(f.read_text())
            date_str = f.stem.replace("latest_", "")

            # 新格式：简化归档
            if "sectors" in data and isinstance(data["sectors"], dict):
                history.append({
                    "date": date_str,
                    "sectors": data["sectors"],
                    "sentiment": data.get("sentiment", ""),
                    "market_view": data.get("market_view", ""),
                    "summary": data.get("summary", ""),
                })
                logger.info(f"  ✅ {date_str}: {len(data['sectors'])} 个板块")
                continue

            # 兼容旧格式（从 result 提取）
            result = data.get("result", {})
            if result.get("sectors"):
                sectors = {
                    s["name"]: {"dir": s["direction"], "heat": s["heat"]}
                    for s in result.get("sectors", [])
                }
                history.append({
                    "date": date_str,
                    "sectors": sectors,
                    "sentiment": result.get("sentiment", ""),
                    "market_view": result.get("market_view", ""),
                    "summary": result.get("summary", ""),
                })
                logger.info(f"  ✅ {date_str}: {len(sectors)} 个板块 (旧格式)")
            else:
                logger.info(f"  ⏭️ {date_str}: 无数据")
        except Exception as e:
            logger.warning(f"  ❌ 读取 {f.name} 失败: {e}")

    logger.info(f"📊 成功加载 {len(history)} 天历史数据")
    return history


def _describe_trend(arrows: list[str]) -> str:
    """根据箭头序列生成趋势描述"""
    if not arrows:
        return ""

    if len(arrows) == 1:
        return "利好" if arrows[0] == "↑" else "利空" if arrows[0] == "↓" else "中性"

    # 统计连续相同方向
    up_count = arrows.count("↑")
    down_count = arrows.count("↓")

    # 检查最近趋势
    recent = arrows[-3:] if len(arrows) >= 3 else arrows
    recent_up = recent.count("↑")
    recent_down = recent.count("↓")

    # 生成描述
    if all(a == "↑" for a in arrows):
        return "利好"
    elif all(a == "↓" for a in arrows):
        return "利空"
    elif recent_up >= 2 and down_count > 0:
        return "转好"
    elif recent_down >= 2 and up_count > 0:
        return "转弱"
    elif up_count > down_count:
        return "偏好"
    elif down_count > up_count:
        return "偏弱"
    else:
        return "震荡"


def format_history_context(history: list[dict]) -> str:
    """格式化历史数据为 AI 上下文（历史观点 + 板块趋势）"""
    if not history:
        return ""

    lines = []

    # 添加历史市场观点和摘要（最近7天）
    history_items = []
    for h in history[:7]:
        date = h.get("date", "")
        view = h.get("market_view", "")
        summary = h.get("summary", "")
        if date and (view or summary):
            item = f"### {date}\n"
            if view:
                item += f"**观点**: {view}\n"
            if summary:
                item += f"**摘要**: {summary}\n"
            history_items.append(item)

    if history_items:
        lines.append("## 近7日市场回顾")
        lines.extend(history_items)

    # 收集所有出现过的板块
    all_sectors = set()
    for h in history:
        all_sectors.update(h.get("sectors", {}).keys())

    if all_sectors:
        lines.append("## 近7日板块趋势")

    # 为每个板块生成趋势箭头
    for sector in sorted(all_sectors):
        arrows = []
        for h in reversed(history):  # 从旧到新
            s = h.get("sectors", {}).get(sector, {})
            d = s.get("dir", "")
            if d == "利好":
                arrows.append("↑")
            elif d == "利空":
                arrows.append("↓")
            elif d:
                arrows.append("→")

        if arrows:
            arrow_str = "".join(arrows)
            # 生成趋势描述
            desc = _describe_trend(arrows)
            lines.append(f"- {sector}: {arrow_str} ({desc})")

    return "\n".join(lines)


def build_sector_trends(history: list[dict], current_sectors: list[dict]) -> dict:
    """构建板块7日趋势数据，供前端展示

    返回: {"黄金": {"arrows": "↑↑↑↑↑↑↑", "desc": "7连利好"}, ...}
    """
    trends = {}

    # 当前板块名列表
    current_names = {s["name"] for s in current_sectors}

    for sector_name in current_names:
        arrows = []
        # 从历史数据中提取（从旧到新），没提到的天显示中性
        for h in reversed(history):
            s = h.get("sectors", {}).get(sector_name, {})
            d = s.get("dir", "")
            if d == "利好":
                arrows.append("↑")
            elif d == "利空":
                arrows.append("↓")
            else:
                arrows.append("→")  # 没提到或中性都显示→

        # 添加今日
        current = next((s for s in current_sectors if s["name"] == sector_name), None)
        if current:
            d = current.get("direction", "")
            if d == "利好":
                arrows.append("↑")
            elif d == "利空":
                arrows.append("↓")
            else:
                arrows.append("→")

        if arrows:
            trends[sector_name] = {
                "arrows": "".join(arrows[-7:]),  # 最多7天
                "desc": _describe_trend(arrows[-7:])
            }

    return trends


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
    from src.services.ai_client import AIClient, AIRequest, parse_json_with_repair

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
- 如"科技"可映射到["芯片", "软件", "AI"]
- 无法映射则返回空数组[]"""

    try:
        client = AIClient()
        text = await client.send(AIRequest(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            timeout=60,
        ))
        return parse_json_with_repair(text)
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
