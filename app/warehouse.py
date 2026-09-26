"""Merge and edit operations on the career warehouse."""

import re
from dataclasses import dataclass

from app.importing.text_utils import extract_numbers
from app.importing.vocabulary import BulletTechTagger, VocabularyBuilder
from app.models import Bullet, EducationEntry, Item, Personal, Profile

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_STOP = {"and", "the", "of", "at", "a", "an", "for", "in", "to"}
_LINK_SCHEME_RE = re.compile(r"^https?://", re.I)
_GARBAGE_LOCATION_LEN = 160


def _norm(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _tokens(value: str | None) -> set[str]:
    return set(_PUNCT_RE.sub(" ", _norm(value)).split()) - _STOP


def _similar(a: str | None, b: str | None, *, min_len: int = 12) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return min(len(na), len(nb)) >= min_len
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def _norm_link(url: str) -> str:
    cleaned = _LINK_SCHEME_RE.sub("", url.strip().lower())
    cleaned = re.sub(r"^www\.", "", cleaned)
    return cleaned.rstrip("/")


def _union(existing: list[str], incoming: list[str], *, key=_norm) -> tuple[list[str], int]:
    """Preserve first-seen casing. Returns (list, number of new values)."""
    seen = {key(v): True for v in existing if key(v)}
    added = 0
    for value in incoming:
        k = key(value)
        if not k or k in seen:
            continue
        seen[k] = True
        existing.append(value)
        added += 1
    return existing, added


def _dedupe_list(values: list[str], *, key=_norm) -> list[str]:
    seen: dict[str, bool] = {}
    out: list[str] = []
    for value in values:
        k = key(value)
        if not k or k in seen:
            continue
        seen[k] = True
        out.append(value)
    return out


def _bullets_same(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(shorter) >= 40 and shorter in longer


def _is_garbage_item(item: Item) -> bool:
    return not item.bullets and len(item.location or "") >= _GARBAGE_LOCATION_LEN


def _items_match(existing: Item, incoming: Item) -> bool:
    if _norm(existing.title) == _norm(incoming.title) and _norm(existing.org) == _norm(incoming.org):
        return True
    if existing.org and incoming.org and _similar(existing.org, incoming.org) and _similar(existing.title, incoming.title):
        return True
    if (not existing.org or not incoming.org) and _similar(existing.title, incoming.title):
        return True
    blob = _norm(f"{incoming.title} {incoming.org or ''}")
    if existing.title and _norm(existing.title) in blob:
        if not existing.org or _norm(existing.org) in blob:
            return True
    if not incoming.org and existing.org and _norm(existing.org) in _norm(incoming.title):
        head = incoming.title.split("|")[0].split("@")[0]
        if _similar(existing.title, head):
            return True
    return False


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
    """Union an incoming profile into the warehouse. Same job/project/education
    is folded into the existing record; only truly new facts are added."""

    def merge(self, base: Profile, incoming: Profile) -> tuple[Profile, MergeReport]:
        report = MergeReport()
        self._collapse_items(base.experiences, report)
        self._collapse_items(base.projects, report)
        self._collapse_education(base)
        self._merge_personal(base, incoming)
        if not base.summary:
            base.summary = incoming.summary

        for item in incoming.experiences:
            self._merge_item(base.experiences, item, base, "exp", report)
        for item in incoming.projects:
            self._merge_item(base.projects, item, base, "proj", report)
        for edu in incoming.education:
            self._merge_education(base, edu, report)

        base.skills[:] = _dedupe_list(base.skills)
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
        dest.links[:] = _dedupe_list(dest.links, key=_norm_link)
        _union(dest.links, src.links, key=_norm_link)

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
            if _is_garbage_item(incoming):
                report.duplicates_skipped += 1
                return
            new_item = Item(
                id=next_item_id(profile, prefix),
                title=incoming.title,
                org=incoming.org,
                dates=incoming.dates,
                location=incoming.location if not _is_garbage_item(incoming) else None,
                tech=list(incoming.tech),
                bullets=[],
            )
            self._fold_bullets(new_item, incoming, report, count=True)
            dest.append(new_item)
            if prefix == "exp":
                report.new_experiences += 1
            else:
                report.new_projects += 1
            return

        self._fold_fields(existing, incoming)
        self._fold_bullets(existing, incoming, report, count=True)

    def _fold_fields(self, existing: Item, incoming: Item) -> None:
        existing.org = existing.org or incoming.org
        existing.dates = existing.dates or incoming.dates
        if incoming.location and len(incoming.location) < _GARBAGE_LOCATION_LEN:
            existing.location = existing.location or incoming.location
        _union(existing.tech, incoming.tech)

    def _fold_bullets(
        self,
        dest: Item,
        incoming: Item,
        report: MergeReport,
        *,
        count: bool,
    ) -> None:
        for bullet in incoming.bullets:
            if any(_bullets_same(bullet.text, existing.text) for existing in dest.bullets):
                if count:
                    report.duplicates_skipped += 1
                continue
            dest.bullets.append(
                Bullet(
                    id=next_bullet_id(dest),
                    text=bullet.text,
                    tech=list(bullet.tech),
                    numbers=list(bullet.numbers),
                )
            )
            if count:
                report.new_bullets += 1

    def _find_item(self, items: list[Item], incoming: Item) -> Item | None:
        for item in items:
            if _items_match(item, incoming):
                return item
        return None

    def _collapse_items(self, items: list[Item], report: MergeReport) -> None:
        kept: list[Item] = []
        for item in items:
            match = self._find_item(kept, item)
            if match is None:
                kept.append(item)
                continue
            self._fold_fields(match, item)
            self._fold_bullets(match, item, report, count=False)
        items[:] = kept

    def _collapse_education(self, base: Profile) -> None:
        kept: list[EducationEntry] = []
        for edu in base.education:
            match = self._find_education(kept, edu)
            if match is None:
                kept.append(edu)
                continue
            match.degree = match.degree or edu.degree
            match.dates = match.dates or edu.dates
            _union(match.details, edu.details)
        base.education[:] = kept

    def _find_education(self, entries: list[EducationEntry], incoming: EducationEntry) -> EducationEntry | None:
        for edu in entries:
            if _similar(edu.school, incoming.school):
                return edu
        return None

    def _merge_education(self, base: Profile, incoming: EducationEntry, report: MergeReport) -> None:
        existing = self._find_education(base.education, incoming)
        if existing is not None:
            existing.degree = existing.degree or incoming.degree
            existing.dates = existing.dates or incoming.dates
            _union(existing.details, incoming.details)
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
            dest[:] = _dedupe_list(dest)
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
