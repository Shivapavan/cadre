# ── Top staffing / consulting firms that post C2C / 1099 / H1B roles ──
# These companies post directly on their own career portals AND on Dice/Indeed
# We hit their Greenhouse/Lever portals for direct job listings
STAFFING_GREENHOUSE = [
    "insightglobal", "teksystems", "cognizant", "infosys", "wipro",
    "hcltech", "ltimindtree", "tcs", "capgemini", "accenture",
    "ibm", "deloitte", "kforce", "spherion", "adecco",
    "manpowergroup", "randstad", "robert-half", "kelly-services",
    "ciber", "sapient", "publicissapient", "nttdata",
    "dxc", "unisys", "cgi", "slalom", "boozallen",
    "leidos", "saic", "caci", "mps-group", "volt",
    "mastech", "igate", "cyient", "hexaware", "mphasis",
    "sonata-software", "birlasoft", "zensar", "niit-tech",
]

STAFFING_LEVER = [
    "apex-systems", "teksystems", "insight-global", "turnberry-solutions",
    "meridian-technologies", "belcan", "alten", "modis",
    "bsquare", "lancesoft", "world-wide-technology", "wwt",
    "perficient", "sparkhound", "ness-digital",
    "pythian", "coda-global", "virtusa", "trigent",
]

# Dice RSS C2C searches — company-specific queries
STAFFING_DICE_COMPANIES = [
    "Insight Global", "TEKsystems", "Meridian Technologies",
    "Turnberry Solutions", "Apex Systems", "Cognizant", "Infosys",
    "Wipro", "TCS", "HCLTech", "LTIMindtree", "Capgemini",
    "Accenture", "IBM", "Deloitte", "NTT Data", "DXC Technology",
    "Mastech", "iGate", "Kforce", "Spherion", "Robert Half",
    "Randstad", "ManpowerGroup", "Volt Information Sciences",
    "Belcan", "Modis", "Alten", "Perficient", "Slalom",
    "World Wide Technology", "Leidos", "SAIC", "CACI",
    "Booz Allen Hamilton", "Sapient", "Publicis Sapient",
    "Hexaware", "Mphasis", "Birlasoft", "Zensar", "Cyient",
    "Virtusa", "Lancesoft", "Trigent", "Pythian",
]

# Company career portal slugs by ATS platform
# Greenhouse, Lever, Ashby all expose PUBLIC APIs — no auth needed
# These are the actual slugs used in their APIs

GREENHOUSE_COMPANIES = [
    # ── Data / Cloud / AI ──
    "databricks", "snowflake", "dbtlabs", "fivetran", "airbyte", "starburst",
    "astronomer", "prefect", "montecarladata", "greathexpectations", "datafold",
    "atscale", "imply", "lightdash", "metabase", "preset", "thoughtspot",
    "alation", "collibra", "atlan", "selectstar", "stemma",
    # ── Fintech ──
    "stripe", "brex", "plaid", "robinhood", "coinbase", "gemini",
    "chime", "marqeta", "payoneer", "adyen", "checkout", "ramp",
    "mercury", "deel", "rippling", "gusto", "lattice", "carta",
    "equityzen", "forge", "vise", "altruist", "apex",
    # ── Consumer / Social ──
    "airbnb", "doordash", "instacart", "lyft", "bird", "lime",
    "reddit", "pinterest", "discord", "roblox", "unity",
    "peloton", "strava", "duolingo", "coursera", "masterclass",
    "calm", "headspace", "bumble", "hinge",
    # ── Enterprise SaaS ──
    "figma", "notion", "airtable", "miro", "loom", "pitch",
    "linear", "clickup", "asana", "monday", "lattice",
    "glean", "guru", "confluence", "lucid", "mural",
    "hubspot", "intercom", "drift", "outreach", "salesloft",
    "gong", "chorus", "clari", "seismic", "highspot",
    "workato", "tray", "zapier", "make",
    # ── Security ──
    "crowdstrike", "paloaltonetworks", "sentinelone", "okta", "zscaler",
    "lacework", "orca", "wiz", "snyk", "veracode",
    "qualys", "tenable", "rapid7", "darktrace", "cyberark",
    "beyondtrust", "sailpoint", "saviynt", "ping", "jumpcloud",
    # ── Infrastructure / DevOps ──
    "hashicorp", "confluent", "cockroachlabs", "planetscale",
    "neon", "supabase", "railway", "render",
    "datadog", "honeycomb", "newrelic", "dynatrace", "appdynamics",
    "grafana", "chronosphere", "lightstep", "splitio",
    "launchdarkly", "statsig", "growthbook",
    # ── Healthcare / Biotech ──
    "oscarhealth", "devoted", "cityblock", "hinge", "virta",
    "modernhealth", "springhealth", "lyrahealth", "cerebral",
    "tempus", "flatiron", "veeva", "benchling", "ginkgobioworks",
    # ── Embedded / Hardware ──
    "anduril", "palantir", "shield", "skydio", "joby",
    "rivian", "lucidmotors", "canoo", "waymo",
    # ── E-commerce / Retail ──
    "shopify", "affirm", "klarna", "afterpay", "sezzle",
    "faire", "returnly", "loop", "gorgias",
    # ── Media / Gaming ──
    "netflix", "hulu", "peacock", "paramount",
    "epicgames", "ea", "2k", "zynga", "scopely",
    # ── Real Estate / PropTech ──
    "opendoor", "offerpad", "compass", "keller", "redfin",
    # ── HR / Recruiting ──
    "greenhouse", "lever", "ashby", "jobvite", "icims",
    "workday", "successfactors", "bamboohr", "hibob",
    # ── Misc High-Growth ──
    "canva", "procore", "toast", "squarespace", "wix",
    "godaddy", "automattic", "mailchimp", "klaviyo",
    "attentive", "iterable", "sendgrid", "postmark",
    "twilio", "bandwidth", "vonage", "daily",
    "zoom", "ringcentral", "8x8", "dialpad",
    "dropbox", "box", "egnyte", "druva",
    "vmware", "nutanix", "pure", "netapp",
]

LEVER_COMPANIES = [
    # ── Dev Tools / Open Source ──
    "github", "gitlab", "netlify", "cloudflare", "fastly",
    "vercel", "fly", "deno", "buf", "earthly",
    "sourcegraph", "codeium", "tabnine", "replit",
    "gitpod", "codespaces", "codesandbox",
    # ── Analytics / Data ──
    "amplitude", "segment", "mixpanel", "heap", "fullstory",
    "contentsquare", "hotjar", "userpilot",
    "looker", "sisense", "periscope", "chartio",
    "rockset", "imply", "pinot", "druid",
    "great-expectations", "monte-carlo",
    # ── AI / ML ──
    "openai", "anthropic", "cohere", "ai21", "huggingface",
    "scale-ai", "labelbox", "aquarium", "weights-biases",
    "determined-ai", "cerebras", "groq", "together",
    "perplexity", "character-ai", "inflection",
    "midjourney", "stability", "runway",
    # ── Productivity / Collaboration ──
    "notion", "coda", "roam", "obsidian",
    "loom", "mmhmm", "otter", "fireflies",
    "calendly", "doodle", "cal",
    "zapier", "make", "n8n", "activepieces",
    # ── Fintech ──
    "braintrust", "justworks", "rippling", "remote",
    "pilot", "bench", "quickbooks", "freshbooks",
    "bill", "tipalti", "melio", "plastiq",
    "stripe", "checkout", "recurly", "chargebee",
    # ── Security ──
    "1password", "bitwarden", "dashlane", "lastpass",
    "vanta", "drata", "secureframe", "tugboat",
    "normalyze", "ermetic", "dig-security",
    # ── HR / People Ops ──
    "culture-amp", "leapsome", "15five", "reflektive",
    "betterworks", "small-improvements",
    "greenhouse", "pave", "levels", "radford",
    # ── Healthcare ──
    "ro", "hims", "noom", "bay-area-health",
    "everlywell", "lab-corp", "quest",
    "woebot", "talkspace", "betterhelp",
    # ── E-commerce ──
    "faire", "gorgias", "yotpo", "okendo",
    "stamped", "loyaltylion", "referralcandy",
    "shipbob", "shipstation", "easypost",
    # ── Climate / Energy ──
    "arcadia", "octopus-energy", "stem", "enphase",
    "sunrun", "sunnova", "solar-winds",
    "aurora-solar", "opensolar", "helioscope",
    # ── Real Estate ──
    "bungalow", "updated", "homelight", "orchard",
    "knock", "flyhomes", "reali",
    # ── EdTech ──
    "brainly", "chegg", "varsity-tutors", "preply",
    "codecademy", "treehouse", "pluralsight",
    "brilliant", "khan-academy", "outschool",
    # ── Logistics ──
    "flexport", "freightos", "convoy", "transfix",
    "project44", "fourkites", "descartes",
    # ── Misc ──
    "carvana", "vroom", "shift", "carmax",
    "thumbtack", "angi", "taskrabbit",
    "fiverr", "upwork", "toptal", "braintrust",
]

ASHBY_COMPANIES = [
    # ── Dev Tools / Infra (Ashby is popular with Series A-C startups) ──
    "linear", "vercel", "railway", "supabase", "neon",
    "planetscale", "turso", "xata", "convex", "liveblocks",
    "inngest", "trigger", "temporal", "windmill",
    "posthog", "june", "hyperping", "checkly",
    "sentry", "highlight", "baselime", "axiom",
    "clerk", "stytch", "magic", "privy",
    "resend", "loops", "customer-io", "engage",
    # ── AI Startups ──
    "mistral", "together", "anyscale", "modal",
    "replicate", "banana", "beam", "lepton",
    "dust", "langchain", "llamaindex", "fixie",
    "mem", "reflect", "notion-ai", "lex",
    "jasper", "copy-ai", "writer", "anyword",
    # ── Fintech ──
    "mercury", "brex", "ramp", "puzzle",
    "karat", "lithic", "increase", "column",
    "unit", "bond", "treasury-prime", "synctera",
    # ── Healthcare ──
    "elation", "athenahealth", "canvas-medical",
    "commure", "particle-health", "redox",
    # ── Climate ──
    "watershed", "patch", "pachama", "terrawatch",
    "bright-machines", "veo-robotics",
    # ── Misc ──
    "deel", "remote", "oyster", "papaya",
    "captions", "descript", "opus-clip",
    "beehiiv", "ghost", "substack", "convertkit",
    "circle", "kajabi", "podia", "thinkific",
    "cal", "savvycal", "reclaim", "clockwise",
]
