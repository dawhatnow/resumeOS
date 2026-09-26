"""Fetch a public job URL to visible text. No board-specific APIs (that's M5)."""

import httpx
from bs4 import BeautifulSoup

from app.models import JobPosting

_STRIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "svg"}
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class FetchError(Exception):
    pass


class GenericFetcher:
    def fetch(self, url: str) -> JobPosting:
        try:
            response = httpx.get(url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=20.0)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise FetchError(f"Could not fetch {url}: {e}") from e

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(_STRIP_TAGS):
            tag.decompose()
        title = (soup.title.string.strip() if soup.title and soup.title.string else None)
        heading = soup.find(["h1", "h2"])
        heading_text = heading.get_text(" ", strip=True) if heading else None
        raw = soup.get_text("\n", strip=True)
        return JobPosting(
            url=url,
            source="url",
            title=heading_text or title,
            raw_text=raw,
        )
