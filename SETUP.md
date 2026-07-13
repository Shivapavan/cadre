# Cadre — Go-Live Setup Checklist

Everything is built. You just need to wire up the infrastructure.
Complete these 6 steps in order and cadre-jobs.vercel.app will show real live jobs.

---

## Step 1 — Create Supabase Project

1. Go to https://supabase.com and sign in
2. Click **New Project** → give it any name (e.g. `cadre-jobs`)
3. Choose a region close to you → click **Create**
4. Wait ~2 min for it to provision
5. Go to **SQL Editor** (left sidebar)
6. Open the file `database/schema.sql` from this project folder
7. Paste the entire contents into the SQL editor → click **Run**
8. Go to **Settings → API** and copy:
   - **Project URL** (looks like `https://xxxx.supabase.co`) → save this
   - **service_role** key (under "Project API keys") → save this

---

## Step 2 — Push Code to GitHub

Run these commands in your terminal:

```bash
cd /Users/shiva/claude_projects/Cadre

git init
git add .
git commit -m "Initial Cadre build"
git remote add origin https://github.com/Shivapavan/cadre.git
git push -u origin main
```

> Make sure the repo `Shivapavan/cadre` exists on GitHub first.
> Create it at https://github.com/new (set to Public, no README)

---

## Step 3 — Add GitHub Actions Secrets

1. Go to your repo on GitHub: https://github.com/Shivapavan/cadre
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret** for each of these:

| Secret Name           | Value                                      |
|-----------------------|--------------------------------------------|
| `SUPABASE_URL`        | Your Project URL from Step 1               |
| `SUPABASE_SERVICE_KEY`| Your service_role key from Step 1          |
| `ADZUNA_APP_ID`       | Your Adzuna App ID (from Step 6 below)     |
| `ADZUNA_API_KEY`      | Your Adzuna API key (from Step 6 below)    |

> Adzuna secrets can be added later — the scraper skips them if not set.

---

## Step 4 — Add Vercel Environment Variables

1. Go to https://vercel.com → open your `cadre-jobs` project
2. Click **Settings → Environment Variables**
3. Add these (select all environments: Production, Preview, Development):

| Variable Name         | Value                                      |
|-----------------------|--------------------------------------------|
| `SUPABASE_URL`        | Your Project URL from Step 1               |
| `SUPABASE_SERVICE_KEY`| Your service_role key from Step 1          |
| `ADZUNA_APP_ID`       | Your Adzuna App ID                         |
| `ADZUNA_API_KEY`      | Your Adzuna API key                        |

4. Click **Save** after each one
5. Go to **Deployments** → click **Redeploy** on the latest deployment

---

## Step 5 — Seed the Database (First Run)

1. Go to https://github.com/Shivapavan/cadre/actions
2. Click **Fetch Live Jobs** workflow
3. Click **Run workflow → Run workflow**
4. Wait ~5 min for it to complete
5. Check Supabase → **Table Editor → jobs** to confirm rows are appearing

After this, the cron runs automatically every 30 minutes.

---

## Step 6 — Adzuna API Key (Optional but Recommended)

Adzuna adds 400+ additional live market jobs per run.

1. Go to https://developer.adzuna.com/signup
2. Create a free account
3. Go to **Dashboard → API Access Details**
4. Copy your **App ID** and **API Key**
5. Add them as secrets in Step 3 and env vars in Step 4

---

## What's Already Built

| File / Folder                          | What it does                                      |
|----------------------------------------|---------------------------------------------------|
| `index.html`                           | Full job board UI (filters, C2C badges, AI Assist)|
| `api/jobs.js`                          | Vercel API — queries Supabase with filters + pagination |
| `api/stats.js`                         | Vercel API — returns total/c2c/remote counts      |
| `database/schema.sql`                  | Supabase table, indexes, RLS policies             |
| `scraper/fetch_jobs.py`                | Fetches jobs from all sources → upserts to Supabase |
| `scraper/companies.py`                 | 300+ Greenhouse/Lever/Ashby company slugs + 50+ staffing firms |
| `.github/workflows/fetch-jobs.yml`     | GitHub Actions cron (every 30 min)                |
| `package.json` + `vercel.json`         | Vercel function config                            |

### Job Sources (all legal, public APIs)
- **Greenhouse** — 200+ tech companies (Databricks, Snowflake, Stripe, Airbnb, Figma, Coinbase...)
- **Lever** — 200+ companies (GitHub, Cloudflare, OpenAI, Anthropic...)
- **Ashby** — 100+ startups (Linear, Vercel, Supabase, PostHog...)
- **Staffing firms** — Insight Global, TEKsystems, Cognizant, Infosys, Wipro, TCS, HCLTech, LTIMindtree, Capgemini, Mastech, Accenture, IBM, Deloitte, Kforce, Randstad, Booz Allen, NTT Data, DXC, Apex Systems, Turnberry Solutions, Meridian Technologies + 20 more
- **Dice RSS** — C2C / H1B / 1099 contract roles
- **Adzuna API** — 400+ additional live market jobs (needs API key)

---

## Live URL

https://cadre-jobs.vercel.app
