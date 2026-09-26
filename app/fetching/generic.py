"""Any other job page: schema.org JobPosting data first, visible text second.

Many JavaScript-heavy career sites (Workday, SmartRecruiters, iCIMS, company
sites) still embed a JSON-LD JobPosting for search engines, so the JD is
readable without running JavaScript. If neither yields a real description,
say so instead of matching against a page of navigation links.
"""

import json

from bs4 import BeautifulSoup

from app.fetching.base import MIN_JD_CHARS, FetchError, JobFetcher, html_to_text
from app.models import JobPosting

__all__ = ["FetchError", "GenericFetcher"]

_STRIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "svg"}


class GenericFetcher(JobFetcher):
    name = "web"

    def handles(self, url: str) -> bool:
        return url.lower().startswith(("http://", "https://"))

    def fetch(self, url: str) -> JobPosting:
        page = self._get(url).text
        soup = BeautifulSoup(page, "html.parser")
        if (posting := _json_ld_posting(soup, url)) is not None:
            return posting
        for tag in soup(_STRIP_TAGS):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        heading = soup.find(["h1", "h2"])
        raw = soup.get_text("\n", strip=True)
        if len(raw) < MIN_JD_CHARS:
            raise FetchError(
                "That page loads the job with JavaScript, so there's almost no text to read. "
                "Copy the job description and paste it instead."
            )
        return JobPosting(url=url, source="url", title=(heading.get_text(" ", strip=True) if heading else None) or title, raw_text=raw)


def _json_ld_posting(soup: BeautifulSoup, url: str) -> JobPosting | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _nodes(data):
            types = node.get("@type")
            if "JobPosting" not in (types if isinstance(types, list) else [types]):
                continue
            body = html_to_text(str(node.get("description") or ""))
            if len(body) < MIN_JD_CHARS // 2:
                continue
            org = node.get("hiringOrganization")
            company = org.get("name") if isinstance(org, dict) else org if isinstance(org, str) else None
            title = node.get("title")
            head = "\n".join(x for x in [title, company] if x)
            return JobPosting(url=url, source="url", company=company, title=title, raw_text=f"{head}\n\n{body}")
    return None


def _nodes(data):
    """JSON-LD may be one object, a list, or an @graph."""
    if isinstance(data, list):
        for item in data:
            yield from _nodes(item)
    elif isinstance(data, dict):
        yield data
        if isinstance(data.get("@graph"), list):
            yield from _nodes(data["@graph"])
