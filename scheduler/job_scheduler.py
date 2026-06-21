"""
scheduler/job_scheduler.py
APScheduler-based scheduler that runs the agent 24/7.
– Scrapes jobs every 2 hours
– Sends a Slack daily summary at 10 AM Pacific
"""
import logging
import json
import datetime
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config.settings import (
    SLACK_BOT_TOKEN, SLACK_CHANNEL_ID,
    DAILY_REPORT_HOUR, SCRAPE_INTERVAL_HOURS
)
from database.models import db, JobListing, TailoredResume, ApplicationDraft, Submission, init_db
from scrapers.remotive_scraper import RemotiveScraper
from scrapers.remoteok_scraper import RemoteOKScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.wellfound_scraper import WellfoundScraper
from scrapers.linkedin_scraper import LinkedInScraper
from llm.resume_tailor import tailor_resume, score_match

logger = logging.getLogger(__name__)
scheduler = BlockingScheduler(timezone="America/Los_Angeles")
slack = WebClient(token=SLACK_BOT_TOKEN)
PACIFIC = pytz.timezone("America/Los_Angeles")


# ── Core scrape + tailor job ──────────────────────────────────────────────────

def run_scrapers():
    """Run all scrapers and save new jobs to the database."""
    logger.info("=== Starting scrape cycle ===")
    # Remotive: always free, no quota
    # Indeed/Wellfound: Apify quota (resets monthly) – reduced to 15 queries to stay within free plan
    # LinkedIn: RapidAPI (resets monthly)
    # Remotive + RemoteOK: always free, no quota
    # Indeed/Wellfound: Apify quota (resets monthly)
    # LinkedIn: RapidAPI (resets monthly)
    scrapers = [RemotiveScraper(), RemoteOKScraper(), IndeedScraper(), WellfoundScraper(), LinkedInScraper()]
    new_count = 0

    for scraper in scrapers:
        try:
            jobs = scraper.run()
            for job_data in jobs:
                # Skip if already in DB
                if JobListing.select().where(JobListing.job_id == job_data["job_id"]).exists():
                    continue

                # Score the match with Haiku (fast + cheap)
                score, reason, gaps = score_match(job_data)
                if score < 30:
                    logger.info(f"Low match ({score}) – skipping: {job_data['title']} @ {job_data['company']}")
                    continue

                # Save to DB
                with db:
                    job = JobListing.create(
                        job_id=job_data["job_id"],
                        source=job_data["source"],
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data["location"],
                        salary_min=job_data.get("salary_min"),
                        salary_max=job_data.get("salary_max"),
                        work_type=job_data.get("work_type"),
                        funding_stage=job_data.get("funding_stage"),
                        description=job_data.get("description", ""),
                        apply_url=job_data.get("apply_url", ""),
                        posted_at=job_data.get("posted_at"),
                        match_score=score,
                        status="new",
                    )

                new_count += 1
                logger.info(f"Saved: {job_data['title']} @ {job_data['company']} (score: {score})")

        except Exception as e:
            logger.error(f"Scraper {scraper.source_name} failed: {e}")

    logger.info(f"=== Scrape cycle complete. {new_count} new jobs saved. ===")


def tailor_pending_jobs():
    """Tailor resumes for ALL new jobs that passed scoring (score ≥ 30).

    Every job on the dashboard gets a resume tailored to that specific role
    using claude-sonnet-4-6.  (~$0.033 per job, ~10 new jobs/day → ~$0.33/day)
    """
    new_jobs = JobListing.select().where(JobListing.status == "new")
    logger.info(f"Processing {new_jobs.count()} new jobs for tailoring...")

    for job in new_jobs:
        try:
            # Tailor resume for every job that made it past scoring
            tailored_text = tailor_resume({
                "title":       job.title,
                "company":     job.company,
                "description": job.description,
            })
            if tailored_text:
                with db:
                    TailoredResume.create(job=job, resume_text=tailored_text)
                logger.info(f"Tailored (score {job.match_score}): {job.title} @ {job.company}")
            else:
                logger.warning(f"Tailoring returned empty for {job.title} @ {job.company}")

            with db:
                job.status = "pending_review"
                job.save()

        except Exception as e:
            logger.error(f"Failed to process job {job.job_id}: {e}")


# ── Daily Slack report ────────────────────────────────────────────────────────

def send_daily_slack_report():
    """Send the 10 AM daily summary to Slack."""
    logger.info("Sending daily Slack report...")

    now = datetime.datetime.now(PACIFIC)
    yesterday = now - datetime.timedelta(days=1)

    # Stats
    new_found       = JobListing.select().where(JobListing.found_at >= yesterday.replace(tzinfo=None)).count()
    tailored_today  = (TailoredResume
                       .select()
                       .join(JobListing)
                       .where(JobListing.found_at >= yesterday.replace(tzinfo=None))
                       .count())
    pending_review  = JobListing.select().where(JobListing.status == "pending_review").count()
    submitted_today = Submission.select().where(Submission.submitted_at >= yesterday.replace(tzinfo=None)).count()
    total_submitted = Submission.select().count()

    # Top new jobs (highest match score)
    top_jobs = (JobListing
                .select()
                .where(JobListing.found_at >= yesterday.replace(tzinfo=None))
                .order_by(JobListing.match_score.desc())
                .limit(5))

    top_jobs_text = ""
    for j in top_jobs:
        salary_str = ""
        if j.salary_min:
            salary_str = f" · ${j.salary_min//1000}K–${j.salary_max//1000}K" if j.salary_max else f" · ${j.salary_min//1000}K+"
        top_jobs_text += f"• *{j.title}* @ {j.company} ({j.source}){salary_str} · Match: {j.match_score}/100\n"

    dashboard_url = "https://web-production-239b4.up.railway.app"

    message = f"""
🤖 *Job Hunt Agent – Daily Report*
📅 {now.strftime('%A, %B %d, %Y · %I:%M %p PT')}

*Last 24 hours:*
🔍 New jobs found: *{new_found}*
✏️ Resumes tailored: *{tailored_today}*
✅ Applications submitted: *{submitted_today}*
📋 Waiting for your review: *{pending_review}*
📊 Total submitted (all time): *{total_submitted}*

*Top new matches:*
{top_jobs_text or "No new matches in the last 24 hours."}

👉 *Review & approve:* {dashboard_url}
""".strip()

    try:
        slack.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=message,
            mrkdwn=True,
        )
        logger.info("Daily Slack report sent successfully.")
    except SlackApiError as e:
        logger.error(f"Failed to send Slack report: {e.response['error']}")


# ── Scheduler setup ───────────────────────────────────────────────────────────

def start():
    """Start the 24/7 scheduler."""
    init_db()
    logger.info("Initializing Job Hunt Agent scheduler...")

    # Scrape every N hours, 24/7
    scheduler.add_job(
        run_scrapers,
        trigger=IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS),
        id="scraper",
        name="Job Scraper",
        replace_existing=True,
        next_run_time=datetime.datetime.now(),  # Run immediately on startup
    )

    # Tailor resumes 30 min after each scrape
    scheduler.add_job(
        tailor_pending_jobs,
        trigger=IntervalTrigger(hours=SCRAPE_INTERVAL_HOURS, minutes=30),
        id="tailor",
        name="Resume Tailor",
        replace_existing=True,
    )

    # Daily Slack report at 10 AM Pacific
    scheduler.add_job(
        send_daily_slack_report,
        trigger=CronTrigger(hour=DAILY_REPORT_HOUR, minute=0, timezone=PACIFIC),
        id="daily_report",
        name="Daily Slack Report",
        replace_existing=True,
    )

    logger.info(f"Scheduler started. Scraping every {SCRAPE_INTERVAL_HOURS}h. Report at {DAILY_REPORT_HOUR}:00 AM PT.")
    scheduler.start()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start()
