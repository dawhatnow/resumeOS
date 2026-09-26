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
