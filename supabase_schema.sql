-- Supabase 表结构
-- 在 Supabase Dashboard -> SQL Editor 中执行

-- 1. 旧报告表（兼容）
CREATE TABLE IF NOT EXISTS reports_v2 (
    id BIGSERIAL PRIMARY KEY,
    period TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL,
    one_liner TEXT,
    market_emotion INTEGER DEFAULT 50,
    emotion_suggestion TEXT,
    global_events JSONB DEFAULT '[]',
    sector_opportunities JSONB DEFAULT '[]',
    policy_insights JSONB DEFAULT '[]',
    position_advices JSONB DEFAULT '[]',
    risk_warnings JSONB DEFAULT '[]',
    news_sources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 新闻表
CREATE TABLE IF NOT EXISTS news_items (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'domestic',
    url TEXT,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    content_hash TEXT UNIQUE,
    language TEXT DEFAULT 'zh',
    summary_zh TEXT
);

-- 3. 每日报告表
CREATE TABLE IF NOT EXISTS daily_reports (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE UNIQUE NOT NULL,
    last_updated TIMESTAMPTZ,
    version INTEGER DEFAULT 1,
    is_finalized BOOLEAN DEFAULT FALSE,
    one_liner TEXT,
    market_emotion INTEGER DEFAULT 50,
    emotion_suggestion TEXT,
    focus_events JSONB DEFAULT '[]',
    position_advices JSONB DEFAULT '[]',
    risk_warnings JSONB DEFAULT '[]',
    news_ids JSONB DEFAULT '[]'
);

-- 4. 历史摘要表
CREATE TABLE IF NOT EXISTS market_summaries (
    id BIGSERIAL PRIMARY KEY,
    period_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    summary TEXT NOT NULL,
    key_events JSONB DEFAULT '[]',
    market_trend TEXT DEFAULT 'neutral',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(period_type, period_start)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_news_collected_at ON news_items(collected_at);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_items(published_at);
CREATE INDEX IF NOT EXISTS idx_news_content_hash ON news_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports(report_date);
CREATE INDEX IF NOT EXISTS idx_reports_v2_generated_at ON reports_v2(generated_at);

-- 启用 RLS（可选，如果需要安全控制）
-- ALTER TABLE reports_v2 ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE news_items ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE market_summaries ENABLE ROW LEVEL SECURITY;
