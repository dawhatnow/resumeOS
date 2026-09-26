"""Greenhouse: public board API, no key.

URL shapes:
  https://boards.greenhouse.io/<board>/jobs/<id>
  https://job-boards.greenhouse.io/<board>/jobs/<id>   (also .eu.)
  https://<company site>/...?gh_jid=<id>               (board guessed from the domain)
"""

import re
from urllib.parse import parse_qs, urlparse

from app.fetching.base import FetchError, JobFetcher, html_to_text
from app.models import JobPosting

_PATH = re.compile(r"^/(?:embed/job_app\?for=)?([\w-]+)/jobs/(\d+)")


class GreenhouseFetcher(JobFetcher):
    name = "greenhouse"

    def handles(self, url: str) -> bool:
        u = urlparse(url)
        return "greenhouse.io" in u.netloc or "gh_jid" in parse_qs(u.query)

    def fetch(self, url: str) -> JobPosting:
        u = urlparse(url)
        query = parse_qs(u.query)
        api = "https://boards-api.eu.greenhouse.io" if ".eu." in u.netloc else "https://boards-api.greenhouse.io"
        if m := _PATH.match(u.path):
            candidates, job_id = [m.group(1)], m.group(2)
        elif "for" in query and "token" in query:  # embed/job_app?for=<board>&token=<id>
            candidates, job_id = [query["for"][0]], query["token"][0]
        elif "gh_jid" in query:
            job_id = query["gh_jid"][0]
            host = u.netloc.lower().removeprefix("www.").split(".")
            candidates = list(dict.fromkeys([host[0], host[-2] if len(host) > 1 else host[0]]))
        else:
            raise FetchError("greenhouse: couldn't find a job id in that URL")
        last_error: FetchError | None = None
        for board in candidates:
            try:
                data = self._get(f"{api}/v1/boards/{board}/jobs/{job_id}").json()
            except FetchError as e:
                last_error = e
                continue
            location = (data.get("location") or {}).get("name")
            body = html_to_text(data.get("content") or "")
            head = [data.get("title") or "", " — ".join(x for x in [data.get("company_name"), location] if x)]
            return JobPosting(
                url=url,
                source="greenhouse",
                company=data.get("company_name") or board,
                title=(data.get("title") or "").strip() or None,
                raw_text="\n".join(h for h in head if h) + "\n\n" + body,
            )
        raise last_error or FetchError("greenhouse: job not found")
