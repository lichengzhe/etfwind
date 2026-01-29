import type { LatestData, HotWord } from '../types'
import { styles } from './styles'

// 格式化时间（年月日 时分）
function formatTime(dateStr: string): string {
  const match = dateStr.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (match) {
    return `${match[1]}年${parseInt(match[2])}月${parseInt(match[3])}日 ${match[4]}:${match[5]}`
  }
  return '--'
}

// 生成星星
function stars(n: number): string {
  return '★'.repeat(n)
}

// 方向样式
function dirClass(dir: string): string {
  if (dir === '利好') return 'up'
  if (dir === '利空') return 'down'
  return 'neutral'
}

// 渲染词云
function renderWordCloud(hotWords: HotWord[] | string[] | undefined): string {
  if (!hotWords?.length) return ''
  // 兼容旧格式（字符串数组）和新格式（对象数组）
  const normalized: HotWord[] = hotWords.map((hw, i) => {
    if (typeof hw === 'string') {
      // 旧格式：按位置分配权重（前面的词权重高）
      return { word: hw, weight: Math.max(1, 5 - i) }
    }
    return hw
  })
  // 打乱顺序让词云更自然
  const shuffled = normalized.sort(() => Math.random() - 0.5)
  return `<div class="word-cloud">${shuffled.map(hw =>
    `<span class="word w${hw.weight}">${hw.word}</span>`
  ).join('')}</div>`
}

// 客户端 JS
const clientScript = `
function sparkline(vals, w=40, h=14) {
  if (!vals || vals.length < 2) return '';
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const pts = vals.map((v, i) => \`\${i * w / (vals.length - 1)},\${h - (v - min) / range * h}\`).join(' ');
  const color = vals[vals.length-1] >= vals[0] ? '#dc2626' : '#16a34a';
  return \`<svg class="sparkline" width="\${w}" height="\${h}"><polyline points="\${pts}" fill="none" stroke="\${color}" stroke-width="1.2"/></svg>\`;
}

async function loadSectorEtfs() {
  const tables = document.querySelectorAll('.etf-table');
  const sectors = Array.from(tables).map(t => t.dataset.sector);
  if (!sectors.length) return;
  try {
    const resp = await fetch('/api/batch-sector-etfs?sectors=' + encodeURIComponent(sectors.join(',')));
    const { data } = await resp.json();
    for (const sector of sectors) {
      const table = document.querySelector(\`.etf-table[data-sector="\${sector}"]\`);
      const etfs = data[sector] || [];
      renderEtfs(table, etfs);
    }
  } catch (e) { console.error(e); }
}

function renderEtfs(table, etfs) {
  if (!etfs.length) return;
  const cls = v => v >= 0 ? 'up' : 'down';
  const fmt = v => Math.abs(v).toFixed(1) + '%';
  const fmtPrice = v => v == null ? '--' : v.toFixed(2);
  // 只更新实时数据列
  for (const f of etfs) {
    const row = table.querySelector(\`tr[data-code="\${f.code}"]\`);
    if (!row) continue;
    row.querySelector('.price').textContent = fmtPrice(f.price);
    const changeCell = row.querySelector('.change');
    changeCell.textContent = fmt(f.change_pct);
    changeCell.className = 'change ' + cls(f.change_pct);
    row.querySelector('.amount').textContent = f.amount_yi.toFixed(1) + '亿';
  }
}

loadSectorEtfs();
`

// 板块别名映射（AI输出 -> ETF板块）
const sectorAlias: Record<string, string> = {
  '新能源车': '锂电池', '新能源': '光伏', '创新药': '医药',
  '贵金属': '黄金', '券商': '证券',
}

// 渲染板块卡片
function renderSectorCard(sector: any, etfMaster: Record<string, any>): string {
  // 服务端预渲染 ETF 占位数据，按成交额排序
  const lookupSector = sectorAlias[sector.name] || sector.name
  const sectorEtfs = Object.values(etfMaster)
    .filter((e: any) => e.sector === lookupSector)
    .sort((a: any, b: any) => (b.amount_yi || 0) - (a.amount_yi || 0))
    .slice(0, 3) as any[]

  let tbodyHtml = '<tr><td colspan="6">暂无数据</td></tr>'
  if (sectorEtfs.length) {
    tbodyHtml = sectorEtfs.map((f: any) => `
      <tr data-code="${f.code}">
        <td><a href="https://quote.eastmoney.com/${f.code.startsWith('15') || f.code.startsWith('16') ? 'sz' : 'sh'}${f.code}.html" target="_blank">${f.name}(${f.code})</a></td>
        <td class="price">--</td>
        <td class="change">--</td>
        <td class="amount">--</td>
        <td class="${f.change_20d >= 0 ? 'up' : 'down'}">${Math.abs(f.change_20d).toFixed(1)}%</td>
        <td>${f.kline?.length ? `<svg class="sparkline" viewBox="0 0 100 16" preserveAspectRatio="none"><polyline points="${f.kline.map((v: number, i: number) => `${i * 100 / (f.kline.length - 1)},${16 - (v - Math.min(...f.kline)) / (Math.max(...f.kline) - Math.min(...f.kline) || 1) * 16}`).join(' ')}" fill="none" stroke="${f.kline[f.kline.length-1] >= f.kline[0] ? '#dc2626' : '#16a34a'}" stroke-width="1.2"/></svg>` : '-'}</td>
      </tr>
    `).join('')
  }

  const etfTableHtml = `
    <table class="etf-table" data-sector="${sector.name}">
      <thead>
        <tr>
          <th>ETF推荐</th><th>价格</th>
          <th>日涨跌</th><th>日成交</th><th>20日涨跌</th><th>20日走势</th>
        </tr>
      </thead>
      <tbody>${tbodyHtml}</tbody>
    </table>
  `

  return `
    <div class="sector-card ${dirClass(sector.direction)} heat-${sector.heat}">
      <div class="sector-header">
        <span class="sector-name">${sector.name}</span>
        <span class="sector-heat">${stars(sector.heat)}</span>
        <span class="sector-dir ${dirClass(sector.direction)}">${sector.direction}</span>
      </div>
      <div class="sector-analysis">${sector.analysis}</div>
      ${etfTableHtml}
    </div>
  `
}

// 渲染首页
export function renderHome(data: LatestData, etfMaster: Record<string, any>): string {
  const { result, updated_at, news_count, source_stats } = data

  // Source 按权威度排序
  const sourceOrder = ['Bloomberg', 'WSJ', 'CNBC', '财联社', '财联社电报', '新浪财经', '东方财富', '东财快讯', '新浪7x24', '金十数据', '华尔街见闻']
  const sourceStatsHtml = Object.entries(source_stats)
    .sort((a, b) => {
      const ia = sourceOrder.indexOf(a[0])
      const ib = sourceOrder.indexOf(b[0])
      return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
    })
    .map(([name, count]) => `<a href="/news?source=${encodeURIComponent(name)}">${name} ${count}</a>`)
    .join('')

  // 排序：利好优先，然后按热度从高到低
  const dirOrder: Record<string, number> = { '利好': 0, '中性': 1, '利空': 2 }
  const sectors = result.sectors || []
  const sortedSectors = [...sectors].sort((a, b) => {
    const dirDiff = (dirOrder[a.direction] ?? 1) - (dirOrder[b.direction] ?? 1)
    if (dirDiff !== 0) return dirDiff
    return b.heat - a.heat
  })
  const sectorsHtml = sortedSectors
    .map(sector => renderSectorCard(sector, etfMaster))
    .join('')

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ETF风向标</title>
  <style>${styles}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>ETF风向标</h1>
      <span class="meta">${formatTime(updated_at)}</span>
      <a href="/news" class="news-total">总新闻${news_count}条</a>
      <div class="source-stats">${sourceStatsHtml}</div>
      <a href="https://github.com/lichengzhe/etfwind" target="_blank" class="github-link" title="GitHub">
        <svg height="28" width="28" viewBox="0 0 1024 1024" fill="#1B1F23"><path fill-rule="evenodd" clip-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8C0 11.54 2.29 14.53 5.47 15.59C5.87 15.66 6.02 15.42 6.02 15.21C6.02 15.02 6.01 14.39 6.01 13.72C4 14.09 3.48 13.23 3.32 12.78C3.23 12.55 2.84 11.84 2.5 11.65C2.22 11.5 1.82 11.13 2.49 11.12C3.12 11.11 3.57 11.7 3.72 11.94C4.44 13.15 5.59 12.81 6.05 12.6C6.12 12.08 6.33 11.73 6.56 11.53C4.78 11.33 2.92 10.64 2.92 7.58C2.92 6.71 3.23 5.99 3.74 5.43C3.66 5.23 3.38 4.41 3.82 3.31C3.82 3.31 4.49 3.1 6.02 4.13C6.66 3.95 7.34 3.86 8.02 3.86C8.7 3.86 9.38 3.95 10.02 4.13C11.55 3.09 12.22 3.31 12.22 3.31C12.66 4.41 12.38 5.23 12.3 5.43C12.81 5.99 13.12 6.7 13.12 7.58C13.12 10.65 11.25 11.33 9.47 11.53C9.76 11.78 10.01 12.26 10.01 13.01C10.01 14.08 10 14.94 10 15.21C10 15.42 10.15 15.67 10.55 15.59C13.71 14.53 16 11.53 16 8C16 3.58 12.42 0 8 0Z" transform="scale(64)"/></svg>
      </a>
      <span class="powered-by" title="Claude Code 制作">
        <img src="https://hieufromwaterloo.ca/post/claude-code-complete-guide/featured.jpg_hu44047db731b94227537d7d3e39d43169_11674_1200x2500_fit_q75_h2_lanczos_3.webp" alt="Claude Code" height="32">
      </span>
    </header>

    <div class="card">
      <h2>${result.market_view}</h2>
      <p>${result.narrative}</p>
      ${result.facts?.length ? `
      <div class="foth-section">
        <div class="facts">
          <strong>今日事件</strong>
          <ul>${result.facts.map((f: string) => `<li>${f}</li>`).join('')}</ul>
        </div>
        ${result.opinions ? `
        <div class="opinions">
          <strong>市场情绪</strong>
          <span class="sentiment">${result.opinions.sentiment || ''}</span>
          <img src="/api/wordcloud" alt="词云" class="wordcloud-img" onerror="this.style.display='none'">
        </div>
        ` : ''}
      </div>
      ` : ''}
    </div>

    <div class="sectors-grid">
      ${sectorsHtml}
    </div>
  </div>

  <script>${clientScript}</script>
</body>
</html>`
}
