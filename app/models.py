"""Data models passed between pipeline stages.

Every stage takes one of these in and returns one out, so stages can be
tested, cached, or swapped independently (see design spec, "JSON between
every stage"). Personal/Profile/Item/Bullet/EducationEntry are populated
today by the import stage; JobPosting/JobAnalysis/ResumePlan/TailoredResume/
Generation are the shapes the not-yet-built fetch/analyze/plan/write/render
stages will produce.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Bullet:
    id: str
    text: str
    tech: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)


@dataclass
class Item:
    """One experience or project entry."""

    id: str
    title: str
    org: str | None = None
    dates: str | None = None
    location: str | None = None
    tech: list[str] = field(default_factory=list)
    bullets: list[Bullet] = field(default_factory=list)


@dataclass
class EducationEntry:
    school: str
    degree: str | None = None
    dates: str | None = None
    details: list[str] = field(default_factory=list)


@dataclass
class Personal:
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    links: list[str] = field(default_factory=list)


@dataclass
class Profile:
    """The user's career profile. Source of truth: built once by import, edited anytime."""

    personal: Personal = field(default_factory=Personal)
    summary: str | None = None
    experiences: list[Item] = field(default_factory=list)
    projects: list[Item] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    vocabulary: list[str] = field(default_factory=list)
    other_sections: dict[str, list[str]] = field(default_factory=dict)
    raw_text: str = ""

    def all_items(self) -> list[Item]:
        return self.experiences + self.projects

    def find_bullet(self, source_id: str) -> Bullet | None:
        for item in self.all_items():
            for bullet in item.bullets:
                if bullet.id == source_id:
                    return bullet
        return None


# --- Shapes for not-yet-implemented pipeline stages (fetch/analyze/plan/write) ---


@dataclass
class JobPosting:
    url: str
    source: str
    company: str | None = None
    title: str | None = None
    raw_text: str = ""
    clean_text: str = ""
    fetched_at: datetime | None = None


@dataclass
class JobAnalysis:
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class PlannedPick:
    item_id: str
    bullet_ids: list[str]
    reason: str


@dataclass
class ResumePlan:
    selected: list[PlannedPick] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class TailoredLine:
    source_id: str
    text: str


@dataclass
class TailoredResume:
    lines: list[TailoredLine] = field(default_factory=list)


@dataclass
class Generation:
    job: JobPosting
    plan: ResumePlan
    resume: TailoredResume
    pdf_path: str | None = None
    created_at: datetime | None = None
