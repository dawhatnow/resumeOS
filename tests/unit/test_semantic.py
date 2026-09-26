import numpy as np

from app.analyzing.semantic import SemanticMatcher
from app.models import Bullet, Item, JobAnalysis, Profile
from app.planning.planner import ResumePlanner

# Fake 3-d "embedding": which topic words a text mentions.
TOPICS = [("ingest", "pipeline", "scrape"), ("dashboard", "report"), ("logo", "brand")]


def fake_embed(texts):
    return [np.array([sum(w in t.lower() for w in words) for words in TOPICS], dtype=float) + 0.01 for t in texts]


def test_bonus_goes_to_bullets_close_in_meaning():
    m = SemanticMatcher(embed=fake_embed)
    out = m.bonuses(
        {"a": "Automated monthly ingestion from an API", "b": "Designed a logo and brand"},
        ["Build data pipelines that scrape and ingest data"],
        [],
    )
    assert out["a"][0] > 1.5 and "pipelines" in out["a"][1]
    assert out["b"] == (0.0, "")


def test_vectors_cached_on_disk(_isolated_resume_home):
    calls = []
    embed = lambda ts: calls.append(list(ts)) or fake_embed(ts)
    SemanticMatcher(embed=embed).bonuses({"a": "ingest data"}, ["ingest pipeline"], [])
    SemanticMatcher(embed=embed).bonuses({"a": "ingest data"}, ["ingest pipeline"], [])
    bullet_calls = [c for c in calls if c == ["ingest data"]]
    assert len(bullet_calls) == 1, "second run reuses the cached bullet vector"


def test_meaning_reorders_bullets_but_not_coverage():
    item = Item(id="exp.1", title="Analyst", bullets=[
        Bullet(id="exp.1.1", text="Designed a logo and brand."),
        Bullet(id="exp.1.2", text="Automated monthly ingestion from the StatCan API."),
    ])
    profile = Profile(experiences=[item])
    analysis = JobAnalysis(must_have=["Python"], keywords=["Python"])
    semantic = {"exp.1.2": (2.0, "Build data pipelines"), "exp.1.1": (0.0, "")}
    plan = ResumePlanner(budget={"experiences": 3, "projects": 3, "bullets_per_item": 1}).plan(analysis, profile, semantic)
    assert plan.selected[0].bullet_ids == ["exp.1.2"]
    assert "close to “Build data pipelines”" in plan.selected[0].reason
    assert plan.coverage == "0/1", "meaning never counts as covering a keyword requirement"
    assert plan.semantic
