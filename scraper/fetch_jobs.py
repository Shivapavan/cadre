"""
Cadre job scraper — GitHub Actions cron every 30 min
Sources (all public APIs, no auth, no scraping, ToS-compliant):
  • Greenhouse  → 200+ company career portals
  • Lever       → 200+ company career portals
  • Ashby       → 100+ startup career portals
  • Dice RSS    → C2C / H1B / contract roles
Writes to Supabase (upsert — no duplicates, no deleted jobs accumulating)
"""

import json, os, re, sys, hashlib, time, urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from companies import (
    GREENHOUSE_COMPANIES, LEVER_COMPANIES, ASHBY_COMPANIES,
    STAFFING_GREENHOUSE, STAFFING_LEVER, STAFFING_DICE_COMPANIES,
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]   # service_role key
HEADERS_SB   = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",          # upsert behaviour
}

# ── Helpers ──────────────────────────────────────────────────────────────

SKILL_LIST = [
    "Java","Spring Boot","Python","PySpark","Spark","SQL","Databricks","Delta Lake",
    "Azure","AWS","GCP","Kubernetes","Docker","Terraform","Kafka","Airflow","dbt",
    "Snowflake","React","Node.js","TypeScript","Angular","Vue","C++","C","Go",
    "Scala","Kotlin","Swift","Flutter","Rust","SAP","ABAP","Salesforce","MuleSoft",
    "Embedded","RTOS","FPGA","Verilog","SystemVerilog","UVM","AUTOSAR",
    "TensorFlow","PyTorch","LLM","LangChain","RAG","MLflow","OpenAI",
    "Ansible","Jenkins","ArgoCD","Helm","Prometheus","Grafana","Datadog",
    "PostgreSQL","MySQL","MongoDB","Redis","DynamoDB","BigQuery","Redshift",
    "Elasticsearch","Cassandra","ClickHouse","Pinecone","Chroma","Weaviate",
    "JIRA","Agile","Scrum","Power BI","Tableau","Looker","dbt","Fivetran",
]

COMPANY_COLORS = {
    "databricks":"#FF6154","snowflake":"#29B5E8","stripe":"#6772E5",
    "airbnb":"#FF5A5F","openai":"#10A37F","anthropic":"#D4A96A",
    "github":"#333333","gitlab":"#FC6D26","cloudflare":"#F6821F",
    "figma":"#F24E1E","notion":"#000000","vercel":"#000000",
    "coinbase":"#0052FF","brex":"#FF6B35","plaid":"#00D4B1",
    "doordash":"#FF3008","lyft":"#EA0029","uber":"#000000",
    "netflix":"#E50914","reddit":"#FF4500","discord":"#5865F2",
    "palantir":"#1A1A1A","crowdstrike":"#E60000","okta":"#007DC1",
    "shopify":"#96BF48","hubspot":"#FF7A59","intercom":"#1F8DD6",
    "datadog":"#632CA6","confluent":"#CC1F28","hashicorp":"#7B42BC",
    "amplitude":"#1A73E8","segment":"#52BD94","mixpanel":"#7856FF",
    "scale-ai":"#9B59B6","huggingface":"#FF9A00","cohere":"#39594D",
    "rippling":"#F95800","gusto":"#F45D48","lattice":"#6C2ED9",
    "carta":"#3D5AFE","linear":"#5E6AD2","posthog":"#F54E00",
    "supabase":"#3ECF8E","planetscale":"#000000","neon":"#12A594",
    "mercury":"#5A31F4","ramp":"#FF3D00","deel":"#29B473",
}

def color_for(company: str) -> str:
    k = re.sub(r"[^a-z0-9]", "-", company.lower()).strip("-")
    for key, val in COMPANY_COLORS.items():
        if key in k or k in key:
            return val
    # deterministic colour from company name hash
    h = int(hashlib.md5(company.encode()).hexdigest()[:6], 16)
    hue = h % 360
    return f"hsl({hue},60%,45%)"

def letter_for(company: str) -> str:
    return company.strip()[0].upper() if company.strip() else "?"

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()

def extract_skills(text: str) -> list:
    found, lower = [], text.lower()
    for s in SKILL_LIST:
        if s.lower() in lower:
            found.append(s)
        if len(found) >= 6:
            break
    return found or ["Engineering", "APIs", "Cloud"]

def classify_cat(title: str, text: str) -> str:
    t = (title + " " + text).lower()
    if any(x in t for x in ["data engineer","databricks","pyspark","delta lake","airflow","dbt ","snowflake","etl","sap bw","hana","data platform","data pipeline","analytics engineer"]):
        return "data"
    if any(x in t for x in ["machine learning","ml engineer","llm","generative ai","genai","ai engineer","pytorch","tensorflow","nlp","deep learning","computer vision","mlops"]):
        return "ml"
    if any(x in t for x in ["embedded","firmware","fpga","verilog","vlsi","autosar","rtos","arm cortex","microcontroller","bsp","driver"]):
        return "embedded"
    if any(x in t for x in ["devops","platform engineer","sre ","site reliability","kubernetes","terraform","ci/cd","cloud engineer","infrastructure"]):
        return "devops"
    if any(x in t for x in ["react","angular","vue","frontend","front-end","ui developer","javascript developer","typescript developer","next.js"]):
        return "frontend"
    if any(x in t for x in ["ios engineer","android engineer","flutter","react native","mobile engineer","swift developer","kotlin developer"]):
        return "mobile"
    if any(x in t for x in ["security engineer","cybersecurity","devsecops","pen test","soc analyst","detection engineer","appsec","threat"]):
        return "security"
    if any(x in t for x in ["technical program","tpm","product manager","project manager","scrum master","business analyst","engineering manager","engineering lead"]):
        return "pm"
    return "backend"   # default

NON_TECH_TITLE_KEYWORDS = [
    "recruiter", "recruiting", "talent acquisition", "talent partner",
    "hr business partner", "human resources", "people operations", "people partner",
    "sales", "account executive", "account manager", "business development",
    "gtm", "go-to-market", "channel partner", "partnerships manager",
    "customer success", "customer support", "customer service", "support specialist",
    "marketing", "content writer", "copywriter", "social media", "community manager",
    "brand ", "seo specialist", "growth marketer",
    "legal", "counsel", "paralegal", "compliance officer", "compliance analyst", "compliance manager",
    "finance", "accounting", "accountant", "controller", "payroll", "bookkeeper", "treasury",
    "executive assistant", "office manager", "administrative assistant", "receptionist", "facilities",
    "procurement", "supply chain", "logistics coordinator", "warehouse", "retail", "store associate",
    "event coordinator", "event manager", "hospitality", "chef", "esthetician", "stylist",
    "fraud", "disputes", "chargeback",
    "curriculum", "instructor", "teacher", "tutor",
    "physician", "nurse", "clinical", "chaplain", "therapist", "pharmacist",
    "real estate agent", "property manager",
    "mental health", "support worker", "supported living", "care assistant", "care worker",
    "social worker", "youth worker", "healthcare assistant", "home care", "domiciliary care",
    "residential care", "support staff", "care coordinator", "case worker", "caregiver",
]

def is_technical_role(title: str) -> bool:
    t = title.lower()
    return not any(kw in t for kw in NON_TECH_TITLE_KEYWORDS)

def is_senior(title: str) -> bool:
    t = title.lower()
    return any(x in t for x in ["senior","staff","principal","lead","architect","manager","director","head of","vp ","vice president","distinguished"])

def job_id(source: str, company_slug: str, ext_id) -> str:
    return hashlib.sha1(f"{source}:{company_slug}:{ext_id}".encode()).hexdigest()[:20]

def posted_label(dt: datetime) -> str:
    diff = datetime.now(timezone.utc) - dt
    h = int(diff.total_seconds() / 3600)
    if h < 1:   return "Just now"
    if h < 24:  return f"{h}h ago"
    if h < 48:  return "Yesterday"
    return f"{diff.days}d ago"

# ── Supabase upsert ───────────────────────────────────────────────────────

def upsert_jobs(records: list) -> bool:
    if not records:
        return True
    # Dedupe by id — Postgres rejects an upsert batch outright if the same
    # conflict key appears twice in one command ("cannot affect row a second time").
    deduped = list({r["id"]: r for r in records}.values())
    if len(deduped) != len(records):
        print(f"  Deduped {len(records) - len(deduped)} duplicate id(s) before upsert")
    ok = True
    # Supabase REST accepts up to 500 rows per call
    for i in range(0, len(deduped), 400):
        chunk = deduped[i:i+400]
        payload = json.dumps(chunk).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/jobs",
            data=payload,
            headers={**HEADERS_SB, "Prefer": "resolution=merge-duplicates,return=minimal"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                pass
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  Supabase upsert error: {e.code} {body[:300]}")
            ok = False
    return ok

def delete_old_jobs():
    """Remove jobs fetched more than 45 days ago."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/jobs?fetched_at=lt.{urllib.parse.quote(cutoff, safe='')}",
        headers=HEADERS_SB,
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
        print("  Cleaned up old jobs")
    except Exception as e:
        print(f"  Cleanup error: {e}")

# ── Source 1: Greenhouse ──────────────────────────────────────────────────

def fetch_greenhouse() -> list:
    records = []
    now = datetime.now(timezone.utc)
    for slug in GREENHOUSE_COMPANIES:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cadre/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())
        except Exception:
            continue

        company_display = data.get("company", {}).get("name", slug.title())
        for j in data.get("jobs", []):
            title = (j.get("title") or "").strip()
            if not title:
                continue
            loc_name = (j.get("location") or {}).get("name", "") or ""
            desc     = strip_html(j.get("content") or "")[:500]
            skills   = extract_skills(title + " " + desc)
            cat      = classify_cat(title, desc)
            remote   = any(x in loc_name.lower() for x in ["remote","anywhere","distributed"])

            try:
                updated = datetime.fromisoformat(j["updated_at"].replace("Z","+00:00"))
            except Exception:
                updated = now

            records.append({
                "id":           job_id("greenhouse", slug, j.get("id", title)),
                "source":       "greenhouse",
                "emp_type":     "fulltime",
                "cat":          cat,
                "company":      company_display,
                "company_slug": slug,
                "color":        color_for(company_display),
                "letter":       letter_for(company_display),
                "stage":        "Career Portal",
                "title":        title,
                "location":     loc_name or "US",
                "is_remote":    remote,
                "posted_at":    updated.isoformat(),
                "posted_label": posted_label(updated),
                "is_new":       (now - updated).days < 3,
                "tc":           "Competitive",
                "level":        "Senior" if is_senior(title) else "Mid-Senior",
                "yoe":          "5+ years" if is_senior(title) else "3+ years",
                "skills":       skills,
                "visa":         "",
                "description":  desc,
                "apply_url":    j.get("absolute_url", ""),
                "fetched_at":   now.isoformat(),
            })

        time.sleep(0.05)  # gentle rate limit

    print(f"  Greenhouse: {len(records)} jobs from {len(GREENHOUSE_COMPANIES)} companies")
    return records

# ── Source 2: Lever ───────────────────────────────────────────────────────

def fetch_lever() -> list:
    records = []
    now = datetime.now(timezone.utc)
    for slug in LEVER_COMPANIES:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=200"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cadre/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                postings = json.loads(r.read())
        except Exception:
            continue

        if not isinstance(postings, list):
            continue

        for j in postings:
            title = (j.get("text") or "").strip()
            if not title:
                continue
            cats     = j.get("categories") or {}
            loc_name = cats.get("location", "") or cats.get("allLocations", [""])[0] if isinstance(cats.get("allLocations"), list) else ""
            desc     = strip_html(j.get("description") or j.get("descriptionPlain") or "")[:500]
            skills   = extract_skills(title + " " + desc)
            cat      = classify_cat(title, desc)
            remote   = any(x in (loc_name or "").lower() for x in ["remote","anywhere","distributed"])
            company  = slug.replace("-"," ").title()

            try:
                created = datetime.fromtimestamp(j["createdAt"] / 1000, tz=timezone.utc)
            except Exception:
                created = now

            records.append({
                "id":           job_id("lever", slug, j.get("id", title)),
                "source":       "lever",
                "emp_type":     "fulltime",
                "cat":          cat,
                "company":      company,
                "company_slug": slug,
                "color":        color_for(company),
                "letter":       letter_for(company),
                "stage":        "Career Portal",
                "title":        title,
                "location":     loc_name or "US",
                "is_remote":    remote,
                "posted_at":    created.isoformat(),
                "posted_label": posted_label(created),
                "is_new":       (now - created).days < 3,
                "tc":           "Competitive",
                "level":        "Senior" if is_senior(title) else "Mid-Senior",
                "yoe":          "5+ years" if is_senior(title) else "3+ years",
                "skills":       skills,
                "visa":         "",
                "description":  desc,
                "apply_url":    j.get("hostedUrl", ""),
                "fetched_at":   now.isoformat(),
            })

        time.sleep(0.05)

    print(f"  Lever: {len(records)} jobs from {len(LEVER_COMPANIES)} companies")
    return records

# ── Source 3: Ashby ───────────────────────────────────────────────────────

def fetch_ashby() -> list:
    records = []
    now = datetime.now(timezone.utc)
    for slug in ASHBY_COMPANIES:
        url = f"https://api.ashbyhq.com/posting-public/job-board/{slug}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cadre/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())
        except Exception:
            continue

        company = data.get("organizationName", slug.replace("-"," ").title())
        for j in data.get("jobPostings", []):
            title = (j.get("title") or "").strip()
            if not title:
                continue
            loc_name = j.get("locationName", "") or ""
            desc     = strip_html(j.get("descriptionHtml") or j.get("description") or "")[:500]
            skills   = extract_skills(title + " " + desc)
            cat      = classify_cat(title, desc)
            remote   = j.get("isRemote", False) or any(x in loc_name.lower() for x in ["remote","anywhere"])

            try:
                created = datetime.fromisoformat(j["createdAt"].replace("Z","+00:00"))
            except Exception:
                created = now

            records.append({
                "id":           job_id("ashby", slug, j.get("id", title)),
                "source":       "ashby",
                "emp_type":     "fulltime",
                "cat":          cat,
                "company":      company,
                "company_slug": slug,
                "color":        color_for(company),
                "letter":       letter_for(company),
                "stage":        "Career Portal",
                "title":        title,
                "location":     loc_name or "Remote",
                "is_remote":    remote,
                "posted_at":    created.isoformat(),
                "posted_label": posted_label(created),
                "is_new":       (now - created).days < 3,
                "tc":           "Competitive",
                "level":        "Senior" if is_senior(title) else "Mid-Senior",
                "yoe":          "5+ years" if is_senior(title) else "3+ years",
                "skills":       skills,
                "visa":         "",
                "description":  desc,
                "apply_url":    j.get("jobUrl", ""),
                "fetched_at":   now.isoformat(),
            })

        time.sleep(0.05)

    print(f"  Ashby: {len(records)} jobs from {len(ASHBY_COMPANIES)} companies")
    return records

# ── Source 4: Dice RSS (C2C / H1B contract roles) ────────────────────────

# Build per-company Dice searches for staffing firms
def _staffing_dice_searches():
    searches = []
    roles = ["data+engineer","java+developer","python+developer","devops+engineer",
             "react+developer","full+stack","sap+consultant","salesforce+developer",
             "ml+engineer","business+analyst","qa+automation","cloud+engineer"]
    for company in STAFFING_DICE_COMPANIES:
        encoded = company.replace(" ", "+")
        for role in roles[:4]:  # limit per company to avoid too many requests
            searches.append((f"{role}+%22{encoded}%22", "backend", "Corp+to+Corp"))
    return searches

DICE_SEARCHES = [
    ("data+engineer",           "data",     "Corp+to+Corp"),
    ("java+developer",          "backend",  "Corp+to+Corp"),
    ("devops+engineer+aws",     "devops",   "Corp+to+Corp"),
    ("python+developer",        "backend",  "Corp+to+Corp"),
    ("embedded+engineer",       "embedded", "Corp+to+Corp"),
    ("machine+learning+engineer","ml",      "Corp+to+Corp"),
    ("sap+consultant",          "data",     "Corp+to+Corp"),
    ("salesforce+developer",    "backend",  "Corp+to+Corp"),
    ("react+developer",         "frontend", "Corp+to+Corp"),
    ("full+stack+developer",    "backend",  "Corp+to+Corp"),
    ("cloud+architect",         "devops",   "Corp+to+Corp"),
    ("data+analyst",            "data",     "Corp+to+Corp"),
    ("android+developer",       "mobile",   "Corp+to+Corp"),
    ("ios+developer",           "mobile",   "Corp+to+Corp"),
    ("security+engineer",       "security", "Corp+to+Corp"),
    ("qa+automation",           "backend",  "Corp+to+Corp"),
    ("business+analyst",        "pm",       "Corp+to+Corp"),
    ("vlsi+engineer",           "embedded", "Corp+to+Corp"),
    ("network+engineer",        "devops",   "Corp+to+Corp"),
    ("dotnet+developer",        "backend",  "Corp+to+Corp"),
]

def fetch_dice() -> list:
    records = []
    now = datetime.now(timezone.utc)
    for query, cat, emp_type in DICE_SEARCHES:
        url = (f"https://www.dice.com/jobs/rss?q={query}&sc_pref8={emp_type}"
               f"&countryCode=US&page=1&pageSize=20&filters.postedDate=THREE")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cadre/1.0 (job-board)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print(f"  Dice error [{query}]: {e}")
            continue

        channel = root.find("channel")
        if not channel:
            continue
        dice_ns = "http://www.dice.com/rss"

        for item in channel.findall("item")[:15]:
            title_el   = item.find("title")
            link_el    = item.find("link")
            desc_el    = item.find("description")
            date_el    = item.find("pubDate")
            loc_el     = item.find(f"{{{dice_ns}}}location")
            comp_el    = item.find(f"{{{dice_ns}}}company")

            if title_el is None or link_el is None:
                continue

            title   = (title_el.text or "").strip()
            company = (comp_el.text if comp_el is not None else "").strip() or "Staffing Firm"
            loc     = (loc_el.text if loc_el is not None else "").strip() or "US"
            desc    = strip_html(desc_el.text or "")[:400] if desc_el is not None else ""
            link    = (link_el.text or "").strip()
            skills  = extract_skills(title + " " + desc)
            remote  = "remote" in loc.lower() or "remote" in title.lower()

            try:
                from email.utils import parsedate_to_datetime
                posted_dt = parsedate_to_datetime(date_el.text)
            except Exception:
                posted_dt = now

            records.append({
                "id":           job_id("dice", company, title + link[-20:]),
                "source":       "dice",
                "emp_type":     "c2c",
                "cat":          cat,
                "company":      company,
                "company_slug": re.sub(r"[^a-z0-9]", "-", company.lower()),
                "color":        color_for(company),
                "letter":       letter_for(company),
                "stage":        "Dice · C2C / 1099",
                "title":        title,
                "location":     loc,
                "is_remote":    remote,
                "posted_at":    posted_dt.isoformat(),
                "posted_label": posted_label(posted_dt),
                "is_new":       (now - posted_dt).days < 2,
                "tc":           "Market Rate (C2C)",
                "level":        "Senior" if is_senior(title) else "Mid-Senior",
                "yoe":          "5+ years",
                "skills":       skills,
                "visa":         "H1B OK · H4 EAD OK · GC · USC",
                "description":  desc or f"C2C/1099 contract: {title}",
                "apply_url":    link,
                "fetched_at":   now.isoformat(),
            })

    print(f"  Dice C2C: {len(records)} jobs")
    return records

# ── Main ─────────────────────────────────────────────────────────────────

# ── Source 5: Adzuna API ─────────────────────────────────────────────────

ADZUNA_SEARCHES = [
    # (query,                           cat,       what_or)
    ("senior data engineer",            "data"),
    ("senior data engineer contract",   "data"),
    ("java developer senior",           "backend"),
    ("java developer c2c contract",     "backend"),
    ("python backend developer",        "backend"),
    ("senior devops engineer",          "devops"),
    ("cloud engineer aws azure",        "devops"),
    ("senior frontend react typescript","frontend"),
    ("machine learning engineer llm",   "ml"),
    ("mlops engineer pytorch",          "ml"),
    ("embedded software engineer",      "embedded"),
    ("vlsi design engineer",            "embedded"),
    ("security engineer aws",           "security"),
    ("product manager technical",       "pm"),
    ("senior android developer kotlin", "mobile"),
    ("senior ios developer swift",      "mobile"),
    ("salesforce developer contract",   "backend"),
    ("sap abap consultant contract",    "data"),
    ("full stack developer react node", "backend"),
    ("data analyst sql power bi",       "data"),
]

def fetch_adzuna() -> list:
    app_id  = os.environ.get("ADZUNA_APP_ID", "")
    api_key = os.environ.get("ADZUNA_API_KEY", "")
    if not app_id or not api_key:
        print("  Adzuna: skipped (set ADZUNA_APP_ID + ADZUNA_API_KEY secrets)")
        return []

    import urllib.parse
    records = []
    now = datetime.now(timezone.utc)

    for query, cat in ADZUNA_SEARCHES:
        encoded = urllib.parse.quote(query)
        url = (
            f"https://api.adzuna.com/v1/api/jobs/us/search/1"
            f"?app_id={app_id}&app_key={api_key}"
            f"&results_per_page=20&what={encoded}"
            f"&content-type=application/json"
            f"&sort_by=date"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cadre/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
        except Exception as e:
            print(f"  Adzuna error [{query}]: {e}")
            continue

        for j in data.get("results", []):
            title   = (j.get("title") or "").strip()
            company = (j.get("company") or {}).get("display_name", "").strip() or "Employer"
            loc     = (j.get("location") or {}).get("display_name", "").strip() or "US"
            desc    = strip_html(j.get("description") or "")[:400]
            skills  = extract_skills(title + " " + desc)
            remote  = "remote" in loc.lower() or "remote" in title.lower()
            is_c2c  = any(x in (title + desc).lower() for x in ["c2c","corp to corp","1099","contract"])

            try:
                created = datetime.fromisoformat(j["created"].replace("Z","+00:00"))
            except Exception:
                created = now

            records.append({
                "id":           job_id("adzuna", company, j.get("id", title)),
                "source":       "adzuna",
                "emp_type":     "c2c" if is_c2c else "fulltime",
                "cat":          cat,
                "company":      company,
                "company_slug": re.sub(r"[^a-z0-9]","-",company.lower()),
                "color":        color_for(company),
                "letter":       letter_for(company),
                "stage":        "Adzuna · Live Market",
                "title":        title,
                "location":     loc,
                "is_remote":    remote,
                "posted_at":    created.isoformat(),
                "posted_label": posted_label(created),
                "is_new":       (now - created).days < 3,
                "tc":           "Competitive",
                "level":        "Senior" if is_senior(title) else "Mid-Senior",
                "yoe":          "5+ years" if is_senior(title) else "3+ years",
                "skills":       skills,
                "visa":         "H1B OK · H4 EAD OK" if is_c2c else "",
                "description":  desc,
                "apply_url":    j.get("redirect_url", ""),
                "fetched_at":   now.isoformat(),
            })

        time.sleep(0.2)  # Adzuna rate limit

    print(f"  Adzuna: {len(records)} jobs")
    return records


def main():
    ts = datetime.now(timezone.utc).isoformat()
    print(f"\n[{ts}] Starting Cadre job fetch...")

    all_records = []

    # Tech company career portals via ATS APIs
    all_records.extend(fetch_greenhouse())
    all_records.extend(fetch_lever())
    all_records.extend(fetch_ashby())

    # Staffing firms via their own portals (Greenhouse + Lever)
    print("  Fetching staffing firm portals...")
    staffing_gh_records = []
    for slug in STAFFING_GREENHOUSE:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Cadre/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            company = data.get("company", {}).get("name", slug.title())
            for j in data.get("jobs", []):
                title = (j.get("title") or "").strip()
                if not title: continue
                loc   = (j.get("location") or {}).get("name", "US")
                desc  = strip_html(j.get("content") or "")[:400]
                now   = datetime.now(timezone.utc)
                try:
                    updated = datetime.fromisoformat(j["updated_at"].replace("Z","+00:00"))
                except Exception:
                    updated = now
                staffing_gh_records.append({
                    "id": job_id("greenhouse", slug, j.get("id", title)),
                    "source":"greenhouse","emp_type":"c2c",
                    "cat": classify_cat(title, desc),
                    "company":company,"company_slug":slug,
                    "color":color_for(company),"letter":letter_for(company),
                    "stage":"Staffing · C2C / W2",
                    "title":title,"location":loc,
                    "is_remote":"remote" in loc.lower() or "remote" in title.lower(),
                    "posted_at":updated.isoformat(),"posted_label":posted_label(updated),
                    "is_new":(now-updated).days < 3,
                    "tc":"Market Rate","level":"Senior" if is_senior(title) else "Mid",
                    "yoe":"5+ years" if is_senior(title) else "3+ years",
                    "skills":extract_skills(title+" "+desc),
                    "visa":"H1B OK · H4 EAD OK · GC · USC",
                    "description":desc,"apply_url":j.get("absolute_url",""),
                    "fetched_at":now.isoformat(),
                })
            time.sleep(0.05)
        except Exception:
            continue
    print(f"  Staffing Greenhouse: {len(staffing_gh_records)} jobs")
    all_records.extend(staffing_gh_records)

    # C2C roles from Dice (generic searches + per-staffing-firm searches)
    all_records.extend(fetch_dice())

    # Adzuna live market jobs (optional — skipped if env vars not set)
    all_records.extend(fetch_adzuna())

    before = len(all_records)
    all_records = [r for r in all_records if is_technical_role(r["title"])]
    print(f"  Filtered out {before - len(all_records)} non-technical roles")

    print(f"\nTotal records collected: {len(all_records)}")
    print("Upserting to Supabase...")
    ok = upsert_jobs(all_records)
    delete_old_jobs()
    if not ok:
        print(f"FAILED. Upsert error(s) above — jobs may not have been written.")
        sys.exit(1)
    print(f"Done. {len(all_records)} jobs in DB.")

if __name__ == "__main__":
    main()
