// AI Assist — generates a tailored resume, cover letter, interview prep, and
// negotiation guide from a candidate's saved resume + job posting. Tries
// Anthropic first, falls back to OpenAI if the primary call fails or its key
// isn't configured.

const { supabaseAdmin, getAuthedUser } = require("../lib/supabaseAdmin");

const RESULT_SCHEMA = {
  name: "tailored_application_materials",
  description: "Tailored resume, cover letter, interview prep, and negotiation guide for this job",
  input_schema: {
    type: "object",
    properties: {
      resume: {
        type: "string",
        description:
          "Plain-text tailored resume highlights. Must pull REAL bullets/achievements from the candidate's actual pasted resume (reworded/reordered for relevance) — never invent experience they didn't provide. Include a SUMMARY, KEY ACHIEVEMENTS (3-4 real bullets from their resume, most relevant first), and SKILLS TO LEAD WITH.",
      },
      coverLetter: {
        type: "string",
        description:
          "A complete, ready-to-send cover letter referencing specific real details from the candidate's resume and the job posting. No placeholder brackets.",
      },
      interviewPrep: {
        type: "string",
        description:
          "3-4 likely technical/behavioral questions for this specific role with guidance on how to answer, referencing the candidate's actual background where relevant.",
      },
      negotiation: {
        type: "string",
        description:
          "Practical negotiation guidance for this role/level/company: market TC context, what to ask for, and 1-2 example phrasings.",
      },
    },
    required: ["resume", "coverLetter", "interviewPrep", "negotiation"],
  },
};

function buildPrompt(resume, job) {
  return `You are a career coach helping a candidate apply to a specific job. Use ONLY real information from the resume they pasted below — never fabricate experience, employers, or metrics they didn't mention. If their resume lacks a strong quantified bullet for something, say so plainly rather than inventing one.

CANDIDATE'S RESUME (pasted as-is):
"""
${resume.slice(0, 6000)}
"""

JOB THEY'RE APPLYING TO:
Title: ${job.title}
Company: ${job.company}
Location: ${job.location || "US"}
Level: ${job.level || "Mid-Senior"}
Required skills: ${(job.skills || []).join(", ")}
Company stage/context: ${job.stage || ""}
${job.intel ? `Company intel: ${job.intel}` : ""}

Produce tailored application materials using the tool provided.`;
}

async function callAnthropic(resume, job) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error("ANTHROPIC_API_KEY not configured");

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 2000,
      tools: [RESULT_SCHEMA],
      tool_choice: { type: "tool", name: RESULT_SCHEMA.name },
      messages: [{ role: "user", content: buildPrompt(resume, job) }],
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Anthropic ${res.status}: ${body.slice(0, 300)}`);
  }

  const data = await res.json();
  const toolUse = (data.content || []).find((c) => c.type === "tool_use");
  if (!toolUse) throw new Error("Anthropic response had no tool_use block");
  return toolUse.input;
}

async function callOpenAI(resume, job) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error("OPENAI_API_KEY not configured");

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      response_format: { type: "json_object" },
      max_tokens: 2000,
      messages: [
        {
          role: "system",
          content:
            'Respond with a single JSON object with exactly these string keys: "resume", "coverLetter", "interviewPrep", "negotiation". No other text.',
        },
        { role: "user", content: buildPrompt(resume, job) },
      ],
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`OpenAI ${res.status}: ${body.slice(0, 300)}`);
  }

  const data = await res.json();
  const text = data.choices?.[0]?.message?.content;
  if (!text) throw new Error("OpenAI response had no content");
  return JSON.parse(text);
}

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

  let result, provider;
  try {
    result = await callAnthropic(resume, job);
    provider = "anthropic";
  } catch (anthropicErr) {
    console.error("Anthropic failed, trying OpenAI:", anthropicErr.message);
    try {
      result = await callOpenAI(resume, job);
      provider = "openai";
    } catch (openaiErr) {
      console.error("OpenAI also failed:", openaiErr.message);
      return res.status(502).json({
        error: "Both AI providers failed",
        details: { anthropic: anthropicErr.message, openai: openaiErr.message },
      });
    }
  }

  res.status(200).json({ ...result, provider });
};
