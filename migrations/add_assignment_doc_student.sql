-- Migration: add doc_name and student_id to assignments table
-- Run this in the Supabase SQL Editor

ALTER TABLE assignments
    ADD COLUMN IF NOT EXISTS doc_name   TEXT,
    ADD COLUMN IF NOT EXISTS student_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- Optional index for fast filtering by student
CREATE INDEX IF NOT EXISTS idx_assignments_student_id ON assignments(student_id);
CREATE INDEX IF NOT EXISTS idx_assignments_doc_name   ON assignments(doc_name);
