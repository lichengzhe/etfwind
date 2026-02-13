# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ETF风向标 - AI 驱动的 ETF 投资风向分析工具。自动采集财经新闻，通过 Claude AI 分析生成板块研判和 ETF 推荐，部署在 Cloudflare Workers。

**在线访问**: https://etf.aurora-bots.com/
**GitHub**: https://github.com/lichengzhe/etfwind

## Commands

```bash
# 只运行采集（输出 news_raw.json）
PYTHONPATH=. uv run python -m src.collect_news

# 只运行分析（读取 news_raw.json，输出 latest.json）
PYTHONPATH=. uv run python -m src.analyze_news

# 采集+分析一起跑（旧方式，仍可用）
PYTHONPATH=. uv run python -m src.worker_simple

# 部署 Workers 前端
cd workers && npx wrangler deploy

# 本地开发 Workers
cd workers && npx wrangler dev

# TypeScript 类型检查
cd workers && npx tsc --noEmit

# 更新 ETF 主数据（从东方财富拉取最新 ETF，AI 重新分类板块）
PYTHONPATH=. uv run python scripts/update_etf_master.py
```

## Architecture

```
GitHub Actions
├── Collect News (collect_news.yml, 每2小时 6:00-20:00 UTC+8) → news_raw.json → R2
│   └── 含 Playwright，耗时 ~1.5分钟
│
├── Analyze News (analyze_news.yml, 采集后自动触发 / 手动)
│   └── 读取 news_raw.json → AI分析 → latest.json + review.json + etf_master.json → R2
│   └── 无需 Playwright，耗时 ~1分钟
│
└── Update ETF Master (update_etf_master.yml, 每月1号 / 手动)
    └── 全量重建 etf_master.json（ETF列表 + AI分类 + 90天K线）→ R2
    └── 耗时 ~10分钟

Cloudflare Workers ← 从 R2 读取 JSON 渲染页面
```

**关键文件：**
- `src/collect_news.py` - 新闻采集模块
- `src/analyze_news.py` - AI 分析模块
- `src/worker_simple.py` - 共享逻辑（归档、历史、ETF匹配）
- `src/analyzers/realtime.py` - Claude AI 分析
- `src/collectors/` - 11个新闻采集器（含证券时报）
- `src/services/fund_service.py` - ETF 数据服务
- `src/notify/` - 通知推送模块（企业微信）
- `config/etf_master.json` - ETF 主数据（699个ETF，30个板块）
- `scripts/update_etf_master.py` - ETF Master 更新脚本
- `workers/src/index.ts` - Hono 路由
- `workers/src/pages/Home.ts` - 首页渲染
- `src/data/review.json` - 信号回测数据（1/3/7/20交易日胜率）
- `.github/workflows/update_etf_master.yml` - ETF Master 月度更新

## Configuration

环境变量（.env）：
- `CLAUDE_API_KEY`: Claude API 密钥（必需）
- `CLAUDE_BASE_URL`: API 地址，当前中转 `zenmux.openclawfarm.com/api/anthropic`
- `CLAUDE_MODEL`: 模型名称，默认 claude-opus-4-6
- `WECHAT_WEBHOOK_URL`: 企业微信 Webhook URL（可选，配置后自动推送）

Cloudflare R2（数据存储）：
- Bucket: `invest-data`
- GitHub Secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`

## Deployment

- **Web**: Cloudflare Workers（`workers/`）
- **采集/分析**: GitHub Actions（每 2 小时 6:00-20:00 UTC+8，含 Playwright）
- **ETF Master 更新**: GitHub Actions（每月 1 号，含 AI 分类 + K 线）
- **数据存储**: Cloudflare R2（`invest-data` bucket）
- **URL**: https://etf.aurora-bots.com/

## Key Data Structures

**etf_master.json（ETF 主数据）：**
```json
{
  "etfs": {
    "518880": {
      "code": "518880",
      "name": "黄金ETF",
      "full_name": "华安易富黄金交易型开放式证券投资基金",
      "exchange": "上海",
      "manager": "华安基金",
      "establish_date": "2013年07月18日",
      "amount_yi": 108.45,
      "sector": "黄金",
      "desc": "投资上海黄金交易所黄金现货合约",
      "scope": "上海黄金交易所挂盘交易的黄金现货合约...",
      "risk": "本基金属于黄金ETF...",
      "change_5d": 8.45,
      "change_20d": 13.31,
      "kline": [9.563, 9.363, ...]
    }
  },
  "sectors": {"黄金": ["518880", "159934", ...], ...},
  "sector_list": ["黄金", "有色", "芯片", ...],
  "updated_at": "2026-01-29 11:41"
}
```

**latest.json（AI 分析结果，含决策仪表盘）：**
```json
{
  "result": {
    "market_view": "🎯 市场状态一句话",
    "summary": "市场全景分析（150字）",
    "sentiment": "偏乐观/分歧/偏悲观",
    "sectors": [
      {
        "name": "板块名",
        "heat": 5,
        "direction": "利好/利空/中性",
        "confidence": 80,
        "analysis": "板块深度分析（80-100字）",
        "signal": "🟢买入/🟡观望/🔴回避"
      }
    ],
    "risk_alerts": ["风险1：...", "风险2：..."],
    "opportunity_hints": ["机会1：...", "机会2：..."],
    "commodity_cycle": {
      "stage": 1,
      "stage_name": "黄金领涨期",
      "leader": "gold",
      "analysis": "周期分析"
    }
  },
  "sector_trends": {
    "黄金": {"arrows": "↑↓↓↓↓↑↑", "desc": "近日转好"},
    "机器人": {"arrows": "↑↑↑↑↑", "desc": "5连利好"}
  },
  "updated_at": "2026-01-28T10:00:00+08:00",
  "news_count": 302,
  "source_stats": {"财联社": 50, "东方财富": 35, ...}
}
```

**review.json（信号回测数据）：**
```json
{
  "signals": [
    {
      "date": "2026-02-05",
      "sector": "黄金",
      "type": "overall",
      "signal": "🟢买入",
      "etf_code": "518880",
      "entry_price": 10.523
    }
  ],
  "updated_at": "2026-02-11T10:00:00+08:00"
}
```
信号按 `(date, sector, etf_code)` 去重，板块名归一化到 etf_master 标准名。
记录买入/观望/回避三种信号，复盘统计时买入看涨为胜、回避看跌为胜。
```

**ETF 实时数据（/api/funds）：**
```json
{
  "518880": {
    "code": "518880",
    "name": "黄金ETF",
    "price": 10.934,
    "change_pct": 0.09,
    "change_5d": 8.45,
    "change_20d": 13.31,
    "amount_yi": 83.96,
    "flow_yi": -4.25,
    "turnover": 7.06,
    "kline": [9.563, 9.363, ...]
  }
}
```

## API Endpoints

**Workers (workers/src/index.ts)：**
- `GET /` - 首页（30min缓存）
- `GET /news` - 新闻列表（支持 `?source=财联社` 过滤）
- `GET /cycle` - 商品周期页面
- `GET /api/data` - 分析数据 JSON（30min缓存）
- `GET /api/funds?codes=518880,512760` - ETF 实时行情（5min缓存）
- `GET /api/kline?codes=518880,512760` - ETF K线数据（90天收盘价+5日/20日涨跌幅，24h缓存）
- `GET /api/batch-sector-etfs?sectors=黄金,芯片` - 批量板块 ETF（5min缓存）
- `GET /api/etf-master` - ETF 主数据（含 sector_list/sectors/updated_at，24h缓存）
- `GET /api/market-overview` - 全球指标+商品周期（10min缓存）
- `GET /api/review` - 信号回测数据（30min缓存）
- `GET /api/poster` - 每日海报 SVG（1h缓存）
- `GET /health` - 健康检查

## Tech Stack

**前端：** Cloudflare Workers / Hono / TypeScript

**AI：** Claude API (httpx 直接调用)

**数据源：** 东方财富 API

**采集：** httpx / BeautifulSoup / Playwright（GitHub Actions）

**部署：** Cloudflare Workers + R2 / GitHub Actions / uv (包管理)

## Lessons Learned

### Python 命令必须用 uv run

本项目使用 uv 管理 Python 依赖，运行任何 Python 命令都必须加 `uv run` 前缀：

```bash
# 正确
uv run python -m src.worker_simple
uv run python -c "from src.config import settings; print(settings)"

# 错误（会报 ModuleNotFoundError）
python -m src.worker_simple
python3 -c "..."
```

### 板块名一致性（单一数据源原则）

板块名必须全链路一致，`etf_master.json` 的 `sector_list` 是唯一权威源（30个标准名）。

**出过的问题**：板块合并后（人工智能→AI, 半导体→芯片, 恒生科技→港股），前端显示"暂无数据"，因为 AI 分析输出新名但 etf_master 还是旧名。

**需要同步的 5 个位置**：
1. `config/etf_master.json` → `sector_list`（权威源）
2. `scripts/update_etf_master.py` → AI 分类 prompt 中的板块列表
3. `src/analyzers/realtime.py` → 默认板块列表（fallback）
4. `workers/src/types.ts` → `SECTOR_ALIAS`（别名安全网）
5. `src/data/archive/` → 历史归档中的板块 key

**改板块名时**：先改 etf_master，再同步其余 4 处，最后跑 `Update ETF Master` workflow 重建数据。

### CI/CD 时序：先推代码再触发 workflow

手动触发 GitHub Actions workflow 时，必须确保代码已推送到 remote：
```
# 正确顺序
git push → 确认到达 → gh workflow run

# 错误：先触发再推代码，workflow 跑的是旧代码
gh workflow run → git push  ← 白跑一次
```

### R2 写入前必须检查数据质量

`update_etf_master.py` 已加入质量门槛：AI 分类后板块数 < 10 则 `exit(1)`，阻止上传 R2。

**出过的问题**：中转 proxy 挂了 → AI 分类全部 404 → 所有 ETF 归为"其他" → sector_list=[] 的坏数据覆盖了 R2 → 前端所有板块 ETF 推荐为空。

**原则**：外部依赖会静默失败，写入持久存储前必须校验数据质量。Fast-fail 优于静默容错。

### AI 结构化使用原则

AI 只负责"内容生成"，代码负责"结构组装"。分步提取 → 代码组装 → 验证兜底。不要让 AI 直接输出完整 JSON（字段遗漏、格式不一致）。

## Design Notes

- **FOTH Matrix**：新闻分析按 Facts/Opinions × History/Latest 四象限拆分，避免情绪污染事实判断。详见 `src/analyzers/realtime.py` 中的 `format_history_context()`
- **数据源降级**：东方财富 → 新浪自动降级；R2 binding → HTTP 公开 URL 降级
- **SSR + 异步水合**：首屏 SSR 渲染历史数据，JS 异步覆盖实时价格（/api/batch-sector-etfs）
- **AI JSON 修复**：自动移除尾部逗号、替换中文引号，见 `src/analyzers/realtime.py`
