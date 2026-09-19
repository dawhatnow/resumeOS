from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.fetching.base import FetchError, JobFetcher
from app.models import JobPosting

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "noscript", "svg", "form")


class GenericFetcher(JobFetcher):
    """Fallback for any URL not handled by a platform-specific fetcher: fetch
    HTML with httpx and extract the main text with BeautifulSoup. Always
    handles() True since it's the last resort in JobFetcherRouter's chain.

    Playwright fallback for JavaScript-only pages isn't implemented yet —
    on those pages clean_text will come back thin or empty."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def handles(self, url: str) -> bool:
        return True

    def fetch(self, url: str) -> JobPosting:
        html = self._download(url)
        soup = BeautifulSoup(html, "html.parser")

        return JobPosting(
            url=url,
            source="generic",
            company=self._meta(soup, "og:site_name"),
            title=self._title(soup),
            raw_text=html,
            clean_text=self._extract_text(soup),
            fetched_at=datetime.now(timezone.utc),
        )

    def _download(self, url: str) -> str:
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=self._timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise FetchError(f"Failed to fetch {url}: {e}") from e
        return response.text

    def _title(self, soup: BeautifulSoup) -> str | None:
        og_title = self._meta(soup, "og:title")
        if og_title:
            return og_title
        return soup.title.get_text(strip=True) if soup.title else None

    def _meta(self, soup: BeautifulSoup, property_name: str) -> str | None:
        tag = soup.find("meta", property=property_name)
        return tag.get("content", "").strip() or None if tag else None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        for tag in soup.find_all(_STRIP_TAGS):
            tag.decompose()
        lines = (line.strip() for line in soup.get_text("\n").splitlines())
        return "\n".join(line for line in lines if line)
