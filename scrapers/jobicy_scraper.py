"""
scrapers/jobicy_scraper.py
Scrapes remote marketing jobs from Jobicy.com — free API, no key needed.
Returns ~50 marketing/sales remote jobs per run.
"""
import logging
import datetime
import html
import requests
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"

MARKETING_TITLE_KEYWORDS = [
    "marketing", "content", "brand", "social media", "growth", "copywriter",
    "communications", "community", "seo", "demand gen", "campaign", "pr ",
]


class JobicyScraper(BaseScraper):
    source_name = "jobicy"

    def fetch_jobs(self) -> list[dict]:
        all_jobs = []

        for tag in ["marketing", "content"]:
            try:
                r = requests.get(
                    JOBICY_URL,
                    params={"count": 50, "tag": tag},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                )
                r.raise_for_status()
                jobs = r.json().get("jobs", [])
                logger.info(f"[jobicy] tag={tag} → {len(jobs)} results")
                for item in jobs:
                    parsed = self._parse_item(item)
                    if parsed:
                        all_jobs.append(parsed)
            except Exception as e:
                logger.error(f"[jobicy] Error on tag={tag}: {e}")

        # Deduplicate
        seen, unique = set(), []
        for job in all_jobs:
            if job["job_id"] not in seen:
                seen.add(job["job_id"])
                unique.append(job)
        return unique

    def _parse_item(self, item: dict) -> dict | None:
        try:
            title = item.get("jobTitle", "")
            # Extra title filter: skip clearly non-marketing roles
            title_lower = title.lower()
            if not any(k in title_lower for k in MARKETING_TITLE_KEYWORDS):
                return None

            geo = item.get("jobGeo", "Remote") or "Remote"

            sal_min = None
            sal_max = None
            try:
                raw_min = item.get("salaryMin")
                raw_max = item.get("salaryMax")
                currency = item.get("salaryCurrency", "USD")
                period = item.get("salaryPeriod", "year")
                if raw_min and currency == "USD" and period == "year":
                    sal_min = int(raw_min)
                    sal_max = int(raw_max) if raw_max else None
            except Exception:
                pass

            posted_at = None
            if item.get("pubDate"):
                try:
                    posted_at = datetime.datetime.strptime(
                        item["pubDate"], "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    pass

            description = html.unescape(item.get("jobDescription", item.get("jobExcerpt", "")))

            return {
                "job_id":        f"jobicy_{item.get('id', item.get('jobSlug', ''))}",
                "source":        "jobicy",
                "title":         title,
                "company":       item.get("companyName", ""),
                "location":      geo,
                "salary_min":    sal_min,
                "salary_max":    sal_max,
                "work_type":     "remote",
                "funding_stage": None,
                "description":   description,
                "apply_url":     item.get("url", ""),
                "posted_at":     posted_at,
            }
        except Exception as e:
            logger.warning(f"[jobicy] parse error: {e}")
            return None
