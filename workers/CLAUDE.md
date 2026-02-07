# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ETF风向标前端 - Cloudflare Workers + Hono，从 R2 读取 AI 分析数据并渲染页面。

## Commands

```bash
npm run dev       # 本地开发 (wrangler dev)
npm run deploy    # 部署到 Cloudflare
npm run typecheck # TypeScript 类型检查
```

## Architecture

```
R2 Bucket (invest-data)
    ├── latest.json      # AI 分析结果
    ├── etf_master.json  # ETF 主数据（含历史涨跌、K线）
    └── news.json        # 新闻列表
           ↓
    index.ts (Hono 路由)
           ↓
    ├── pages/Home.ts    # 首页渲染 + 客户端 JS
    ├── pages/News.ts    # 新闻页
    └── services/fund.ts # 东方财富实时行情 API
```

**数据流：**
- 静态数据（latest.json, etf_master.json）由 GitHub Actions 定时生成并上传到 R2
- 实时数据（价格、今日涨跌、成交额）由 `/api/batch-sector-etfs` 调用东方财富 API 获取
- K线数据（90天收盘价、5日/20日涨跌幅）由 `/api/kline` 按需拉取，24h 缓存
- 前端三层加载：SSR 用 etf_master 渲染 → batch-sector-etfs 更新价格 → /api/kline 刷新 sparkline 和涨跌幅

## API Routes

- `GET /` - 首页 HTML
- `GET /news` - 新闻列表，支持 `?source=财联社` 过滤
- `GET /api/data` - 分析结果 JSON
- `GET /api/batch-sector-etfs?sectors=黄金,芯片` - 批量板块 ETF（合并实时+历史）
- `GET /api/funds?codes=518880,512760` - ETF 实时行情
- `GET /api/kline?codes=518880,512760` - ETF K线（90天收盘价+5日/20日涨跌，24h缓存）
- `GET /api/market-overview` - 全球指标+商品周期（合并，10min缓存）
- `GET /api/etf-master` - ETF 主数据（24h缓存）

## Key Files

- `src/index.ts` - Hono 路由，R2 数据加载
- `src/pages/Home.ts` - 首页模板 + 内嵌客户端 JS（sparkline、ETF 表格渲染）
- `src/services/fund.ts` - 东方财富 API 封装
- `src/types.ts` - TypeScript 类型定义

## R2 Binding

wrangler.toml 配置了 R2 bucket 绑定，通过 `c.env.R2` 访问，比公开 URL 更快。
