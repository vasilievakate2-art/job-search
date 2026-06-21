"""
ui/app.py
Flask web app – Kate's approval dashboard.
Shows pending jobs, tailored resumes, and lets her approve/edit/skip each one.
"""
import re
import json
import logging
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_file
import io
from config.settings import SECRET_KEY, APPLICANT
from database.models import db, JobListing, TailoredResume, ApplicationDraft, Submission, init_db
from llm.resume_tailor import generate_essay_answer
from llm.pdf_generator import generate_resume_pdf

app = Flask(__name__)
app.secret_key = SECRET_KEY
logger = logging.getLogger(__name__)

init_db()


@app.route("/")
def index():
    """Dashboard home – show stats and pending reviews."""
    pending = (JobListing
               .select()
               .where(JobListing.status == "pending_review")
               .order_by(JobListing.match_score.desc()))

    approved = JobListing.select().where(JobListing.status == "approved").count()
    submitted = Submission.select().count()
    total_found = JobListing.select().count()

    return render_template("index.html",
        pending=pending,
        approved_count=approved,
        submitted_count=submitted,
        total_found=total_found,
        applicant=APPLICANT,
    )


@app.route("/job/<int:job_id>")
def job_detail(job_id):
    """Show a single job with tailored resume side by side."""
    try:
        job = JobListing.get_by_id(job_id)
    except JobListing.DoesNotExist:
        flash("Job not found — it may have been removed.", "error")
        return redirect(url_for("index"))
    resume = TailoredResume.select().where(TailoredResume.job == job).first()
    draft  = ApplicationDraft.select().where(ApplicationDraft.job == job).first()

    return render_template("job_detail.html",
        job=job,
        resume=resume,
        draft=draft,
        applicant=APPLICANT,
    )


@app.route("/job/<int:job_id>/approve", methods=["POST"])
def approve_job(job_id):
    """Kate approves a job – saves edited resume + essay answers."""
    try:
        job = JobListing.get_by_id(job_id)
    except JobListing.DoesNotExist:
        flash("Job not found.", "error")
        return redirect(url_for("index"))
    resume = TailoredResume.select().where(TailoredResume.job == job).first()

    # Get form data
    edited_resume   = request.form.get("resume_text", resume.resume_text if resume else "")
    essay_answers   = {}
    notes           = request.form.get("notes", "")

    # Collect any essay Q&A pairs
    questions = request.form.getlist("question[]")
    answers   = request.form.getlist("answer[]")
    for q, a in zip(questions, answers):
        if q.strip():
            essay_answers[q] = a

    # Standard form fields (pre-filled from APPLICANT config)
    form_fields = {
        "name":           APPLICANT["name"],
        "email":          APPLICANT["email"],
        "phone":          APPLICANT["phone"],
        "location":       APPLICANT["location"],
        "linkedin":       APPLICANT["linkedin"],
        "portfolio":      APPLICANT["portfolio"],
        "work_auth":      APPLICANT["work_auth"],
        "sponsorship":    APPLICANT["needs_sponsorship"],
        "desired_salary": APPLICANT["desired_salary"],
        "start_date":     APPLICANT["start_date"],
    }

    with db:
        # Update tailored resume text if Kate edited it
        if resume and edited_resume:
            resume.resume_text = edited_resume
            resume.save()

        # Create or update draft (resume may be None if not yet tailored)
        existing_draft = ApplicationDraft.select().where(ApplicationDraft.job == job).first()
        if existing_draft:
            draft = existing_draft
        else:
            draft = ApplicationDraft(job=job, resume=resume)

        draft.form_fields   = json.dumps(form_fields)
        draft.essay_answers = json.dumps(essay_answers)
        draft.notes         = notes
        draft.approved      = True
        draft.save()

        job.status = "approved"
        job.save()

    flash(f"✅ {job.title} at {job.company} approved and queued for submission.", "success")
    return redirect(url_for("index"))


@app.route("/job/<int:job_id>/skip", methods=["POST"])
def skip_job(job_id):
    """Kate skips a job."""
    try:
        job = JobListing.get_by_id(job_id)
    except JobListing.DoesNotExist:
        flash("Job not found — it may have already been removed.", "info")
        return redirect(url_for("index"))
    with db:
        job.status = "skipped"
        job.save()
    flash(f"Skipped: {job.title} at {job.company}.", "info")
    return redirect(url_for("index"))


@app.route("/api/generate-essay", methods=["POST"])
def api_generate_essay():
    """AJAX endpoint – generate an essay answer for a custom question."""
    data     = request.get_json()
    question = data.get("question", "")
    job_id   = data.get("job_id")

    if not question or not job_id:
        return jsonify({"error": "Missing question or job_id"}), 400

    job = JobListing.get_by_id(job_id)
    answer = generate_essay_answer(question, {
        "title":       job.title,
        "company":     job.company,
        "description": job.description,
    })

    return jsonify({"answer": answer})


@app.route("/job/<int:job_id>/resume.pdf")
def download_resume_pdf(job_id):
    """Download the tailored resume for a job as a PDF."""
    job = JobListing.get_by_id(job_id)
    resume = TailoredResume.select().where(TailoredResume.job == job).first()

    if not resume or not resume.resume_text:
        flash("No tailored resume available for this job yet.", "error")
        return redirect(url_for("index"))

    pdf_bytes = generate_resume_pdf(
        resume_text=resume.resume_text,
        job_title=job.title,
        company=job.company,
        applicant=APPLICANT,
    )

    # Clean filename: Resume_Kate_ContentLead_Acme.pdf
    safe_title   = re.sub(r"[^a-zA-Z0-9]+", "_", job.title)[:30]
    safe_company = re.sub(r"[^a-zA-Z0-9]+", "_", job.company)[:20]
    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", APPLICANT.get("name", "Resume").split()[0])
    filename = f"Resume_{safe_name}_{safe_title}_{safe_company}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/run-scraper", methods=["POST"])
def api_run_scraper():
    """Trigger a full scrape + tailor cycle immediately (runs in background thread)."""
    def _run():
        try:
            from scheduler.job_scheduler import run_scrapers, tailor_pending_jobs
            run_scrapers()
            tailor_pending_jobs()
        except Exception as e:
            logger.error(f"Manual scrape run failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "Scrape cycle started — refresh in ~60 seconds to see new jobs."})


@app.route("/api/tailor-missing", methods=["POST"])
def api_tailor_missing():
    """Backfill: generate tailored resumes for any pending_review jobs that have none."""
    def _run():
        try:
            from llm.resume_tailor import tailor_resume
            jobs_missing = (JobListing
                            .select()
                            .where(JobListing.status == "pending_review")
                            .where(~JobListing.id.in_(
                                TailoredResume.select(TailoredResume.job_id)
                            )))
            count = 0
            for job in jobs_missing:
                try:
                    tailored_text = tailor_resume({
                        "title":       job.title,
                        "company":     job.company,
                        "description": job.description,
                    })
                    if tailored_text:
                        with db:
                            TailoredResume.create(job=job, resume_text=tailored_text)
                        count += 1
                        logger.info(f"Backfill tailored: {job.title} @ {job.company}")
                except Exception as e:
                    logger.error(f"Backfill failed for job {job.id}: {e}")
            logger.info(f"Backfill complete: {count} resumes generated.")
        except Exception as e:
            logger.error(f"Backfill run failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "Tailoring missing resumes in background — refresh in ~2 minutes."})


@app.route("/api/clear-expired", methods=["POST"])
def api_clear_expired():
    """Mark all pending_review jobs older than MAX_POSTING_AGE_DAYS as skipped."""
    import datetime as _dt
    from config.settings import MAX_POSTING_AGE_DAYS
    cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=MAX_POSTING_AGE_DAYS)

    # Use found_at as the reliable cutoff (always set; posted_at may be null)
    expired = (JobListing
               .select()
               .where(JobListing.status == "pending_review")
               .where(JobListing.found_at < cutoff))

    count = 0
    with db:
        for job in expired:
            job.status = "skipped"
            job.save()
            count += 1

    logger.info(f"Cleared {count} expired jobs (older than {MAX_POSTING_AGE_DAYS} days).")
    return jsonify({"cleared": count, "message": f"Cleared {count} expired jobs older than {MAX_POSTING_AGE_DAYS} days."})


@app.route("/api/import-jobs", methods=["POST"])
def api_import_jobs():
    """Bulk-import jobs + tailored resumes from a JSON export."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    jobs_data    = data.get("jobs", [])
    resumes_data = data.get("resumes", [])
    imported_jobs    = 0
    skipped_jobs     = 0
    imported_resumes = 0

    import datetime as _dt

    # Map from old DB id → new JobListing object (for resume linking)
    old_id_to_job = {}

    for j in jobs_data:
        # Skip if already in DB by job_id
        if JobListing.select().where(JobListing.job_id == j["job_id"]).exists():
            skipped_jobs += 1
            old_id_to_job[j["id"]] = JobListing.get(JobListing.job_id == j["job_id"])
            continue

        # Parse datetime strings
        def _parse_dt(s):
            if not s:
                return None
            try:
                return _dt.datetime.fromisoformat(s)
            except Exception:
                return None

        status = j.get("status", "new")
        # Treat all "new" imports as pending_review so they show on dashboard
        if status == "new":
            status = "pending_review"

        with db:
            job = JobListing.create(
                job_id        = j["job_id"],
                source        = j.get("source", ""),
                title         = j.get("title", ""),
                company       = j.get("company", ""),
                location      = j.get("location", ""),
                salary_min    = j.get("salary_min"),
                salary_max    = j.get("salary_max"),
                work_type     = j.get("work_type"),
                funding_stage = j.get("funding_stage"),
                description   = j.get("description", ""),
                apply_url     = j.get("apply_url", ""),
                posted_at     = _parse_dt(j.get("posted_at")),
                found_at      = _parse_dt(j.get("found_at")),
                match_score   = j.get("match_score"),
                status        = status,
            )
        old_id_to_job[j["id"]] = job
        imported_jobs += 1

    for r in resumes_data:
        old_job_id = r.get("job_id")
        job = old_id_to_job.get(old_job_id)
        if not job:
            continue
        if TailoredResume.select().where(TailoredResume.job == job).exists():
            continue
        with db:
            TailoredResume.create(job=job, resume_text=r.get("resume_text", ""))
        imported_resumes += 1

    return jsonify({
        "imported_jobs":    imported_jobs,
        "skipped_jobs":     skipped_jobs,
        "imported_resumes": imported_resumes,
    })


@app.route("/submitted")
def submitted_list():
    """Show all submitted applications."""
    submissions = (Submission
                   .select(Submission, JobListing)
                   .join(JobListing)
                   .order_by(Submission.submitted_at.desc()))
    return render_template("submitted.html", submissions=submissions)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
