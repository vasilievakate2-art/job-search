"""
main.py
Entry point for the Job Hunt Agent.
Starts both the Flask approval dashboard and the APScheduler in parallel threads.
"""
import logging
import threading
import os
import json
import datetime
from database.models import init_db, db, JobListing, TailoredResume

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SEED_FILE = os.path.join(os.path.dirname(__file__), "data", "initial_jobs.json")


def seed_database():
    """On first startup (empty DB), import jobs from the committed seed file."""
    if not os.path.exists(SEED_FILE):
        return
    if JobListing.select().count() > 0:
        logger.info("Database already has jobs — skipping seed import.")
        return

    logger.info("Empty database detected — importing seed jobs from initial_jobs.json...")
    with open(SEED_FILE) as f:
        data = json.load(f)

    jobs_data   = data.get("jobs", [])
    resume_data = data.get("resumes", [])
    imported = 0
    old_id_map = {}

    for j in jobs_data:
        if JobListing.select().where(JobListing.job_id == j["job_id"]).exists():
            old_id_map[j["id"]] = JobListing.get(JobListing.job_id == j["job_id"])
            continue
        def _dt(s):
            try: return datetime.datetime.fromisoformat(s) if s else None
            except: return None
        status = j.get("status", "new")
        if status == "new":
            status = "pending_review"
        with db:
            job = JobListing.create(
                job_id=j["job_id"], source=j.get("source",""),
                title=j.get("title",""), company=j.get("company",""),
                location=j.get("location",""), salary_min=j.get("salary_min"),
                salary_max=j.get("salary_max"), work_type=j.get("work_type"),
                funding_stage=j.get("funding_stage"),
                description=j.get("description",""), apply_url=j.get("apply_url",""),
                posted_at=_dt(j.get("posted_at")), found_at=_dt(j.get("found_at")),
                match_score=j.get("match_score"), status=status,
            )
        old_id_map[j["id"]] = job
        imported += 1

    for r in resume_data:
        job = old_id_map.get(r.get("job_id"))
        if not job:
            continue
        if TailoredResume.select().where(TailoredResume.job == job).exists():
            continue
        with db:
            TailoredResume.create(job=job, resume_text=r.get("resume_text",""))

    logger.info(f"Seed import complete: {imported} jobs loaded.")


def run_flask():
    """Run the Flask approval dashboard."""
    from ui.app import app
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting approval dashboard on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_scheduler():
    """Run the 24/7 job scraper + tailor scheduler."""
    from scheduler.job_scheduler import start
    logger.info("Starting job hunt scheduler...")
    start()


if __name__ == "__main__":
    # Initialize database tables
    init_db()
    # Restore jobs from seed file if DB is empty (e.g. after Railway redeploy)
    seed_database()
    logger.info("Job Hunt Agent starting up...")

    # Run Flask in a background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run scheduler in the main thread (blocking)
    run_scheduler()
