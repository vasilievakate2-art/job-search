# 🤖 Job Hunt Agent

An AI-powered job search agent that runs 24/7 — scrapes job boards, scores matches against your resume, tailors a custom resume for every role using Claude AI, and sends you a daily Slack summary. You review and approve applications from a web dashboard.

**Free to run.** Uses free-tier APIs for scraping and Claude's $5 sign-up credit covers ~150 tailored resumes.

---

## How it works

```
Every 2 hours:
  1. Scrape → Indeed, Wellfound, LinkedIn, Remotive, RemoteOK
  2. Score   → Claude Haiku rates each job against your resume (0–100)
  3. Save    → Jobs scoring ≥ 30 are saved to the database
  4. Tailor  → Claude Sonnet writes a custom resume for every saved job

Every morning at 10 AM (Pacific):
  5. Report  → Slack message with top new matches and dashboard link

You (whenever):
  6. Review  → Open dashboard, read the tailored resume, approve or skip
```

---

## Features

- **5 job sources** — Indeed, Wellfound, LinkedIn, Remotive (free), RemoteOK (free)
- **AI scoring** — Claude Haiku rates every job against your resume in seconds
- **Resume tailoring** — Claude Sonnet rewrites your resume for each specific role
- **Web dashboard** — review jobs side-by-side with the tailored resume, edit, approve
- **PDF download** — download the tailored resume as a formatted PDF
- **Essay answers** — auto-generate answers to custom application questions
- **Daily Slack report** — morning summary with top matches and stats
- **Salary & work-type filters** — remote $110k+, on-site $120k+, configurable
- **Deploy to Railway** — runs 24/7 in the cloud for ~$5/month

---

## Requirements

### API Keys you need

| Service | Purpose | Cost | Sign-up link |
|---------|---------|------|-------------|
| **Anthropic** | Resume tailoring + scoring | Free $5 credit, then ~$3–5/month | [console.anthropic.com](https://console.anthropic.com) |
| **Apify** | Indeed + Wellfound scraping | Free ~500 runs/month | [console.apify.com](https://console.apify.com) |
| **RapidAPI** | LinkedIn scraping | Free 200 req/month | [rapidapi.com](https://rapidapi.com) → search "JSearch" |
| **Slack** | Daily job report | Free | [api.slack.com/apps](https://api.slack.com/apps) |

> **Remotive and RemoteOK** are completely free — no API key needed. They run every cycle regardless of other quotas.

### Software requirements

- Python 3.11 or 3.12
- pip
- Git

---

## Setup (local)

### 1. Clone the repo

```bash
git clone https://github.com/vasilievakate2-art/job-search.git
cd job-search
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Mac / Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 3. Add your resume

Place your resume (as a `.docx` Word file) in the `data/` folder and name it `resume.docx`:

```
data/resume.docx
```

> Your resume is the foundation — Claude reads it to score job matches and tailor each application. The more detailed it is, the better the results.

### 4. Configure your environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in every value. See the section below for how to get each key.

### 5. Customize your job search

Open `config/settings.py` and edit:

```python
TARGET_TITLES = [
    "Content Marketing Manager",
    "Head of Marketing",
    "Brand Strategist",
    # add your own titles here
]

SALARY_MIN        = 110_000   # Minimum for remote roles
SALARY_MIN_ONSITE = 120_000   # Minimum for hybrid / on-site
SALARY_IDEAL      = 130_000   # Target for scoring
```

### 6. Run locally

```bash
python main.py
```

Dashboard → **http://localhost:5000**

The scraper runs immediately on startup, then every 2 hours. The first run may take a few minutes.

---

## Getting each API key

### Anthropic (Claude)

1. Go to [console.anthropic.com](https://console.anthropic.com) and create an account
2. You get **$5 free credit** on sign-up (no credit card needed initially)
3. Go to **API Keys** → **Create Key**
4. Copy the key starting with `sk-ant-api03-...`

### Apify (Indeed + Wellfound)

1. Go to [console.apify.com](https://console.apify.com) and sign up (free)
2. Go to **Settings → Integrations → API tokens**
3. Copy your token starting with `apify_api_...`
4. The free plan gives ~500 actor compute units/month (resets on the 1st)

### RapidAPI (LinkedIn / JSearch)

1. Go to [rapidapi.com](https://rapidapi.com) and create an account
2. Search for **"JSearch"** and click **Subscribe to Test** (free tier: 200 requests/month)
3. Go to your [RapidAPI Dashboard](https://rapidapi.com/developer/dashboard) → **Security** → copy your API key

### Slack

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it "Job Hunt Agent", pick your workspace
3. Go to **OAuth & Permissions** → add scope: `chat:write`
4. Click **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
5. Invite the bot to a channel: `/invite @Job Hunt Agent`
6. Get the channel ID: right-click the channel → **View channel details** → copy the ID at the bottom (starts with `C`)

---

## Deploy to Railway (run 24/7 in the cloud)

Railway is a cloud platform that keeps the agent running around the clock for ~$5/month.

### Steps

1. **Push your repo to GitHub** (your fork with your `.env` values added as Railway variables — do NOT commit `.env`)

2. **Create a Railway account** at [railway.app](https://railway.app) (free to start)

3. **New Project** → **Deploy from GitHub repo** → select your repo

4. **Add environment variables** — go to your service → **Variables** tab → paste in every variable from your `.env` file

5. Railway auto-detects Python and runs `python main.py`

6. Your dashboard will be live at `https://your-app.up.railway.app`

### Railway environment variables to set

Copy every line from your `.env` file into Railway's Variables tab. The most important ones:

```
ANTHROPIC_API_KEY
APIFY_API_TOKEN
RAPIDAPI_KEY
SLACK_BOT_TOKEN
SLACK_CHANNEL_ID
APPLICANT_NAME
APPLICANT_EMAIL
APPLICANT_LINKEDIN
RESUME_FILENAME
SECRET_KEY
```

> **Resume on Railway:** Upload your `resume.docx` by adding a Railway Volume mounted at `/data`, then upload the file. Or use the dashboard's "Run Scraper Now" button — the agent works without a resume (tailoring will be skipped until you add one).

---

## Dashboard walkthrough

| Feature | How to use |
|---------|-----------|
| **▶ Run Scraper Now** | Triggers an immediate scrape + tailor cycle (takes ~2 min) |
| **✏️ Tailor Missing Resumes** | Generates resumes for any jobs that don't have one yet |
| **Review →** | Opens job detail: read description, edit the tailored resume, answer essay questions |
| **✅ Approve** | Marks job as approved and queues it for submission |
| **⬇ PDF** | Downloads the tailored resume as a formatted PDF |
| **Skip** | Removes the job from your queue |

---

## Project structure

```
job-search/
├── main.py                      # Entry point — starts Flask + scheduler
├── config/
│   └── settings.py              # Job search preferences & targets
├── scrapers/
│   ├── base_scraper.py          # Shared filter logic (title, salary, age)
│   ├── remotive_scraper.py      # Remotive.com — free, no quota
│   ├── remoteok_scraper.py      # RemoteOK.com — free, no quota
│   ├── indeed_scraper.py        # Indeed via Apify
│   ├── wellfound_scraper.py     # Wellfound (AngelList) via Apify
│   └── linkedin_scraper.py      # LinkedIn via RapidAPI
├── llm/
│   ├── resume_tailor.py         # Claude scoring + resume tailoring + essay answers
│   └── pdf_generator.py         # Generates formatted PDF resumes
├── database/
│   └── models.py                # SQLite models (Peewee ORM)
├── scheduler/
│   └── job_scheduler.py         # APScheduler — scrape loop + Slack report
├── ui/
│   ├── app.py                   # Flask dashboard
│   └── templates/               # HTML templates
├── data/
│   └── resume.docx              # YOUR resume goes here (not committed to git)
├── .env.example                 # Template — copy to .env and fill in values
├── requirements.txt
└── railway.json                 # Railway deployment config
```

---

## Monthly cost estimate

| Service | Free tier | Paid (if you need more) |
|---------|----------|------------------------|
| Anthropic (Claude) | $5 sign-up credit | ~$3–5/month at 10 jobs/day |
| Apify | ~500 runs/month | $49/month unlimited |
| RapidAPI JSearch | 200 req/month | $10/month |
| Remotive + RemoteOK | Unlimited free | — |
| Railway hosting | $5 free credit | ~$5/month |
| Slack | Free | — |
| **Total (free tier)** | **~$0/month** | — |
| **Total (all paid)** | — | **~$65/month** |

> The free tiers are enough to get started. Apify and RapidAPI quotas reset on the 1st of each month.

---

## Troubleshooting

**No jobs appearing on dashboard**
- Check Railway logs for scraper errors
- Apify/RapidAPI quotas may be exhausted for the month — Remotive + RemoteOK still work for free
- Verify your `ANTHROPIC_API_KEY` is set correctly

**"Internal Server Error" on the dashboard**
- Check that all environment variables are set in Railway
- Make sure `SECRET_KEY` is set

**Tailored resumes not generating**
- Verify `ANTHROPIC_API_KEY` is valid and has credit
- Check that `RESUME_FILENAME` matches the actual file in `data/`

**Slack messages not arriving**
- Confirm the bot is invited to the channel (`/invite @YourBotName`)
- Check `SLACK_CHANNEL_ID` starts with `C` (not the channel name)

---

## License

MIT — free to use, fork, and modify.
