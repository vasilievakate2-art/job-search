"""
database/models.py
SQLite database models using Peewee ORM
"""
import datetime
from peewee import (
    Model, SqliteDatabase, CharField, TextField,
    IntegerField, BooleanField, DateTimeField, ForeignKeyField
)
from config.settings import DB_PATH

db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class JobListing(BaseModel):
    """A job posting found by the scraper."""
    job_id          = CharField(unique=True)          # Platform-specific ID
    source          = CharField()                      # indeed / wellfound / linkedin
    title           = CharField()
    company         = CharField()
    location        = CharField()
    salary_min      = IntegerField(null=True)
    salary_max      = IntegerField(null=True)
    work_type       = CharField(null=True)             # remote / hybrid / on-site
    funding_stage   = CharField(null=True)
    description     = TextField()
    apply_url       = CharField()
    posted_at       = DateTimeField(null=True)
    found_at        = DateTimeField(default=datetime.datetime.utcnow)

    # Matching score (0-100) assigned by LLM
    match_score     = IntegerField(default=0)

    # Status in the pipeline
    status          = CharField(default="new")
    # new → tailored → pending_review → approved → submitted → skipped

    @property
    def salary_range(self):
        """Human-readable salary range string, e.g. '$110K–$130K'."""
        if self.salary_min and self.salary_max:
            return f"${self.salary_min // 1000}K–${self.salary_max // 1000}K"
        if self.salary_min:
            return f"${self.salary_min // 1000}K+"
        if self.salary_max:
            return f"Up to ${self.salary_max // 1000}K"
        return ""

    class Meta:
        table_name = "job_listings"


class TailoredResume(BaseModel):
    """A resume tailored for a specific job."""
    job             = ForeignKeyField(JobListing, backref="resumes")
    resume_text     = TextField()                      # Plain text version
    resume_docx_path = CharField(null=True)            # Path to .docx file
    created_at      = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        table_name = "tailored_resumes"


class ApplicationDraft(BaseModel):
    """A draft application waiting for Kate's review."""
    job             = ForeignKeyField(JobListing, backref="drafts")
    resume          = ForeignKeyField(TailoredResume, backref="drafts", null=True)
    form_fields     = TextField()                      # JSON: pre-filled form data
    essay_answers   = TextField(null=True)             # JSON: essay Q&A
    notes           = TextField(null=True)             # Kate's notes
    created_at      = DateTimeField(default=datetime.datetime.utcnow)
    reviewed_at     = DateTimeField(null=True)
    approved        = BooleanField(null=True)

    class Meta:
        table_name = "application_drafts"


class Submission(BaseModel):
    """A submitted application."""
    job             = ForeignKeyField(JobListing, backref="submissions")
    draft           = ForeignKeyField(ApplicationDraft, backref="submissions")
    submitted_at    = DateTimeField(default=datetime.datetime.utcnow)
    success         = BooleanField(default=False)
    error_message   = TextField(null=True)
    confirmation    = TextField(null=True)             # Confirmation text from site

    class Meta:
        table_name = "submissions"


def init_db():
    """Create all tables if they don't exist."""
    with db:
        db.create_tables([
            JobListing,
            TailoredResume,
            ApplicationDraft,
            Submission,
        ], safe=True)


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
