from app.fetching.base import JobFetcher
from app.models import JobPosting


class GreenhouseFetcher(JobFetcher):
    """Calls Greenhouse's public job API for clean JSON instead of scraping HTML."""

    def handles(self, url: str) -> bool:
        return "greenhouse.io" in url

    def fetch(self, url: str) -> JobPosting:
        raise NotImplementedError("Greenhouse API fetch not yet implemented")
