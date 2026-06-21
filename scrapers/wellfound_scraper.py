"""
scrapers/wellfound_scraper.py
Scrapes Wellfound (formerly AngelList) using the Apify Wellfound actor.
Wellfound is the best source for funded startup roles with salary + equity info.
"""
import logging
import datetime
from apify_client import ApifyClient
from config.settings import APIFY_API_TOKEN, TARGET_TITLES, SALARY_MIN
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Apify Wellfound actor
WELLFOUND_ACTOR_ID = "curious_coder/wellfound-jobs-scraper"


class WellfoundScraper(BaseScraper):

    source_name = "wellfound"

    def __init__(self):
        super().__init__()
        self.client = ApifyClient(APIFY_API_TOKEN)

    def fetch_jobs(self) -> list[dict]:
        """Fetch startup jobs from Wellfound via Apify."""
        all_jobs = []

        # Wellfound searches by role type – broad marketing categories × locations
        search_terms = [
            "marketing manager",
            "content marketing",
            "brand marketing",
            "growth marketing",
            "social media marketing",
            "head of marketing",
            "content lead",
            "demand generation",
            "field marketing",
            "community manager",
        ]
        search_locations = ["San Francisco Bay Area", "United States"]

        for term in search_terms:
            for location_filter in search_locations:
                try:
                    run_input = {
                        "searchQuery":      term,
                        "locationFilter":   location_filter,
                        "remote":           True,
                        "maxResults":       50,
                        "salaryMin":        SALARY_MIN,   # $110k floor – local filter refines further
                    }
                    run   = self.client.actor(WELLFOUND_ACTOR_ID).call(run_input=run_input)
                    items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
                    logger.info(f"[wellfound] '{term}' / {location_filter} → {len(items)} results")

                    for item in items:
                        parsed = self._parse_item(item)
                        if parsed:
                            all_jobs.append(parsed)

                except Exception as e:
                    logger.error(f"[wellfound] Error on term '{term}' / {location_filter}: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)

        return unique

    def _parse_item(self, item: dict) -> dict | None:
        """Convert Wellfound item to standard job dict."""
        try:
            sal_min, sal_max = self._clean_salary(item.get("compensation"))

            # Salary threshold applied centrally in base_scraper._passes_filters

            posted_at = None
            if item.get("postedDate"):
                try:
                    posted_at = datetime.datetime.fromisoformat(str(item["postedDate"]).replace("Z", "+00:00"))
                    posted_at = posted_at.replace(tzinfo=None)
                except Exception:
                    pass

            # Wellfound exposes funding stage directly
            funding = item.get("companyStage") or item.get("stage") or ""
            funding_normalized = self._normalize_funding(funding)

            return {
                "job_id":        f"wellfound_{item.get('id', '')}",
                "source":        "wellfound",
                "title":         item.get("title", ""),
                "company":       item.get("companyName", item.get("company", "")),
                "location":      item.get("location", ""),
                "salary_min":    sal_min,
                "salary_max":    sal_max,
                "work_type":     self._parse_work_type(item),
                "funding_stage": funding_normalized,
                "description":   item.get("description", item.get("jobDescription", "")),
                "apply_url":     item.get("applyUrl", item.get("url", "")),
                "posted_at":     posted_at,
            }
        except Exception as e:
            logger.warning(f"[wellfound] Failed to parse item: {e}")
            return None

    def _normalize_funding(self, raw: str) -> str | None:
        """Map Wellfound stage labels to our standard keys."""
        mapping = {
            "seed":     "seed",
            "series a": "series_a",
            "series b": "series_b",
            "series c": "series_c",
            "public":   "public",
        }
        raw_lower = raw.lower()
        for key, val in mapping.items():
            if key in raw_lower:
                return val
        return None

    def _parse_work_type(self, item: dict) -> str:
        """Detect work type from Wellfound item."""
        remote = item.get("remote", item.get("isRemote", False))
        if remote:
            return "remote"
        loc = str(item.get("location", "")).lower()
        if "remote" in loc:
            return "remote"
        if "hybrid" in loc:
            return "hybrid"
        return "on-site"
