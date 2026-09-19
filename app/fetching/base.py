from abc import ABC, abstractmethod

from app.models import JobPosting


class FetchError(Exception):
    """Raised when a fetcher can't retrieve a job posting."""


class JobFetcher(ABC):
    """One fetcher per job board. Concrete subclasses (Greenhouse, Lever,
    Ashby, generic HTML) implement fetch(); JobFetcherRouter picks which one
    to use based on the URL."""

    @abstractmethod
    def handles(self, url: str) -> bool:
        """Whether this fetcher knows how to handle the given URL."""

    @abstractmethod
    def fetch(self, url: str) -> JobPosting:
        """Fetch and return the raw job posting. Raises FetchError on failure."""
