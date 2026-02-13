// ETF 行情服务 - 调用东方财富 API
import type { EtfData } from '../types'

const EASTMONEY_API = 'https://push2.eastmoney.com/api/qt/ulist.np/get'
const EASTMONEY_KLINE_API = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'

// 获取交易所前缀
function getSecid(code: string): string {
  const prefix = code.startsWith('15') || code.startsWith('16') ? '0' : '1'
  return `${prefix}.${code}`
}

// 批量获取 ETF 实时行情
export async function fetchFunds(codes: string[]): Promise<Record<string, EtfData>> {
  if (!codes.length) return {}

  const secids = codes.map(getSecid).join(',')
  const params = new URLSearchParams({
    secids,
    fields: 'f12,f14,f2,f3,f5,f6,f15,f16,f17,f18',
    ut: 'fa5fd1943c7b386f172d6893dbfba10b'
  })

  const resp = await fetch(`${EASTMONEY_API}?${params}`)
  const json = await resp.json() as any

  const result: Record<string, EtfData> = {}
  for (const item of json.data?.diff || []) {
    result[item.f12] = {
      code: item.f12,
      name: item.f14,
      price: item.f2 / 1000,
      change_pct: item.f3 / 100,
      change_5d: 0,
      change_20d: 0,
      amount_yi: item.f6 / 100000000,
      flow_yi: 0,
      turnover: 0,
      kline: []
    }
  }
  return result
}

// 批量获取 ETF K线数据（90天收盘价 + 5日/20日涨跌幅）
export async function fetchKline(codes: string[]): Promise<Record<string, { name?: string; change_5d: number; change_20d: number; kline: number[] }>> {
  if (!codes.length) return {}

  const results: Record<string, { name?: string; change_5d: number; change_20d: number; kline: number[] }> = {}

  await Promise.all(codes.map(async (code) => {
    try {
      const secid = getSecid(code)
      const resp = await fetch(
        `${EASTMONEY_KLINE_API}?secid=${secid}&fields1=f1,f2,f3&fields2=f51,f52&klt=101&fqt=1&end=20500101&lmt=95`
      )
      const data = await resp.json() as any
      const klines: string[] = data?.data?.klines || []
      const closes = klines.map((k: string) => parseFloat(k.split(',')[1]))
      if (closes.length) {
        const today = closes[closes.length - 1]
        const name = data?.data?.name || undefined
        results[code] = {
          name,
          change_5d: closes.length >= 6 && closes[closes.length - 6] ? +((today - closes[closes.length - 6]) / closes[closes.length - 6] * 100).toFixed(2) : 0,
          change_20d: closes.length >= 21 && closes[closes.length - 21] ? +((today - closes[closes.length - 21]) / closes[closes.length - 21] * 100).toFixed(2) : 0,
          kline: closes.slice(-90),
        }
      }
    } catch (e) {
      console.error(`K线获取失败 ${code}:`, e)
    }
  }))

  return results
}
