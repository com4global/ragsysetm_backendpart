-- Migration 007: Video Batch Control & Replicate Credit Tracking
-- Per-user video generation control + admin oversight

-- 1. Add video generation flag to profiles (default OFF — user must opt-in)
ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS video_generation_enabled BOOLEAN DEFAULT FALSE;

-- 2. Replicate API credit tracking per user
CREATE TABLE IF NOT EXISTS replicate_usage (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    action      TEXT NOT NULL,              -- 'video_generation', 'audio_tts', etc.
    model       TEXT,                       -- which Replicate model was used
    credits     REAL DEFAULT 0,             -- estimated credit cost
    topic       TEXT,                       -- which topic this was for
    doc_name    TEXT,                       -- source document
    duration_ms REAL,                       -- how long the API call took
    status      TEXT DEFAULT 'completed',   -- 'completed', 'failed'
    metadata    JSONB DEFAULT '{}'::jsonb,  -- extra info
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replicate_user   ON replicate_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_replicate_date   ON replicate_usage(created_at DESC);

-- RLS
ALTER TABLE replicate_usage ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    DROP POLICY IF EXISTS "Service role full access on replicate_usage" ON replicate_usage;
EXCEPTION WHEN undefined_object THEN NULL;
END $$;
CREATE POLICY "Service role full access on replicate_usage"
    ON replicate_usage FOR ALL
    USING (auth.role() = 'service_role');

DO $$ BEGIN
    DROP POLICY IF EXISTS "Users see own replicate usage" ON replicate_usage;
EXCEPTION WHEN undefined_object THEN NULL;
END $$;
CREATE POLICY "Users see own replicate usage"
    ON replicate_usage FOR SELECT
    USING (auth.uid() = user_id);

COMMENT ON TABLE replicate_usage IS 'Per-user Replicate API credit tracking for video generation and other AI services.';
COMMENT ON COLUMN profiles.video_generation_enabled IS 'Whether auto video generation is enabled for this user. Default OFF — user or admin must enable.';
