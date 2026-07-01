"""
scrapers/remotive_scraper.py
Scrapes remote marketing jobs from Remotive.com — completely free, no API key needed.
Returns 100+ remote marketing jobs per run.
"""
import logging
import datetime
import requests
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"

# Remotive's category request param is broken — API ignores it and returns ~30 recent jobs regardless.
# We fetch once and filter by the category field in each job's response instead.
MARKETING_RESPONSE_CATEGORIES = {"Marketing", "Writing", "Communications", "Content Creation"}

MARKETING_TITLE_KEYWORDS = [
    "marketing", "content", "brand", "social media", "growth", "copywriter",
    "communications", "community", "seo", "demand gen", "campaign",
]


class RemotiveScraper(BaseScraper):
    source_name = "remotive"

    def fetch_jobs(self) -> list[dict]:
        all_jobs = []

        try:
            r = requests.get(REMOTIVE_URL, params={"limit": 100}, timeout=15)
            r.raise_for_status()
            raw_jobs = r.json().get("jobs", [])
            logger.info(f"[remotive] fetched {len(raw_jobs)} total jobs")

            for item in raw_jobs:
                cat = item.get("category", "")
                title = item.get("title", "").lower()
                # Keep if category matches OR title has marketing keywords
                if cat in MARKETING_RESPONSE_CATEGORIES or any(k in title for k in MARKETING_TITLE_KEYWORDS):
                    parsed = self._parse_item(item)
                    if parsed:
                        all_jobs.append(parsed)

            logger.info(f"[remotive] {len(all_jobs)} marketing-relevant jobs after filtering")
        except Exception as e:
            logger.error(f"[remotive] Error: {e}")

        # Deduplicate
        seen, unique = set(), []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)
        return unique

    def _parse_item(self, item: dict) -> dict | None:
        try:
            sal_min, sal_max = self._clean_salary(item.get("salary"))

            posted_at = None
            if item.get("publication_date"):
                try:
                    posted_at = datetime.datetime.fromisoformat(
                        item["publication_date"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    pass

            return {
                "job_id":        f"remotive_{item.get('id', '')}",
                "source":        "remotive",
                "title":         item.get("title", ""),
                "company":       item.get("company_name", ""),
                "location":      item.get("candidate_required_location", "Remote"),
                "salary_min":    sal_min,
                "salary_max":    sal_max,
                "work_type":     "remote",
                "funding_stage": None,
                "description":   item.get("description", ""),
                "apply_url":     item.get("url", ""),
                "posted_at":     posted_at,
            }
        except Exception as e:
            logger.warning(f"[remotive] parse error: {e}")
            return None
