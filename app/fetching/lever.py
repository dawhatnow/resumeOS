from app.fetching.base import JobFetcher
from app.models import JobPosting


class LeverFetcher(JobFetcher):
    """Calls Lever's public job API for clean JSON instead of scraping HTML."""

    def handles(self, url: str) -> bool:
        return "lever.co" in url

    def fetch(self, url: str) -> JobPosting:
        raise NotImplementedError("Lever API fetch not yet implemented")
