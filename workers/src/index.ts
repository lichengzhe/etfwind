import { Hono } from 'hono'
import { cors } from 'hono/cors'
import type { Env, LatestData, NewsItem } from './types'
import { fetchFunds } from './services/fund'
import { renderHome } from './pages/Home'
import { renderNews } from './pages/News'

const app = new Hono<{ Bindings: Env }>()

// CORS
app.use('*', cors())

// R2 公开 URL（备用）
const R2_URL = 'https://pub-bf3ac083583c4798b8f0091067ae106d.r2.dev'

// 从 R2 加载数据
async function loadData(r2: R2Bucket): Promise<LatestData> {
  const obj = await r2.get('latest.json')
  if (obj) return await obj.json() as LatestData
  // 备用：HTTP 请求
  const resp = await fetch(`${R2_URL}/latest.json`)
  return await resp.json() as LatestData
}

// 从 R2 加载 ETF Master
async function loadEtfMaster(r2: R2Bucket): Promise<Record<string, any>> {
  let data: any
  const obj = await r2.get('etf_master.json')
  if (obj) {
    data = await obj.json()
  } else {
    const resp = await fetch(`${R2_URL}/etf_master.json`)
    data = await resp.json()
  }
  // 处理 { "etfs": { ... } } 结构
  return data.etfs || data
}

// 从 R2 加载新闻
async function loadNews(r2: R2Bucket): Promise<NewsItem[]> {
  let data: any
  const obj = await r2.get('news.json')
  if (obj) {
    data = await obj.json()
  } else {
    const resp = await fetch(`${R2_URL}/news.json`)
    data = await resp.json()
  }
  // 处理 { "news": [...] } 结构
  return data.news || data
}

// ========== 路由 ==========

// 首页
app.get('/', async (c) => {
  const [data, etfMaster, news] = await Promise.all([
    loadData(c.env.R2),
    loadEtfMaster(c.env.R2),
    loadNews(c.env.R2),
  ])
  // 从 news.json 统计实际的 source 分布
  const sourceStats: Record<string, number> = {}
  for (const item of news) {
    sourceStats[item.source] = (sourceStats[item.source] || 0) + 1
  }
  // 覆盖 latest.json 中的 source_stats
  data.source_stats = sourceStats
  data.news_count = news.length
  return c.html(renderHome(data, etfMaster))
})

// API: 分析数据
app.get('/api/data', async (c) => {
  const data = await loadData(c.env.R2)
  return c.json(data)
})

// API: ETF 实时行情
app.get('/api/funds', async (c) => {
  const codes = c.req.query('codes')?.split(',').filter(Boolean) || []
  const funds = await fetchFunds(codes)
  return c.json(funds)
})

// API: 批量板块 ETF
app.get('/api/batch-sector-etfs', async (c) => {
  const sectors = c.req.query('sectors')?.split(',').filter(Boolean) || []
  const etfMaster = await loadEtfMaster(c.env.R2)

  const result: Record<string, any[]> = {}
  const allCodes: string[] = []

  // 找出每个板块的 ETF
  for (const sector of sectors) {
    const etfs = Object.values(etfMaster)
      .filter((e: any) => e.sector === sector)
      .slice(0, 3)
    result[sector] = etfs
    allCodes.push(...etfs.map((e: any) => e.code))
  }

  // 批量获取实时行情
  const realtime = await fetchFunds([...new Set(allCodes)])

  // 合并数据：只用实时数据覆盖价格、今日涨跌、成交额，保留 etfMaster 中的 5日/20日/K线
  for (const sector of sectors) {
    result[sector] = result[sector].map((e: any) => {
      const rt = realtime[e.code]
      if (!rt) return e
      return {
        ...e,
        price: rt.price,
        change_pct: rt.change_pct,
        amount_yi: rt.amount_yi,
      }
    })
    // 按成交额排序
    result[sector].sort((a: any, b: any) => (b.amount_yi || 0) - (a.amount_yi || 0))
  }

  return c.json({ data: result })
})

// API: ETF Master
app.get('/api/etf-master', async (c) => {
  const etfMaster = await loadEtfMaster(c.env.R2)
  return c.json(etfMaster)
})

// 新闻页
app.get('/news', async (c) => {
  const source = c.req.query('source')
  let news = await loadNews(c.env.R2)
  if (source) {
    news = news.filter(n => n.source === source)
  }
  return c.html(renderNews(news, source))
})

// 健康检查
app.get('/health', (c) => c.json({ status: 'ok' }))

export default app
