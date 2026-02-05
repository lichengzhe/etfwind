# ETF风向标

AI 驱动的 ETF 投资风向分析工具。自动采集财经新闻，通过 Claude AI 分析生成板块研判和 ETF 推荐。

**在线访问**: https://etf.aurora-bots.com/

## 项目背景

作为一个业余投资者，每天要看大量财经新闻，但信息太碎片化了。于是萌生了一个想法：**能不能让 AI 帮我读新闻，然后告诉我今天该关注哪些板块？**

## 功能

- 10+ 新闻源自动采集（财联社、东方财富、新浪、Bloomberg、CNBC、金十、华尔街见闻）
- Claude AI 分析市场动态，输出板块研判 + 风险提示
- 板块证据卡片 + 置信度评分（来源可追溯）
- 智能匹配板块 ETF，展示实时行情 + 90日走势
- 商品周期轮动指标（黄金→白银→铜→石油→农产品）
- **决策仪表盘**：买入/观望/回避信号 + 综合分析
- **企业微信推送**：分析完成自动推送到群
- 每小时自动更新，完全自动化

## 架构

```
GitHub Actions (每小时)
├── 采集新闻 → news.json → R2
└── AI分析 → latest.json → R2
         ↓
Cloudflare Workers ← 读取 R2 渲染页面
         ↓
用户访问 etf.aurora-bots.com
```

把采集和分析分开的好处：
1. 采集需要 Playwright，比较重
2. 分析只需要读 JSON，可以单独触发
3. 某一步失败不影响另一步

| 组件 | 技术 |
|------|------|
| 采集 | Python + httpx + Playwright |
| AI | Claude API (httpx 直接调用) |
| 前端 | Cloudflare Workers + Hono |
| 存储 | Cloudflare R2 |
| 数据 | 东方财富 API + Yahoo Finance |

**为什么选这套？** 几乎零成本：
- GitHub Actions 免费额度够用
- Cloudflare Workers/R2 免费额度够用
- Claude API 每小时调用一次，成本可控

## 技术亮点

### 1. 多源采集 + 智能去重

10 个采集器并发跑，用基类统一异常处理：

```python
class BaseCollector:
    async def safe_collect(self):
        try:
            return await self.collect()
        except Exception as e:
            logger.warning(f"{self.name} 采集失败: {e}")
            return []
```

单个源挂了不影响整体，最后按标题去重。

### 2. 让 AI 只做"填空题"

一开始让 AI 直接输出完整 JSON，经常格式错误或字段遗漏。后来改成分步提取：

```python
# 第一步：识别重要事件
step1 = "从新闻中识别最重要的5个事件，只输出标题列表"

# 第二步：逐个分析
step2 = "对于事件'{title}'，提供：1.所属板块 2.分析 3.建议"

# 代码负责组装最终 JSON
```

AI 只负责"内容生成"，代码负责"结构组装"，稳定多了。

### 3. SSR + 异步水合

首屏用服务端渲染历史数据（5日/20日涨跌、K线图），然后客户端异步请求实时价格覆盖：

```javascript
// 服务端预渲染 ETF 表格（历史数据）
// 客户端加载后请求实时数据
async function loadSectorEtfs() {
  const resp = await fetch('/api/batch-sector-etfs?sectors=黄金,芯片')
  // 只更新价格、今日涨跌、成交额
}
```

首屏秒开，实时数据异步加载。

### 4. 商品周期轮动

追踪「黄金→白银→铜→石油→农产品」的周期传导：

```javascript
// 计算动量得分
const momentum = commodities.map(c => ({
  key: c.key,
  score: c.change_5d * 2 + c.change_20d  // 5日权重更高
})).sort((a, b) => b.score - a.score)

const leader = momentum[0].key  // 当前领涨品种
```

理论上，经济周期会按这个顺序传导，可以提前布局下一个品种。

## 本地开发

```bash
# 只运行采集
uv run python -m src.collect_news

# 只运行分析
uv run python -m src.analyze_news

# 采集+分析一起跑
uv run python -m src.worker_simple

# Workers 开发
cd workers && npm run dev

# Workers 部署
cd workers && npm run deploy
```

## 环境变量

```bash
CLAUDE_API_KEY=sk-xxx        # 必需
CLAUDE_BASE_URL=https://...  # 可选，支持中转
CLAUDE_MODEL=claude-sonnet-4-20250514  # 可选
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx  # 可选，企业微信推送
```

## 踩过的坑

1. **Playwright 在 GitHub Actions 里很慢** - 串行执行 + 加延迟，避免被封
2. **AI 输出的 JSON 有时格式错误** - 加了自动修复（移除尾部逗号、替换中文引号）
3. **SVG 里的 emoji 会导致编码错误** - 用正则过滤掉 emoji
4. **ETF 名称多样，关键词匹配不准** - 改用 AI 语义分类

## License

MIT
