// 页面样式
export const styles = `
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; color: #333; line-height: 1.4; font-size: 14px; }
.container { max-width: 1200px; margin: 0 auto; padding: 12px; }
header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: nowrap; overflow-x: auto; }
header h1 { font-size: 20px; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.meta { color: #999; font-size: 12px; }
.news-total { font-size: 12px; color: #0066cc; text-decoration: none; }
.news-total:hover { text-decoration: underline; }
.github-link { display: inline-flex; align-items: center; color: #6b7280; margin-left: auto; }
.github-link:hover { color: #374151; }
.powered-by { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #D97706; text-decoration: none; }
.powered-by:hover { color: #B45309; }
.source-stats { display: flex; flex-wrap: nowrap; gap: 4px; flex-shrink: 0; }
.source-stats a { font-size: 11px; padding: 3px 10px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 12px; text-decoration: none; color: #6b7280; transition: all 0.15s; }
.source-stats a:hover { background: #f3f4f6; border-color: #d1d5db; color: #374151; }
.card { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.card h2 { font-size: 16px; margin-bottom: 6px; color: #1a1a1a; }
.card p { font-size: 13px; color: #555; }
.sectors-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
@media (max-width: 600px) { .sectors-grid { grid-template-columns: 1fr; } }
.sector-card { background: #fff; border-radius: 10px; padding: 10px 12px; border: none; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.sector-card.up { background: #fffbf7; border-left: 3px solid #f97316; }
.sector-card.up.heat-4 { border-left-color: #ea580c; }
.sector-card.up.heat-5 { border-left-color: #dc2626; }
.sector-card.down { background: #f8fafc; border-left: 3px solid #64748b; }
.sector-card.down.heat-4 { border-left-color: #475569; }
.sector-card.down.heat-5 { border-left-color: #334155; }
.sector-card.neutral { background: #fafafa; border-left: 3px solid #d1d5db; }
.sector-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.sector-dir { font-size: 12px; font-weight: 500; padding: 2px 8px; border-radius: 3px; margin-left: auto; }
.sector-dir.up { background: #fef3c7; color: #b45309; }
.sector-dir.down { background: #e2e8f0; color: #475569; }
.sector-dir.neutral { background: #f3f4f6; color: #6b7280; }
.sector-name { font-size: 17px; font-weight: 700; color: #1f2937; }
.sector-heat { font-size: 12px; color: #fbbf24; letter-spacing: -1px; }
.sector-analysis { font-size: 12px; color: #64748b; margin-bottom: 6px; line-height: 1.5; }
.etf-labels { display: flex; font-size: 11px; color: #9ca3af; margin-bottom: 4px; }
.etf-labels span:first-child { margin-left: 32%; width: 36%; text-align: center; }
.etf-labels span:last-child { width: 32%; text-align: center; }
.etf-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.etf-table thead { display: none; }
.etf-table td { padding: 2px 4px; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.etf-table td:nth-child(2) { padding-left: 10px; border-left: 1px solid #e2e8f0; }
.etf-table td:nth-child(5) { padding-left: 10px; border-left: 1px solid #e2e8f0; }
.etf-table td:last-child { width: 80px; }
.etf-table .sparkline { width: 80px; height: 16px; }
.etf-table .up { color: #dc2626; }
.etf-table .down { color: #16a34a; }
.etf-table a { color: #0066cc; text-decoration: none; }
.etf-table a:hover { text-decoration: underline; }
`
