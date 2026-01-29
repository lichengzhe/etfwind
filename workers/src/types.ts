// 板块数据
export interface Sector {
  name: string
  heat: number
  direction: '利好' | '利空' | '中性'
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

// 分析结果（FOTH Matrix）
export interface AnalysisResult {
  market_view: string
  narrative: string
  facts?: string[]
  opinions?: Opinions
  sectors: Sector[]
  risk_level: string
}

// API 返回的完整数据
export interface LatestData {
  result: AnalysisResult
  updated_at: string
  news_count: number
  source_stats: Record<string, number>
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
