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

MARKETING_CATEGORIES = [
    "marketing",
    "copywriting",
    "customer-success",
]


class RemotiveScraper(BaseScraper):
    source_name = "remotive"

    def fetch_jobs(self) -> list[dict]:
        all_jobs = []

        for category in MARKETING_CATEGORIES:
            try:
                r = requests.get(REMOTIVE_URL, params={"category": category, "limit": 100}, timeout=15)
                r.raise_for_status()
                jobs = r.json().get("jobs", [])
                logger.info(f"[remotive] category={category} → {len(jobs)} results")
                for item in jobs:
                    parsed = self._parse_item(item)
                    if parsed:
                        all_jobs.append(parsed)
            except Exception as e:
                logger.error(f"[remotive] Error on category {category}: {e}")

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
