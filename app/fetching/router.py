"""Turn a CLI source (URL, file path, or '-') into a JobPosting."""

from pathlib import Path

from app.models import JobPosting
from app.paths import ResumePathResolver


class JobSourceRouter:
    def __init__(self, fetchers=None, generic=None) -> None:
        """fetchers/generic: injectable for tests (no network)."""
        self.fetchers = fetchers
        self.generic = generic

    def resolve(self, source: str, *, pasted: str | None = None) -> JobPosting:
        raw = source.strip()
        if raw in {"-", "paste"}:
            text = (pasted or "").strip()
            if not text:
                raise ValueError("Paste a job description, or pass a URL / file path.")
            return JobPosting(url="", source="paste", raw_text=text)

        if raw.lower().startswith(("http://", "https://")):
            return self.fetch_url(raw)

        path = ResumePathResolver().resolve(raw)
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            return JobPosting(url=str(path), source="file", raw_text=text)

        raise ValueError(f"Not a URL or file: {source}. Use a http(s) URL, a text file, or '-' to paste.")

    def fetch_url(self, url: str) -> JobPosting:
        """Board API first (cleanest text); if that fails, the page itself."""
        from app.fetching.ashby import AshbyFetcher
        from app.fetching.base import FetchError
        from app.fetching.generic import GenericFetcher
        from app.fetching.greenhouse import GreenhouseFetcher
        from app.fetching.lever import LeverFetcher

        for fetcher in self.fetchers or (GreenhouseFetcher(), LeverFetcher(), AshbyFetcher()):
            if fetcher.handles(url):
                try:
                    return fetcher.fetch(url)
                except FetchError:
                    break  # e.g. guessed board was wrong: the page may still work
        return (self.generic or GenericFetcher()).fetch(url)
