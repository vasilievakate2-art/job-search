"""
scrapers/linkedin_scraper.py
Scrapes LinkedIn job listings via the LinkedIn Jobs Search API on RapidAPI.
LinkedIn blocks direct scrapers, so RapidAPI is the cleanest workaround.
"""
import logging
import datetime
import requests
from config.settings import RAPIDAPI_KEY, TARGET_TITLES, SALARY_MIN
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

RAPIDAPI_HOST = "linkedin-jobs-search.p.rapidapi.com"
RAPIDAPI_URL  = f"https://{RAPIDAPI_HOST}/get-jobs-details"


class LinkedInScraper(BaseScraper):

    source_name = "linkedin"

    def __init__(self):
        super().__init__()
        self.headers = {
            "X-RapidAPI-Key":  RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        }

    def fetch_jobs(self) -> list[dict]:
        """Fetch jobs from LinkedIn via RapidAPI."""
        if not RAPIDAPI_KEY:
            logger.warning("[linkedin] RAPIDAPI_KEY not set – skipping LinkedIn scrape.")
            return []

        all_jobs = []
        search_pairs = [
            ("content marketing manager",  "San Francisco Bay Area"),
            ("head of marketing",          "San Francisco Bay Area"),
            ("brand strategist",           "San Francisco Bay Area"),
            ("growth marketer",            "San Francisco Bay Area"),
            ("social media manager",       "San Francisco Bay Area"),
            ("content lead",               "United States"),
            ("marketing manager",          "San Francisco Bay Area"),
            ("demand generation manager",  "United States"),
            ("field marketing manager",    "United States"),
            ("content production manager", "United States"),
            ("community growth manager",   "United States"),
            ("marketing content manager",  "United States"),
        ]

        for title, location in search_pairs:
            for page in ["1", "2"]:   # fetch two pages per query
                try:
                    params = {
                        "query":    title,
                        "location": location,
                        "page":     page,
                    }
                    response = requests.get(RAPIDAPI_URL, headers=self.headers, params=params, timeout=15)
                    response.raise_for_status()
                    data = response.json()

                    items = data if isinstance(data, list) else data.get("data", [])
                    logger.info(f"[linkedin] '{title}' p{page} → {len(items)} results")

                    for item in items:
                        parsed = self._parse_item(item)
                        if parsed:
                            all_jobs.append(parsed)

                except Exception as e:
                    logger.error(f"[linkedin] Error on '{title}' p{page}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)

        return unique

    def _parse_item(self, item: dict) -> dict | None:
        """Convert LinkedIn API item to standard job dict."""
        try:
            sal_min, sal_max = self._clean_salary(item.get("salary"))

            posted_at = None
            if item.get("postedDate") or item.get("posted_at"):
                raw_date = item.get("postedDate") or item.get("posted_at")
                try:
                    posted_at = datetime.datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                    posted_at = posted_at.replace(tzinfo=None)
                except Exception:
                    pass

            job_id = item.get("id") or item.get("jobId") or item.get("job_id", "")

            return {
                "job_id":        f"linkedin_{job_id}",
                "source":        "linkedin",
                "title":         item.get("title", item.get("job_title", "")),
                "company":       item.get("company", item.get("company_name", "")),
                "location":      item.get("location", ""),
                "salary_min":    sal_min,
                "salary_max":    sal_max,
                "work_type":     self._parse_work_type(item),
                "funding_stage": None,  # LinkedIn doesn't expose this
                "description":   item.get("description", item.get("job_description", "")),
                "apply_url":     item.get("url", item.get("apply_url", item.get("linkedin_url", ""))),
                "posted_at":     posted_at,
            }
        except Exception as e:
            logger.warning(f"[linkedin] Failed to parse item: {e}")
            return None

    def _parse_work_type(self, item: dict) -> str:
        """Detect work type from LinkedIn item."""
        work_type = str(item.get("workType", item.get("work_type", ""))).lower()
        if "remote" in work_type:
            return "remote"
        if "hybrid" in work_type:
            return "hybrid"
        if "on-site" in work_type or "onsite" in work_type:
            return "on-site"
        # Fall back to title/description text
        text = " ".join([
            item.get("title", ""),
            str(item.get("description", ""))[:300]
        ]).lower()
        if "remote" in text:
            return "remote"
        if "hybrid" in text:
            return "hybrid"
        return "on-site"
