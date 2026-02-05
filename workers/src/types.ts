// 板块数据
export interface Sector {
  name: string
  heat: number
  direction: '利好' | '利空' | '中性'
  confidence?: number
  analysis: string
  catalyst?: string
  news?: string[]
  etfs?: EtfData[]
}

// 市场情绪
export interface Opinions {
  sentiment?: string
  hot_words?: string[]
  media_bias?: string
}

// 分析结果
export interface AnalysisResult {
  market_view: string
  summary?: string
  narrative?: string
  sentiment?: string
  sectors: Sector[]
  risk_alerts?: string[]
  opportunity_hints?: string[]
  commodity_cycle?: {
    stage: number
    stage_name: string
    leader: string
    analysis: string
  }
}

// API 返回的完整数据
export interface LatestData {
  result: AnalysisResult
  sector_trends?: Record<string, SectorTrend>
  review?: ReviewSummary
  overheat?: OverheatInfo | null
  updated_at: string
  news_count: number
  source_stats: Record<string, number>
}

export interface ReviewSummary {
  as_of: string
  horizons: Record<string, ReviewHorizon>
  benchmark?: { name: string; secid: string }
}

export interface ReviewHorizon {
  count: number
  win_rate: number
  avg_return: number
  avg_excess?: number
}

export interface OverheatInfo {
  level: '偏热' | '过热'
  note: string
  count: number
}

// 板块7日趋势
export interface SectorTrend {
  arrows: string  // "↑↑↓↑↑↑↑"
  desc: string    // "近日转好"
}

// ETF 数据
export interface EtfData {
  code: string
  name: string
  price: number
  change_pct: number
  change_5d: number
  change_20d: number
  amount_yi: number
  flow_yi: number
  turnover: number
  kline: number[]
}

// 新闻条目
export interface NewsItem {
  title: string
  source: string
  url: string
  published_at: string
}

// Cloudflare 绑定
export interface Env {
  R2: R2Bucket
}

// 板块别名映射（AI输出 -> ETF板块）
export const SECTOR_ALIAS: Record<string, string> = {
  '新能源车': '锂电池',
  '新能源': '光伏',
  '创新药': '医药',
  '贵金属': '黄金',
  '券商': '证券',
}
