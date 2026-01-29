-- Supabase Database Schema for Naver Search Redirect System

CREATE TABLE IF NOT EXISTS links (
    code VARCHAR(11) PRIMARY KEY,
    product_name VARCHAR(255) DEFAULT '',
    queries TEXT[] NOT NULL DEFAULT '{}',
    acqs TEXT[] NOT NULL DEFAULT '{}',
    clicks INTEGER DEFAULT 0,
    click_history TIMESTAMP[] DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for faster sorting by creation date
CREATE INDEX IF NOT EXISTS idx_links_created_at ON links(created_at DESC);

-- Index for faster lookup by code
CREATE INDEX IF NOT EXISTS idx_links_code ON links(code);
