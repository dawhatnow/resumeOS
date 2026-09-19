from app.fetching.ashby import AshbyFetcher
from app.fetching.base import FetchError, JobFetcher
from app.fetching.generic import GenericFetcher
from app.fetching.greenhouse import GreenhouseFetcher
from app.fetching.lever import LeverFetcher
from app.models import JobPosting


class JobFetcherRouter:
    """Picks the right JobFetcher for a URL, trying platform-specific
    fetchers before falling back to the generic HTML one."""

    def __init__(self, fetchers: list[JobFetcher] | None = None) -> None:
        self._fetchers = fetchers or [
            GreenhouseFetcher(),
            LeverFetcher(),
            AshbyFetcher(),
            GenericFetcher(),
        ]

    def fetch(self, url: str) -> JobPosting:
        for fetcher in self._fetchers:
            if fetcher.handles(url):
                return fetcher.fetch(url)
        raise FetchError(f"No fetcher available for {url}")
