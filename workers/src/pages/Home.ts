import type { LatestData } from '../types'
import { SECTOR_ALIAS } from '../types'
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

// 客户端 JS
const clientScript = `
let isHoliday = false;

async function loadIndicators() {
  const el = document.getElementById('indicators-grid');
  if (!el) return;

  // 并发加载两个 API
  const [indicesResp, cycleResp] = await Promise.all([
    fetch('/api/global-indices').catch(() => null),
    fetch('/api/commodity-cycle').catch(() => null)
  ]);

  const indicesData = indicesResp ? await indicesResp.json() : {};
  const cycleData = cycleResp ? await cycleResp.json() : {};

  // 全球指标配置
  const indicesOrder = ['usdcny', 'gold', 'btc', 'sh', 'nasdaq'];
  const indicesSymbols = { usdcny: '💵', gold: '🥇', btc: '₿', sh: '📈', nasdaq: '📊' };

  // 商品周期配置
  const cycleOrder = ['gold', 'silver', 'copper', 'oil', 'corn'];
  const cycleNames = { gold: '黄金', silver: '白银', copper: '铜矿', oil: '石油', corn: '农产' };
  const cycleIcons = { gold: '🥇', silver: '🥈', copper: '🔶', oil: '🛢️', corn: '🌽' };

  // 渲染单个格子
  function renderCell(name, icon, value, kline, isActive) {
    let spark = '';
    if (kline && kline.length > 1) {
      const min = Math.min(...kline), max = Math.max(...kline);
      const range = max - min || 1;
      const pts = kline.map((v,i) => (i*120/(kline.length-1))+','+(20-(v-min)/range*20)).join(' ');
      const color = kline[kline.length-1] >= kline[0] ? '#dc2626' : '#16a34a';
      spark = '<svg class="ind-chart" viewBox="0 0 120 20" preserveAspectRatio="none"><polyline points="'+pts+'" fill="none" stroke="'+color+'" stroke-width="1.5"/></svg>';
    }
    const activeClass = isActive ? ' active' : '';
    return '<div class="ind-cell'+activeClass+'"><b>'+name+'</b> '+icon+' <small>'+value+'</small>'+spark+'</div>';
  }

  // 渲染全球指标（第一行）
  const row1 = indicesOrder.map(k => {
    const d = indicesData[k];
    if (!d || !d.kline?.length) return renderCell('--', indicesSymbols[k] || '', '--', null, false);
    const priceStr = d.price >= 10000 ? (d.price/1000).toFixed(1)+'k' : d.price >= 100 ? d.price.toFixed(0) : d.price.toFixed(2);
    return renderCell(d.name, indicesSymbols[k] || '', priceStr, d.kline, false);
  }).join('');

  // 渲染商品周期（第二行）
  const leader = cycleData.cycle?.leader || '';
  const row2 = cycleOrder.map(k => {
    const c = cycleData.commodities?.[k];
    const chg = c ? (c.change_5d >= 0 ? '+' : '') + c.change_5d.toFixed(1) + '%' : '--';
    return renderCell(cycleNames[k], cycleIcons[k], chg, c?.kline, k === leader);
  }).join('');

  el.innerHTML = row1 + row2;
}

async function checkHoliday() {
  try {
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '-');
    const resp = await fetch('https://timor.tech/api/holiday/info/' + today);
    const data = await resp.json();
    isHoliday = data.type?.type !== 0; // type=0是工作日
  } catch (e) { console.warn('节假日API失败', e); }
}

function getMarketStatus() {
  const now = new Date();
  const h = now.getHours(), m = now.getMinutes(), d = now.getDay();
  const t = h * 60 + m;
  if (d === 0 || d === 6 || isHoliday) return { status: '休市', cls: 'closed' };
  if (t < 9 * 60 + 30) return { status: '盘前', cls: 'pre' };
  if ((t >= 9 * 60 + 30 && t < 11 * 60 + 30) || (t >= 13 * 60 && t < 15 * 60)) return { status: '盘中', cls: 'trading' };
  return { status: '收盘', cls: 'closed' };
}

function updatePriceHeader() {
  const { status, cls } = getMarketStatus();
  document.querySelectorAll('.price-header').forEach(el => {
    el.textContent = status;
    el.className = 'price-header ' + cls;
  });
}

async function loadSectorEtfs() {
  await checkHoliday();
  updatePriceHeader();
  loadIndicators();
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
  const chgCls = v => {
    const abs = Math.abs(v);
    const dir = v >= 0 ? 'up' : 'down';
    if (abs >= 5) return dir + '-5';
    if (abs >= 3) return dir + '-3';
    if (abs >= 1) return dir + '-1';
    return dir;
  };
  const fmt = v => Math.abs(v).toFixed(1) + '%';
  const fmtPrice = v => v == null ? '--' : v.toFixed(3);
  for (const f of etfs) {
    const row = table.querySelector(\`tr[data-code="\${f.code}"]\`);
    if (!row) continue;
    row.querySelector('.price').textContent = fmtPrice(f.price);
    const changeCell = row.querySelector('.change');
    changeCell.textContent = fmt(f.change_pct);
    changeCell.className = 'change ' + chgCls(f.change_pct);
    row.querySelector('.amount').textContent = f.amount_yi.toFixed(1) + '亿';
  }
}

loadSectorEtfs();
`

// 涨跌幅样式类
function chgClass(v: number): string {
  const abs = Math.abs(v)
  const dir = v >= 0 ? 'up' : 'down'
  if (abs >= 5) return dir + '-5'
  if (abs >= 3) return dir + '-3'
  if (abs >= 1) return dir + '-1'
  return dir
}

// 渲染板块卡片
function renderSectorCard(sector: any, etfMaster: Record<string, any>): string {
  // 服务端预渲染 ETF 占位数据，按成交额排序
  const lookupSector = SECTOR_ALIAS[sector.name] || sector.name
  const sectorEtfs = Object.values(etfMaster)
    .filter((e: any) => e.sector === lookupSector)
    .sort((a: any, b: any) => (b.amount_yi || 0) - (a.amount_yi || 0))
    .slice(0, 3) as any[]

  let tbodyHtml = '<tr><td colspan="7">暂无数据</td></tr>'
  if (sectorEtfs.length) {
    tbodyHtml = sectorEtfs.map((f: any) => `
      <tr data-code="${f.code}">
        <td><a href="https://quote.eastmoney.com/${f.code.startsWith('15') || f.code.startsWith('16') ? 'sz' : 'sh'}${f.code}.html" target="_blank">${f.name}(${f.code})</a></td>
        <td class="price">--</td>
        <td class="amount">--</td>
        <td class="change">--</td>
        <td class="${chgClass(f.change_5d || 0)}">${Math.abs(f.change_5d || 0).toFixed(1)}%</td>
        <td class="${chgClass(f.change_20d || 0)}">${Math.abs(f.change_20d || 0).toFixed(1)}%</td>
        <td>${f.kline?.length ? `<svg class="sparkline" viewBox="0 0 100 16" preserveAspectRatio="none"><polyline points="${f.kline.map((v: number, i: number) => `${i * 100 / (f.kline.length - 1)},${16 - (v - Math.min(...f.kline)) / (Math.max(...f.kline) - Math.min(...f.kline) || 1) * 16}`).join(' ')}" fill="none" stroke="${f.kline[f.kline.length-1] >= f.kline[0] ? '#dc2626' : '#16a34a'}" stroke-width="1.2"/></svg>` : '-'}</td>
      </tr>
    `).join('')
  }

  const etfTableHtml = `
    <table class="etf-table" data-sector="${sector.name}">
      <thead>
        <tr>
          <th>ETF</th><th class="price-header">价格</th><th>成交</th><th>日</th><th>5日</th><th>20日</th><th>90日</th>
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

  // 生成动态 SEO 描述
  const topSectors = sortedSectors.slice(0, 3).map(s => s.name).join('、')
  const seoDesc = `${result.market_view} 今日热门板块：${topSectors}。AI 实时分析财经新闻，智能推荐 ETF 投资方向。`

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="${seoDesc}">
  <meta name="keywords" content="ETF,基金,投资,AI分析,${topSectors},股票,理财,指数基金">
  <meta name="author" content="ETF风向标">
  <meta property="og:title" content="ETF风向标 - AI驱动的ETF投资分析">
  <meta property="og:description" content="${seoDesc}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://etf.aurora-bots.com/">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="ETF风向标">
  <meta name="twitter:description" content="${seoDesc}">
  <link rel="canonical" href="https://etf.aurora-bots.com/">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
  <title>ETF风向标 - AI驱动的ETF投资分析</title>
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

    <div id="indicators-grid" class="indicators-grid"></div>

    <div class="card">
      <div class="card-header">
        <h2>${result.market_view}</h2>
        ${result.sentiment ? `<span class="sentiment">${result.sentiment}</span>` : ''}
      </div>
      <p class="summary">${result.summary || result.narrative || ''}</p>
    </div>

    <div class="sectors-grid">
      ${sectorsHtml}
    </div>
  </div>

  <script>${clientScript}</script>
</body>
</html>`
}
