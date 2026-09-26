"""Shared pieces for job fetchers: HTTP client, HTML → text, errors."""

import html as html_lib
import re

import httpx
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
# Less than this much text almost always means a JavaScript-rendered page.
MIN_JD_CHARS = 400


class FetchError(Exception):
    pass


class JobFetcher:
    """handles(url) is pure (no network) so routing is testable offline."""

    name = "base"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20.0)

    def handles(self, url: str) -> bool:
        raise NotImplementedError

    def fetch(self, url: str):
        raise NotImplementedError

    def _get(self, url: str, **kwargs) -> httpx.Response:
        try:
            r = self._client.get(url, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            raise FetchError(f"{self.name}: {url} returned HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise FetchError(f"{self.name}: could not fetch {url}: {e}") from e


def html_to_text(markup: str) -> str:
    """Job-description HTML (possibly entity-escaped, as Greenhouse sends it)
    → plain lines, one per paragraph/heading/list item."""
    if "&lt;" in markup and "<" not in markup:
        markup = html_lib.unescape(markup)
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text("\n", strip=False)
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line == "-":  # list-item marker; its text follows on a later line
            out.append("- ")
        elif out and out[-1] == "- ":
            if line:
                out[-1] = f"- {line}"
        elif line or (out and out[-1]):
            out.append(line)
    return "\n".join(l for l in out if l != "- ").strip()
