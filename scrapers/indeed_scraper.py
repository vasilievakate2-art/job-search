"""
scrapers/indeed_scraper.py
Scrapes Indeed using the Apify Indeed actor.
Apify handles anti-bot protection so we don't get blocked.
"""
import logging
import datetime
from apify_client import ApifyClient
from config.settings import APIFY_API_TOKEN, TARGET_TITLES, TARGET_LOCATIONS, SALARY_MIN
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Apify's official Indeed scraper actor ID
INDEED_ACTOR_ID = "misceres/indeed-scraper"


class IndeedScraper(BaseScraper):

    source_name = "indeed"

    def __init__(self):
        super().__init__()
        self.client = ApifyClient(APIFY_API_TOKEN)

    def fetch_jobs(self) -> list[dict]:
        """Fetch jobs from Indeed via Apify actor.

        Budget: 4 queries per run (Bay Area only). At ~$0.06/query this costs
        ~$0.24/run × 12 runs/day = ~$2.88/day. Keep queries tight to preserve Apify quota.
        """
        all_jobs = []

        # 4 targeted queries: broad Bay Area search with high maxItems to cover all titles at once.
        search_queries = [
            {"position": "marketing manager", "location": "San Francisco Bay Area, CA"},
            {"position": "content marketing",  "location": "San Francisco Bay Area, CA"},
            {"position": "head of marketing",  "location": "San Francisco, CA"},
            {"position": "marketing director", "location": "San Francisco Bay Area, CA"},
        ]

        logger.info(f"[indeed] Running {len(search_queries)} search queries via Apify...")

        for query in search_queries:
            try:
                run_input = {
                    "position": query["position"],
                    "location": query["location"],
                    "maxItems": 100,
                    "parseCompanyDetails": False,
                    "saveOnlyUniqueItems": True,
                    "followApplyRedirects": False,
                }
                run = self.client.actor(INDEED_ACTOR_ID).call(run_input=run_input)
                items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
                logger.info(f"[indeed] '{query['position']}' in '{query['location']}' → {len(items)} results")

                for item in items:
                    parsed = self._parse_item(item)
                    if parsed:
                        all_jobs.append(parsed)

            except Exception as e:
                logger.error(f"[indeed] Error on query {query}: {e}")

        # Deduplicate by job_id
        seen = set()
        unique = []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)

        return unique

    def _parse_item(self, item: dict) -> dict | None:
        """Convert an Apify Indeed item to our standard job dict."""
        try:
            salary_raw = item.get("salary") or item.get("salarySnippet")
            sal_min, sal_max = self._clean_salary(salary_raw)

            # Salary threshold is applied in base_scraper._passes_filters (work-type aware)

            posted_at = None
            if item.get("postedAt"):
                try:
                    posted_at = datetime.datetime.fromisoformat(item["postedAt"].replace("Z", "+00:00"))
                    posted_at = posted_at.replace(tzinfo=None)
                except Exception:
                    pass

            return {
                "job_id":       f"indeed_{item.get('id', item.get('jobKey', ''))}",
                "source":       "indeed",
                "title":        item.get("positionName", ""),
                "company":      item.get("company", ""),
                "location":     item.get("location", ""),
                "salary_min":   sal_min,
                "salary_max":   sal_max,
                "work_type":    self._parse_work_type(item),
                "funding_stage": None,  # Indeed doesn't expose this
                "description":  item.get("description", ""),
                "apply_url":    item.get("url", item.get("externalApplyLink", "")),
                "posted_at":    posted_at,
            }
        except Exception as e:
            logger.warning(f"[indeed] Failed to parse item: {e}")
            return None

    def _parse_work_type(self, item: dict) -> str:
        """Detect work type from job item fields."""
        text = " ".join([
            str(item.get("jobType", "")),
            str(item.get("title", "")),
            str(item.get("description", ""))[:200],
        ]).lower()
        if "remote" in text:
            return "remote"
        if "hybrid" in text:
            return "hybrid"
        return "on-site"
