"""Live network tests against real URLs. Not run by default in CI-like
environments without internet access — run explicitly with:
    pytest tests/integration/test_fetching_live.py -m network
Sites' HTML can change or start blocking bots over time; if a test here
starts failing, check whether the target page itself changed before
assuming the fetcher regressed.
"""

import pytest

from app.fetching.base import FetchError
from app.fetching.generic import GenericFetcher
from app.fetching.router import JobFetcherRouter

pytestmark = pytest.mark.network

JOB_POSTING_URL = (
    "https://weworkremotely.com/remote-jobs/"
    "track-it-forward-lead-developer-rebuild-modernize-scale-social-good-saas-remote"
)
JOB_LISTING_PAGE_URL = "https://www.python.org/jobs/"
GREENHOUSE_URL = "https://job-boards.greenhouse.io/stripe"


def test_fetches_real_job_posting_text():
    posting = GenericFetcher().fetch(JOB_POSTING_URL)
    assert posting.title
    assert len(posting.clean_text) > 500
    assert "Track it Forward" in posting.clean_text


def test_fetches_real_listing_page():
    posting = GenericFetcher().fetch(JOB_LISTING_PAGE_URL)
    assert posting.title
    assert len(posting.clean_text) > 500


def test_router_dispatches_greenhouse_url_to_stub():
    """Greenhouse fetcher isn't implemented yet; the router should still
    correctly recognize the platform and raise the honest stub error rather
    than silently falling through to the generic fetcher."""
    with pytest.raises(NotImplementedError):
        JobFetcherRouter().fetch(GREENHOUSE_URL)


def test_404_raises_fetch_error_not_a_crash():
    with pytest.raises(FetchError):
        GenericFetcher().fetch("https://www.python.org/jobs/nonexistent-404-test/")


def test_unresolvable_domain_raises_fetch_error_not_a_crash():
    with pytest.raises(FetchError):
        GenericFetcher().fetch("https://this-domain-does-not-exist-asdkjhaskd12345.com/")
