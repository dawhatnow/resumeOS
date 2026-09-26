import json

import pytest

from app.ai.provider import LLMProvider, NullProvider, OpenAICompatibleProvider, ProviderError, load_provider
from app.ai.writer import BulletWriter, _parse
from app.guard import TruthGuard
from app.models import Bullet, Item, JobAnalysis, JobPosting, PlannedPick, Profile, ResumePlan
from app.review import PlanReviewer

ORIGINAL = "Built a queue in Python and Redis handling 10,000 jobs/sec for 3 teams."


def _profile() -> Profile:
    return Profile(
        experiences=[Item(id="exp.1", title="Engineer", tech=["Python", "Redis"], bullets=[
            Bullet(id="exp.1.1", text=ORIGINAL),
            Bullet(id="exp.1.2", text="Wrote internal docs for the platform team."),
        ])],
        projects=[Item(id="proj.1", title="Site", tech=["React"], bullets=[Bullet(id="proj.1.1", text="Built a React site.")])],
        skills=["Python", "Redis", "React"],
        vocabulary=["Python", "Redis", "React"],
    )


ANALYSIS = JobAnalysis(must_have=["Python", "Redis", "Kafka"], keywords=["Python", "Redis", "Kafka"])
POSTING = JobPosting(url="", source="paste", title="Backend Engineer")


class Scripted(LLMProvider):
    """Returns canned replies in order; records what it was sent."""

    name, model = "fake", "m"

    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.sent: list[dict] = []

    def complete(self, system: str, user: str) -> str:
        self.sent.append(json.loads(user))
        return json.dumps(self.replies.pop(0))


def _reply(**texts: str) -> dict:
    return {"bullets": [{"id": k.replace("_", "."), "text": v} for k, v in texts.items()]}


def test_honest_rewrite_accepted_in_one_call():
    good = "Built a Python and Redis job queue handling 10,000 jobs/sec for 3 teams."
    llm = Scripted(_reply(exp_1_1=good))
    r = BulletWriter(llm, _profile()).rewrite(["exp.1.1"], ANALYSIS, POSTING)
    assert r.accepted == {"exp.1.1": good} and r.calls == 1
    sent = llm.sent[0]["bullets"][0]
    assert sent["may_use"] == ["Python", "Redis"]  # Kafka isn't backed by this job
    assert sent["max_chars"] > 0


def test_invented_facts_retry_once_then_keep_original():
    bad = "Built a Kafka queue in Python and Redis handling 10,000 jobs/sec for 30 teams."
    llm = Scripted(_reply(exp_1_1=bad), _reply(exp_1_1=bad))
    r = BulletWriter(llm, _profile()).rewrite(["exp.1.1"], ANALYSIS, POSTING)
    assert r.calls == 2 and "exp.1.1" in r.rejected and not r.accepted
    retry = llm.sent[1]["bullets"][0]
    assert retry["previous_attempt"] == bad
    assert any("30" in p for p in retry["problems"]) and any("Kafka" in p for p in retry["problems"])


def test_retry_fixes_it():
    bad = "Built a queue in Python handling many jobs."  # lost numbers + Redis
    good = "Built a Python and Redis queue handling 10,000 jobs/sec for 3 teams."
    r = BulletWriter(Scripted(_reply(exp_1_1=bad), _reply(exp_1_1=good)), _profile()).rewrite(
        ["exp.1.1"], ANALYSIS, POSTING
    )
    assert r.accepted == {"exp.1.1": good} and r.calls == 2


def test_rewrite_may_not_drop_numbers_or_job_keywords():
    g = TruthGuard(_profile())
    problems = g.check_rewrite("exp.1.1", "Built a Python queue for teams.", ["Python", "Redis"])
    assert any("10000" in p and "3" in p for p in problems)
    assert any("Redis" in p for p in problems)
    # your own edit may trim
    assert g.check_bullet("exp.1.1", "Built a Python queue for teams.") == []


def test_unchanged_and_missing_answers():
    llm = Scripted(_reply(exp_1_1=ORIGINAL + " "), _reply())  # exp.1.2 missing twice
    r = BulletWriter(llm, _profile()).rewrite(["exp.1.1", "exp.1.2"], ANALYSIS, POSTING)
    assert r.unchanged == ["exp.1.1"]
    assert r.rejected == {"exp.1.2": ["No rewrite returned for this bullet."]}


def test_parse_tolerates_fences_and_id_map():
    assert _parse('```json\n{"bullets": [{"id": "a", "text": "x"}]}\n```') == {"a": "x"}
    assert _parse('Sure! {"a": "x"}') == {"a": "x"}
    with pytest.raises(ProviderError):
        _parse("no json here")


def test_review_rewrite_marks_and_reset_all():
    good = "Built a Python and Redis job queue handling 10,000 jobs/sec for 3 teams."
    p = _profile()
    plan = ResumePlan(selected=[PlannedPick(item_id="exp.1", bullet_ids=["exp.1.1", "exp.1.2"], reason="")])
    writer = BulletWriter(Scripted(_reply(exp_1_1=good, exp_1_2="Wrote internal docs for the platform team.")), p)
    feed = iter(["rewrite exp.1", ""])
    out = PlanReviewer(
        p, plan, prompt=lambda *a, **k: next(feed),
        rewriter=lambda ids: writer.rewrite(ids, ANALYSIS, POSTING),
    ).run()
    assert out.edits == {"exp.1.1": good} and out.rewritten == ["exp.1.1"]

    feed2 = iter(["reset all", ""])
    out2 = PlanReviewer(p, out, prompt=lambda *a, **k: next(feed2)).run()
    assert out2.edits == {} and out2.rewritten == []


def test_review_rewrite_leaves_your_edits_alone():
    p = _profile()
    plan = ResumePlan(
        selected=[PlannedPick(item_id="exp.1", bullet_ids=["exp.1.1"], reason="")],
        edits={"exp.1.1": "Built a Python queue handling 10,000 jobs/sec for 3 teams."},
    )
    called = []
    feed = iter(["rewrite", ""])
    PlanReviewer(p, plan, prompt=lambda *a, **k: next(feed), rewriter=lambda ids: called.append(ids)).run()
    assert called == []


def test_load_provider_config_and_keys(tmp_path, monkeypatch):
    for var in ("RESUME_LLM_PROVIDER", "RESUME_LLM_MODEL", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    cfg = tmp_path / "config.toml"

    p = load_provider(cfg)  # no file → ollama default
    assert isinstance(p, OpenAICompatibleProvider) and p.name == "ollama" and p.local

    cfg.write_text('[llm]\nprovider = "groq"\n')
    with pytest.raises(ProviderError, match="GROQ_API_KEY"):
        load_provider(cfg)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert load_provider(cfg).name == "groq"

    cfg.write_text('[llm]\nprovider = "none"\n')
    assert isinstance(load_provider(cfg), NullProvider)

    monkeypatch.setenv("RESUME_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("RESUME_LLM_MODEL", "llama3.1")
    assert load_provider(cfg).label == "ollama/llama3.1"


def test_unreachable_server_is_a_clear_error():
    p = OpenAICompatibleProvider("ollama", "http://127.0.0.1:9", "m", None, local=True, timeout=2)
    with pytest.raises(ProviderError, match="ollama serve"):
        p.complete("s", "u")
