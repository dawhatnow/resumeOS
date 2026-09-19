from app.fetching.base import JobFetcher
from app.models import JobPosting


class AshbyFetcher(JobFetcher):
    """Calls Ashby's public job API for clean JSON instead of scraping HTML."""

    def handles(self, url: str) -> bool:
        return "ashbyhq.com" in url

    def fetch(self, url: str) -> JobPosting:
        raise NotImplementedError("Ashby API fetch not yet implemented")
