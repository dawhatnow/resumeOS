from app.importing.profile_builder import ProfileImporter

SAMPLE_RESUME = """Jane Doe
jane.doe@example.com | 555-123-4567

Summary
Backend engineer focused on distributed systems and developer tooling.

Experience
Senior Backend Engineer @ Acme Corp Jan 2023 – Present
Remote
• Rebuilt the billing pipeline in Go, cutting invoice-generation latency from
12s to 400ms for 50,000+ monthly customers.
• Led migration of the primary datastore from MySQL to PostgreSQL with zero
downtime.
Backend Engineer @ Initech Jun 2020 – Dec 2022
• Built a Kafka-based event pipeline (ResNet18 was not involved) processing
2M events/day.

Projects
Task Queue § Code Python, Redis, Docker
• Built a distributed task queue supporting 10,000 jobs/sec with at-least-once
delivery semantics.

Technical Skills
Languages: Python, Go, SQL
Databases: PostgreSQL, MySQL
Cloud: AWS(S3, ECS, ECR), GCP

Education
State University Springfield, IL
Bachelor of Science in Computer Science Expected May 2020
• GPA: 3.8 / 4.0

Awards & Honors
• Employee of the Year, Acme Corp — for the billing pipeline rebuild.
"""


def _profile():
    return ProfileImporter().import_text(SAMPLE_RESUME)


def test_contact_info():
    profile = _profile()
    assert profile.personal.name == "Jane Doe"
    assert profile.personal.email == "jane.doe@example.com"
    assert profile.personal.phone == "555-123-4567"


def test_wrapped_bullet_lines_stay_one_bullet():
    """Regression: a bullet wrapping onto a second physical line must not be
    misread as a new experience/project item (real bug found 2026-09-19)."""
    profile = _profile()
    assert len(profile.experiences) == 2

    first_job = profile.experiences[0]
    assert first_job.title == "Senior Backend Engineer"
    assert first_job.org == "Acme Corp"
    assert len(first_job.bullets) == 2
    assert "50,000+ monthly customers" in first_job.bullets[0].text
    assert "12s to 400ms" in first_job.bullets[0].text


def test_project_tech_list_extracted():
    profile = _profile()
    assert len(profile.projects) == 1
    project = profile.projects[0]
    assert project.title == "Task Queue"
    assert project.tech == ["Python", "Redis", "Docker"]


def test_awards_section_does_not_bleed_into_education():
    """Regression: an unrecognized-but-aliased heading must not get absorbed
    into whatever section preceded it (real bug found 2026-09-19)."""
    profile = _profile()
    assert len(profile.education) == 1
    assert profile.education[0].school == "State University Springfield, IL"
    assert profile.education[0].degree == "Bachelor of Science in Computer Science"
    assert "awards" in profile.other_sections
    assert any("Employee of the Year" in line for line in profile.other_sections["awards"])


def test_skills_expand_parenthetical_without_breaking_on_internal_commas():
    """Regression: 'AWS(S3, ECS, ECR)' must not get shredded by a naive
    comma-split (real bug found 2026-09-19)."""
    profile = _profile()
    for expected in ("AWS", "S3", "ECS", "ECR", "GCP", "Python", "Go", "SQL"):
        assert expected in profile.skills


def test_numbers_exclude_digits_glued_to_identifiers():
    """Regression: 'ResNet18' must not leak '18' into the numbers list
    (real bug found 2026-09-19)."""
    profile = _profile()
    bullet = profile.experiences[1].bullets[0]
    assert "18" not in bullet.numbers
    assert "2M" not in bullet.numbers  # "2M" isn't matched by digit-only regex; documents current behavior


def test_bullet_tech_tagged_from_vocabulary():
    profile = _profile()
    billing_bullet = profile.experiences[0].bullets[1]
    assert "PostgreSQL" in billing_bullet.tech
