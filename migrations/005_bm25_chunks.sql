-- Migration: Create bm25_chunks table for hybrid search
-- Part of RAG Enhancement Phase 1: Hybrid Search (BM25 + Vector)
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS bm25_chunks (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  doc_name text NOT NULL,
  chunk_text text NOT NULL,
  page text DEFAULT 'N/A',
  path text DEFAULT '',
  metadata jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

-- Indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_bm25_chunks_user_id ON bm25_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_bm25_chunks_doc_name ON bm25_chunks(doc_name);
CREATE INDEX IF NOT EXISTS idx_bm25_chunks_user_doc ON bm25_chunks(user_id, doc_name);

-- RLS: service role has full access
ALTER TABLE bm25_chunks ENABLE ROW LEVEL SECURITY;

-- Drop existing policies first (safe to re-run)
DROP POLICY IF EXISTS "Service role full access on bm25_chunks" ON bm25_chunks;
DROP POLICY IF EXISTS "Users read own bm25 chunks" ON bm25_chunks;

-- Allow service role full access (used by backend)
CREATE POLICY "Service role full access on bm25_chunks" ON bm25_chunks
  FOR ALL USING (true) WITH CHECK (true);

-- Users can read their own chunks (if needed from frontend)
CREATE POLICY "Users read own bm25 chunks" ON bm25_chunks
  FOR SELECT USING (auth.uid() = user_id);
