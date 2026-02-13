// 页面样式
export const styles = `
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; color: #333; line-height: 1.4; font-size: 14px; }
.container { max-width: 1400px; margin: 0 auto; padding: 16px 24px; }
header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: nowrap; overflow-x: auto; }
header h1 { font-size: 20px; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; flex-shrink: 0; }
.meta { color: #999; font-size: 12px; flex-shrink: 0; white-space: nowrap; }
.news-total { font-size: 12px; color: #0066cc; text-decoration: none; flex-shrink: 0; white-space: nowrap; }
.news-total:hover { text-decoration: underline; }
.github-link { display: inline-flex; align-items: center; color: #6b7280; margin-left: auto; }
.github-link:hover { color: #374151; }
.powered-by { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #D97706; text-decoration: none; }
.powered-by:hover { color: #B45309; }
.source-stats { display: flex; flex-wrap: nowrap; gap: 4px; flex-shrink: 1; overflow: hidden; }
.source-stats a { font-size: 11px; padding: 4px 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; text-decoration: none; color: #6b7280; transition: all 0.15s; flex-shrink: 0; }
.source-stats a:hover { background: #f3f4f6; border-color: #d1d5db; color: #374151; }
.card { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.indicators-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 10px; background: #fff; border-radius: 10px; padding: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.ind-cell { font-size: 13px; padding: 6px 10px; background: #f9fafb; border-radius: 6px; white-space: nowrap; display: flex; align-items: center; gap: 6px; }
.ind-cell.active { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); }
.ind-cell small { color: #6b7280; font-size: 11px; }
.ind-cell.active small { color: #b45309; }
.ind-chart { width: 120px; height: 20px; margin-left: auto; flex-shrink: 0; }
.ind-chart polyline { stroke-width: 1.5; }
.card h2 { font-size: 16px; margin-bottom: 6px; color: #1a1a1a; }
.card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.card-header h2 { margin-bottom: 0; }
.card p { font-size: 13px; color: #555; }
.sectors-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.sector-card { background: #fff; border-radius: 10px; padding: 10px 12px; border: none; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.sector-card.up { background: #fffbf7; border-left: 3px solid #f97316; }
.sector-card.up.heat-4 { border-left-color: #ea580c; }
.sector-card.up.heat-5 { border-left-color: #dc2626; }
.sector-card.down { background: #f8fafc; border-left: 3px solid #64748b; }
.sector-card.down.heat-4 { border-left-color: #475569; }
.sector-card.down.heat-5 { border-left-color: #334155; }
.sector-card.neutral { background: #fafafa; border-left: 3px solid #d1d5db; }
.sector-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: nowrap; overflow-x: auto; }
.sector-right { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.sector-dir { font-size: 12px; font-weight: 500; padding: 2px 8px; border-radius: 3px; }
.sector-dir.up { background: #fef3c7; color: #b45309; }
.sector-dir.down { background: #e2e8f0; color: #475569; }
.sector-dir.neutral { background: #f3f4f6; color: #6b7280; }
.sector-trend { font-size: 13px; letter-spacing: 1px; cursor: help; }
.sector-trend { background: linear-gradient(90deg, #dc2626, #f97316, #16a34a); -webkit-background-clip: text; background-clip: text; }
.sector-name { font-size: 17px; font-weight: 700; color: #1f2937; white-space: nowrap; }
.sector-heat { font-size: 12px; color: #fbbf24; letter-spacing: -1px; }
.sector-analysis { font-size: 12px; color: #64748b; margin-bottom: 6px; line-height: 1.5; }
.etf-table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
.etf-table thead th { font-size: 11px; color: #9ca3af; font-weight: normal; padding: 4px; text-align: right; }
.etf-table thead th:nth-child(1) { text-align: left; }
.etf-table thead th:nth-child(7) { text-align: center; }
.etf-table td, .etf-table th { padding: 2px 4px; border-bottom: 1px solid #f1f5f9; white-space: nowrap; overflow: hidden; }
.etf-table td:nth-child(1), .etf-table th:nth-child(1) { width: 28%; }
.etf-table td:nth-child(2), .etf-table th:nth-child(2) { width: 11%; text-align: right; }
.etf-table td:nth-child(3), .etf-table th:nth-child(3) { width: 11%; text-align: right; }
.etf-table td:nth-child(4), .etf-table th:nth-child(4) { width: 10%; text-align: right; }
.etf-table td:nth-child(5), .etf-table th:nth-child(5) { width: 10%; text-align: right; }
.etf-table td:nth-child(6), .etf-table th:nth-child(6) { width: 10%; text-align: right; }
.etf-table td:nth-child(7), .etf-table th:nth-child(7) { width: 20%; }
.etf-table .sparkline { width: 100%; height: 16px; }
.etf-table .up { color: #dc2626; }
.etf-table .down { color: #16a34a; }
.etf-table .up-1 { background: #fef2f2; color: #dc2626; }
.etf-table .up-3 { background: #fee2e2; color: #dc2626; }
.etf-table .up-5 { background: #fecaca; color: #b91c1c; font-weight: 500; }
.etf-table .down-1 { background: #f0fdf4; color: #16a34a; }
.etf-table .down-3 { background: #dcfce7; color: #16a34a; }
.etf-table .down-5 { background: #bbf7d0; color: #15803d; font-weight: 500; }
.etf-table a { color: #0066cc; text-decoration: none; }
.etf-table a:hover { text-decoration: underline; }
.price-header { font-weight: 500; }
.price-header.trading { color: #dc2626; }
.price-header.pre { color: #f59e0b; }
.price-header.closed { color: #9ca3af; }
.card p.summary { font-size: 14px; color: #374151; line-height: 1.8; }
.sentiment { display: inline-block; padding: 2px 10px; background: #fef3c7; color: #b45309; border-radius: 4px; font-size: 12px; font-weight: 500; }
.review-card { padding: 10px 12px; }
.review-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.review-item { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; text-align: center; }
.review-title { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.review-metrics { display: flex; justify-content: center; gap: 8px; font-size: 13px; color: #1f2937; }
.review-legend { font-size: 11px; color: #94a3b8; margin-left: auto; white-space: nowrap; }
.alerts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
.alert-box { background: #fff; border-radius: 10px; padding: 10px 12px; font-size: 12px; line-height: 1.6; }
.alert-box b { display: block; margin-bottom: 4px; font-size: 13px; }
.alert-box.risk { border-left: 3px solid #ef4444; background: #fef2f2; }
.alert-box.risk b { color: #dc2626; }
.alert-box.opportunity { border-left: 3px solid #22c55e; background: #f0fdf4; }
.alert-box.opportunity b { color: #16a34a; }
.sector-signal { font-size: 11px; padding: 2px 6px; border-radius: 3px; background: #f3f4f6; }
.sector-confidence { font-size: 11px; padding: 2px 6px; border-radius: 3px; background: #eef2ff; color: #4f46e5; }
@media (max-width: 600px) {
  .container { padding: 12px; }
  header { flex-wrap: wrap; gap: 6px; }
  header h1 { font-size: 18px; }
  .source-stats { flex-wrap: wrap; width: 100%; margin-top: 4px; }
  .source-stats a { font-size: 10px; padding: 3px 8px; }
  .github-link, .powered-by { display: none; }
  .indicators-grid { grid-template-columns: repeat(2, 1fr); padding: 8px; gap: 6px; grid-auto-flow: column; grid-template-rows: repeat(5, auto); }
  .ind-cell { font-size: 12px; padding: 4px 8px; }
  .ind-chart { width: 60px; height: 16px; }
  .sectors-grid { grid-template-columns: 1fr; }
  .alerts-row { grid-template-columns: 1fr; }
  .alert-box { font-size: 11px; padding: 8px 10px; }
  .card h2 { font-size: 15px; }
  .card p { font-size: 12px; }
  .sector-name { font-size: 15px; }
  .sector-analysis { font-size: 11px; }
  .sector-card { overflow-x: hidden; }
  .review-grid { display: flex; gap: 8px; overflow-x: auto; }
  .review-metrics { gap: 4px; font-size: 12px; white-space: nowrap; }
  .m-hide { display: none; }
  .etf-table { font-size: 12px; table-layout: fixed; }
  .etf-table thead { display: none; }
  .etf-table td:nth-child(1) { width: 41%; }
  .etf-table td:nth-child(2) { display: none; }
  .etf-table td:nth-child(3) { display: none; }
  .etf-table td:nth-child(4) { width: 12%; }
  .etf-table td:nth-child(5) { width: 12%; }
  .etf-table td:nth-child(6) { width: 12%; }
  .etf-table td:nth-child(7) { width: 23%; }
  .etf-table .sparkline { width: 100%; }
}
`
