-- Migration 006: Faithfulness Scores Table
-- Stores background faithfulness evaluation results for trend analysis.
-- Lightweight — only a sample of queries are scored (default 10%).

CREATE TABLE IF NOT EXISTS faithfulness_scores (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    answer_preview TEXT,
    score       REAL NOT NULL DEFAULT -1,           -- 0.0 to 1.0 (-1 = error)
    supported_claims   INT DEFAULT 0,
    unsupported_claims INT DEFAULT 0,
    hallucinated       BOOLEAN DEFAULT FALSE,
    reason      TEXT,
    doc_name    TEXT,
    response_time_ms  REAL,
    scored_at   TIMESTAMPTZ DEFAULT NOW(),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Index for dashboard queries (recent scores, per-user, low scores)
CREATE INDEX IF NOT EXISTS idx_faithfulness_scored_at ON faithfulness_scores(scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_faithfulness_user     ON faithfulness_scores(user_id);
CREATE INDEX IF NOT EXISTS idx_faithfulness_low      ON faithfulness_scores(score) WHERE score < 0.5;

-- RLS Policies
ALTER TABLE faithfulness_scores ENABLE ROW LEVEL SECURITY;

-- Admin can see all scores
DO $$ BEGIN
    DROP POLICY IF EXISTS "Service role full access on faithfulness_scores" ON faithfulness_scores;
EXCEPTION WHEN undefined_object THEN NULL;
END $$;
CREATE POLICY "Service role full access on faithfulness_scores"
    ON faithfulness_scores FOR ALL
    USING (auth.role() = 'service_role');

-- Users can only see their own scores
DO $$ BEGIN
    DROP POLICY IF EXISTS "Users see own faithfulness scores" ON faithfulness_scores;
EXCEPTION WHEN undefined_object THEN NULL;
END $$;
CREATE POLICY "Users see own faithfulness scores"
    ON faithfulness_scores FOR SELECT
    USING (auth.uid() = user_id);

COMMENT ON TABLE faithfulness_scores IS 'Background faithfulness evaluation results. Sampled at 10% of queries, scored by GPT-4o-mini judge.';
