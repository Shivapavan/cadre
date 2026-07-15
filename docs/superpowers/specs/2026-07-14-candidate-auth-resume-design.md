# Candidate Login + Saved Resumes + AI Assist Reuse

## Problem

AI Assist currently requires a candidate to paste their resume text into a textarea every single time they apply to a job. There's no account system at all — "Sign in" and "Get started free" in the header are dead links (`href="#"`). Candidates re-paste the same resume repeatedly, and copy-pasting from Word/PDF resumes can silently drop content (e.g. a name stored in a DOCX header, diagnosed in a real test case with `Srikanth_Sama.docx`).

## Goal

Candidates create an account, upload one or more resumes once, and AI Assist uses a selected saved resume automatically for every job — no more re-pasting. AI-generated results (resume highlights, cover letter, interview prep, negotiation guide) become editable in place.

## Explicitly out of scope for this build

- Daily job matching / recommendations ("Get matched daily" step)
- Application tracking Kanban ("Track & negotiate" step)
- Full candidate profile (target salary, remote preference, companies to avoid)
- Persisting edited AI Assist output back to the database (edits are in-session only)
- Social login / MFA / third-party auth providers

## Architecture & Data Model

**Auth**: Supabase Auth (email/password), email confirmation required before login. Reuses Supabase's built-in `auth.users` — no custom credentials table.

*Operational note*: Supabase's default outbound email (used for confirmation links) has low rate limits on free/low tiers. Fine for beta-scale signups; if signup volume grows enough to hit those limits, the fix is configuring custom SMTP in the Supabase dashboard — no code change required, called out here so it isn't a surprise later.

**New table — `resumes`**:
```sql
CREATE TABLE resumes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  label        TEXT DEFAULT 'My Resume',
  file_path    TEXT,           -- Supabase Storage path, null if paste-only
  file_name    TEXT,           -- original filename, null if paste-only
  resume_text  TEXT NOT NULL,  -- extracted/pasted plain text, used by AI Assist
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own resumes" ON resumes
  FOR ALL USING (auth.uid() = user_id);
```

**New Storage bucket** — `resumes`, private (not public read). Files stored at `resumes/{user_id}/{resume_id}.{ext}`, so path structure alone prevents cross-user access even before RLS/storage policies are considered.

No changes to the existing `jobs` table.

## New/Modified Backend APIs (Vercel functions)

All three require a valid Supabase auth JWT (sent automatically by the browser client via the `Authorization` header) and explicitly verify resume ownership server-side — not relying on RLS alone.

- **`api/resume-upload.js`** (new) — `POST`. Accepts either a file (PDF/DOCX, sent as base64 JSON to avoid a multipart-parsing dependency) or pasted text (JSON). If a file: extracts text server-side using `pdf-parse` (PDF) or, for DOCX, by reading the file's internal ZIP structure directly with `jszip` and concatenating `word/header*.xml` + `word/document.xml` + `word/footer*.xml` (tags stripped) — this is the fix for the name-in-header bug. (Correction from an earlier draft of this spec: `mammoth` was considered for DOCX but verified to never have supported header/footer extraction — a `jszip`-based direct extraction is used instead, and is in fact simpler than the two-dependency approach originally proposed.) Uploads the original file to the `resumes` Storage bucket, inserts a row into the `resumes` table. Returns the created resume record.
- **`api/resumes.js`** (new) — `GET` lists the authenticated candidate's resumes (id, label, file_name, created_at — not the full text, to keep the picker payload light). `DELETE /?id=` removes one (also deletes the Storage file).
- **`api/ai-assist.js`** (modified) — request body changes from `{resume, job}` to `{resumeId, job}`. Looks up `resume_text` from the `resumes` table (filtered by `id = resumeId AND user_id = <authenticated user>`), then proceeds with the existing Anthropic-primary/OpenAI-fallback logic completely unchanged.

**New dependencies**: `pdf-parse`, `jszip` (approved — see correction note above; `jszip` replaces the originally-proposed `mammoth`). No client-side parsing libraries needed — extraction is server-side only, keeping `index.html` free of large new JS bundles.

## Frontend Flow (`index.html`)

- **Auth modal** replaces the dead `href="#"` links. Email/password fields call the Supabase browser client (`@supabase/supabase-js`, using the public `anon` key — safe to expose, same pattern as any Supabase web app) directly: `supabase.auth.signUp()` / `supabase.auth.signInWithPassword()`. Session persistence is handled automatically by the client library (localStorage). Header switches to showing the candidate's email + "Sign out" once authenticated.
- **"My Resumes" section** — upload a new resume via a standard file input (no drag-drop in this build) or paste text, with an optional label (e.g. "Backend resume", "Data resume"). Lists existing resumes with delete action.
- **AI Assist Step 1 changes**: the paste textarea is replaced with a **resume picker** — select from saved resumes (defaulting to the most recently created one, switchable), or a shortcut to upload a new one inline without leaving the flow. If the candidate isn't logged in, this step shows a sign-in/sign-up prompt instead.
- **Result panels become editable**: `result-resume-content`, `result-cover-content`, `result-prep-content`, `result-nego-content` change from read-only `<div>`s (currently just `.textContent` set once) to editable text areas, so the candidate can tweak AI-generated content before copying. Not persisted — session-only, consistent with the "no application tracking yet" scope boundary.

## Error Handling

- Unauthenticated access to AI Assist → sign-in prompt, not the resume picker
- Upload failures (unsupported type, extraction failure, oversized file) → clear inline error message, never a silent failure
- Auth errors (wrong password, unconfirmed email, duplicate signup email) → surfaced directly in the auth modal, using Supabase Auth's own error messages where they're already clear
- Every resume-related endpoint filters by the authenticated `user_id` server-side, in addition to RLS — defense in depth against ID-guessing attacks

## Security

- `SUPABASE_SERVICE_KEY` (already a secret, used by the scraper and `api/jobs.js`) stays server-side only
- Browser uses the public Supabase `anon` key for auth — this is safe to expose client-side (it's designed to be), and it's a *different* key from the service-role secret already in use
- RLS policies on `resumes` + per-user Storage paths + explicit server-side ownership checks (three independent layers, not just one)

## Testing Plan

Manual verification only (static-HTML project, no test framework):

1. Sign up → receive and click confirmation email → log in
2. Upload a PDF resume → verify extracted text is complete and correct
3. Upload a DOCX resume, specifically re-testing `Srikanth_Sama.docx` → confirm the candidate's name (previously missing because it lived in a DOCX header) now extracts correctly via the `jszip`-based header/footer extraction
4. Paste resume text directly (no file) → verify it saves correctly
5. Run AI Assist against an uploaded resume for a real job listing → confirm tailored materials generate correctly using the saved resume, no paste box shown
6. Edit a generated result in place → confirm the edit is reflected in the Copy button's output
7. Sign out, sign back in → confirm saved resumes persist and the picker still works
8. Attempt to access another user's resume by guessing an ID (via direct API call) → confirm it's rejected
