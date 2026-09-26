from pathlib import Path

from app.analyzing.analyzer import JobAnalyzer
from app.analyzing.cleaner import JobDescriptionCleaner
from app.analyzing.keywords import KeywordMatcher
from app.apply import JobMatcher
from app.fetching.router import JobSourceRouter
from app.importing.profile_builder import ProfileImporter
from app.models import Item, JobPosting, Profile
from app.planning.planner import ResumePlanner

SWE = """Jane Doe
jane@example.com

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 – Present
• Rebuilt the billing pipeline in Go, cutting invoice latency from 12s to 400ms.
• Led migration from MySQL to PostgreSQL.

Projects
Task Queue § Code Python, Redis, Docker
• Built a distributed task queue supporting 10,000 jobs/sec.

Technical Skills
Python, Go, SQL, PostgreSQL
"""

DS = """Jane Doe
jane@example.com

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 – Present
• Built a churn model in Python and pandas that flagged at-risk accounts.

Data Analyst @ Contoso Jan 2019 – May 2020
• Analyzed A/B tests in SQL and Python for 200,000 weekly users.

Projects
Churn Predictor § Code Python, pandas, scikit-learn
• Trained a classification model on 2 years of billing data.

Technical Skills
Python, pandas, SQL, scikit-learn
"""

DS_JD = """Data Scientist
Requirements
Experience with pandas, scikit-learn, and SQL required.
Nice to have
Docker
"""


def _warehouse() -> Profile:
    from app.warehouse import ProfileMerger

    base = ProfileImporter().import_text(SWE)
    merged, _ = ProfileMerger().merge(base, ProfileImporter().import_text(DS))
    return merged


def test_cleaner_drops_cookie_chrome():
    text = JobDescriptionCleaner().clean("Cookie settings\nReal requirement: Python\nApply now")
    assert "Python" in text
    assert "Cookie" not in text
    assert "Apply now" not in text


def test_postgres_alias_hits_vocabulary():
    must, _, _ = KeywordMatcher().match(
        "Requirements\nMust know Postgres and k8s.\n",
        ["PostgreSQL", "Kubernetes"],
    )
    assert "PostgreSQL" in must
    assert "Kubernetes" in must


def test_ds_jd_ranks_ds_items_first():
    profile = _warehouse()
    posting = JobPosting(url="", source="paste", raw_text=DS_JD)
    analysis = JobAnalyzer().analyze(posting, profile)
    plan = ResumePlanner().plan(analysis, profile)

    assert "pandas" in analysis.must_have
    assert plan.must_have_total >= 1
    top = plan.selected[0]
    assert top.item_id in {"exp.2", "proj.2", "exp.1"}
    ds_ids = {p.item_id for p in plan.selected}
    assert "exp.2" in ds_ids or "proj.2" in ds_ids
    scores = plan.scores
    assert scores.get("proj.2", 0) >= scores.get("proj.1", 0)


def test_weak_match_still_picks():
    profile = Profile(
        experiences=[Item(id="exp.1", title="Cashier", org="Shop", bullets=[])],
        projects=[],
        vocabulary=["Python"],
    )
    # add a bullet without touching warehouse.py helpers
    from app.models import Bullet

    profile.experiences[0].bullets = [Bullet(id="exp.1.1", text="Stocked shelves.")]
    posting = JobPosting(url="", source="paste", raw_text="Requirements\nNeed Rust and Kafka experts.\n")
    analysis = JobAnalyzer().analyze(posting, profile)
    plan = ResumePlanner().plan(analysis, profile)
    assert plan.selected
    assert plan.selected[0].item_id == "exp.1"


def test_router_reads_file(tmp_path):
    jd = tmp_path / "job.txt"
    jd.write_text(DS_JD)
    posting = JobSourceRouter().resolve(str(jd))
    assert posting.source == "file"
    assert "pandas" in posting.raw_text


def test_router_paste():
    posting = JobSourceRouter().resolve("-", pasted=DS_JD)
    assert posting.source == "paste"
    assert "scikit-learn" in posting.raw_text


def test_matcher_from_file(tmp_path):
    jd = tmp_path / "job.txt"
    jd.write_text(DS_JD)
    posting, analysis, plan = JobMatcher().run(str(jd), _warehouse())
    assert analysis.keywords
    assert plan.selected
    assert "/" in plan.coverage


# --- regression: matcher accuracy ---

from app.analyzing.terms import TermIndex
from app.models import Bullet

BACKEND_JD = """Software Engineer, Backend
About the team
You have the chance to work on systems that go global. We use Node.js services.
Requirements: 3+ years with Python and C++
- Experience with Kubernetes, Kafka and AWS
- Strong SQL and PostgreSQL skills
Nice to have
- Go, Terraform
Benefits
- Free lunch, Docker-themed swag, Excel stipend
"""


def test_cpp_and_csharp_match_and_do_not_leak_c():
    index = TermIndex(["C", "C++"])
    assert index.find("Strong C++ and C# skills") == ["c++", "c#"]
    assert index.find("Built it in C++20.") == ["c++"]
    assert index.find("Wrote a kernel in C, then Python.") == ["c", "python"]


def test_ambiguous_short_terms_need_tech_context():
    index = TermIndex([])
    assert index.find("Go to market and report to the C-suite on R&D.") == []
    assert index.find("Services written in Go and R.") == ["go", "r"]
    assert index.find("a graph node") == []
    assert index.find("Node.js APIs") == ["node.js", "apis"]  # not JavaScript via "js"


def test_aliases_resolve_both_ways_to_user_display():
    must, _, _ = KeywordMatcher().match("Requirements\nGo and Postgres\n", ["Golang", "PostgreSQL"])
    assert must == ["Golang", "PostgreSQL"]


def test_inline_heading_keeps_its_content():
    must, _, _ = KeywordMatcher().match("Requirements: Python and Rust\n", [])
    assert must == ["Python", "Rust"]


def test_benefits_section_is_ignored_and_sentences_are_not_headings():
    must, nice, keywords = KeywordMatcher().match(BACKEND_JD, ["Docker", "Excel"])
    assert must == ["Python", "C++", "Kubernetes", "Kafka", "AWS", "SQL", "PostgreSQL"]
    assert nice == ["Go", "Terraform"]
    assert "Docker" not in keywords and "Excel" not in keywords
    assert "Node.js" in keywords


def test_missing_reports_requirements_outside_warehouse():
    profile = Profile(
        experiences=[Item(id="exp.1", title="Engineer", bullets=[Bullet(id="exp.1.1", text="Built APIs in Python on AWS.")])],
        skills=["Python"],
        vocabulary=["Python"],
    )
    analysis = JobAnalyzer().analyze(JobPosting(url="", source="paste", raw_text=BACKEND_JD), profile)
    # AWS is only in bullet text, still counts as backed up.
    assert analysis.missing == ["C++", "Kubernetes", "Kafka", "SQL", "PostgreSQL"]
    plan = ResumePlanner().plan(analysis, profile)
    assert plan.coverage == "2/7"


def test_bullet_count_does_not_beat_relevance():
    many = Item(id="proj.1", title="Busy", bullets=[Bullet(id=f"proj.1.{i}", text="Used Python.") for i in range(1, 5)])
    focused = Item(id="proj.2", title="Fit", bullets=[Bullet(id="proj.2.1", text="Ran Kafka on Kubernetes with Python.")])
    profile = Profile(projects=[many, focused], vocabulary=["Python", "Kafka", "Kubernetes"])
    analysis = JobAnalyzer().analyze(JobPosting(url="", source="paste", raw_text=BACKEND_JD), profile)
    plan = ResumePlanner().plan(analysis, profile)
    assert [p.item_id for p in plan.selected] == ["proj.2", "proj.1"]


def test_bullets_within_item_are_ranked_by_their_own_text():
    item = Item(
        id="proj.1",
        title="Svc",
        tech=["Kafka"],
        bullets=[Bullet(id="proj.1.1", text="Wrote docs."), Bullet(id="proj.1.2", text="Tuned PostgreSQL.")],
    )
    profile = Profile(projects=[item], vocabulary=["Kafka", "PostgreSQL"])
    analysis = JobAnalyzer().analyze(JobPosting(url="", source="paste", raw_text=BACKEND_JD), profile)
    plan = ResumePlanner(budget={"experiences": 3, "projects": 3, "bullets_per_item": 1}).plan(analysis, profile)
    assert plan.selected[0].bullet_ids == ["proj.1.2"]


def test_user_aliases_file(_isolated_resume_home):
    vocab = _isolated_resume_home / "vocab"
    vocab.mkdir()
    (vocab / "aliases.yaml").write_text("Kubernetes: [kube]\nGenesys Cloud: []\n")
    index = TermIndex([])
    assert index.find("Ran kube clusters and Genesys Cloud queues.") == ["kubernetes", "genesys cloud"]
    assert index.display("genesys cloud") == "Genesys Cloud"
