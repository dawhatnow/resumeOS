from app.importing.profile_builder import ProfileImporter
from app.models import Bullet, EducationEntry, Item, Personal, Profile
from app.warehouse import (
    ProfileMerger,
    add_bullet,
    add_experience,
    add_project,
    format_counts,
    warehouse_counts,
)

SWE = """Jane Doe
jane.doe@example.com | 555-123-4567

Summary
Backend engineer focused on distributed systems.

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 – Present
• Rebuilt the billing pipeline in Go, cutting invoice-generation latency from
12s to 400ms for 50,000+ monthly customers.
• Led migration of the primary datastore from MySQL to PostgreSQL with zero
downtime.

Projects
Task Queue § Code Python, Redis, Docker
• Built a distributed task queue supporting 10,000 jobs/sec.

Technical Skills
Python, Go, SQL, PostgreSQL

Education
State University
Bachelor of Science in Computer Science 2020
"""

DS = """Jane Doe
jane.doe@example.com

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 – Present
• Rebuilt the billing pipeline in Go, cutting invoice-generation latency from 12s to 400ms for 50,000+ monthly customers.
• Built a churn model in Python and pandas that flagged at-risk accounts.

Data Analyst @ Contoso Jan 2019 – May 2020
• Analyzed A/B tests in SQL and Python for 200,000 weekly users.

Projects
Churn Predictor § Code Python, pandas, scikit-learn
• Trained a classification model on 2 years of billing data.

Technical Skills
Python, pandas, SQL, scikit-learn
"""


def _import(text: str) -> Profile:
    return ProfileImporter().import_text(text)


def test_merge_unions_overlap_and_appends_new_lanes():
    merged, report = ProfileMerger().merge(_import(SWE), _import(DS))

    assert report.new_experiences == 1
    assert report.new_projects == 1
    assert report.new_bullets == 3  # new Acme bullet + Contoso bullet + Churn bullet
    assert report.duplicates_skipped == 1
    assert "pandas" in merged.skills
    assert "scikit-learn" in merged.skills

    assert len(merged.experiences) == 2
    acme = next(item for item in merged.experiences if item.org == "Acme Corp")
    assert acme.id == "exp.1"
    assert len(acme.bullets) == 3
    assert any("churn model" in b.text for b in acme.bullets)
    assert [b.id for b in acme.bullets] == ["exp.1.1", "exp.1.2", "exp.1.3"]

    contoso = next(item for item in merged.experiences if item.org == "Contoso")
    assert contoso.id == "exp.2"
    assert contoso.bullets[0].id == "exp.2.1"

    assert len(merged.projects) == 2
    assert {p.title for p in merged.projects} == {"Task Queue", "Churn Predictor"}
    assert any(p.id == "proj.2" for p in merged.projects)


def test_merge_matches_job_case_insensitively():
    base = Profile(
        experiences=[
            Item(
                id="exp.1",
                title="Senior Backend Engineer",
                org="Acme Corp",
                bullets=[Bullet(id="exp.1.1", text="Did billing work.")],
            )
        ]
    )
    incoming = Profile(
        experiences=[
            Item(
                id="exp.9",
                title="senior backend engineer",
                org="acme corp",
                bullets=[Bullet(id="ignored", text="Did billing work.")],
            )
        ]
    )
    merged, report = ProfileMerger().merge(base, incoming)
    assert report.new_experiences == 0
    assert report.duplicates_skipped == 1
    assert len(merged.experiences) == 1


def test_merge_fills_blank_personal_and_keeps_existing_summary():
    base = Profile(personal=Personal(name="Jane"), summary="Keep me")
    incoming = Profile(
        personal=Personal(email="jane@example.com", links=["https://github.com/jane"]),
        summary="Ignore me",
    )
    merged, _ = ProfileMerger().merge(base, incoming)
    assert merged.personal.name == "Jane"
    assert merged.personal.email == "jane@example.com"
    assert merged.personal.links == ["https://github.com/jane"]
    assert merged.summary == "Keep me"


def test_merge_unions_education():
    base = Profile(education=[EducationEntry(school="State U", degree="BS CS", details=["GPA: 3.8"])])
    incoming = Profile(
        education=[
            EducationEntry(school="State U", degree="BS CS", details=["Dean's list"]),
            EducationEntry(school="Other U", degree="MS Stats"),
        ]
    )
    merged, report = ProfileMerger().merge(base, incoming)
    assert report.new_education == 1
    assert merged.education[0].details == ["GPA: 3.8", "Dean's list"]
    assert merged.education[1].school == "Other U"


def test_add_experience_and_bullet_mint_ids():
    profile = _import(SWE)
    job = add_experience(profile, title="Intern", org="Google", bullets=["Wrote dashboards."])
    assert job.id == "exp.2"
    assert job.bullets[0].id == "exp.2.1"
    extra = add_bullet(profile, "exp.1", "Mentored two engineers.")
    assert extra.id == "exp.1.3"


def test_add_project_and_unknown_bullet_id():
    profile = _import(SWE)
    project = add_project(profile, title="Portfolio", tech=["HTML"], bullets=["Shipped a site."])
    assert project.id == "proj.2"
    try:
        add_bullet(profile, "exp.99", "nope")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "exp.99" in str(e)


def test_merge_folds_near_duplicate_job_and_shorter_bullet():
    base = Profile(
        experiences=[
            Item(
                id="exp.1",
                title="Data Governance & Quality Co-op",
                org="Equitable Life of Canada",
                dates="May 2026 – Aug 2026",
                bullets=[
                    Bullet(
                        id="exp.1.1",
                        text="Built a Power BI dashboard tracking completeness, accuracy, and timeliness across source systems.",
                    )
                ],
            )
        ],
        personal=Personal(links=["https://linkedin.com/in/jane", "https://github.com/jane"]),
    )
    incoming = Profile(
        personal=Personal(links=["linkedin.com/in/jane", "https://www.github.com/jane"]),
        experiences=[
            Item(
                id="exp.9",
                title="Data Governance & Quality Co-op | Equitable Life of Canada May 2026 – Aug 2026",
                bullets=[
                    Bullet(
                        id="x",
                        text="Built a Power BI dashboard tracking completeness, accuracy, and timeliness",
                    )
                ],
            )
        ],
    )
    merged, report = ProfileMerger().merge(base, incoming)
    assert report.new_experiences == 0
    assert report.new_bullets == 0
    assert report.duplicates_skipped == 1
    assert len(merged.experiences) == 1
    assert merged.experiences[0].id == "exp.1"
    assert len(merged.personal.links) == 2


def test_merge_skips_garbage_parse_blob():
    base = Profile(
        experiences=[
            Item(id="exp.1", title="Engineer", org="Acme", bullets=[Bullet(id="exp.1.1", text="Did a thing.")])
        ]
    )
    incoming = Profile(
        experiences=[
            Item(
                id="exp.9",
                title="Engineer | Acme Jan 2023 – Present leftover dump of the whole page " + ("x" * 200),
                location="Built a thing then another job title then awards " * 20,
            )
        ]
    )
    merged, report = ProfileMerger().merge(base, incoming)
    assert report.new_experiences == 0
    assert len(merged.experiences) == 1
    assert merged.experiences[0].location is None


def test_merge_collapses_existing_warehouse_duplicates():
    base = Profile(
        experiences=[
            Item(id="exp.1", title="Engineer", org="Acme", bullets=[Bullet(id="exp.1.1", text="Did a thing.")]),
            Item(id="exp.5", title="Engineer @ Acme Jan 2023 – Present", org=None, bullets=[]),
        ]
    )
    merged, report = ProfileMerger().merge(base, Profile())
    assert len(merged.experiences) == 1
    assert merged.experiences[0].id == "exp.1"
    assert report.new_experiences == 0


def test_merge_education_same_school_different_degree_wording():
    base = Profile(education=[EducationEntry(school="University of Guelph", degree="B.Eng. Software")])
    incoming = Profile(
        education=[EducationEntry(school="University of Guelph", degree="Bachelor of Engineering, Software", details=["GPA 3.97"])]
    )
    merged, report = ProfileMerger().merge(base, incoming)
    assert report.new_education == 0
    assert len(merged.education) == 1
    assert "GPA 3.97" in merged.education[0].details


def test_counts_line():
    profile = _import(SWE)
    assert warehouse_counts(profile)["experiences"] == 1
    assert format_counts(profile).startswith("Warehouse:")
