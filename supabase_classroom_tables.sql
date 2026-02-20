-- ================================================================
-- Classroom / LMS Tables for EdTech AI Learning Platform
-- Run this SQL in Supabase Dashboard → SQL Editor
-- ================================================================

-- 1. Classrooms table (created by teachers)
CREATE TABLE IF NOT EXISTS classrooms (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    teacher_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    doc_name TEXT DEFAULT '',          -- linked textbook / document name
    join_code TEXT NOT NULL UNIQUE,     -- 6-char uppercase code for students to join
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Classroom students (students who joined)
CREATE TABLE IF NOT EXISTS classroom_students (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    classroom_id UUID NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(classroom_id, student_id)
);

-- 3. Assignments (teacher sets chapter/topic goals)
CREATE TABLE IF NOT EXISTS assignments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    classroom_id UUID NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    chapter_title TEXT NOT NULL,
    topics JSONB DEFAULT '[]'::jsonb,   -- array of topic strings
    due_date DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Student progress tracking
CREATE TABLE IF NOT EXISTS student_progress (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    classroom_id UUID,                  -- NULL for individual learners
    topic TEXT NOT NULL,
    conversation_completed BOOLEAN DEFAULT false,
    video_completed BOOLEAN DEFAULT false,
    quiz_score NUMERIC DEFAULT 0,
    quiz_answers JSONB DEFAULT '{}'::jsonb,
    completed_at TIMESTAMPTZ,           -- NULL until fully done
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, classroom_id, topic)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_classrooms_teacher ON classrooms(teacher_id);
CREATE INDEX IF NOT EXISTS idx_cs_student ON classroom_students(student_id);
CREATE INDEX IF NOT EXISTS idx_cs_classroom ON classroom_students(classroom_id);
CREATE INDEX IF NOT EXISTS idx_assignments_classroom ON assignments(classroom_id);
CREATE INDEX IF NOT EXISTS idx_progress_student ON student_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_progress_classroom ON student_progress(classroom_id);
CREATE INDEX IF NOT EXISTS idx_classrooms_join_code ON classrooms(join_code);

-- Add 'role' column to profiles if it doesn't exist yet
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profiles' AND column_name = 'role'
    ) THEN
        ALTER TABLE profiles ADD COLUMN role TEXT DEFAULT 'student';
    END IF;
END $$;

-- RLS Policies (enable row-level security)
ALTER TABLE classrooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE classroom_students ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_progress ENABLE ROW LEVEL SECURITY;

-- Classrooms: teachers see own, students see joined
CREATE POLICY "Teachers manage own classrooms" ON classrooms
    FOR ALL USING (teacher_id = auth.uid());

CREATE POLICY "Members can view classrooms" ON classrooms
    FOR SELECT USING (
        id IN (SELECT classroom_id FROM classroom_students WHERE student_id = auth.uid())
    );

-- Students: manage own memberships
CREATE POLICY "Users manage own memberships" ON classroom_students
    FOR ALL USING (student_id = auth.uid());

CREATE POLICY "Teachers view classroom members" ON classroom_students
    FOR SELECT USING (
        classroom_id IN (SELECT id FROM classrooms WHERE teacher_id = auth.uid())
    );

-- Assignments: teachers create for own classrooms, members can view
CREATE POLICY "Teachers manage assignments" ON assignments
    FOR ALL USING (
        classroom_id IN (SELECT id FROM classrooms WHERE teacher_id = auth.uid())
    );

CREATE POLICY "Members view assignments" ON assignments
    FOR SELECT USING (
        classroom_id IN (SELECT classroom_id FROM classroom_students WHERE student_id = auth.uid())
    );

-- Progress: students manage own, teachers view for own classrooms
CREATE POLICY "Students manage own progress" ON student_progress
    FOR ALL USING (student_id = auth.uid());

CREATE POLICY "Teachers view classroom progress" ON student_progress
    FOR SELECT USING (
        classroom_id IN (SELECT id FROM classrooms WHERE teacher_id = auth.uid())
    );
