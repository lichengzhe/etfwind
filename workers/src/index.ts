import { Hono } from 'hono'
import { cors } from 'hono/cors'
import type { Env, LatestData, NewsItem } from './types'
import { SECTOR_ALIAS } from './types'
import { fetchFunds, fetchKline } from './services/fund'
import { renderHome } from './pages/Home'
import { renderNews } from './pages/News'
import { renderCycle } from './pages/Cycle'

const app = new Hono<{ Bindings: Env }>()

// CORS
app.use('*', cors())

// Basic in-memory rate limiter (best-effort per worker instance)
const RATE_LIMIT_WINDOW_MS = 60_000
const RATE_LIMIT_MAX = 120
const rateState = new Map<string, { count: number; reset: number }>()

function getClientId(c: any): string {
  return (
    c.req.header('cf-connecting-ip') ||
    c.req.header('x-forwarded-for') ||
    'unknown'
  )
}

function checkRateLimit(c: any): Response | null {
  const now = Date.now()
  const key = getClientId(c)
  const state = rateState.get(key)
  if (!state || now > state.reset) {
    rateState.set(key, { count: 1, reset: now + RATE_LIMIT_WINDOW_MS })
    return null
  }
  state.count += 1
  if (state.count > RATE_LIMIT_MAX) {
    return c.json({ error: 'rate_limited' }, 429)
  }
  return null
}

async function withCache(
  c: any,
  key: string,
  ttlSeconds: number,
  fetcher: () => Promise<Response>
): Promise<Response> {
  const cache = caches.default
  const cacheKey = new Request(key)
  const cached = await cache.match(cacheKey)
  if (cached) return cached

  const resp = await fetcher()
  const out = new Response(resp.body, resp)
  out.headers.set('Cache-Control', `public, max-age=${ttlSeconds}`)
  c.executionCtx.waitUntil(cache.put(cacheKey, out.clone()))
  return out
}

// Apply rate limiting to API routes only
app.use('/api/*', async (c, next) => {
  const limited = checkRateLimit(c)
  if (limited) return limited
  await next()
})

// R2 公开 URL（备用）
const R2_URL = 'https://pub-bf3ac083583c4798b8f0091067ae106d.r2.dev'

// 从 R2 加载数据
async function loadData(r2: R2Bucket): Promise<LatestData> {
  try {
    const obj = await r2.get('latest.json')
    if (obj) return await obj.json() as LatestData
  } catch (e) {
    console.error('R2 load failed:', e)
  }
  // 备用：HTTP 请求
  const resp = await fetch(`${R2_URL}/latest.json`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  return await resp.json() as LatestData
}

// 从 R2 加载 ETF Master
async function loadEtfMaster(r2: R2Bucket): Promise<Record<string, any>> {
  let data: any
  try {
    const obj = await r2.get('etf_master.json')
    if (obj) {
      data = await obj.json()
      return data.etfs || data
    }
  } catch (e) {
    console.error('R2 etf_master load failed:', e)
  }
  const resp = await fetch(`${R2_URL}/etf_master.json`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  data = await resp.json()
  return data.etfs || data
}

// 从 R2 加载新闻
async function loadNews(r2: R2Bucket): Promise<NewsItem[]> {
  let data: any
  try {
    const obj = await r2.get('news.json')
    if (obj) {
      data = await obj.json()
      return data.news || data
    }
  } catch (e) {
    console.error('R2 news load failed:', e)
  }
  const resp = await fetch(`${R2_URL}/news.json`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  data = await resp.json()
  return data.news || data
}

// ========== 路由 ==========

// 首页
app.get('/', async (c) => {
  return await withCache(c, c.req.url, 300, async () => {
    const [data, etfMaster] = await Promise.all([
      loadData(c.env.R2),
      loadEtfMaster(c.env.R2),
    ])
    return c.html(renderHome(data, etfMaster))
  })
})

// API: 分析数据
app.get('/api/data', async (c) => {
  return await withCache(c, c.req.url, 1800, async () => {
    const data = await loadData(c.env.R2)
    return c.json(data)
  })
})

// API: ETF 实时行情
app.get('/api/funds', async (c) => {
  return await withCache(c, c.req.url, 300, async () => {
    const codes = c.req.query('codes')?.split(',').filter(Boolean) || []
    const funds = await fetchFunds(codes)
    return c.json(funds)
  })
})

// API: ETF K线数据（90天收盘价 + 5日/20日涨跌幅，24h缓存）
app.get('/api/kline', async (c) => {
  return await withCache(c, c.req.url, 86400, async () => {
    const codes = c.req.query('codes')?.split(',').filter(Boolean) || []
    if (!codes.length) return c.json({})
    const klineData = await fetchKline(codes)
    return c.json(klineData)
  })
})

// API: 批量板块 ETF
app.get('/api/batch-sector-etfs', async (c) => {
  return await withCache(c, c.req.url, 300, async () => {
    const sectors = c.req.query('sectors')?.split(',').filter(Boolean) || []
    const etfMaster = await loadEtfMaster(c.env.R2)

    const result: Record<string, any[]> = {}
    const allCodes: string[] = []

    // 找出每个板块的 ETF（按成交额排序）
    for (const sector of sectors) {
      const lookupSector = SECTOR_ALIAS[sector] || sector
      const etfs = Object.values(etfMaster)
        .filter((e: any) => e.sector === lookupSector)
        .sort((a: any, b: any) => (b.amount_yi || 0) - (a.amount_yi || 0))
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
})

// API: ETF Master（返回完整数据含 sector_list/sectors/updated_at）
app.get('/api/etf-master', async (c) => {
  return await withCache(c, c.req.url, 86400, async () => {
    let data: any
    try {
      const obj = await c.env.R2.get('etf_master.json')
      if (obj) {
        data = await obj.json()
        return c.json(data)
      }
    } catch (e) {
      console.error('R2 etf_master load failed:', e)
    }
    const resp = await fetch(`${R2_URL}/etf_master.json`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data = await resp.json()
    return c.json(data)
  })
})

// API: 市场总览（全球指标 + 商品周期，合并减少请求数）
app.get('/api/market-overview', async (c) => {
  return await withCache(c, c.req.url, 600, async () => {
    const indices: Record<string, any> = {}
    const commodities: Record<string, any> = {}

    // === 全球指标 ===
    const emCodes: Record<string, { secid: string; name: string }> = {
      usdcny: { secid: '133.USDCNH', name: '美元' },
      gold: { secid: '101.GC00Y', name: '黄金' },
      sh: { secid: '1.000001', name: '上证' },
    }

    // Yahoo 符号：BTC、纳指 + 商品周期
    const yahooSymbols: Record<string, { symbol: string; name: string; target: 'indices' | 'commodities' }> = {
      btc: { symbol: 'BTC-USD', name: 'BTC', target: 'indices' },
      nasdaq: { symbol: '%5EIXIC', name: '纳指', target: 'indices' },
      gold_c: { symbol: 'GC=F', name: '黄金', target: 'commodities' },
      silver: { symbol: 'SI=F', name: '白银', target: 'commodities' },
      copper: { symbol: 'HG=F', name: '铜', target: 'commodities' },
      oil: { symbol: 'CL=F', name: '原油', target: 'commodities' },
      corn: { symbol: 'ZC=F', name: '玉米', target: 'commodities' },
    }

    // 并发：东方财富 + 所有 Yahoo 请求
    const emFetches = Object.entries(emCodes).map(async ([key, { secid, name }]) => {
      try {
        const resp = await fetch(
          `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=${secid}&fields1=f1,f2,f3&fields2=f51,f52&klt=101&fqt=1&end=20500101&lmt=180`
        )
        const data = await resp.json() as any
        const klines = data?.data?.klines || []
        const prices = klines.map((k: string) => parseFloat(k.split(',')[1]))
        if (prices.length) {
          indices[key] = { name, price: prices[prices.length - 1], kline: prices }
        }
      } catch (e) { console.error(`东方财富 ${name} 错误:`, e) }
    })

    const yahooFetches = Object.entries(yahooSymbols).map(async ([key, { symbol, name, target }]) => {
      try {
        const resp = await fetch(
          `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=6mo`,
          { headers: { 'User-Agent': 'Mozilla/5.0' } }
        )
        const data = await resp.json() as any
        const closes = data?.chart?.result?.[0]?.indicators?.quote?.[0]?.close || []
        const prices = closes.filter((c: any) => c != null)
        if (!prices.length) return

        const price = prices[prices.length - 1]
        if (target === 'indices') {
          indices[key] = { name, price, kline: prices }
        } else {
          if (prices.length >= 20) {
            const price5d = prices[prices.length - 6] || prices[0]
            const price20d = prices[prices.length - 21] || prices[0]
            const realKey = key === 'gold_c' ? 'gold' : key
            commodities[realKey] = {
              name, price, kline: prices,
              change_5d: ((price - price5d) / price5d * 100),
              change_20d: ((price - price20d) / price20d * 100),
            }
          }
        }
      } catch (e) { console.error(`Yahoo ${name} 错误:`, e) }
    })

    await Promise.all([...emFetches, ...yahooFetches])

    // === 商品周期计算 ===
    const order = ['gold', 'silver', 'copper', 'oil', 'corn']
    const stageNames = ['黄金领涨期', '白银跟涨期', '铜价上涨期', '油价上涨期', '农产品补涨期']
    const momentum = order
      .filter(k => commodities[k])
      .map(k => ({
        key: k,
        score: (commodities[k].change_5d || 0) * 2 + (commodities[k].change_20d || 0)
      }))
      .sort((a, b) => b.score - a.score)

    const leader = momentum[0]?.key || 'gold'
    const stage = order.indexOf(leader) + 1

    return c.json({
      indices,
      commodities,
      cycle: {
        stage,
        leader,
        stage_name: stageNames[stage - 1] || '未知',
        next: order[(stage) % 5],
        momentum: momentum.map(m => ({ ...m, name: commodities[m.key]?.name }))
      }
    })
  })
})

// API: 信号回测数据
app.get('/api/review', async (c) => {
  return await withCache(c, c.req.url, 1800, async () => {
    let data: any
    try {
      const obj = await c.env.R2.get('review.json')
      if (obj) {
        data = await obj.json()
        return c.json(data)
      }
    } catch (e) {
      console.error('R2 review load failed:', e)
    }
    const resp = await fetch(`${R2_URL}/review.json`)
    if (!resp.ok) return c.json({}, 404)
    data = await resp.json()
    return c.json(data)
  })
})

// 周期页面
app.get('/cycle', (c) => {
  return c.html(renderCycle())
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

// Sitemap.xml
app.get('/sitemap.xml', (c) => {
  const today = new Date().toISOString().split('T')[0]
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://etf.aurora-bots.com/</loc>
    <lastmod>${today}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://etf.aurora-bots.com/news</loc>
    <lastmod>${today}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://etf.aurora-bots.com/cycle</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>`
  return c.text(xml, 200, { 'Content-Type': 'application/xml' })
})

// robots.txt
app.get('/robots.txt', (c) => {
  const txt = `User-agent: *
Allow: /
Sitemap: https://etf.aurora-bots.com/sitemap.xml`
  return c.text(txt)
})

// API: 每日海报 SVG
app.get('/api/poster', async (c) => {
  return await withCache(c, c.req.url, 3600, async () => {
    const data = await loadData(c.env.R2)
    const { result, updated_at } = data

  // XML 转义 + 移除 emoji
  const esc = (s: string) => s
    .replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .trim()

  // 格式化日期
  const date = new Date(updated_at)
  const dateStr = `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`

  // 取前4个板块
  const sectors = (result.sectors || []).slice(0, 4)

  // 生成板块列表 SVG
  const sectorsSvg = sectors.map((s: any, i: number) => {
    const y = 280 + i * 80
    const dirColor = s.direction === '利好' ? '#dc2626' : s.direction === '利空' ? '#16a34a' : '#6b7280'
    const stars = '★'.repeat(s.heat)
    const analysis = esc(s.analysis.slice(0, 35))
    return `<rect x="40" y="${y}" width="520" height="70" rx="8" fill="#fff" opacity="0.9"/>
<text x="60" y="${y + 30}" font-size="20" font-weight="bold" fill="#1f2937">${esc(s.name)}</text>
<text x="60" y="${y + 55}" font-size="14" fill="#6b7280">${analysis}...</text>
<text x="480" y="${y + 30}" font-size="14" fill="${dirColor}" text-anchor="end">${s.direction}</text>
<text x="540" y="${y + 30}" font-size="12" fill="#fbbf24" text-anchor="end">${stars}</text>`
  }).join('\n')

  const marketView = esc(result.market_view)
  const narrative = result.summary || result.narrative || ''
  const line1 = esc(narrative.slice(0, 40))
  const line2 = esc(narrative.slice(40, 80))
  const line3 = esc(narrative.slice(80, 120))

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
<defs>
<linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
<stop offset="0%" stop-color="#667eea"/>
<stop offset="100%" stop-color="#764ba2"/>
</linearGradient>
</defs>
<rect width="600" height="800" fill="url(#bg)"/>
<text x="300" y="60" font-size="32" font-weight="bold" fill="#fff" text-anchor="middle">ETF风向标</text>
<text x="300" y="95" font-size="16" fill="#ffffffcc" text-anchor="middle">${dateStr} - AI驱动投资分析</text>
<rect x="40" y="120" width="520" height="130" rx="12" fill="#fff" opacity="0.95"/>
<text x="60" y="155" font-size="18" font-weight="bold" fill="#1f2937">${marketView}</text>
<text x="60" y="185" font-size="13" fill="#6b7280">
<tspan x="60" dy="0">${line1}</tspan>
<tspan x="60" dy="20">${line2}</tspan>
<tspan x="60" dy="20">${line3}...</tspan>
</text>
<text x="300" y="265" font-size="16" font-weight="bold" fill="#fff" text-anchor="middle">今日热门板块</text>
${sectorsSvg}
<text x="300" y="760" font-size="14" fill="#ffffffb3" text-anchor="middle">etf.aurora-bots.com</text>
<text x="300" y="780" font-size="12" fill="#ffffff80" text-anchor="middle">数据来源：财联社、东方财富、Bloomberg</text>
</svg>`

    return c.text(svg, 200, { 'Content-Type': 'image/svg+xml; charset=utf-8' })
  })
})

// 健康检查
app.get('/health', (c) => c.json({ status: 'ok' }))

export default app
