"""
scrapers/base_scraper.py
Base class all scrapers inherit from.
"""
import logging
import datetime
from abc import ABC, abstractmethod
from config.settings import MAX_POSTING_AGE_DAYS, TARGET_TITLES, TARGET_LOCATIONS, SALARY_MIN, SALARY_MIN_ONSITE

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    source_name: str = "unknown"

    def __init__(self):
        self.results = []

    @abstractmethod
    def fetch_jobs(self) -> list[dict]:
        """Fetch raw job listings from the source. Must be implemented by subclass."""
        pass

    def run(self) -> list[dict]:
        """Run the scraper, filter results, and return cleaned jobs."""
        logger.info(f"[{self.source_name}] Starting scrape...")
        raw = self.fetch_jobs()
        filtered = [j for j in raw if self._passes_filters(j)]
        logger.info(f"[{self.source_name}] Found {len(raw)} listings, {len(filtered)} passed filters.")
        return filtered

    def _passes_filters(self, job: dict) -> bool:
        """Check if a job passes basic filters (age, title, location)."""
        # Age filter
        if job.get("posted_at"):
            age = (datetime.datetime.utcnow() - job["posted_at"]).days
            if age > MAX_POSTING_AGE_DAYS:
                return False

        # Title filter – at least one target keyword must appear
        title = job.get("title", "").lower()
        broad_keywords = [
            "content", "marketing", "brand", "growth",
            "social media", "community", "demand gen", "field marketing",
            "copywriter", "copywriting", "paid media", "paid social", "paid search",
            "seo", "sem", "email marketing", "campaign", "communications",
            "public relations", " pr ", "customer success", "customer marketing",
            "product marketing", "account manager", "account executive",
            "creative director", "creative strategist", "storytelling",
            "influencer", "partnership", "revenue", "go-to-market", "gtm",
            "editorial", "writer", "content editor", "copy editor", "journalist", "blogger",
        ]
        if not any(kw in title for kw in broad_keywords):
            return False

        # Salary filter – only reject if salary IS listed and clearly below threshold
        # Jobs with no salary listed pass through (salary unknown)
        sal_min = job.get("salary_min")
        sal_max = job.get("salary_max")
        if sal_max:
            work_type = job.get("work_type", "remote")
            floor = SALARY_MIN if work_type == "remote" else SALARY_MIN_ONSITE
            if sal_max < floor:
                return False

        return True

    @staticmethod
    def _clean_salary(raw: str | int | None) -> tuple[int | None, int | None]:
        """Parse salary string into annual (min, max) integers.
        Handles: '$130,000', '$75k', '$90-$150/hour', '75k - 95k', etc.
        """
        if raw is None:
            return None, None
        if isinstance(raw, int):
            return raw, raw

        import re
        raw_str = str(raw).lower().strip()
        if not raw_str or raw_str in ("-", "n/a", "tbd", "competitive"):
            return None, None

        # Detect hourly rates – convert to annual (× 2080 work hours/year)
        is_hourly = bool(re.search(r'/\s*h(ou?r)?', raw_str))

        # Extract all numeric tokens, respecting optional 'k' suffix
        numbers = []
        for m in re.finditer(r'(\d[\d,]*)(\s*k\b)?', raw_str):
            n = int(m.group(1).replace(",", ""))
            if m.group(2):      # "k" suffix → multiply by 1000
                n *= 1000
            if n < 10:          # skip noise (e.g. stray "2" in "2-year")
                continue
            numbers.append(n)

        if not numbers:
            return None, None

        lo, hi = numbers[0], numbers[-1]
        if lo > hi:
            lo, hi = hi, lo

        if is_hourly:
            lo = lo * 2080
            hi = hi * 2080

        return lo, hi
