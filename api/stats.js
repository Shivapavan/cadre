const { createClient } = require("@supabase/supabase-js");

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  const [{ count: total }, { count: c2c }, { count: remote }, { count: newToday }] =
    await Promise.all([
      supabase.from("jobs").select("*", { count: "exact", head: true }),
      supabase.from("jobs").select("*", { count: "exact", head: true }).eq("emp_type", "c2c"),
      supabase.from("jobs").select("*", { count: "exact", head: true }).eq("is_remote", true),
      supabase.from("jobs").select("*", { count: "exact", head: true }).eq("is_new", true),
    ]);

  res.setHeader("Cache-Control", "s-maxage=120, stale-while-revalidate=600");
  res.status(200).json({ total, c2c, remote, newToday });
};
