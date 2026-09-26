import json

import httpx
import pytest

from app.fetching.ashby import AshbyFetcher
from app.fetching.base import FetchError, html_to_text
from app.fetching.generic import GenericFetcher
from app.fetching.greenhouse import GreenhouseFetcher
from app.fetching.lever import LeverFetcher
from app.fetching.router import JobSourceRouter

JD_HTML = "<h3>Requirements</h3><ul><li><p>5+ years of Python</p></li><li>AWS &amp; Terraform</li></ul>" + "<p>More text.</p>" * 40


def client(routes: dict[str, tuple[int, object]]) -> httpx.Client:
    """Fake HTTP: exact URL (without query unless given) → (status, json-or-text)."""
    def handler(request: httpx.Request) -> httpx.Response:
        for key in (str(request.url), str(request.url).split("?")[0]):
            if key in routes:
                status, body = routes[key]
                if isinstance(body, str):
                    return httpx.Response(status, text=body)
                return httpx.Response(status, json=body)
        return httpx.Response(404, json={"error": "not found"})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_routing_is_offline():
    assert GreenhouseFetcher().handles("https://job-boards.greenhouse.io/acme/jobs/123")
    assert GreenhouseFetcher().handles("https://stripe.com/jobs/search?gh_jid=8172508")
    assert LeverFetcher().handles("https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd")
    assert AshbyFetcher().handles("https://jobs.ashbyhq.com/ramp/34413f8d-26bf-4bbc-8ade-eb309a0e2245")
    assert not LeverFetcher().handles("https://example.com/job")


def test_html_to_text_keeps_list_items_and_unescapes():
    assert html_to_text(JD_HTML).startswith("Requirements\n\n- 5+ years of Python\n\n- AWS & Terraform")
    assert html_to_text("&lt;ul&gt;&lt;li&gt;SQL &amp;amp; dbt&lt;/li&gt;&lt;/ul&gt;") == "- SQL & dbt"


def test_greenhouse_board_url_and_company_site_gh_jid():
    job = {"title": " Backend Engineer ", "company_name": "Acme", "location": {"name": "Toronto"},
           "content": JD_HTML.replace("<", "&lt;").replace(">", "&gt;")}
    c = client({"https://boards-api.greenhouse.io/v1/boards/acme/jobs/123": (200, job)})
    p = GreenhouseFetcher(c).fetch("https://job-boards.greenhouse.io/acme/jobs/123")
    assert (p.source, p.company, p.title) == ("greenhouse", "Acme", "Backend Engineer")
    assert "- 5+ years of Python" in p.raw_text
    # company site: board guessed from the domain
    p2 = GreenhouseFetcher(c).fetch("https://www.acme.com/careers?gh_jid=123")
    assert p2.title == "Backend Engineer"


def test_lever_sections_become_headings():
    posting = {"text": "Data Analyst", "categories": {"location": "Toronto", "team": "Data"},
               "descriptionPlain": "We analyze.", "lists": [{"text": "Requirements", "content": "<li>SQL</li><li>Python</li>"}],
               "additionalPlain": "Benefits: dental."}
    c = client({"https://api.lever.co/v0/postings/acme/6ed76ce8-4156-4b60-b120-403538bd66cd": (200, posting)})
    p = LeverFetcher(c).fetch("https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd/apply")
    assert "Requirements\n- SQL" in p.raw_text and "- Python" in p.raw_text and p.title == "Data Analyst"


def test_ashby_finds_job_on_board_or_says_closed():
    jid = "34413f8d-26bf-4bbc-8ade-eb309a0e2245"
    board = {"jobs": [{"id": jid, "title": " Security Engineer ", "location": "NYC", "department": "Eng",
                       "descriptionHtml": JD_HTML}]}
    c = client({"https://api.ashbyhq.com/posting-api/job-board/ramp": (200, board)})
    p = AshbyFetcher(c).fetch(f"https://jobs.ashbyhq.com/ramp/{jid}")
    assert p.title == "Security Engineer" and "AWS & Terraform" in p.raw_text
    with pytest.raises(FetchError, match="closed"):
        AshbyFetcher(c).fetch("https://jobs.ashbyhq.com/ramp/00000000-0000-0000-0000-000000000000")


def test_generic_reads_json_ld_job_posting():
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage"},
        {"@type": "JobPosting", "title": "ML Engineer", "hiringOrganization": {"name": "Acme"}, "description": JD_HTML},
    ]}
    page = f'<html><script type="application/ld+json">{json.dumps(ld)}</script><body><div id="app"></div></body></html>'
    p = GenericFetcher(client({"https://careers.acme.com/job/1": (200, page)})).fetch("https://careers.acme.com/job/1")
    assert (p.title, p.company) == ("ML Engineer", "Acme") and "5+ years of Python" in p.raw_text


def test_generic_thin_js_page_says_paste():
    page = "<html><body><div id='root'></div><script>app()</script></body></html>"
    with pytest.raises(FetchError, match="paste"):
        GenericFetcher(client({"https://x.com/j": (200, page)})).fetch("https://x.com/j")


def test_router_falls_back_to_page_when_board_api_fails():
    page = "<html><body><h1>Backend Engineer</h1>" + "<p>Requirements: Python and AWS.</p>" * 30 + "</body></html>"
    c = client({"https://www.acme.com/careers": (200, page)})  # board API 404s
    router = JobSourceRouter(fetchers=[GreenhouseFetcher(c)], generic=GenericFetcher(c))
    p = router.resolve("https://www.acme.com/careers?gh_jid=999")
    assert p.source == "url" and p.title == "Backend Engineer"
