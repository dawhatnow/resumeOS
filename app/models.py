"""Data models for the career warehouse.

Personal/Profile/Item/Bullet/EducationEntry are populated by import and
edited by merge/add. This file is the source of truth for those shapes.
"""

from dataclasses import dataclass, field


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
    """The user's career warehouse. Built by import, grown by merge/add."""

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

    def find_item(self, item_id: str) -> Item | None:
        for item in self.all_items():
            if item.id == item_id:
                return item
        return None

    def find_bullet(self, source_id: str) -> Bullet | None:
        for item in self.all_items():
            for bullet in item.bullets:
                if bullet.id == source_id:
                    return bullet
        return None


# --- M2: apply / match (JD → plan). Warehouse types above stay as-is. ---


@dataclass
class JobPosting:
    url: str
    source: str
    company: str | None = None
    title: str | None = None
    raw_text: str = ""
    clean_text: str = ""


@dataclass
class JobAnalysis:
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    # Either/or requirements ("Tableau, Power BI, or similar"): one is enough.
    alternatives: list[list[str]] = field(default_factory=list)
    # JD requirement/responsibility lines and nice-to-have lines, for meaning-based matching.
    must_lines: list[str] = field(default_factory=list)
    nice_lines: list[str] = field(default_factory=list)


@dataclass
class PlannedPick:
    item_id: str
    bullet_ids: list[str]
    reason: str
    score: float = 0.0


@dataclass
class ResumePlan:
    selected: list[PlannedPick] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    must_have_hit: int = 0
    must_have_total: int = 0
    # Must/nice terms the selected picks back up (directly or implied, e.g. PostgreSQL → SQL).
    covered: list[str] = field(default_factory=list)
    # M3: relevance per bullet id (fit loop drops the lowest first) and
    # reviewed rewrites of bullet text, keyed by bullet id.
    bullet_scores: dict[str, float] = field(default_factory=dict)
    edits: dict[str, str] = field(default_factory=dict)
    rewritten: list[str] = field(default_factory=list)  # ids whose edit came from the AI writer
    semantic: bool = False  # meaning-based scoring was used

    @property
    def coverage(self) -> str:
        return f"{self.must_have_hit}/{self.must_have_total}"
