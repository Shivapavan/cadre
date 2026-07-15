-- database/resumes_schema.sql
-- Run this in Supabase SQL editor (same project as schema.sql), after schema.sql

CREATE TABLE IF NOT EXISTS resumes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  label        TEXT DEFAULT 'My Resume',
  file_path    TEXT,           -- Supabase Storage path, null if paste-only
  file_name    TEXT,           -- original filename, null if paste-only
  resume_text  TEXT NOT NULL,  -- extracted/pasted plain text, used by AI Assist
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast filtering by user
CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);

-- Enable Row Level Security
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

-- Users can only access and manage their own resumes
CREATE POLICY "Users manage own resumes" ON resumes
  FOR ALL USING (auth.uid() = user_id);

-- Base table grants
GRANT SELECT, INSERT, UPDATE, DELETE ON resumes TO authenticated;
GRANT ALL ON resumes TO service_role;

-- Private Storage bucket for original resume files
INSERT INTO storage.buckets (id, name, public)
VALUES ('resumes', 'resumes', false)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: a user can only touch files under their own user_id "folder"
-- (file paths are always {user_id}/{resume_id}.{ext} — see Task 4)
CREATE POLICY "Users manage own resume files" ON storage.objects
  FOR ALL USING (
    bucket_id = 'resumes' AND
    (storage.foldername(name))[1] = auth.uid()::text
  );
