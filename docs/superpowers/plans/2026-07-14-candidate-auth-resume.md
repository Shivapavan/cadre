# Candidate Login + Saved Resumes + AI Assist Reuse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Candidates create an account, upload one or more resumes once (PDF/DOCX/paste), and AI Assist uses a selected saved resume automatically for every job — no more re-pasting, and results become editable in place.

**Architecture:** Supabase Auth (email/password + confirmation) for accounts. A new `resumes` table (RLS-protected) + private Storage bucket hold resume text and original files. Three Vercel functions handle upload/extraction, listing/deletion, and the (modified) AI Assist call. `index.html` gains an auth modal, a "My Resumes" modal, a resume picker in the AI Assist flow, and editable result panels.

**Tech Stack:** Vanilla HTML/CSS/JS (no build step, no framework), Vercel serverless functions (Node.js, CommonJS), Supabase (Postgres + Auth + Storage), `@supabase/supabase-js` (already a dependency), `pdf-parse` + `jszip` (new dependencies, approved).

## Global Constraints

- No test framework exists in this project and none is being added — every task's "testing" step is a manual, exact `curl` command or browser action with an expected result, matching how every existing feature in this codebase has been verified.
- No build step — `index.html` is served as-is; all JS/CSS stays inline in that single file, matching existing convention.
- Resume uploads are sent as base64-encoded JSON (not multipart/form-data) specifically to avoid adding a multipart-parsing dependency.
- Vercel's default request body limit is 4.5MB — reject files over 3MB raw (before base64 encoding, which adds ~33% overhead) client-side with a clear error before upload.
- `SUPABASE_SERVICE_KEY` (already a secret in Vercel env vars) is server-side only, never sent to the browser. The browser uses a **different**, publicly-safe key (the Supabase "anon"/"publishable" key) for auth — this is Supabase's standard client-side pattern, not a secret leak.
- The Supabase project URL is `https://igtfiygorammhnjfhfcp.supabase.co` (not secret — safe to hardcode in `index.html`, same as any Supabase web app).
- DOCX text extraction does NOT use `mammoth` (verified during planning: mammoth.js has never supported header/footer extraction — open GitHub issue since 2013). It uses `jszip` to read the docx's internal ZIP structure directly and extract `word/header*.xml` + `word/document.xml` + `word/footer*.xml`.

---

### Task 1: Database schema — `resumes` table, RLS, Storage bucket

**Files:**
- Create: `database/resumes_schema.sql`

**Interfaces:**
- Produces: `resumes` table (columns: `id`, `user_id`, `label`, `file_path`, `file_name`, `resume_text`, `created_at`), Storage bucket `resumes` (private), RLS policies on both.

- [ ] **Step 1: Write the schema file**

```sql
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

CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON resumes(user_id);

ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own resumes" ON resumes
  FOR ALL USING (auth.uid() = user_id);

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
```

- [ ] **Step 2: Run it in the Supabase SQL editor**

Go to supabase.com → your project → SQL Editor → paste the full contents of `database/resumes_schema.sql` → Run.

Expected: no errors. "Success. No rows returned."

- [ ] **Step 3: Verify in the Supabase dashboard**

Table Editor → confirm `resumes` table exists with the 6 columns above. Storage → confirm a `resumes` bucket exists and is marked private (not public).

- [ ] **Step 4: Commit**

```bash
git add database/resumes_schema.sql
git commit -m "Add resumes table, RLS policies, and Storage bucket schema"
```

---

### Task 2: Supabase browser client + session handling foundation

**Files:**
- Modify: `index.html` (add CDN script tag near other `<script>` tags; add client init + session helpers near the top of the main `<script>` block, before the `JOBS` data array)

**Interfaces:**
- Produces: `sb` (global Supabase JS client instance), `async function getCurrentUser()` (returns the Supabase user object or `null`), `async function updateAuthUI()` (updates header based on session state — body filled in Task 3, stubbed here)

- [ ] **Step 1: Add the Supabase JS CDN script tag**

Find this line in `index.html` (near the top of `<head>` or just before the closing `</body>`, alongside any other external script tags — if none exist, add it directly before the main `<script>` tag):

```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js"></script>
```

Insert it immediately before this existing line:
```html
<script>
// JOB DATA
const JOBS = [
```

- [ ] **Step 2: Add client initialization and session helpers**

Immediately after the `<script>` opening tag, before `// JOB DATA`, add:

```javascript
// ── AUTH: Supabase client ────────────────────────────────────────────────
const SUPABASE_URL = 'https://igtfiygorammhnjfhfcp.supabase.co';
const SUPABASE_ANON_KEY = 'REPLACE_WITH_ANON_KEY'; // get from Supabase dashboard → Settings → API Keys → anon/publishable key
const sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function getCurrentUser() {
  const { data: { session } } = await sb.auth.getSession();
  return session?.user || null;
}

async function getAuthToken() {
  const { data: { session } } = await sb.auth.getSession();
  return session?.access_token || null;
}

async function updateAuthUI() {
  // Filled in during Task 3 — for now, just log so we can verify session detection works
  const user = await getCurrentUser();
  console.log('[auth] current user:', user?.email || 'not logged in');
}

sb.auth.onAuthStateChange((_event, _session) => { updateAuthUI(); });
document.addEventListener('DOMContentLoaded', updateAuthUI);
```

**⚠️ Live setup step required before this task can be tested:** Go to supabase.com → your project → Settings → API Keys → copy the **anon** (or **publishable**) key → replace `REPLACE_WITH_ANON_KEY` above with the real value. This key is safe to embed in client-side code (that's its intended use — protected by RLS, not secrecy).

- [ ] **Step 3: Manual test — verify the client loads and detects session state**

Open `https://cadre-jobs.vercel.app` (or run locally) in a browser, open DevTools Console.

Expected: `[auth] current user: not logged in` printed, no errors about `supabase is not defined` or invalid API key.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "Add Supabase browser client and session-detection foundation"
```

---

### Task 3: Auth UI — sign up / sign in / sign out

**Files:**
- Modify: `index.html`
  - Replace lines 343-344 (the dead `Sign in` / `Get started free` header links)
  - Add a new auth modal (place it right after the closing `</div>` of the AI Assist modal, before the final `<style>` block — same pattern as the existing `ai-modal`)
  - Fill in the `updateAuthUI()` stub from Task 2

**Interfaces:**
- Consumes: `sb`, `getCurrentUser()` from Task 2
- Produces: `openAuthModal(mode)` (`mode` is `'signin'` or `'signup'`), `closeAuthModal()`, `async function handleAuthSubmit()`, `async function handleSignOut()`

- [ ] **Step 1: Replace the header auth links**

Find (around line 342-345):
```html
    <div class="nav-actions">
      <a href="#" class="btn-ghost">Sign in</a>
      <a href="#" class="btn-primary">Get started free</a>
    </div>
```

Replace with:
```html
    <div class="nav-actions" id="nav-auth-area">
      <a href="#" class="btn-ghost" id="nav-signin-link" onclick="openAuthModal('signin');return false;">Sign in</a>
      <a href="#" class="btn-primary" id="nav-signup-link" onclick="openAuthModal('signup');return false;">Get started free</a>
    </div>
```

- [ ] **Step 2: Add the auth modal HTML**

Find this closing structure (end of the AI Assist modal, currently the last modal in the file):
```html
        </div>
      </div>
    </div>
  </div>
</div>

<style>
.ai-step{}
```

Insert a new modal directly before `<style>`:
```html
<!-- AUTH MODAL -->
<div class="modal-overlay" id="auth-modal">
  <div class="modal" style="max-width:420px">
    <div class="modal-header">
      <div style="font-size:1.2rem;font-weight:800;color:var(--navy)" id="auth-modal-title">Sign in</div>
      <button class="modal-close" onclick="closeAuthModal()">✕</button>
    </div>
    <div class="modal-body">
      <div id="auth-error" style="display:none;background:#FEF2F2;border:1px solid #FECACA;color:#DC2626;padding:.75rem 1rem;border-radius:10px;font-size:.85rem;margin-bottom:1rem"></div>
      <div id="auth-success" style="display:none;background:#F0FDF4;border:1px solid #BBF7D0;color:#15803D;padding:.75rem 1rem;border-radius:10px;font-size:.85rem;margin-bottom:1rem"></div>
      <label style="font-size:.8rem;font-weight:600;color:var(--navy);display:block;margin-bottom:.4rem">Email</label>
      <input type="email" id="auth-email" placeholder="you@example.com" style="width:100%;padding:.75rem 1rem;border:1px solid var(--border);border-radius:10px;font-size:.95rem;margin-bottom:1rem" />
      <label style="font-size:.8rem;font-weight:600;color:var(--navy);display:block;margin-bottom:.4rem">Password</label>
      <input type="password" id="auth-password" placeholder="At least 6 characters" style="width:100%;padding:.75rem 1rem;border:1px solid var(--border);border-radius:10px;font-size:.95rem;margin-bottom:1.25rem" />
      <button class="apply-action" id="auth-submit-btn" onclick="handleAuthSubmit()">Sign in</button>
      <p style="text-align:center;font-size:.85rem;color:var(--slate);margin-top:1rem">
        <span id="auth-toggle-text">Don't have an account?</span>
        <a href="#" id="auth-toggle-link" onclick="toggleAuthMode();return false;" style="color:var(--indigo);font-weight:600">Sign up</a>
      </p>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add the auth JS logic**

Add this near the end of the main `<script>` block, right before the closing `// Close AI modal on overlay click` section:

```javascript
// ── AUTH: modal + signup/signin/signout ─────────────────────────────────
let authMode = 'signin';

function openAuthModal(mode) {
  authMode = mode;
  applyAuthMode();
  document.getElementById('auth-error').style.display = 'none';
  document.getElementById('auth-success').style.display = 'none';
  document.getElementById('auth-email').value = '';
  document.getElementById('auth-password').value = '';
  document.getElementById('auth-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeAuthModal() {
  document.getElementById('auth-modal').classList.remove('open');
  document.body.style.overflow = '';
}

function toggleAuthMode() {
  authMode = authMode === 'signin' ? 'signup' : 'signin';
  applyAuthMode();
}

function applyAuthMode() {
  const isSignup = authMode === 'signup';
  document.getElementById('auth-modal-title').textContent = isSignup ? 'Create your account' : 'Sign in';
  document.getElementById('auth-submit-btn').textContent = isSignup ? 'Sign up' : 'Sign in';
  document.getElementById('auth-toggle-text').textContent = isSignup ? 'Already have an account?' : "Don't have an account?";
  document.getElementById('auth-toggle-link').textContent = isSignup ? 'Sign in' : 'Sign up';
}

async function handleAuthSubmit() {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const errorEl = document.getElementById('auth-error');
  const successEl = document.getElementById('auth-success');
  errorEl.style.display = 'none';
  successEl.style.display = 'none';

  if (!email || !password) {
    errorEl.textContent = 'Email and password are required.';
    errorEl.style.display = 'block';
    return;
  }

  if (authMode === 'signup') {
    const { error } = await sb.auth.signUp({ email, password });
    if (error) {
      errorEl.textContent = error.message;
      errorEl.style.display = 'block';
      return;
    }
    successEl.textContent = 'Account created! Check your email to confirm, then sign in.';
    successEl.style.display = 'block';
    authMode = 'signin';
    applyAuthMode();
  } else {
    const { error } = await sb.auth.signInWithPassword({ email, password });
    if (error) {
      errorEl.textContent = error.message;
      errorEl.style.display = 'block';
      return;
    }
    closeAuthModal();
  }
}

async function handleSignOut() {
  await sb.auth.signOut();
}
```

- [ ] **Step 4: Fill in the `updateAuthUI()` stub from Task 2**

Find the stub added in Task 2:
```javascript
async function updateAuthUI() {
  // Filled in during Task 3 — for now, just log so we can verify session detection works
  const user = await getCurrentUser();
  console.log('[auth] current user:', user?.email || 'not logged in');
}
```

Replace with:
```javascript
async function updateAuthUI() {
  const user = await getCurrentUser();
  const navArea = document.getElementById('nav-auth-area');
  if (user) {
    navArea.innerHTML = `
      <span style="font-size:.85rem;color:var(--slate);margin-right:.5rem">${user.email}</span>
      <a href="#" class="btn-ghost" onclick="handleSignOut();return false;">Sign out</a>
    `;
  } else {
    navArea.innerHTML = `
      <a href="#" class="btn-ghost" onclick="openAuthModal('signin');return false;">Sign in</a>
      <a href="#" class="btn-primary" onclick="openAuthModal('signup');return false;">Get started free</a>
    `;
  }
}
```

- [ ] **Step 5: Add overlay-click-to-close for the new modal**

Find:
```javascript
// Close AI modal on overlay click
document.getElementById('ai-modal').addEventListener('click', function(e) {
  if (e.target === this) closeAIModal();
});
```

Add immediately after:
```javascript
document.getElementById('auth-modal').addEventListener('click', function(e) {
  if (e.target === this) closeAuthModal();
});
```

- [ ] **Step 6: Manual test — full signup/signin/signout cycle**

1. Open the site, click "Get started free" → modal opens in signup mode
2. Enter a real email you can check + a password → click "Sign up"
3. Expected: green success message about checking email
4. Check the email inbox → click the confirmation link
5. Back on the site, click "Sign in" → enter the same credentials → click "Sign in"
6. Expected: modal closes, header now shows your email + "Sign out"
7. Click "Sign out" → header reverts to "Sign in" / "Get started free"

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "Add sign up/sign in/sign out UI wired to Supabase Auth"
```

---

### Task 4: Shared backend auth helper + `api/resume-upload.js`

**Files:**
- Create: `lib/supabaseAdmin.js` (outside `api/` so it's never treated as its own route)
- Create: `api/resume-upload.js`
- Modify: `package.json` (add `pdf-parse`, `jszip`)

**Interfaces:**
- Produces: `supabaseAdmin` (service-role Supabase client), `async function getAuthedUser(req)` (returns Supabase user object or `null`) — both exported from `lib/supabaseAdmin.js`, used by Tasks 5 and 6 too.
- Produces: `POST /api/resume-upload` — body `{ label?, fileName?, fileBase64?, mimeType?, pastedText? }`, header `Authorization: Bearer <token>` → returns `{ id, label, file_name, created_at }` on success.

- [ ] **Step 1: Add new dependencies to `package.json`**

Current `package.json`:
```json
{
  "name": "cadre-jobs",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "@supabase/supabase-js": "^2.45.0"
  }
}
```

Replace with:
```json
{
  "name": "cadre-jobs",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "@supabase/supabase-js": "^2.45.0",
    "pdf-parse": "^1.1.1",
    "jszip": "^3.10.1"
  }
}
```

- [ ] **Step 2: Create the shared auth helper**

```javascript
// lib/supabaseAdmin.js
const { createClient } = require("@supabase/supabase-js");

const supabaseAdmin = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Verifies a Supabase access token sent from the browser and returns the
// authenticated user, or null if missing/invalid.
async function getAuthedUser(req) {
  const authHeader = req.headers.authorization || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
  if (!token) return null;
  const { data, error } = await supabaseAdmin.auth.getUser(token);
  if (error || !data?.user) return null;
  return data.user;
}

module.exports = { supabaseAdmin, getAuthedUser };
```

- [ ] **Step 3: Write the DOCX header/footer-aware text extractor**

This is a standalone function — write it directly into `api/resume-upload.js` (Step 4) since it's only used there.

- [ ] **Step 4: Create `api/resume-upload.js`**

```javascript
// api/resume-upload.js
const pdfParse = require("pdf-parse");
const JSZip = require("jszip");
const { supabaseAdmin, getAuthedUser } = require("../lib/supabaseAdmin");

const MAX_FILE_BYTES = 3 * 1024 * 1024; // 3MB raw, matches Global Constraints

function stripXmlTags(xml) {
  return xml.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

// docx files are a ZIP of XML parts. mammoth.js (considered during planning)
// never supported header/footer extraction — headers/footers commonly hold
// a candidate's name and contact info, so we read the ZIP directly instead.
async function extractDocxText(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const fileNames = Object.keys(zip.files).sort();
  const parts = [];

  for (const name of fileNames) {
    if (/^word\/header\d*\.xml$/.test(name)) {
      parts.push(await zip.files[name].async("string"));
    }
  }
  if (zip.files["word/document.xml"]) {
    parts.push(await zip.files["word/document.xml"].async("string"));
  }
  for (const name of fileNames) {
    if (/^word\/footer\d*\.xml$/.test(name)) {
      parts.push(await zip.files[name].async("string"));
    }
  }

  return stripXmlTags(parts.join(" "));
}

async function extractPdfText(buffer) {
  const data = await pdfParse(buffer);
  return (data.text || "").trim();
}

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "Please sign in first" });

  const { label, fileName, fileBase64, mimeType, pastedText } = req.body || {};

  let resumeText = "";
  let filePath = null;
  let storedFileName = null;

  if (pastedText && pastedText.trim()) {
    resumeText = pastedText.trim();
  } else if (fileBase64 && fileName) {
    const buffer = Buffer.from(fileBase64, "base64");
    if (buffer.length > MAX_FILE_BYTES) {
      return res.status(400).json({ error: "File too large (max 3MB)" });
    }

    const ext = fileName.split(".").pop().toLowerCase();
    try {
      if (ext === "pdf") {
        resumeText = await extractPdfText(buffer);
      } else if (ext === "docx") {
        resumeText = await extractDocxText(buffer);
      } else {
        return res.status(400).json({ error: "Only PDF and DOCX files are supported" });
      }
    } catch (e) {
      console.error("Extraction error:", e.message);
      return res.status(400).json({ error: "Could not read that file — try pasting the text instead" });
    }

    if (!resumeText) {
      return res.status(400).json({ error: "No text could be extracted from that file" });
    }

    storedFileName = fileName;
    filePath = `${user.id}/${Date.now()}-${fileName.replace(/[^a-zA-Z0-9._-]/g, "_")}`;
    const { error: uploadError } = await supabaseAdmin.storage
      .from("resumes")
      .upload(filePath, buffer, { contentType: mimeType || "application/octet-stream", upsert: false });
    if (uploadError) {
      console.error("Storage upload error:", uploadError.message);
      return res.status(500).json({ error: "Failed to store the resume file" });
    }
  } else {
    return res.status(400).json({ error: "Provide either pastedText or a fileBase64 + fileName" });
  }

  const { data: inserted, error: insertError } = await supabaseAdmin
    .from("resumes")
    .insert({
      user_id: user.id,
      label: label && label.trim() ? label.trim() : "My Resume",
      file_path: filePath,
      file_name: storedFileName,
      resume_text: resumeText,
    })
    .select("id, label, file_name, created_at")
    .single();

  if (insertError) {
    console.error("Resume insert error:", insertError.message);
    return res.status(500).json({ error: "Failed to save resume" });
  }

  res.status(200).json(inserted);
};
```

- [ ] **Step 5: Manual test — paste-text upload**

Get a real access token first by signing in via the browser (Task 3), then in DevTools Console:
```javascript
const token = await getAuthToken();
console.log(token);
```
Copy that token, then:
```bash
curl -s -X POST "https://cadre-jobs.vercel.app/api/resume-upload" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE" \
  -d '{"pastedText": "Jane Doe, Senior Engineer, 8 years experience.", "label": "Test Resume"}'
```
Expected: `{"id":"...","label":"Test Resume","file_name":null,"created_at":"..."}`

- [ ] **Step 6: Manual test — reject unauthenticated requests**

```bash
curl -s -X POST "https://cadre-jobs.vercel.app/api/resume-upload" \
  -H "Content-Type: application/json" \
  -d '{"pastedText": "test"}'
```
Expected: `{"error":"Please sign in first"}` with HTTP 401.

- [ ] **Step 7: Manual test — the exact DOCX bug fix, using the real file**

```bash
python3 -c "
import base64, json
with open('/Users/shiva/Downloads/Srikanth_Sama.docx', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
print(json.dumps({'fileName': 'Srikanth_Sama.docx', 'fileBase64': b64, 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'label': 'Docx Test'}))
" > /tmp/docx_test_payload.json

curl -s -X POST "https://cadre-jobs.vercel.app/api/resume-upload" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE" \
  -d @/tmp/docx_test_payload.json
```
Then verify the extracted text actually contains the name by querying Supabase directly (using the service key, same pattern used throughout this project):
```bash
curl -s "https://igtfiygorammhnjfhfcp.supabase.co/rest/v1/resumes?label=eq.Docx%20Test&select=resume_text" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" | grep -o "SRIKANTH SAMA"
```
Expected: `SRIKANTH SAMA` is found in the output — confirming the header-extraction fix works on the exact file that originally exposed the bug.

- [ ] **Step 8: Manual test — PDF upload and extraction**

Using any real PDF resume file you have on hand (a hand-crafted minimal PDF isn't a reliable substitute — real PDFs vary enough in internal structure that `pdf-parse` should be tested against one that actually exists):

```bash
python3 -c "
import base64, json, sys
path = sys.argv[1]
with open(path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
print(json.dumps({'fileName': 'test-resume.pdf', 'fileBase64': b64, 'mimeType': 'application/pdf', 'label': 'PDF Test'}))
" /path/to/any/real/resume.pdf > /tmp/pdf_test_payload.json

curl -s -X POST "https://cadre-jobs.vercel.app/api/resume-upload" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE" \
  -d @/tmp/pdf_test_payload.json
```
Expected: `{"id":"...","label":"PDF Test","file_name":"test-resume.pdf","created_at":"..."}`. Spot-check the extracted text is non-empty and roughly matches the PDF's visible content via the same Supabase query pattern as Step 7 (swap `label=eq.Docx%20Test` for `label=eq.PDF%20Test`).

- [ ] **Step 9: Commit**

```bash
git add lib/supabaseAdmin.js api/resume-upload.js package.json
git commit -m "Add resume upload API: PDF/DOCX extraction (with docx header/footer support via jszip) + paste, Storage upload"
```

---

### Task 5: `api/resumes.js` — list and delete

**Files:**
- Create: `api/resumes.js`

**Interfaces:**
- Consumes: `supabaseAdmin`, `getAuthedUser` from `lib/supabaseAdmin.js` (Task 4)
- Produces: `GET /api/resumes` → `{ resumes: [{id, label, file_name, created_at}, ...] }`; `DELETE /api/resumes?id=<uuid>` → `{ success: true }`

- [ ] **Step 1: Create the file**

```javascript
// api/resumes.js
const { supabaseAdmin, getAuthedUser } = require("../lib/supabaseAdmin");

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();

  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "Please sign in first" });

  if (req.method === "GET") {
    const { data, error } = await supabaseAdmin
      .from("resumes")
      .select("id, label, file_name, created_at")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false });

    if (error) {
      console.error("List resumes error:", error.message);
      return res.status(500).json({ error: "Failed to fetch resumes" });
    }
    return res.status(200).json({ resumes: data });
  }

  if (req.method === "DELETE") {
    const { id } = req.query;
    if (!id) return res.status(400).json({ error: "id is required" });

    const { data: resume } = await supabaseAdmin
      .from("resumes")
      .select("file_path")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (!resume) return res.status(404).json({ error: "Resume not found" });

    if (resume.file_path) {
      await supabaseAdmin.storage.from("resumes").remove([resume.file_path]);
    }

    const { error } = await supabaseAdmin
      .from("resumes")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) {
      console.error("Delete resume error:", error.message);
      return res.status(500).json({ error: "Failed to delete resume" });
    }
    return res.status(200).json({ success: true });
  }

  return res.status(405).json({ error: "GET or DELETE only" });
};
```

- [ ] **Step 2: Manual test — list resumes**

```bash
curl -s "https://cadre-jobs.vercel.app/api/resumes" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE"
```
Expected: `{"resumes":[{...the test resumes from Task 4...}]}`

- [ ] **Step 3: Manual test — delete a resume**

```bash
curl -s -X DELETE "https://cadre-jobs.vercel.app/api/resumes?id=PASTE_RESUME_ID_HERE" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE"
```
Expected: `{"success":true}`. Re-run the list command from Step 2 — the deleted resume should no longer appear.

- [ ] **Step 4: Manual test — cross-user access is rejected**

Sign up a second test account (different email), get its token, and try deleting the first account's resume with the second account's token.

Expected: `{"error":"Resume not found"}` with HTTP 404 (not 403 — this intentionally doesn't reveal whether the ID exists at all).

- [ ] **Step 5: Commit**

```bash
git add api/resumes.js
git commit -m "Add resume list/delete API"
```

---

### Task 6: Modify `api/ai-assist.js` to use `resumeId`

**Files:**
- Modify: `api/ai-assist.js`

**Interfaces:**
- Consumes: `supabaseAdmin`, `getAuthedUser` from `lib/supabaseAdmin.js` (Task 4)
- Changes the request contract: `POST /api/ai-assist` body changes from `{resume, job}` to `{resumeId, job}`, now requires `Authorization: Bearer <token>`.

- [ ] **Step 1: Add the shared-lib import**

Find the top of `api/ai-assist.js`:
```javascript
// AI Assist — generates a tailored resume, cover letter, interview prep, and
// negotiation guide from a pasted resume + job posting. Tries Anthropic first,
// falls back to OpenAI if the primary call fails or its key isn't configured.

const RESULT_SCHEMA = {
```

Replace with:
```javascript
// AI Assist — generates a tailored resume, cover letter, interview prep, and
// negotiation guide from a candidate's saved resume + job posting. Tries
// Anthropic first, falls back to OpenAI if the primary call fails or its key
// isn't configured.

const { supabaseAdmin, getAuthedUser } = require("../lib/supabaseAdmin");

const RESULT_SCHEMA = {
```

- [ ] **Step 2: Replace the request handling in `module.exports`**

Find:
```javascript
module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const { resume, job } = req.body || {};
  if (!resume || typeof resume !== "string" || !resume.trim()) {
    return res.status(400).json({ error: "resume is required" });
  }
  if (!job || !job.title || !job.company) {
    return res.status(400).json({ error: "job (title, company) is required" });
  }
```

Replace with:
```javascript
module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const user = await getAuthedUser(req);
  if (!user) return res.status(401).json({ error: "Please sign in first" });

  const { resumeId, job } = req.body || {};
  if (!resumeId) {
    return res.status(400).json({ error: "resumeId is required" });
  }
  if (!job || !job.title || !job.company) {
    return res.status(400).json({ error: "job (title, company) is required" });
  }

  const { data: resumeRow, error: resumeErr } = await supabaseAdmin
    .from("resumes")
    .select("resume_text")
    .eq("id", resumeId)
    .eq("user_id", user.id)
    .single();

  if (resumeErr || !resumeRow) {
    return res.status(404).json({ error: "Resume not found" });
  }
  const resume = resumeRow.resume_text;
```

Everything below this point in the file (`let result, provider; try { ... }`) is unchanged — it already uses the local variable `resume`, which now comes from the database lookup instead of the request body.

- [ ] **Step 3: Manual test — full flow with a real saved resume**

Using the resume ID created in Task 4's Step 5 test and the same auth token:
```bash
curl -s "https://cadre-jobs.vercel.app/api/ai-assist" -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE" \
  -d '{"resumeId": "PASTE_RESUME_ID_HERE", "job": {"title":"Senior Engineer","company":"Coinbase","location":"US","level":"Senior","skills":["Python","AWS"]}}' \
  --max-time 30
```
Expected: full JSON response with `resume`, `coverLetter`, `interviewPrep`, `negotiation`, `provider` — same shape as before, just sourced from the saved resume instead of a pasted one.

- [ ] **Step 4: Manual test — missing/wrong resumeId is rejected**

```bash
curl -s "https://cadre-jobs.vercel.app/api/ai-assist" -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer PASTE_TOKEN_HERE" \
  -d '{"resumeId": "00000000-0000-0000-0000-000000000000", "job": {"title":"Senior Engineer","company":"Coinbase"}}'
```
Expected: `{"error":"Resume not found"}` with HTTP 404.

- [ ] **Step 5: Commit**

```bash
git add api/ai-assist.js
git commit -m "Require auth + saved resumeId in AI Assist instead of pasted resume text"
```

---

### Task 7: Frontend — "My Resumes" UI

**Files:**
- Modify: `index.html` (new modal + JS, following the same `.modal-overlay` pattern as `auth-modal` and `ai-modal`)

**Interfaces:**
- Consumes: `sb`, `getAuthToken()`, `getCurrentUser()` (Task 2); `/api/resume-upload`, `/api/resumes` (Tasks 4, 5)
- Produces: `openMyResumesModal()`, `closeMyResumesModal()`, `async function loadResumeList()`, `async function handleResumeUpload()`, `async function deleteResume(id)`, `async function fileToBase64(file)`

- [ ] **Step 1: Add the "My Resumes" modal HTML**

Insert directly after the auth modal's closing `</div>` (added in Task 3, Step 2), before `<style>`:

```html
<!-- MY RESUMES MODAL -->
<div class="modal-overlay" id="resumes-modal">
  <div class="modal" style="max-width:560px">
    <div class="modal-header">
      <div style="font-size:1.2rem;font-weight:800;color:var(--navy)">My Resumes</div>
      <button class="modal-close" onclick="closeMyResumesModal()">✕</button>
    </div>
    <div class="modal-body">
      <div id="resume-upload-error" style="display:none;background:#FEF2F2;border:1px solid #FECACA;color:#DC2626;padding:.75rem 1rem;border-radius:10px;font-size:.85rem;margin-bottom:1rem"></div>

      <div style="border:1px dashed var(--border);border-radius:12px;padding:1.25rem;margin-bottom:1.5rem">
        <label style="font-size:.8rem;font-weight:600;color:var(--navy);display:block;margin-bottom:.4rem">Label (optional)</label>
        <input type="text" id="resume-upload-label" placeholder="e.g. Backend resume" style="width:100%;padding:.6rem 1rem;border:1px solid var(--border);border-radius:10px;font-size:.9rem;margin-bottom:.75rem" />
        <label style="font-size:.8rem;font-weight:600;color:var(--navy);display:block;margin-bottom:.4rem">Upload a file (PDF or DOCX)</label>
        <input type="file" id="resume-upload-file" accept=".pdf,.docx" style="width:100%;margin-bottom:.75rem" />
        <label style="font-size:.8rem;font-weight:600;color:var(--navy);display:block;margin-bottom:.4rem">— or paste text directly</label>
        <textarea id="resume-upload-paste" placeholder="Paste resume text here…" style="width:100%;min-height:100px;padding:.6rem 1rem;border:1px solid var(--border);border-radius:10px;font-size:.85rem;margin-bottom:.75rem"></textarea>
        <button class="apply-action" id="resume-upload-btn" onclick="handleResumeUpload()">Save Resume</button>
      </div>

      <div style="font-size:.8rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--slate);margin-bottom:.75rem">Saved Resumes</div>
      <div id="resume-list"></div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add a nav trigger for the modal**

Find the logged-in branch inside `updateAuthUI()` (Task 3, Step 4):
```javascript
    navArea.innerHTML = `
      <span style="font-size:.85rem;color:var(--slate);margin-right:.5rem">${user.email}</span>
      <a href="#" class="btn-ghost" onclick="handleSignOut();return false;">Sign out</a>
    `;
```

Replace with:
```javascript
    navArea.innerHTML = `
      <a href="#" class="btn-ghost" onclick="openMyResumesModal();return false;">My Resumes</a>
      <span style="font-size:.85rem;color:var(--slate);margin-right:.5rem">${user.email}</span>
      <a href="#" class="btn-ghost" onclick="handleSignOut();return false;">Sign out</a>
    `;
```

- [ ] **Step 3: Add the "My Resumes" JS**

Add after the auth JS block from Task 3 (before the overlay-click-to-close listeners):

```javascript
// ── MY RESUMES ────────────────────────────────────────────────────────────
const MAX_RESUME_FILE_BYTES = 3 * 1024 * 1024; // 3MB, matches api/resume-upload.js

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function openMyResumesModal() {
  document.getElementById('resumes-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
  await loadResumeList();
}

function closeMyResumesModal() {
  document.getElementById('resumes-modal').classList.remove('open');
  document.body.style.overflow = '';
}

async function loadResumeList() {
  const listEl = document.getElementById('resume-list');
  listEl.innerHTML = '<p style="color:var(--slate);font-size:.85rem">Loading…</p>';
  const token = await getAuthToken();
  const res = await fetch('/api/resumes', { headers: { Authorization: `Bearer ${token}` } });
  const data = await res.json();
  if (!res.ok) {
    listEl.innerHTML = `<p style="color:#DC2626;font-size:.85rem">${data.error || 'Failed to load resumes'}</p>`;
    return;
  }
  if (!data.resumes.length) {
    listEl.innerHTML = '<p style="color:var(--slate);font-size:.85rem">No resumes saved yet.</p>';
    return;
  }
  listEl.innerHTML = data.resumes.map(r => `
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.75rem 1rem;border:1px solid var(--border);border-radius:10px;margin-bottom:.6rem">
      <div>
        <div style="font-weight:700;font-size:.9rem;color:var(--navy)">${r.label}</div>
        <div style="font-size:.75rem;color:var(--slate)">${r.file_name || 'Pasted text'} · ${new Date(r.created_at).toLocaleDateString()}</div>
      </div>
      <button style="background:none;border:none;color:#DC2626;cursor:pointer;font-size:.85rem;font-weight:600" onclick="deleteResume('${r.id}')">Delete</button>
    </div>
  `).join('');
}

async function handleResumeUpload() {
  const errorEl = document.getElementById('resume-upload-error');
  errorEl.style.display = 'none';
  const label = document.getElementById('resume-upload-label').value.trim();
  const fileInput = document.getElementById('resume-upload-file');
  const pastedText = document.getElementById('resume-upload-paste').value.trim();
  const btn = document.getElementById('resume-upload-btn');

  const file = fileInput.files[0];
  if (!file && !pastedText) {
    errorEl.textContent = 'Upload a file or paste resume text.';
    errorEl.style.display = 'block';
    return;
  }
  if (file && file.size > MAX_RESUME_FILE_BYTES) {
    errorEl.textContent = 'File too large (max 3MB).';
    errorEl.style.display = 'block';
    return;
  }

  btn.textContent = 'Saving…';
  btn.disabled = true;

  const token = await getAuthToken();
  let body;
  if (file) {
    const fileBase64 = await fileToBase64(file);
    body = { label, fileName: file.name, fileBase64, mimeType: file.type };
  } else {
    body = { label, pastedText };
  }

  const res = await fetch('/api/resume-upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  const data = await res.json();

  btn.textContent = 'Save Resume';
  btn.disabled = false;

  if (!res.ok) {
    errorEl.textContent = data.error || 'Failed to save resume';
    errorEl.style.display = 'block';
    return;
  }

  document.getElementById('resume-upload-label').value = '';
  document.getElementById('resume-upload-file').value = '';
  document.getElementById('resume-upload-paste').value = '';
  await loadResumeList();
}

async function deleteResume(id) {
  const token = await getAuthToken();
  await fetch(`/api/resumes?id=${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  await loadResumeList();
}
```

- [ ] **Step 4: Add overlay-click-to-close**

Add alongside the other overlay listeners:
```javascript
document.getElementById('resumes-modal').addEventListener('click', function(e) {
  if (e.target === this) closeMyResumesModal();
});
```

- [ ] **Step 5: Manual test — upload, list, delete via the UI**

1. Sign in, click "My Resumes"
2. Upload the `Srikanth_Sama.docx` file with label "Docx Test" → click Save Resume
3. Expected: appears in the list below within a second or two, showing "Docx Test" and the filename
4. Paste some text with a different label, save → expected: also appears in the list
5. Click Delete on one → expected: disappears from the list immediately

- [ ] **Step 6: Manual test — resumes persist across sign-out/sign-in**

1. With at least one resume still saved from Step 5, click "Sign out"
2. Sign back in with the same account
3. Click "My Resumes" again
4. Expected: the resume(s) from Step 5 are still listed — confirms resumes are tied to the account in the database, not to browser session state

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "Add My Resumes UI: upload (file/paste), list, delete"
```

---

### Task 8: Frontend — AI Assist resume picker + auth gate

**Files:**
- Modify: `index.html`
  - Replace the Step 1 content of the AI Assist modal (currently the paste textarea, lines ~801-829)
  - Modify `openAIAssist()`, `runAIAssist()`, `resetAI()`

**Interfaces:**
- Consumes: everything from Tasks 2, 3, 4, 5, 7
- Produces: `selectedResumeId` (module-level variable tracking the picker's current selection)

- [ ] **Step 1: Replace AI Assist Step 1 HTML**

Find (the full existing Step 1 block, lines ~801-829):
```html
    <!-- STEP 1: Upload Resume -->
    <div id="ai-step-1" class="ai-step">
      <div class="modal-body">
        <div class="step-indicator">
          <div class="step-dot active" data-s="1">1</div>
          <div class="step-line"></div>
          <div class="step-dot" data-s="2">2</div>
          <div class="step-line"></div>
          <div class="step-dot" data-s="3">3</div>
          <div class="step-line"></div>
          <div class="step-dot" data-s="4">4</div>
        </div>
        <h3 style="font-size:1.1rem;font-weight:700;color:var(--navy);margin:1.5rem 0 .5rem">Paste your resume or key experience</h3>
        <p style="font-size:.875rem;color:#64748B;margin-bottom:1.25rem">The AI will tailor your resume, write a cover letter, and generate interview prep — all specific to this role.</p>
        <textarea id="resume-input" class="resume-textarea" placeholder="Paste your resume text here…

Example:
Senior Data Engineer at Accenture (2020–present)
• Built medallion architecture pipelines using Azure Data Factory and Databricks
• Designed Bronze/Silver/Gold Delta Lake layers processing 50M+ records/day
• Led migration from on-prem SQL Server to Microsoft Fabric OneLake

Skills: PySpark, Python, SQL, Azure, Databricks, dbt, Airflow, Power BI"></textarea>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:1rem">
          <span style="font-size:.78rem;color:var(--slate)">Your data is never stored or shared</span>
          <button class="apply-action" style="width:auto;padding:.75rem 2rem" onclick="runAIAssist()">Generate with AI →</button>
        </div>
      </div>
    </div>
```

Replace with:
```html
    <!-- STEP 1: Pick a resume (or sign in) -->
    <div id="ai-step-1" class="ai-step">
      <div class="modal-body">
        <div class="step-indicator">
          <div class="step-dot active" data-s="1">1</div>
          <div class="step-line"></div>
          <div class="step-dot" data-s="2">2</div>
          <div class="step-line"></div>
          <div class="step-dot" data-s="3">3</div>
          <div class="step-line"></div>
          <div class="step-dot" data-s="4">4</div>
        </div>

        <div id="ai-signin-prompt" style="display:none;text-align:center;padding:2rem 1rem">
          <p style="font-size:.95rem;color:var(--navy);margin-bottom:1.25rem">Sign in to use a saved resume with AI Assist.</p>
          <button class="apply-action" style="width:auto;padding:.75rem 2rem" onclick="closeAIModal();openAuthModal('signin');">Sign in →</button>
        </div>

        <div id="ai-resume-picker-wrap" style="display:none">
          <h3 style="font-size:1.1rem;font-weight:700;color:var(--navy);margin:1.5rem 0 .5rem">Choose a resume</h3>
          <p style="font-size:.875rem;color:#64748B;margin-bottom:1.25rem">The AI will tailor this resume, write a cover letter, and generate interview prep — all specific to this role.</p>
          <div id="ai-resume-picker-list"></div>
          <button style="width:100%;padding:.75rem;border:1px dashed var(--border);border-radius:10px;background:none;cursor:pointer;color:var(--indigo);font-weight:600;font-size:.85rem;margin-top:.75rem" onclick="closeAIModal();openMyResumesModal();">+ Upload a new resume</button>
          <div style="display:flex;justify-content:flex-end;margin-top:1.25rem">
            <button class="apply-action" style="width:auto;padding:.75rem 2rem" id="ai-generate-btn" onclick="runAIAssist()" disabled>Generate with AI →</button>
          </div>
        </div>
      </div>
    </div>
```

- [ ] **Step 2: Modify `openAIAssist()` to gate on auth and load the picker**

Find:
```javascript
function openAIAssist(i) {
  aiJobIndex = i;
  const j = JOBS[i];
  document.getElementById('ai-modal-title').textContent = `Apply to ${j.company} — ${j.title}`;
  showAIStep(1);
  document.getElementById('resume-input').value = '';
  document.getElementById('ai-modal').style.display = 'flex';
  document.getElementById('ai-modal').style.alignItems = 'center';
  document.getElementById('ai-modal').style.justifyContent = 'center';
  document.body.style.overflow = 'hidden';
}
```

Replace with:
```javascript
let selectedResumeId = null;

async function openAIAssist(i) {
  aiJobIndex = i;
  const j = JOBS[i];
  document.getElementById('ai-modal-title').textContent = `Apply to ${j.company} — ${j.title}`;
  showAIStep(1);
  selectedResumeId = null;
  document.getElementById('ai-modal').style.display = 'flex';
  document.getElementById('ai-modal').style.alignItems = 'center';
  document.getElementById('ai-modal').style.justifyContent = 'center';
  document.body.style.overflow = 'hidden';

  const user = await getCurrentUser();
  if (!user) {
    document.getElementById('ai-signin-prompt').style.display = 'block';
    document.getElementById('ai-resume-picker-wrap').style.display = 'none';
    return;
  }
  document.getElementById('ai-signin-prompt').style.display = 'none';
  document.getElementById('ai-resume-picker-wrap').style.display = 'block';
  await loadAIResumePicker();
}

async function loadAIResumePicker() {
  const listEl = document.getElementById('ai-resume-picker-list');
  const genBtn = document.getElementById('ai-generate-btn');
  listEl.innerHTML = '<p style="color:var(--slate);font-size:.85rem">Loading your resumes…</p>';
  const token = await getAuthToken();
  const res = await fetch('/api/resumes', { headers: { Authorization: `Bearer ${token}` } });
  const data = await res.json();

  if (!res.ok || !data.resumes.length) {
    listEl.innerHTML = '<p style="color:var(--slate);font-size:.85rem">No saved resumes yet — upload one to continue.</p>';
    genBtn.disabled = true;
    return;
  }

  listEl.innerHTML = data.resumes.map((r, idx) => `
    <label style="display:flex;align-items:center;gap:.6rem;padding:.75rem 1rem;border:1px solid var(--border);border-radius:10px;margin-bottom:.5rem;cursor:pointer">
      <input type="radio" name="ai-resume-choice" value="${r.id}" ${idx === 0 ? 'checked' : ''} onchange="selectedResumeId='${r.id}';document.getElementById('ai-generate-btn').disabled=false;">
      <div>
        <div style="font-weight:700;font-size:.85rem;color:var(--navy)">${r.label}</div>
        <div style="font-size:.72rem;color:var(--slate)">${r.file_name || 'Pasted text'} · ${new Date(r.created_at).toLocaleDateString()}</div>
      </div>
    </label>
  `).join('');

  selectedResumeId = data.resumes[0].id;
  genBtn.disabled = false;
}
```

- [ ] **Step 3: Modify `runAIAssist()` to send `resumeId`**

Find:
```javascript
async function runAIAssist() {
  const resume = document.getElementById('resume-input').value.trim();
  if (!resume) {
    document.getElementById('resume-input').style.borderColor = '#EF4444';
    document.getElementById('resume-input').placeholder = 'Please paste your resume first…';
    setTimeout(() => {
      document.getElementById('resume-input').style.borderColor = '';
    }, 2000);
    return;
  }

  const j = JOBS[aiJobIndex];
```

Replace with:
```javascript
async function runAIAssist() {
  if (!selectedResumeId) return;
  const j = JOBS[aiJobIndex];
```

Find (a few lines further down, the fetch call body):
```javascript
    const res = await fetch('/api/ai-assist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume,
        job: {
          title: j.title, company: j.company, location: j.location,
          level: j.level, skills: j.skills, stage: j.stage, intel: j.intel,
        },
      }),
    });
```

Replace with:
```javascript
    const token = await getAuthToken();
    const res = await fetch('/api/ai-assist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        resumeId: selectedResumeId,
        job: {
          title: j.title, company: j.company, location: j.location,
          level: j.level, skills: j.skills, stage: j.stage, intel: j.intel,
        },
      }),
    });
```

- [ ] **Step 4: Modify `resetAI()` (drop the now-removed textarea reference)**

Find:
```javascript
function resetAI() {
  showAIStep(1);
  document.getElementById('resume-input').value = '';
}
```

Replace with:
```javascript
function resetAI() {
  showAIStep(1);
}
```

- [ ] **Step 5: Manual test — signed-out state shows sign-in prompt**

1. Sign out (or use a private/incognito window)
2. Click "View & Apply" on any job → "Apply with AI Assist"
3. Expected: Step 1 shows "Sign in to use a saved resume with AI Assist" and a Sign in button, no resume picker

- [ ] **Step 6: Manual test — signed-in full flow with a saved resume**

1. Sign in (an account with at least one saved resume from Task 7's test)
2. Click "Apply with AI Assist" on a job
3. Expected: resume picker shows your saved resume(s), first one pre-selected, "Generate with AI" enabled
4. Click Generate → expected: same loading/results flow as before, using the saved resume's text
5. Verify the generated content reflects the selected resume's actual content (not a different one, if you have multiple)

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "Replace AI Assist paste box with a saved-resume picker, gated on auth"
```

---

### Task 9: Frontend — editable result panels

**Files:**
- Modify: `index.html`
  - CSS for `.result-content` (currently a read-only `<div>`)
  - The 4 result panel elements (lines ~868, 876, 884, 892) — change from `<div>` to `<textarea readonly>`... actually `<textarea>` (editable)
  - `renderResults()` and `copyResult()`

**Interfaces:**
- No new functions — modifies existing `renderResults()` and `copyResult()` behavior only.

- [ ] **Step 1: Update the CSS**

Find:
```css
.result-content{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.25rem;font-size:.875rem;color:var(--navy);line-height:1.8;white-space:pre-wrap;max-height:320px;overflow-y:auto;font-family:'Courier New',monospace}
```

Replace with:
```css
.result-content{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.25rem;font-size:.875rem;color:var(--navy);line-height:1.8;white-space:pre-wrap;max-height:320px;overflow-y:auto;font-family:'Courier New',monospace;width:100%;resize:vertical;min-height:200px}
.result-content:focus{outline:none;border-color:var(--indigo);box-shadow:0 0 0 3px rgba(99,102,241,0.1)}
```

- [ ] **Step 2: Change the 4 result elements from `<div>` to `<textarea>`**

Find each of these 4 lines:
```html
          <div class="result-content" id="result-resume-content"></div>
```
```html
          <div class="result-content" id="result-cover-content"></div>
```
```html
          <div class="result-content" id="result-prep-content"></div>
```
```html
          <div class="result-content" id="result-nego-content"></div>
```

Replace each with the `<textarea>` equivalent (same id, same class):
```html
          <textarea class="result-content" id="result-resume-content"></textarea>
```
```html
          <textarea class="result-content" id="result-cover-content"></textarea>
```
```html
          <textarea class="result-content" id="result-prep-content"></textarea>
```
```html
          <textarea class="result-content" id="result-nego-content"></textarea>
```

- [ ] **Step 3: Update `renderResults()` to use `.value` instead of `.textContent`**

Find:
```javascript
function renderResults(j, result) {
  document.getElementById('result-resume-content').textContent = result.resume;
  document.getElementById('result-cover-content').textContent = result.coverLetter;
  document.getElementById('result-prep-content').textContent = result.interviewPrep;
  document.getElementById('result-nego-content').textContent = result.negotiation;
```

Replace with:
```javascript
function renderResults(j, result) {
  document.getElementById('result-resume-content').value = result.resume;
  document.getElementById('result-cover-content').value = result.coverLetter;
  document.getElementById('result-prep-content').value = result.interviewPrep;
  document.getElementById('result-nego-content').value = result.negotiation;
```

- [ ] **Step 4: Update `copyResult()` to read `.value` (so edits get copied, not the original AI output)**

Find:
```javascript
function copyResult(id) {
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.textContent).then(() => {
```

Replace with:
```javascript
function copyResult(id) {
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.value).then(() => {
```

- [ ] **Step 5: Manual test — edit and copy**

1. Generate AI Assist results for any job (Task 8's flow)
2. Click into the "Tailored Resume" panel, edit some text
3. Click "Copy"
4. Paste into a text editor → expected: your edited text is what got copied, not the original AI output

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "Make AI Assist result panels editable; Copy now copies edited text"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Auth (Task 3) ✓, resume storage original+text (Task 4) ✓, multiple resumes with picker (Tasks 5, 8) ✓, PDF/DOCX/paste (Task 4) ✓, editable results (Task 9) ✓, email confirmation (Supabase Auth default, Task 3) ✓, AI Assist requires login (Task 8) ✓, security/ownership checks (Tasks 4, 5, 6) ✓, Srikanth Sama docx re-test (Task 4, Step 7) ✓.
  - Cross-checked against the spec's 8-item testing plan directly — found and fixed two gaps during self-review: no explicit PDF upload test existed (added Task 4 Step 8), and no test verified saved resumes survive a sign-out/sign-in cycle (added Task 7 Step 6).
  - Cross-user resumeId access on `ai-assist.js` (Task 6) isn't separately tested with a real second account, but reuses byte-identical `.eq("user_id", user.id)` ownership-check logic already verified against a real second account in Task 5 Step 4 — judged sufficient rather than redundant.
- **Placeholder scan:** The only literal placeholder in the plan is `REPLACE_WITH_ANON_KEY` in Task 2 — flagged explicitly as a required live setup step (the actual value doesn't exist until fetched from the Supabase dashboard), not a lazy omission.
- **Type/name consistency verified:** `sb` (client), `getCurrentUser()`, `getAuthToken()`, `getAuthedUser(req)`, `supabaseAdmin`, `selectedResumeId` are each defined once and used with identical names in every consuming task.
