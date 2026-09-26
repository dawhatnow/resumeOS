"""Matcher evals on real job postings (tests/evals/postings/*.txt).

Two layers:
- JD side: what the posting asks for. Empty vocabulary, so it only depends
  on the lexicon + section parsing. Always runs.
- Warehouse side: what's missing and which items get picked for *your*
  warehouse (~/.resume/profile.yaml). Skipped if there is no warehouse. If
  you change the warehouse, re-check these by hand and update them.

To add a posting: save the JD text in postings/, run
`python -m tests.evals.report postings/<file>.txt`, check the output
against the posting yourself, then add an entry to CASES.
"""

from pathlib import Path

import pytest

from app.analyzing.analyzer import JobAnalyzer
from app.analyzing.cleaner import JobDescriptionCleaner
from app.analyzing.keywords import KeywordMatcher
from app.models import JobPosting
from app.planning.planner import ResumePlanner
from app.store import ProfileStore

POSTINGS = Path(__file__).parent / "postings"

# must / nice: terms that must appear in that list. not_must: must not.
# missing: exact. top_projects / top_experiences: first-ranked items, in order.
CASES = {
    "infotrack_full_stack_developer.txt": {
        "must": ["React", "TypeScript", "HTML", "CSS", "C#", ".NET", "PostgreSQL", "MySQL"],
        "nice": ["AWS", "Microsoft Azure", "GCP", "Docker", "Kubernetes", "CI/CD"],
        "not_must": ["Redux"],  # "Our stack" section, not a requirement
        "missing": ["C#", ".NET"],  # MySQL is "e.g." with PostgreSQL
        "top_projects": ["proj.4"],
        "top_experiences": ["exp.2"],
    },
    "moneris_business_data_analyst.txt": {
        "must": ["SQL", "Excel", "Tableau", "Power BI", "dashboards"],
        "nice": ["Python", "Snowflake", "dbt", "statistics"],  # "would set you apart"
        "not_must": ["Python", "Snowflake", "dbt", "statistics", "Documentation"],
        "missing": [],  # Tableau "or similar" to Power BI
        "top_experiences": ["exp.1", "exp.3"],
    },
    "paradigm_junior_technical_analyst.txt": {
        "must": ["Python", "SQL", "APIs"],
        "not_must": [],
        "missing": [],
        "top_projects": ["proj.4"],  # the LLM project
        "top_experiences": ["exp.2"],
    },
    "scotiabank_data_analyst.txt": {
        "must": ["SQL", "Excel", "dashboards"],
        "nice": ["Python", "Power BI", "Tableau", "SAS", "VBA", "ETL"],
        "not_must": ["Python", "Power BI"],
        "missing": [],
        "top_experiences_set": {"exp.1", "exp.3"},  # both data/BI roles, either order
    },
    "shyftlabs_associate_ai_engineer.txt": {
        "must": ["Python", "PyTorch", "TensorFlow", "scikit-learn", "SQL", "AWS", "REST", "LLM"],
        "nice": ["JavaScript", "TypeScript", "Node.js", "Docker", "Git", "Kafka"],  # "an asset"
        "not_must": ["JavaScript", "Node.js", "Documentation"],
        "missing": ["microservices", "REST", "Agile"],  # TensorFlow/sklearn: "or" with PyTorch
        "top_projects": ["proj.1", "proj.4", "proj.2"],  # the three AI/ML projects
        "top_experiences": ["exp.2"],
    },
}


def _text(name: str) -> str:
    return JobDescriptionCleaner().clean((POSTINGS / name).read_text())


def test_every_posting_has_a_case():
    assert sorted(p.name for p in POSTINGS.glob("*.txt")) == sorted(CASES)


@pytest.mark.parametrize("name", sorted(CASES))
def test_jd_side(name):
    case = CASES[name]
    must, nice, _ = KeywordMatcher().match(_text(name), [])
    assert [t for t in case["must"] if t not in must] == [], f"must-haves not found; got {must}"
    assert [t for t in case.get("nice", []) if t not in nice] == [], f"nice-to-haves not found; got {nice}"
    assert [t for t in case["not_must"] if t in must] == [], f"wrongly required; got {must}"


@pytest.fixture(scope="module")
def warehouse():
    store = ProfileStore()
    if not store.exists():
        pytest.skip("no warehouse at ~/.resume/profile.yaml")
    return store.load()


@pytest.mark.parametrize("name", sorted(CASES))
def test_warehouse_side(name, warehouse):
    case = CASES[name]
    posting = JobPosting(url=name, source="file", raw_text=(POSTINGS / name).read_text())
    analysis = JobAnalyzer().analyze(posting, warehouse)
    plan = ResumePlanner().plan(analysis, warehouse)
    assert analysis.missing == case["missing"]

    exp_ids = [p.item_id for p in plan.selected if p.item_id.startswith("exp.")]
    proj_ids = [p.item_id for p in plan.selected if p.item_id.startswith("proj.")]
    if "top_projects" in case:
        assert proj_ids[: len(case["top_projects"])] == case["top_projects"], plan.selected
    if "top_experiences" in case:
        assert exp_ids[: len(case["top_experiences"])] == case["top_experiences"], plan.selected
    if "top_experiences_set" in case:
        assert set(exp_ids[: len(case["top_experiences_set"])]) == case["top_experiences_set"]


@pytest.mark.parametrize("name", sorted(CASES))
def test_spec_targets_one_page_and_nothing_invented(name, warehouse):
    """Spec eval targets: 100% one-page, 0 truth violations — without AI rewriting."""
    import io

    from pypdf import PdfReader

    from app.render import ResumeRenderer

    posting = JobPosting(url=name, source="file", raw_text=(POSTINGS / name).read_text())
    analysis = JobAnalyzer().analyze(posting, warehouse)
    plan = ResumePlanner().plan(analysis, warehouse)
    result = ResumeRenderer().fit(warehouse, plan, analysis.keywords)

    assert len(PdfReader(io.BytesIO(result.pdf)).pages) == 1
    sources = {b.text for i in warehouse.all_items() for b in i.bullets}
    printed = [b for s in result.data["sections"] if s["kind"] == "items" for e in s["entries"] for b in e["bullets"]]
    assert printed and all(b in sources for b in printed), "a printed bullet isn't in the warehouse"
    skills = next(s for s in result.data["sections"] if s["kind"] == "skills")["entries"]
    assert set(skills) <= set(warehouse.skills), "a printed skill isn't in the warehouse"
