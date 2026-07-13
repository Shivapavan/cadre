const { createClient } = require("@supabase/supabase-js");

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") return res.status(200).end();

  const {
    cat    = "all",
    emp    = "all",
    search = "",
    page   = "1",
    limit  = "24",
  } = req.query;

  const pageNum  = Math.max(1, parseInt(page)  || 1);
  const limitNum = Math.min(100, parseInt(limit) || 24);
  const from     = (pageNum - 1) * limitNum;
  const to       = from + limitNum - 1;

  let query = supabase
    .from("jobs")
    .select("*", { count: "exact" })
    .order("posted_at", { ascending: false })
    .range(from, to);

  // Category filter
  if (cat && cat !== "all") {
    query = query.eq("cat", cat);
  }

  // Employment type filter
  if (emp && emp !== "all") {
    if (emp === "remote") {
      query = query.eq("is_remote", true);
    } else {
      query = query.eq("emp_type", emp);
    }
  }

  // Full-text search across title, company, description
  if (search && search.trim()) {
    const term = search.trim().replace(/[%_]/g, "\\$&");
    query = query.or(
      `title.ilike.%${term}%,company.ilike.%${term}%,description.ilike.%${term}%`
    );
  }

  const { data, error, count } = await query;

  if (error) {
    console.error("Supabase error:", error);
    return res.status(500).json({ error: "Failed to fetch jobs" });
  }

  // Cache for 60s, allow stale for 5 min
  res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=300");
  res.status(200).json({
    jobs:       data || [],
    total:      count || 0,
    page:       pageNum,
    limit:      limitNum,
    totalPages: Math.ceil((count || 0) / limitNum),
  });
};
