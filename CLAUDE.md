# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI投资助手 - 自动采集财经新闻，通过 Claude AI 分析生成投资建议和ETF推荐，部署在 Fly.io。

## Commands

```bash
# 启动 Web 服务（本地开发，简化版）
uv run uvicorn src.web.app_simple:app --reload --port 8000

# 启动 Web 服务（完整版，需要 Supabase）
uv run uvicorn src.web.app:app --reload --port 8000

# 手动运行采集+分析（输出到 src/web/data/）
PYTHONPATH=. uv run python -m src.worker_simple

# 部署到 Fly.io
fly deploy

# 查看生产日志
fly logs --app invest-report --no-tail | tail -50
```

## Architecture

```
GitHub Actions (每30分钟定时触发)
        ↓
worker_simple.py → collectors/ → realtime.py → src/web/data/*.json
                   (10个采集器)   (Claude API)        ↓
                                              GitHub 自动提交
                                                     ↓
                                              Fly.io (app_simple.py)
                                              从 GitHub raw 读取 JSON
```

**两种运行模式：**

1. **简化模式（当前使用）**：
   - GitHub Actions 运行 `worker_simple.py` 采集+分析
   - 结果存入 `src/web/data/latest.json` 并提交到 GitHub
   - Fly.io 运行 `app_simple.py`，从 GitHub raw URL 读取数据
   - 无需数据库，轻量部署

2. **完整模式（可选）**：
   - 使用 Supabase 数据库存储新闻和分析结果
   - Fly.io 运行 `app.py`，支持 SSE 实时推送
   - 适合需要历史数据的场景

**关键模块：**
- `src/worker_simple.py`: 简化版采集+分析，输出 JSON 文件
- `src/analyzers/realtime.py`: 实时分析器，调用 Claude API
- `src/services/fund_service.py`: ETF 实时行情服务（东方财富/新浪 API）
- `src/web/app_simple.py`: 简化版 FastAPI，从 GitHub 读取数据
- `src/web/app.py`: 完整版 FastAPI，含 Supabase 和 SSE

**采集器（src/collectors/）：**
- **普通采集器**：CLSNewsCollector、EastMoneyCollector、SinaFinanceCollector
- **RSS 采集器**：CNBCCollector、BloombergCollector、WSJCollector
- **Playwright 采集器**（GitHub Actions 使用）：
  - CLSPlaywrightCollector、SinaPlaywrightCollector、EastMoneyPlaywrightCollector
  - WallStreetCNCollector（华尔街见闻）、Jin10Collector（金十数据）

## Configuration

环境变量（.env）：
- `CLAUDE_API_KEY`: Claude API 密钥（必需）
- `CLAUDE_BASE_URL`: API 地址，支持中转
- `CLAUDE_MODEL`: 模型名称，默认 claude-sonnet-4-20250514

可选（完整模式）：
- `SUPABASE_URL`: Supabase 项目 URL
- `SUPABASE_KEY`: Supabase anon key

## Deployment

- **Web**: Fly.io（新加坡，256MB，auto_stop）
- **采集/分析**: GitHub Actions（每 30 分钟，含 Playwright）
- **数据存储**: GitHub 仓库 `src/web/data/*.json`
- **URL**: https://invest-report.fly.dev/

## Key Data Structures

**latest.json（AI 分析结果）：**
```json
{
  "result": {
    "market_view": "🎯 市场状态一句话",
    "narrative": "市场全景分析（150字）",
    "sectors": [
      {
        "name": "板块名",
        "direction": "利好/利空/中性",
        "reason": "📈 原因",
        "etf": "芯片ETF(512760)",
        "events": [{"title": "事件", "suggestion": "💡 建议"}]
      }
    ],
    "risk_level": "低/中/高"
  },
  "updated_at": "2026-01-28T10:00:00+08:00",
  "news_count": 302,
  "source_stats": {"财联社": 50, "东方财富": 35, ...}
}
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

**简化版 (app_simple.py)：**
- `GET /` - 首页，渲染 simple.html
- `GET /api/data` - 返回分析数据 JSON
- `GET /api/funds?codes=518880,512760` - ETF 实时行情
- `GET /api/hot-etfs?limit=10` - 热门 ETF（按成交额排序）
- `GET /health` - 健康检查

## Tech Stack

**后端：** Python 3.11+ / FastAPI / Uvicorn / Jinja2

**AI：** Claude API (httpx 直接调用)

**数据源：** 东方财富 API / 新浪财经 API（回退）

**采集：** httpx / BeautifulSoup / Playwright（GitHub Actions）

**部署：** Fly.io / GitHub Actions / uv (包管理)

## Lessons Learned

### Playwright 闭环验证

修改前端代码后，使用 Playwright 自动打开网站验证效果：
```
1. 部署后用 browser_navigate 打开页面
2. 用 browser_snapshot 获取页面结构，检查数据是否正确渲染
3. 发现问题 → 修复代码 → 重新部署 → 再次验证
4. 完成后用 browser_close 关闭浏览器
```

### AI 结构化使用原则

让 AI 只负责"内容生成"，代码负责"结构组装"，避免让 AI 自由发挥格式：

**问题**：让 AI 直接输出完整 JSON，会导致字段遗漏、格式不一致（如 sources 有时有有时无）

**解决方案**：
1. **分步提取**：将复杂任务拆分为多个简单问题，每次只问一个方面
2. **代码组装**：由代码构建最终数据结构，AI 只填充内容
3. **明确约束**：给 AI 提供输入数据的索引，让它引用而非重新格式化
4. **验证兜底**：代码层面检查必填字段，缺失时记录警告或使用默认值

**示例**：
```python
# 不好：让 AI 输出完整 JSON
prompt = "分析新闻，输出 JSON 格式的 focus_events..."

# 好：分步提取，代码组装
step1 = "从以下新闻中识别最重要的5个事件，只输出事件标题列表"
step2 = "对于事件'{title}'，提供：1.所属板块 2.分析(80字) 3.建议(15字)"
step3 = "事件'{title}'相关的ETF代码是？从候选列表中选择：{etf_list}"
# 代码负责组装最终结构，并从原始新闻中提取 sources
```
