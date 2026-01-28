# ETF风向标

AI 驱动的 ETF 投资风向分析工具。自动采集财经新闻，通过 Claude AI 分析生成板块研判和 ETF 推荐。

**在线访问**: https://etf.aurora-ai.workers.dev/

## 功能

- 10+ 新闻源自动采集（财联社、东方财富、新浪、Bloomberg、CNBC、金十、华尔街见闻）
- Claude AI 分析市场动态，输出板块研判 + 风险提示
- 智能匹配板块 ETF，展示实时行情 + 20日走势
- 每小时自动更新

## 架构

```
GitHub Actions (每小时) → 采集+AI分析 → JSON → R2 → Cloudflare Workers
```

| 组件 | 技术 |
|------|------|
| 前端 | Cloudflare Workers + Hono + TypeScript |
| AI | Claude API (httpx 直接调用) |
| 采集 | httpx + BeautifulSoup + Playwright |
| 数据 | 东方财富 API + 新浪 API |
| 存储 | Cloudflare R2 |

## 技术亮点

**多源采集**：10个采集器并发，Playwright 处理动态页面，按标题去重

**AI 语义分类**：Claude 批量分类 ETF，"科创芯片ETF"和"半导体龙头"都归入"芯片"

**数据源降级**：新浪→东方财富自动切换，K线缓存5分钟

**SSR + 水合**：服务端预渲染历史数据，客户端异步加载实时价格

**零成本部署**：GitHub Actions + Cloudflare Workers 免费额度

## 本地开发

```bash
# 运行采集+分析
uv run python -m src.worker_simple

# Workers 开发/部署
cd workers && npm run dev
cd workers && npm run deploy
```

## 环境变量

```bash
CLAUDE_API_KEY=sk-xxx        # 必需
CLAUDE_BASE_URL=https://...  # 可选，支持中转
```

## License

MIT
