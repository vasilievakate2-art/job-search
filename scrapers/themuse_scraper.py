"""
scrapers/themuse_scraper.py
Scrapes marketing jobs from The Muse — completely free, no API key needed.
Covers US remote + on-site marketing roles at vetted companies.
"""
import logging
import datetime
import requests
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

MUSE_URL = "https://www.themuse.com/api/public/jobs"

MUSE_CATEGORIES = [
    "Marketing & PR",
    "Content & Writing",
    "Social Media & Community",
]

MUSE_LEVELS = ["Mid Level", "Senior Level", "Manager", "Director"]


class TheMuseScraper(BaseScraper):
    source_name = "themuse"

    def fetch_jobs(self) -> list[dict]:
        all_jobs = []

        for category in MUSE_CATEGORIES:
            for page in range(0, 3):   # pages 0-2
                try:
                    params = {
                        "category": category,
                        "level":    MUSE_LEVELS,
                        "page":     page,
                        "descending": "true",
                    }
                    r = requests.get(MUSE_URL, params=params, timeout=15)
                    r.raise_for_status()
                    results = r.json().get("results", [])
                    logger.info(f"[themuse] '{category}' p{page} → {len(results)} results")
                    for item in results:
                        parsed = self._parse_item(item)
                        if parsed:
                            all_jobs.append(parsed)
                    if len(results) == 0:
                        break
                except Exception as e:
                    logger.error(f"[themuse] Error on '{category}' p{page}: {e}")

        seen, unique = set(), []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)
        return unique

    def _parse_item(self, item: dict) -> dict | None:
        try:
            locations = item.get("locations", [])
            location_str = ", ".join(loc.get("name", "") for loc in locations) or "US"

            work_type = "remote" if any(
                "remote" in loc.get("name", "").lower() for loc in locations
            ) else "on-site"

            posted_at = None
            if item.get("publication_date"):
                try:
                    posted_at = datetime.datetime.fromisoformat(
                        item["publication_date"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    pass

            company = item.get("company", {}).get("name", "")
            job_id  = str(item.get("id", ""))
            title   = item.get("name", "")
            url     = item.get("refs", {}).get("landing_page", "")

            return {
                "job_id":        f"themuse_{job_id}",
                "source":        "themuse",
                "title":         title,
                "company":       company,
                "location":      location_str,
                "salary_min":    None,
                "salary_max":    None,
                "work_type":     work_type,
                "funding_stage": None,
                "description":   item.get("body", item.get("contents", "")),
                "apply_url":     url,
                "posted_at":     posted_at,
            }
        except Exception as e:
            logger.warning(f"[themuse] parse error: {e}")
            return None
