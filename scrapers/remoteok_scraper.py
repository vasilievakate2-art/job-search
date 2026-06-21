"""
scrapers/remoteok_scraper.py
Scrapes marketing jobs from RemoteOK — completely free, no API key needed.
Returns 10-20 remote marketing jobs per run.
"""
import logging
import datetime
import requests
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

REMOTEOK_URL = "https://remoteok.com/api"

# Marketing-relevant tags to filter by (in addition to title filter)
MARKETING_TAGS = {
    "marketing", "content", "copywriting", "seo", "sem", "social-media",
    "growth", "brand", "email", "communications", "pr", "advertising",
    "demand-generation", "product-marketing",
}


class RemoteOKScraper(BaseScraper):
    source_name = "remoteok"

    def fetch_jobs(self) -> list[dict]:
        all_jobs = []

        try:
            headers = {"User-Agent": "JobHuntAgent/1.0"}
            r = requests.get(REMOTEOK_URL, headers=headers, timeout=20)
            r.raise_for_status()
            items = r.json()
            logger.info(f"[remoteok] Fetched {len(items)} total items")

            for item in items:
                if not isinstance(item, dict) or item.get("legal"):
                    continue  # skip metadata row
                parsed = self._parse_item(item)
                if parsed:
                    all_jobs.append(parsed)

        except Exception as e:
            logger.error(f"[remoteok] Error fetching jobs: {e}")

        # Deduplicate
        seen, unique = set(), []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)

        logger.info(f"[remoteok] {len(unique)} unique marketing jobs found")
        return unique

    def _parse_item(self, item: dict) -> dict | None:
        try:
            position = item.get("position", "")
            tags = [t.lower() for t in item.get("tags", [])]

            # Must match either by title keywords OR by having a marketing-relevant tag
            broad_keywords = [
                "content", "marketing", "brand", "growth", "social media",
                "copywriter", "copywriting", "seo", "sem", "email marketing",
                "communications", "product marketing", "creative director",
                "editorial", "writer", "editor", "campaign", "paid media",
            ]
            title_match = any(kw in position.lower() for kw in broad_keywords)
            tag_match = bool(MARKETING_TAGS & set(tags))

            if not (title_match or tag_match):
                return None

            # Parse salary
            salary_str = item.get("salary", "")
            sal_min, sal_max = self._clean_salary(salary_str if salary_str else None)
            # Salary threshold applied centrally in base_scraper._passes_filters

            # Parse date
            posted_at = None
            date_str = item.get("date") or item.get("epoch")
            if date_str:
                try:
                    if isinstance(date_str, (int, float)):
                        posted_at = datetime.datetime.utcfromtimestamp(date_str)
                    else:
                        posted_at = datetime.datetime.fromisoformat(
                            str(date_str).replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                except Exception:
                    pass

            job_id = str(item.get("id", item.get("slug", "")))
            url = item.get("url", f"https://remoteok.com/remote-jobs/{job_id}")

            return {
                "job_id":        f"remoteok_{job_id}",
                "source":        "remoteok",
                "title":         position,
                "company":       item.get("company", ""),
                "location":      "Remote",
                "salary_min":    sal_min,
                "salary_max":    sal_max,
                "work_type":     "remote",
                "funding_stage": None,
                "description":   item.get("description", ""),
                "apply_url":     url,
                "posted_at":     posted_at,
            }
        except Exception as e:
            logger.warning(f"[remoteok] parse error: {e}")
            return None
