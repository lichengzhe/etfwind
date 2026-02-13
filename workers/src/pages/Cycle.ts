import { styles } from './styles'

// 周期页面样式
const cycleStyles = `
.cycle-container { max-width: 900px; margin: 0 auto; padding: 20px; }
.cycle-title { font-size: 24px; font-weight: 700; margin-bottom: 20px; }
.cycle-progress { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.cycle-stages { display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.cycle-stage { padding: 12px 20px; background: #f3f4f6; border-radius: 8px; text-align: center; min-width: 80px; }
.cycle-stage.active { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); box-shadow: 0 2px 8px rgba(251,191,36,0.3); }
.cycle-stage .icon { font-size: 24px; display: block; margin-bottom: 4px; }
.cycle-stage .name { font-size: 14px; font-weight: 600; color: #1f2937; }
.cycle-stage .change { font-size: 12px; color: #6b7280; margin-top: 2px; }
.cycle-stage.active .change { color: #b45309; font-weight: 500; }
.cycle-arrow { color: #d1d5db; font-size: 20px; }
.cycle-status { text-align: center; font-size: 15px; color: #4b5563; }
.cycle-status strong { color: #b45309; }
.chart-card { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.chart-card h3 { font-size: 16px; margin-bottom: 16px; color: #1f2937; }
.commodity-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }
.commodity-row:last-child { border-bottom: none; }
.commodity-icon { font-size: 20px; width: 32px; text-align: center; }
.commodity-name { width: 60px; font-weight: 500; color: #374151; }
.commodity-price { width: 80px; text-align: right; font-family: monospace; color: #6b7280; }
.commodity-changes { display: flex; gap: 8px; }
.commodity-change { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.commodity-change.up { background: #fef2f2; color: #dc2626; }
.commodity-change.down { background: #f0fdf4; color: #16a34a; }
.commodity-chart { flex: 1; height: 32px; min-width: 120px; }
.etf-section { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.etf-section h3 { font-size: 16px; margin-bottom: 16px; color: #1f2937; }
.etf-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.etf-card { background: #f9fafb; border-radius: 8px; padding: 12px; text-align: center; }
.etf-card .name { font-size: 13px; color: #374151; margin-bottom: 4px; }
.etf-card .code { font-size: 11px; color: #9ca3af; }
.etf-card .change { font-size: 14px; font-weight: 600; margin-top: 4px; }
.etf-card .change.up { color: #dc2626; }
.etf-card .change.down { color: #16a34a; }
.back-link { display: inline-block; margin-bottom: 16px; color: #6b7280; text-decoration: none; font-size: 14px; }
.back-link:hover { color: #374151; }
@media (max-width: 600px) {
  .cycle-container { padding: 12px; }
  .cycle-stages { gap: 4px; }
  .cycle-stage { padding: 8px 12px; min-width: 60px; }
  .cycle-stage .icon { font-size: 20px; }
  .cycle-stage .name { font-size: 12px; }
  .cycle-arrow { font-size: 14px; }
  .commodity-row { flex-wrap: wrap; }
  .commodity-chart { width: 100%; order: 10; }
}
`

export function renderCycle(): string {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔄</text></svg>">
  <title>商品周期轮动 - ETF风向标</title>
  <style>${styles}${cycleStyles}</style>
</head>
<body>
  <div class="cycle-container">
    <a href="/" class="back-link">← 返回首页</a>
    <h1 class="cycle-title">商品周期轮动</h1>

    <div class="cycle-progress">
      <div id="cycle-stages" class="cycle-stages">加载中...</div>
      <div id="cycle-status" class="cycle-status"></div>
    </div>

    <div class="chart-card">
      <h3>5大商品走势（180天）</h3>
      <div id="commodity-list"></div>
    </div>

    <div class="etf-section">
      <h3>相关ETF</h3>
      <div id="etf-grid" class="etf-grid"></div>
    </div>
  </div>

  <script>
${cycleScript}
  </script>
</body>
</html>`
}

const cycleScript = `
const order = ['gold', 'silver', 'copper', 'oil', 'corn'];
const names = { gold: '黄金', silver: '白银', copper: '铜', oil: '原油', corn: '玉米' };
const icons = { gold: '🥇', silver: '🥈', copper: '🔶', oil: '🛢️', corn: '🌽' };
const etfMap = {
  gold: [{ code: '518880', name: '黄金ETF' }, { code: '517520', name: '黄金股ETF' }],
  silver: [{ code: '161226', name: '白银LOF' }],
  copper: [{ code: '512400', name: '有色金属ETF' }, { code: '159980', name: '有色ETF' }],
  oil: [{ code: '561360', name: '石油ETF' }, { code: '159697', name: '油气ETF' }],
  corn: [{ code: '159985', name: '豆粕ETF' }]
};

async function loadCycleData() {
  try {
    const resp = await fetch('/api/market-overview');
    const data = await resp.json();
    renderStages(data);
    renderCommodities(data);
    renderEtfs(data);
  } catch (e) {
    console.error('加载失败', e);
  }
}

function renderStages(data) {
  const el = document.getElementById('cycle-stages');
  const statusEl = document.getElementById('cycle-status');
  if (!el || !data.cycle) return;

  const html = order.map(k => {
    const c = data.commodities[k];
    const isActive = k === data.cycle.leader;
    const chg = c ? (c.change_5d >= 0 ? '+' : '') + c.change_5d.toFixed(1) + '%' : '--';
    return '<div class="cycle-stage ' + (isActive ? 'active' : '') + '">' +
      '<span class="icon">' + icons[k] + '</span>' +
      '<span class="name">' + names[k] + '</span>' +
      '<span class="change">' + chg + '</span>' +
    '</div>';
  }).join('<span class="cycle-arrow">→</span>');

  el.innerHTML = html;
  if (statusEl) statusEl.textContent = '当前阶段：' + data.cycle.stage_name + ' | 下一站：' + (names[data.cycle.next] || data.cycle.next);
}

function renderCommodities(data) {
  const el = document.getElementById('commodity-list');
  if (!el) return;

  const html = order.map(k => {
    const c = data.commodities[k];
    if (!c) return '';

    const priceStr = c.price >= 1000 ? (c.price/1000).toFixed(1) + 'k' : c.price.toFixed(2);
    const chg5 = c.change_5d;
    const chg20 = c.change_20d;
    const chg5Cls = chg5 >= 0 ? 'up' : 'down';
    const chg20Cls = chg20 >= 0 ? 'up' : 'down';

    // Sparkline
    const kline = c.kline || [];
    let sparkline = '';
    if (kline.length > 1) {
      const min = Math.min(...kline), max = Math.max(...kline);
      const range = max - min || 1;
      const pts = kline.map((v, i) => (i * 200 / (kline.length - 1)) + ',' + (30 - (v - min) / range * 28)).join(' ');
      const color = kline[kline.length - 1] >= kline[0] ? '#dc2626' : '#16a34a';
      sparkline = '<svg class="commodity-chart" viewBox="0 0 200 32" preserveAspectRatio="none"><polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="1.5"/></svg>';
    }

    return '<div class="commodity-row">' +
      '<span class="commodity-icon">' + icons[k] + '</span>' +
      '<span class="commodity-name">' + names[k] + '</span>' +
      '<span class="commodity-price">' + priceStr + '</span>' +
      '<div class="commodity-changes">' +
        '<span class="commodity-change ' + chg5Cls + '">5日 ' + (chg5 >= 0 ? '+' : '') + chg5.toFixed(1) + '%</span>' +
        '<span class="commodity-change ' + chg20Cls + '">20日 ' + (chg20 >= 0 ? '+' : '') + chg20.toFixed(1) + '%</span>' +
      '</div>' +
      sparkline +
    '</div>';
  }).join('');

  el.innerHTML = html;
}

function renderEtfs(data) {
  const el = document.getElementById('etf-grid');
  if (!el) return;

  // 按周期顺序展示ETF
  const leader = data.cycle?.leader || 'gold';
  const sortedKeys = [leader, ...order.filter(k => k !== leader)];

  const html = sortedKeys.flatMap(k => {
    const etfs = etfMap[k] || [];
    return etfs.map(etf => {
      return '<div class="etf-card">' +
        '<div class="name">' + icons[k] + ' ' + etf.name + '</div>' +
        '<div class="code">' + etf.code + '</div>' +
      '</div>';
    });
  }).join('');

  el.innerHTML = html;
}

loadCycleData();
`
