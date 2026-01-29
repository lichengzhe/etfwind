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
.card h2 { font-size: 16px; margin-bottom: 6px; color: #1a1a1a; }
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
.sector-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.sector-dir { font-size: 12px; font-weight: 500; padding: 2px 8px; border-radius: 3px; margin-left: auto; }
.sector-dir.up { background: #fef3c7; color: #b45309; }
.sector-dir.down { background: #e2e8f0; color: #475569; }
.sector-dir.neutral { background: #f3f4f6; color: #6b7280; }
.sector-name { font-size: 17px; font-weight: 700; color: #1f2937; }
.sector-heat { font-size: 12px; color: #fbbf24; letter-spacing: -1px; }
.sector-analysis { font-size: 12px; color: #64748b; margin-bottom: 6px; line-height: 1.5; }
.etf-table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
.etf-table thead th { font-size: 11px; color: #9ca3af; font-weight: normal; padding: 4px; text-align: left; }
.etf-table thead th:nth-child(1) { text-align: center; }
.etf-table thead th:nth-child(6) { text-align: center; }
.etf-table td, .etf-table th { padding: 2px 4px; border-bottom: 1px solid #f1f5f9; white-space: nowrap; overflow: hidden; }
.etf-table td:nth-child(1), .etf-table th:nth-child(1) { width: 25%; }
.etf-table td:nth-child(2), .etf-table th:nth-child(2) { width: 12%; text-align: right; }
.etf-table td:nth-child(3), .etf-table th:nth-child(3) { width: 12%; text-align: right; }
.etf-table td:nth-child(4), .etf-table th:nth-child(4) { width: 12%; text-align: right; }
.etf-table td:nth-child(5), .etf-table th:nth-child(5) { width: 14%; text-align: right; padding-left: 10px; border-left: 1px solid #e2e8f0; }
.etf-table td:nth-child(6), .etf-table th:nth-child(6) { width: 25%; }
.etf-table .sparkline { width: 100%; height: 16px; }
.etf-table .up { color: #dc2626; }
.etf-table .down { color: #16a34a; }
.etf-table a { color: #0066cc; text-decoration: none; }
.etf-table a:hover { text-decoration: underline; }
.foth-section { display: flex; gap: 16px; margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e7eb; font-size: 12px; }
.foth-section .facts { flex: 1; }
.foth-section .facts strong { color: #374151; display: block; margin-bottom: 4px; }
.foth-section .facts ul { margin: 0; padding-left: 16px; color: #6b7280; }
.foth-section .facts li { margin-bottom: 2px; }
.foth-section .opinions { flex-shrink: 0; text-align: right; }
.foth-section .opinions strong { color: #374151; display: block; margin-bottom: 4px; }
.foth-section .sentiment { display: inline-block; padding: 2px 8px; background: #fef3c7; color: #b45309; border-radius: 4px; font-size: 11px; }
.wordcloud-img { display: block; margin-top: 8px; max-width: 200px; height: auto; border-radius: 6px; }
.word-cloud { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; margin-top: 6px; max-width: 200px; margin-left: auto; }
.word-cloud .word { display: inline-block; padding: 2px 6px; border-radius: 4px; white-space: nowrap; transition: transform 0.15s; }
.word-cloud .word:hover { transform: scale(1.1); }
.word-cloud .w1 { font-size: 11px; color: #9ca3af; background: #f3f4f6; }
.word-cloud .w2 { font-size: 12px; color: #6b7280; background: #e5e7eb; }
.word-cloud .w3 { font-size: 13px; color: #4b5563; background: #fef3c7; }
.word-cloud .w4 { font-size: 14px; color: #b45309; background: #fde68a; font-weight: 500; }
.word-cloud .w5 { font-size: 16px; color: #dc2626; background: #fee2e2; font-weight: 600; }
@media (max-width: 600px) {
  .container { padding: 12px; }
  header { flex-wrap: wrap; gap: 6px; }
  header h1 { font-size: 18px; }
  .source-stats { flex-wrap: wrap; width: 100%; margin-top: 4px; }
  .source-stats a { font-size: 10px; padding: 3px 8px; }
  .github-link, .powered-by { display: none; }
  .sectors-grid { grid-template-columns: 1fr; }
  .card h2 { font-size: 15px; }
  .card p { font-size: 12px; }
  .foth-section { flex-direction: column; gap: 8px; }
  .foth-section .opinions { text-align: left; }
  .word-cloud { justify-content: flex-start; max-width: none; margin-left: 0; }
  .sector-name { font-size: 15px; }
  .sector-analysis { font-size: 11px; }
  .sector-card { overflow-x: hidden; }
  .etf-table { font-size: 12px; table-layout: fixed; }
  .etf-table thead { display: none; }
  .etf-table td:nth-child(1) { width: 34%; }
  .etf-table td:nth-child(2) { width: 10%; }
  .etf-table td:nth-child(3) { width: 11%; }
  .etf-table td:nth-child(4) { display: none; width: 0; padding: 0; }
  .etf-table td:nth-child(5) { width: 15%; }
  .etf-table td:nth-child(6) { width: 30%; text-align: right; }
  .etf-table td:nth-child(2), .etf-table td:nth-child(3), .etf-table td:nth-child(5) { border-left: none; }
  .etf-table .sparkline { width: 100%; }
}
`
