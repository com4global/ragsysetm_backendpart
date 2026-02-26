-- ═══════════════════════════════════════════════════════════════════
-- Migration: Create ai_videos table for D-ID / local video caching
-- Run this in: Supabase Dashboard → SQL Editor → New query → Paste → Run
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.ai_videos (
    cache_key   TEXT PRIMARY KEY,
    topic       TEXT NOT NULL,
    doc_name    TEXT DEFAULT '',
    language    TEXT DEFAULT 'en',
    video_id    TEXT DEFAULT '',
    video_url   TEXT NOT NULL,
    script      TEXT DEFAULT '',
    presenter   TEXT DEFAULT '',
    status      TEXT DEFAULT 'completed',
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Index for fast lookups by cache_key + status (already PK on cache_key,
-- but the code also filters by status)
CREATE INDEX IF NOT EXISTS idx_ai_videos_status ON public.ai_videos (status);

-- Allow the anon key to read/write the cache table
ALTER TABLE public.ai_videos ENABLE ROW LEVEL SECURITY;

-- Policy: anyone with a valid JWT can read/write cached videos
CREATE POLICY "Allow authenticated read" ON public.ai_videos
    FOR SELECT USING (true);

CREATE POLICY "Allow authenticated insert" ON public.ai_videos
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow authenticated update" ON public.ai_videos
    FOR UPDATE USING (true);

COMMENT ON TABLE public.ai_videos IS 'Cache for AI-generated teaching videos (D-ID lip-sync, local TTS, HeyGen)';
