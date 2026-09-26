"""Merge and edit operations on the career warehouse."""

from dataclasses import dataclass

from app.importing.text_utils import extract_numbers
from app.importing.vocabulary import BulletTechTagger, VocabularyBuilder
from app.models import Bullet, EducationEntry, Item, Personal, Profile


def _norm(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _union(existing: list[str], incoming: list[str]) -> tuple[list[str], int]:
    """Preserve first-seen casing. Returns (list, number of new values)."""
    seen = {_norm(v): v for v in existing}
    added = 0
    for value in incoming:
        key = _norm(value)
        if not key or key in seen:
            continue
        seen[key] = value
        existing.append(value)
        added += 1
    return existing, added


def _next_index(ids: list[str], prefix: str) -> int:
    highest = 0
    for item_id in ids:
        parts = item_id.split(".")
        if len(parts) >= 2 and parts[0] == prefix and parts[1].isdigit():
            highest = max(highest, int(parts[1]))
    return highest + 1


def next_item_id(profile: Profile, prefix: str) -> str:
    ids = [item.id for item in (profile.experiences if prefix == "exp" else profile.projects)]
    return f"{prefix}.{_next_index(ids, prefix)}"


def next_bullet_id(item: Item) -> str:
    highest = 0
    for bullet in item.bullets:
        parts = bullet.id.split(".")
        if parts and parts[-1].isdigit():
            highest = max(highest, int(parts[-1]))
    return f"{item.id}.{highest + 1}"


def refresh_vocabulary(profile: Profile) -> None:
    profile.vocabulary = VocabularyBuilder().build(profile.skills, profile.all_items())
    BulletTechTagger().tag(profile.all_items(), profile.vocabulary)


def warehouse_counts(profile: Profile) -> dict[str, int]:
    return {
        "experiences": len(profile.experiences),
        "projects": len(profile.projects),
        "bullets": sum(len(item.bullets) for item in profile.all_items()),
        "education": len(profile.education),
        "skills": len(profile.skills),
    }


def format_counts(profile: Profile) -> str:
    counts = warehouse_counts(profile)
    return (
        f"Warehouse: {counts['experiences']} jobs, "
        f"{counts['projects']} projects, {counts['bullets']} bullets"
    )


@dataclass
class MergeReport:
    new_experiences: int = 0
    new_projects: int = 0
    new_education: int = 0
    new_bullets: int = 0
    new_skills: int = 0
    duplicates_skipped: int = 0

    def summary(self) -> str:
        return (
            f"{self.new_experiences} new jobs, {self.new_projects} new projects, "
            f"{self.new_bullets} new bullets, {self.new_skills} new skills, "
            f"{self.duplicates_skipped} duplicates skipped"
        )


class ProfileMerger:
    """Union an incoming profile into the warehouse. Same job/project keeps
    existing IDs; new bullets and new items get fresh IDs."""

    def merge(self, base: Profile, incoming: Profile) -> tuple[Profile, MergeReport]:
        report = MergeReport()
        self._merge_personal(base, incoming)
        if not base.summary:
            base.summary = incoming.summary

        for item in incoming.experiences:
            self._merge_item(base.experiences, item, base, "exp", report)
        for item in incoming.projects:
            self._merge_item(base.projects, item, base, "proj", report)
        for edu in incoming.education:
            self._merge_education(base, edu, report)

        _, added_skills = _union(base.skills, incoming.skills)
        report.new_skills = added_skills
        self._merge_other_sections(base, incoming)
        refresh_vocabulary(profile=base)
        return base, report

    def _merge_personal(self, base: Profile, incoming: Profile) -> None:
        dest = base.personal
        src = incoming.personal
        dest.name = dest.name or src.name
        dest.email = dest.email or src.email
        dest.phone = dest.phone or src.phone
        _union(dest.links, src.links)

    def _merge_item(
        self,
        dest: list[Item],
        incoming: Item,
        profile: Profile,
        prefix: str,
        report: MergeReport,
    ) -> None:
        existing = self._find_item(dest, incoming)
        if existing is None:
            new_item = Item(
                id=next_item_id(profile, prefix),
                title=incoming.title,
                org=incoming.org,
                dates=incoming.dates,
                location=incoming.location,
                tech=list(incoming.tech),
                bullets=[],
            )
            for bullet in incoming.bullets:
                new_item.bullets.append(
                    Bullet(
                        id=next_bullet_id(new_item),
                        text=bullet.text,
                        tech=list(bullet.tech),
                        numbers=list(bullet.numbers),
                    )
                )
                report.new_bullets += 1
            dest.append(new_item)
            if prefix == "exp":
                report.new_experiences += 1
            else:
                report.new_projects += 1
            return

        existing.org = existing.org or incoming.org
        existing.dates = existing.dates or incoming.dates
        existing.location = existing.location or incoming.location
        _union(existing.tech, incoming.tech)
        existing_texts = {_norm(b.text) for b in existing.bullets}
        for bullet in incoming.bullets:
            if _norm(bullet.text) in existing_texts:
                report.duplicates_skipped += 1
                continue
            existing.bullets.append(
                Bullet(
                    id=next_bullet_id(existing),
                    text=bullet.text,
                    tech=list(bullet.tech),
                    numbers=list(bullet.numbers),
                )
            )
            existing_texts.add(_norm(bullet.text))
            report.new_bullets += 1

    def _find_item(self, items: list[Item], incoming: Item) -> Item | None:
        incoming_key = (_norm(incoming.title), _norm(incoming.org))
        for item in items:
            if (_norm(item.title), _norm(item.org)) == incoming_key:
                return item
        return None

    def _merge_education(self, base: Profile, incoming: EducationEntry, report: MergeReport) -> None:
        key = (_norm(incoming.school), _norm(incoming.degree))
        for edu in base.education:
            if (_norm(edu.school), _norm(edu.degree)) == key:
                edu.dates = edu.dates or incoming.dates
                _union(edu.details, incoming.details)
                return
        base.education.append(
            EducationEntry(
                school=incoming.school,
                degree=incoming.degree,
                dates=incoming.dates,
                details=list(incoming.details),
            )
        )
        report.new_education += 1

    def _merge_other_sections(self, base: Profile, incoming: Profile) -> None:
        for name, lines in incoming.other_sections.items():
            dest = base.other_sections.setdefault(name, [])
            _union(dest, lines)


def add_experience(
    profile: Profile,
    title: str,
    org: str | None = None,
    dates: str | None = None,
    location: str | None = None,
    bullets: list[str] | None = None,
    tech: list[str] | None = None,
) -> Item:
    item = Item(
        id=next_item_id(profile, "exp"),
        title=title,
        org=org or None,
        dates=dates or None,
        location=location or None,
        tech=list(tech or []),
        bullets=[],
    )
    for text in bullets or []:
        item.bullets.append(_new_bullet(item, text))
    profile.experiences.append(item)
    refresh_vocabulary(profile)
    return item


def add_project(
    profile: Profile,
    title: str,
    org: str | None = None,
    dates: str | None = None,
    location: str | None = None,
    bullets: list[str] | None = None,
    tech: list[str] | None = None,
) -> Item:
    item = Item(
        id=next_item_id(profile, "proj"),
        title=title,
        org=org or None,
        dates=dates or None,
        location=location or None,
        tech=list(tech or []),
        bullets=[],
    )
    for text in bullets or []:
        item.bullets.append(_new_bullet(item, text))
    profile.projects.append(item)
    refresh_vocabulary(profile)
    return item


def add_bullet(profile: Profile, item_id: str, text: str) -> Bullet:
    item = profile.find_item(item_id)
    if item is None:
        raise ValueError(f"No job or project with id {item_id}")
    bullet = _new_bullet(item, text)
    item.bullets.append(bullet)
    refresh_vocabulary(profile)
    return bullet


def _new_bullet(item: Item, text: str) -> Bullet:
    cleaned = text.strip()
    return Bullet(id=next_bullet_id(item), text=cleaned, numbers=extract_numbers(cleaned))
