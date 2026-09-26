"""Live job boards. Not in the default run: pytest -m network

Picks a currently open job from each board's public list, so these don't
rot when one posting closes.
"""

import httpx
import pytest

from app.analyzing.analyzer import JobAnalyzer
from app.fetching.router import JobSourceRouter
from app.models import Profile

pytestmark = pytest.mark.network


def _first(url: str, pick):
    return pick(httpx.get(url, timeout=20).json())


@pytest.mark.parametrize(
    "board_url, pick",
    [
        ("https://boards-api.greenhouse.io/v1/boards/stripe/jobs", lambda d: d["jobs"][0]["absolute_url"]),
        ("https://api.lever.co/v0/postings/palantir?mode=json&limit=1", lambda d: d[0]["hostedUrl"]),
        ("https://api.ashbyhq.com/posting-api/job-board/ramp", lambda d: d["jobs"][0]["jobUrl"]),
    ],
)
def test_real_board_url_to_analysis(board_url, pick):
    url = _first(board_url, pick)
    posting = JobSourceRouter().resolve(url)
    assert posting.source in {"greenhouse", "lever", "ashby"}
    assert posting.title and len(posting.raw_text) > 1000
    JobAnalyzer().analyze(posting, Profile(vocabulary=["Python"]))  # parses without error
