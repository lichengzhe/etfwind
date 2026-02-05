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
```

## Architecture

```
GitHub Actions
├── Collect News (每小时) → news_raw.json → R2
│   └── 含 Playwright，耗时 ~1.5分钟
│
└── Analyze News (采集后自动触发 / 手动)
    └── 读取 news_raw.json → AI分析 → latest.json → R2
    └── 无需 Playwright，耗时 ~1分钟

Cloudflare Workers ← 从 R2 读取 JSON 渲染页面
```

**关键文件：**
- `src/collect_news.py` - 新闻采集模块
- `src/analyze_news.py` - AI 分析模块
- `src/worker_simple.py` - 共享逻辑（归档、历史、ETF匹配）
- `src/analyzers/realtime.py` - Claude AI 分析
- `src/collectors/` - 10个新闻采集器
- `src/services/fund_service.py` - ETF 数据服务
- `src/notify/` - 通知推送模块（企业微信）
- `config/etf_master.json` - ETF 主数据（642个ETF，32个板块）
- `scripts/update_etf_master.py` - ETF Master 更新脚本
- `workers/src/index.ts` - Hono 路由
- `workers/src/pages/Home.ts` - 首页渲染

## Configuration

环境变量（.env）：
- `CLAUDE_API_KEY`: Claude API 密钥（必需）
- `CLAUDE_BASE_URL`: API 地址，支持中转
- `CLAUDE_MODEL`: 模型名称，默认 claude-sonnet-4-20250514
- `WECHAT_WEBHOOK_URL`: 企业微信 Webhook URL（可选，配置后自动推送）

Cloudflare R2（数据存储）：
- Bucket: `invest-data`
- GitHub Secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`

## Deployment

- **Web**: Cloudflare Workers（`workers/`）
- **采集/分析**: GitHub Actions（每 2 小时，含 Playwright）
- **数据存储**: Cloudflare R2（`invest-data` bucket）
- **URL**: https://etf.aurora-bots.com/

## Key Data Structures

**etf_master.json（ETF 主数据，642个ETF）：**
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
      "risk": "本基金属于黄金ETF..."
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
        "signal": "🟢买入/🟡观望/🔴回避",
        "evidence": [
          {"title": "新闻标题", "source": "来源", "reason": "与板块相关的因果/驱动"}
        ]
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
- `GET /` - 首页
- `GET /news` - 新闻列表
- `GET /api/data` - 分析数据 JSON
- `GET /api/funds?codes=518880,512760` - ETF 实时行情
- `GET /api/batch-sector-etfs?sectors=黄金,芯片` - 批量板块 ETF
- `GET /api/etf-master` - ETF 主数据
- `GET /api/global-indices` - 全球指标（美元、黄金、BTC、上证、纳指）含90天K线
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

### Playwright 闭环验证

修改前端代码后，使用 Playwright 自动打开网站验证效果：
```
1. 部署后用 browser_navigate 打开页面
2. 用 browser_snapshot 获取页面结构，检查数据是否正确渲染
3. 发现问题 → 修复代码 → 重新部署 → 再次验证
4. 完成后用 browser_close 关闭浏览器
```

**注意**：不要用 browser_take_screenshot 截图后发给自己看，图片会导致 context 溢出。始终使用 browser_snapshot 获取文本结构。

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

## FOTH Matrix 信息处理方法论

**FOTH = Facts-Opinions × Time-Horizon**

处理信息流时，按两个维度分离：
- **内容维度**：Facts（客观事件） vs Opinions（主观判断/情绪）
- **时间维度**：History（历史） vs Latest（当前）

```
              │  Facts          │  Opinions
──────────────┼─────────────────┼──────────────────
History       │  历史事件        │  历史情绪
              │  黄金2750→2780   │  当时"看涨"声多
──────────────┼─────────────────┼──────────────────
Latest        │  今日事件        │  今日情绪
              │  黄金2800        │  "避险升温"频现
```

### 四象限的作用

| 象限 | 内容 | 作用 |
|------|------|------|
| History Facts | 价格、涨跌、政策、事件 | 趋势基准，判断延续/反转 |
| History Opinions | 当时的情绪词、媒体倾向 | 情绪对比，识别过热/过冷 |
| Latest Facts | 今天的客观事件 | 当前发生了什么 |
| Latest Opinions | 今天的情绪信号 | 市场现在怎么看 |

### AI 分析策略

基于四象限组合判断：
- Facts 连涨 + Opinions 从冷到热 → 趋势确认
- Facts 连涨 + Opinions 过热 → 可能见顶
- Facts 下跌 + Opinions 恐慌 → 可能超卖
- Facts 平稳 + Opinions 分歧 → 观望

### 实现要点

1. **新闻拆分**：从原始新闻中分离 facts 和 opinions
2. **归档存储**：分别存储，便于历史对比
3. **干净上下文**：给 AI 明确标注哪些是 facts、哪些是 opinions
4. **独立判断**：AI 基于 facts 做判断，参考 opinions 做情绪校准

---

## AI 工作方法论

### 核心循环

**发现 → 理解 → 计划 → 执行 → 试错 → 反馈 → 修正 → 迭代 → 反思**

### 关键原则

1. **突破需要想象力**
   - 避免路径依赖，适当发散思考
   - 大方向和策略的改变比细节优化更重要
   - 工具放大改变的效果和范围（对的和错的都会放大）

2. **积极使用工具**
   - 主动使用 skill、plugin、command
   - AI 只说不做无法产生改变
   - 代码无差别，随时可以重构

3. **从错误中学习**
   - 及时反思总结，增加到 CLAUDE.md
   - 通过 demo 和 case 学习，提取抽象可复制的经验
   - 意识到环境和反馈对自己的影响

4. **最小化 vs 最积极**
   - 架构足够好时，个体智能不需要太高
   - 最小化使用 AI（简单任务）
   - 最积极使用 AI（复杂决策、创意生成）

5. **愿景**
   - 一公司的人打电脑，忽然某天电脑就自己跑起来，人就可以站起来走了
   - 从简单的例子开始变强变复杂
   - AI 能去焦虑

## 技术亮点

### 1. 多源采集 + 智能去重

**架构设计**：采集器基类 + 策略模式，10个采集器并发执行
```
BaseCollector (抽象基类)
├── httpx 采集器：财联社、东方财富、新浪、Bloomberg、CNBC
└── Playwright 采集器：动态渲染页面（金十、华尔街见闻）
```

**亮点**：
- `safe_collect()` 统一异常处理，单个源失败不影响整体
- Playwright 采集器串行执行 + 3秒间隔，避免被封
- 按标题去重，按时间排序，处理混合时区问题

### 2. AI 语义分类 ETF

**问题**：ETF 名称多样（"芯片ETF"、"半导体50"、"集成电路"），关键词匹配不准

**解决方案**：Claude AI 批量分类
```python
prompt = """对以下ETF进行行业板块分类...
分类规则：相似板块统一名称（券商→证券，医疗→医药）
排除类型：宽基指数、债券、货币、跨境..."""
```

**亮点**：
- AI 理解语义，"科创芯片ETF" 和 "半导体龙头" 都归入"芯片"
- 代码层面二次过滤，排除宽基/债券/跨境 ETF
- 板块别名映射（贵金属→黄金，新能源→光伏）保证前后端一致

### 3. 多级数据源降级

**策略**：主源失败自动切换备用源
```
ETF列表：新浪 API → 东方财富 API
K线数据：东方财富 → 新浪（修复 sparkline 缺失）
R2存储：binding 直连 → HTTP 公开 URL
```

**亮点**：
- 缓存机制（K线 5分钟，ETF列表 24小时）减少 API 调用
- 异常时静默降级，不中断主流程

### 4. SSR + 异步水合

**渲染策略**：服务端预渲染 + 客户端异步加载实时数据
```
首屏：SSR 渲染历史数据（20日涨跌、K线图）
水合：JS 异步请求 /api/batch-sector-etfs 覆盖实时价格
```

**亮点**：
- 首屏秒开，无需等待实时 API
- 实时数据只更新价格/涨跌/成交额，保留历史 K线

### 5. JSON 自动修复

**问题**：AI 输出的 JSON 偶尔格式错误

**修复策略**：
```python
# 移除尾部逗号
text = re.sub(r',(\s*[}\]])', r'\1', text)
# 中文引号替换
text = text.replace('"', '"').replace('"', '"')
```

### 6. Serverless 架构

**成本优化**：
- GitHub Actions 免费额度运行采集（含 Playwright）
- Cloudflare Workers 免费额度托管前端
- R2 存储静态 JSON，无数据库成本
- 每小时更新，API 调用量可控

### 7. 决策仪表盘

**借鉴来源**：[daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)

**核心功能**：
- 板块信号：🟢买入 / 🟡观望 / 🔴回避
- 检查清单：✅利好 / ⚠️注意 / ❌风险
- 风险提示 + 机会提示独立展示

**AI Prompt 设计**：
```python
# 嵌入交易原则到 prompt
TRADING_PRINCIPLES = """
1. 板块轮动规律：资金从高位板块流向低位板块
2. ETF配置原则：优先选择成交额>5亿、跟踪误差小的ETF
3. 风险识别要点：连续大涨后警惕回调，政策利空需规避
"""
```

### 8. 企业微信推送

**模块**：`src/notify/wechat.py`

**功能**：
- 分析完成后自动推送到企业微信群
- Markdown 格式，包含板块信号、风险/机会提示
- 配置 `WECHAT_WEBHOOK_URL` 环境变量即可启用

**消息格式**：
```markdown
## 🎯 市场观点标题

摘要内容...

### 板块信号
> 🟢 **半导体** 🔥🔥🔥 利好
>    ✅ AI需求强劲 ✅ 业绩超预期

### ⚠️ 风险提示
> 风险1：...

### 💡 机会提示
> 机会1：...

---
📊 基于 381 条新闻分析 | 01-31 00:41
🔗 [查看详情](https://etf.aurora-bots.com/)
```

### 9. 板块7日趋势

**功能**：展示板块近7天的方向变化，帮助识别趋势

**数据流**：
```
每日归档 → load_history() → build_sector_trends() → 前端展示
                         ↓
              format_history_context() → AI分析上下文
```

**趋势箭头**：
- ↑ 利好 / ↓ 利空 / → 中性或未提及
- 示例：`↑↓↓↓↓↑↑` 表示近日转好

**趋势描述**：
- `N连利好/利空`：连续N天同方向
- `近日转好/转弱`：最近3天方向变化
- `整体偏好/偏弱`：统计多数方向
- `震荡`：涨跌持平

**历史上下文**：AI 分析时会参考近3日市场观点 + 近7日板块趋势
