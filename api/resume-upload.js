// api/resume-upload.js
const pdfParse = require("pdf-parse");
const JSZip = require("jszip");
const { supabaseAdmin, getAuthedUser } = require("../lib/supabaseAdmin");

const MAX_FILE_BYTES = 3 * 1024 * 1024; // 3MB raw, matches Global Constraints

function decodeXmlEntities(s) {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

// Word XML mixes visible text (<w:t> runs) with structural/positioning
// metadata (DrawingML image anchors, textbox coordinates, etc.) that also
// has plain-text content ("right", "285529"). Extracting only <w:t> runs
// avoids pulling that metadata in, and joining runs with no separator
// avoids splitting words Word stored across adjacent runs (e.g. spell-check
// commonly splits a surname into two runs with no space between them).
function extractRunText(xml) {
  const tokenRe = /<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>|<w:tab\s*\/?>|<w:br\s*\/?>|<\/w:p>/g;
  let result = "";
  let match;
  while ((match = tokenRe.exec(xml)) !== null) {
    const token = match[0];
    if (token.startsWith("<w:t")) {
      result += decodeXmlEntities(match[1]);
    } else if (token.startsWith("<w:tab")) {
      result += "\t";
    } else if (token.startsWith("<w:br")) {
      result += "\n";
    } else {
      result += "\n"; // </w:p>
    }
  }
  return result;
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
      parts.push(extractRunText(await zip.files[name].async("string")));
    }
  }
  if (zip.files["word/document.xml"]) {
    parts.push(extractRunText(await zip.files["word/document.xml"].async("string")));
  }
  for (const name of fileNames) {
    if (/^word\/footer\d*\.xml$/.test(name)) {
      parts.push(extractRunText(await zip.files[name].async("string")));
    }
  }

  return parts
    .join("\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
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
