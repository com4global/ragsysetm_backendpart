-- usage_logs table for tracking all 3rd-party API usage per user
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS usage_logs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  service text NOT NULL,          -- 'openai', 'sarvam', 'replicate', 'heygen', 'did'
  action text NOT NULL,           -- 'chat', 'lesson', 'tts', 'video', 'embedding', 'avatar'
  tokens_used integer DEFAULT 0,
  cost_usd numeric(10,6) DEFAULT 0,
  metadata jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

-- Index for fast per-user lookups
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_service ON usage_logs(service);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at DESC);

-- Allow service role to insert/read (no RLS needed for admin queries)
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;

-- Service role policy (backend uses service_role key)
CREATE POLICY "Service role full access" ON usage_logs
  FOR ALL USING (true) WITH CHECK (true);

-- Ensure is_active column exists on profiles (for restrict/unrestrict)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'profiles' AND column_name = 'is_active'
  ) THEN
    ALTER TABLE profiles ADD COLUMN is_active boolean DEFAULT true;
  END IF;
END $$;
