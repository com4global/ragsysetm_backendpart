-- Migration: Add chapter_name column to classrooms table
-- Run this once in your Supabase SQL editor.
-- It is safe to run even if the column already exists.

ALTER TABLE classrooms
ADD COLUMN IF NOT EXISTS chapter_name TEXT DEFAULT '';

COMMENT ON COLUMN classrooms.chapter_name IS
  'Optional chapter the teacher assigned this classroom to. Empty = whole document.';
