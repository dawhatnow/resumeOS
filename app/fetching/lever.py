"""Lever: public postings API, no key. https://jobs.lever.co/<company>/<uuid>"""

import re
from urllib.parse import urlparse

from app.fetching.base import FetchError, JobFetcher, html_to_text
from app.models import JobPosting

_PATH = re.compile(r"^/([\w.-]+)/([0-9a-f-]{36})")


class LeverFetcher(JobFetcher):
    name = "lever"

    def handles(self, url: str) -> bool:
        return urlparse(url).netloc.lower().endswith("lever.co")

    def fetch(self, url: str) -> JobPosting:
        u = urlparse(url)
        m = _PATH.match(u.path)
        if not m:
            raise FetchError("lever: couldn't find a posting id in that URL")
        company, posting_id = m.groups()
        api = "https://api.eu.lever.co" if ".eu." in u.netloc else "https://api.lever.co"
        data = self._get(f"{api}/v0/postings/{company}/{posting_id}").json()
        cats = data.get("categories") or {}
        parts = [data.get("text") or "", " — ".join(x for x in [company, cats.get("location"), cats.get("team")] if x), ""]
        parts.append(data.get("descriptionPlain") or html_to_text(data.get("description") or ""))
        for section in data.get("lists") or []:  # "Requirements", "Nice to have", …
            parts += ["", section.get("text") or "", html_to_text(section.get("content") or "")]
        parts += ["", data.get("additionalPlain") or ""]
        return JobPosting(
            url=url, source="lever", company=company, title=(data.get("text") or "").strip() or None,
            raw_text="\n".join(parts).strip(),
        )
