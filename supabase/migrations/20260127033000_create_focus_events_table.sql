-- 创建独立的焦点事件表，支持瀑布流累积
CREATE TABLE IF NOT EXISTS focus_events (
    id SERIAL PRIMARY KEY,
    event_hash VARCHAR(32) UNIQUE NOT NULL,  -- 用于去重
    title TEXT NOT NULL,
    sector VARCHAR(50),
    event_time VARCHAR(20),  -- 事件发生时间（如 09:30）
    analysis TEXT,
    suggestion TEXT,
    related_funds JSONB DEFAULT '[]',
    sources JSONB DEFAULT '[]',
    importance INTEGER DEFAULT 5,
    created_at TIMESTAMPTZ DEFAULT NOW(),  -- 首次出现时间
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_focus_events_created_at ON focus_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_focus_events_sector ON focus_events(sector);
