"""
llm/resume_tailor.py
Uses Claude (Anthropic) to tailor Kate's master resume for each job posting.

Budget-smart hybrid split:
  Scoring:   claude-haiku-4-5  – fast & cheap  (~$0.001 per job)
  Tailoring: claude-sonnet-4-6 – quality output (~$0.033 per job)

At 3 jobs/day this stretches $5 credit to roughly 6-8 weeks.
"""
import logging
import json
import anthropic
from config.settings import ANTHROPIC_API_KEY, MASTER_RESUME_PATH, GENERATED_DIR, APPLICANT

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Load master resume once at import time ─────────────────────────────────────
def _load_master_resume() -> str:
    """Load the master resume as plain text."""
    try:
        from docx import Document
        doc = Document(MASTER_RESUME_PATH)
        return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    except Exception as e:
        logger.error(f"Failed to load master resume: {e}")
        return ""


MASTER_RESUME_TEXT = _load_master_resume()


# ── Prompts ────────────────────────────────────────────────────────────────────
TAILOR_PROMPT = """You are an expert resume writer helping {name} apply for a job.

MASTER RESUME:
{resume}

JOB POSTING:
Title: {title}
Company: {company}
Description:
{description}

TASK:
Rewrite the resume to be tailored for this specific role. Rules:
1. Keep all facts accurate – do NOT invent experience or skills
2. Reorder bullet points so the most relevant ones come first
3. Adjust the profile summary (2-3 sentences) to match this role's language and requirements
4. Emphasize keywords that appear in the job description when they match Kate's experience
5. Keep the same overall structure and format
6. Target length: same as the original (do not cut major sections)

Return ONLY the rewritten resume text. No preamble, no commentary."""


MATCH_SCORE_PROMPT = """You are a recruiter. Rate how well this candidate's background matches this job posting on a scale of 0-100.

CANDIDATE: {name}
BACKGROUND SUMMARY: {summary}

JOB:
Title: {title}
Company: {company}
Description: {description}

Return ONLY a JSON object with this exact structure:
{{"score": 85, "reason": "Strong match because...", "gaps": ["Missing X", "Would need Y"]}}"""


ESSAY_PROMPT = """You are helping {name} write answers to job application essay questions.

CANDIDATE BACKGROUND:
{resume}

JOB:
Title: {title}
Company: {company}

ESSAY QUESTION: {question}

Write a compelling, specific answer (2-4 sentences) drawing from the candidate's real experience.
Be authentic, concrete, and tailored to this company specifically.
Return ONLY the answer text."""


# ── Public functions ───────────────────────────────────────────────────────────
def tailor_resume(job: dict) -> str:
    """Generate a tailored resume for a job posting using claude-sonnet-4-6."""
    if not MASTER_RESUME_TEXT:
        logger.error("Master resume not loaded – cannot tailor.")
        return ""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": TAILOR_PROMPT.format(
                    name=APPLICANT["name"],
                    resume=MASTER_RESUME_TEXT,
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    description=job.get("description", "")[:3000],
                )
            }],
        )
        tailored = response.content[0].text.strip()
        logger.info(f"Tailored resume for {job.get('title')} at {job.get('company')}")
        return tailored

    except Exception as e:
        logger.error(f"Failed to tailor resume: {e}")
        return MASTER_RESUME_TEXT  # Fall back to master resume if tailoring fails


def score_match(job: dict) -> tuple[int, str, list]:
    """Score how well Kate matches a job posting. Returns (score, reason, gaps).
    Uses claude-haiku-4-5 for speed and cost savings."""
    summary = MASTER_RESUME_TEXT[:1000] if MASTER_RESUME_TEXT else ""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": MATCH_SCORE_PROMPT.format(
                    name=APPLICANT["name"],
                    summary=summary,
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    description=job.get("description", "")[:2000],
                )
            }],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if Claude wraps in ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return data.get("score", 50), data.get("reason", ""), data.get("gaps", [])

    except Exception as e:
        logger.error(f"Failed to score match: {e}")
        return 50, "Scoring failed", []


def generate_essay_answer(question: str, job: dict) -> str:
    """Generate an essay answer for a custom application question using claude-sonnet-4-6."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": ESSAY_PROMPT.format(
                    name=APPLICANT["name"],
                    resume=MASTER_RESUME_TEXT[:2000],
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    question=question,
                )
            }],
        )
        return response.content[0].text.strip()

    except Exception as e:
        logger.error(f"Failed to generate essay answer: {e}")
        return ""
