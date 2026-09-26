"""Ashby: public job-board API, no key. https://jobs.ashbyhq.com/<org>/<uuid>"""

import re
from urllib.parse import urlparse

from app.fetching.base import FetchError, JobFetcher, html_to_text
from app.models import JobPosting

_PATH = re.compile(r"^/([^/]+)/([0-9a-f-]{36})")


class AshbyFetcher(JobFetcher):
    name = "ashby"

    def handles(self, url: str) -> bool:
        return urlparse(url).netloc.lower().endswith("ashbyhq.com")

    def fetch(self, url: str) -> JobPosting:
        m = _PATH.match(urlparse(url).path)
        if not m:
            raise FetchError("ashby: couldn't find a job id in that URL")
        org, job_id = m.groups()
        board = self._get(f"https://api.ashbyhq.com/posting-api/job-board/{org}").json()
        job = next((j for j in board.get("jobs", []) if j.get("id") == job_id), None)
        if job is None:
            raise FetchError("ashby: that job isn't on the board anymore (closed or unlisted)")
        head = [(job.get("title") or "").strip(), " — ".join(x for x in [org, job.get("location"), job.get("department")] if x)]
        body = html_to_text(job.get("descriptionHtml") or "") or job.get("descriptionPlain") or ""
        return JobPosting(
            url=url, source="ashby", company=org, title=(job.get("title") or "").strip() or None,
            raw_text="\n".join(head) + "\n\n" + body,
        )
