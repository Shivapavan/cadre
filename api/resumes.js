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
