-- 1. Create 'uploads' bucket (Public)
INSERT INTO storage.buckets (id, name, public)
VALUES ('uploads', 'uploads', true)
ON CONFLICT (id) DO UPDATE
SET public = true;

-- 2. Add 'blob_url' to user_files table (Safe check)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_files' AND column_name = 'blob_url') THEN
        ALTER TABLE user_files ADD COLUMN blob_url TEXT;
    END IF;
END $$;

-- 3. Enable RLS Policies for Uploads (Drop first to avoid duplication error)
DROP POLICY IF EXISTS "Allow Public Uploads" ON storage.objects;
DROP POLICY IF EXISTS "Allow Public Select" ON storage.objects;
DROP POLICY IF EXISTS "Allow Public Update" ON storage.objects;

CREATE POLICY "Allow Public Uploads"
ON storage.objects FOR INSERT
TO public
WITH CHECK (bucket_id = 'uploads');

CREATE POLICY "Allow Public Select"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'uploads');

CREATE POLICY "Allow Public Update"
ON storage.objects FOR UPDATE
TO public
USING (bucket_id = 'uploads');

-- NOTE: Your version of Supabase does not support setting CORS via SQL.
-- Please go to Storage -> Buckets -> uploads -> Configuration and add http://localhost:3000 to CORS Origins.
