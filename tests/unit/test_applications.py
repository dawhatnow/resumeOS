from datetime import datetime

import pytest

from app.analyzing.analyzer import _company_line
from app.applications import ApplicationStore
from app.models import Bullet, Item, JobPosting, PlannedPick, Profile, ResumePlan
from app.render import RenderResult
from app.style import ResumeStyle


def _profile() -> Profile:
    return Profile(experiences=[
        Item(id="exp.1", title="Engineer", bullets=[Bullet(id="exp.1.1", text="A."), Bullet(id="exp.1.2", text="B.")]),
        Item(id="exp.2", title="Analyst", bullets=[Bullet(id="exp.2.1", text="C.")]),
    ])


def _save(store, company="Acme", title="Backend Engineer", app_id=None, plan=None):
    plan = plan or ResumePlan(
        selected=[PlannedPick(item_id="exp.1", bullet_ids=["exp.1.2", "exp.1.1"], reason="", score=3.0)],
        excluded=["exp.2"], edits={"exp.1.2": "B, reworded."}, rewritten=["exp.1.2"],
    )
    result = RenderResult(pdf=b"%PDF-1.7 fake", pages=1, font_size=10.0, dropped=["exp.1.1"], data={"name": "X"})
    posting = JobPosting(url="https://x", source="url", company=company, title=title, raw_text="JD text")
    return store.save(posting, plan, ResumeStyle("modern", "teal"), result, _profile(), app_id=app_id)


def test_two_jobs_same_day_get_distinct_ids(tmp_path):
    store = ApplicationStore(tmp_path)
    a, b = _save(store), _save(store)
    assert a.id == f"{datetime.now():%Y-%m-%d}_acme_backend_engineer"
    assert b.id == a.id + "-2"
    assert [x.id for x in store.list()][0] in {a.id, b.id} and len(store.list()) == 2


def test_folder_contents_and_round_trip(tmp_path):
    store = ApplicationStore(tmp_path)
    app = _save(store)
    assert sorted(p.name for p in app.folder.iterdir()) == [
        "diff.yaml", "job.yaml", "meta.yaml", "plan.yaml", "resume.pdf", "resume.yaml"]
    assert store.load_posting(app).raw_text == "JD text"
    plan, style, notes = store.load_plan(app, _profile())
    assert plan.selected[0].bullet_ids == ["exp.1.2", "exp.1.1"]
    assert plan.edits == {"exp.1.2": "B, reworded."} and plan.rewritten == ["exp.1.2"]
    assert style == ResumeStyle("modern", "teal") and notes == []
    assert store.load_render_data(app) == {"name": "X"}


def test_reopen_against_changed_warehouse(tmp_path):
    store = ApplicationStore(tmp_path)
    app = _save(store)
    smaller = _profile()
    smaller.experiences[0].bullets = [Bullet(id="exp.1.1", text="A.")]  # exp.1.2 deleted
    plan, _, notes = store.load_plan(app, smaller)
    assert plan.selected[0].bullet_ids == ["exp.1.1"] and plan.edits == {}
    assert notes == ["exp.1: 1 bullet(s) no longer exist"]


def test_update_in_place_keeps_created_and_status(tmp_path):
    store = ApplicationStore(tmp_path)
    app = _save(store)
    store.set_status(app.id, "applied")
    again = _save(store, app_id=app.id)
    assert again.id == app.id and again.created == app.created and again.status == "applied"
    assert len(store.list()) == 1


def test_require_by_unique_part_and_bad_status(tmp_path):
    store = ApplicationStore(tmp_path)
    a = _save(store, company="Stripe")
    _save(store, company="Ramp")
    assert store.require("stripe").id == a.id
    assert store.require("2").id == store.list()[1].id  # numbers from `resume ls`
    with pytest.raises(KeyError, match="matches 2"):
        store.require("backend")
    with pytest.raises(KeyError, match="No application"):
        store.require("nope")
    with pytest.raises(ValueError):
        store.set_status(a.id, "ghosted")


def test_company_from_posting_header():
    assert _company_line(["ShyftLabs — Toronto, ON"]) == "ShyftLabs"
    assert _company_line(["Moneris | Etobicoke"]) == "Moneris"
    assert _company_line(["Source: Indeed JOBSEARCH_100022, posted 2026-09-16"]) is None
