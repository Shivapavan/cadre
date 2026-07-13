-- Run this in your Supabase SQL editor (supabase.com → project → SQL Editor)

CREATE TABLE IF NOT EXISTS jobs (
  id            TEXT PRIMARY KEY,
  source        TEXT NOT NULL,          -- 'greenhouse' | 'lever' | 'ashby' | 'dice'
  emp_type      TEXT DEFAULT 'fulltime',-- 'fulltime' | 'contract' | 'c2c' | 'parttime'
  cat           TEXT DEFAULT 'backend',
  company       TEXT NOT NULL,
  company_slug  TEXT,
  color         TEXT DEFAULT '#6366F1',
  letter        TEXT DEFAULT '?',
  stage         TEXT DEFAULT '',
  title         TEXT NOT NULL,
  location      TEXT DEFAULT 'US',
  is_remote     BOOLEAN DEFAULT false,
  posted_at     TIMESTAMPTZ DEFAULT NOW(),
  posted_label  TEXT DEFAULT 'Recently',
  is_new        BOOLEAN DEFAULT false,
  tc            TEXT DEFAULT 'Competitive',
  level         TEXT DEFAULT 'Senior',
  yoe           TEXT DEFAULT '5+ years',
  skills        TEXT[] DEFAULT '{}',
  visa          TEXT DEFAULT '',
  description   TEXT DEFAULT '',
  apply_url     TEXT DEFAULT '',
  fetched_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_jobs_cat        ON jobs(cat);
CREATE INDEX IF NOT EXISTS idx_jobs_emp_type   ON jobs(emp_type);
CREATE INDEX IF NOT EXISTS idx_jobs_is_remote  ON jobs(is_remote);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at  ON jobs(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_fetched_at ON jobs(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source     ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_company    ON jobs(company);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_jobs_fts ON jobs
  USING GIN(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(company,'') || ' ' || coalesce(description,'')));

-- Auto-delete jobs older than 60 days (keeps DB lean)
-- Run as a scheduled function in Supabase or add to your cron:
-- DELETE FROM jobs WHERE fetched_at < NOW() - INTERVAL '60 days';

-- Enable Row Level Security (allow public read, no public write)
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read" ON jobs
  FOR SELECT USING (true);

-- Only service role can insert/update/delete (used by scraper)
CREATE POLICY "Service write" ON jobs
  FOR ALL USING (auth.role() = 'service_role');
