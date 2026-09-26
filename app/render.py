"""Warehouse + reviewed plan → one-page PDF via Typst. No LLM, no layout by AI.

The template (app/templates/resume.typ) receives everything as JSON, so
bullet text is never parsed as Typst markup. The fit loop shrinks the font
one step, then drops the lowest-scoring bullet until the PDF is one page.
"""

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.models import Item, Profile, ResumePlan

TEMPLATE = Path(__file__).parent / "templates" / "resume.typ"
FONT_SIZES = (10.5, 10.0)
MAX_PAGES = 1


class RenderError(Exception):
    pass


@dataclass
class RenderResult:
    pdf: bytes
    pages: int
    font_size: float
    dropped: list[str] = field(default_factory=list)  # bullet or item ids, in drop order
    data: dict = field(default_factory=dict)  # exactly what the template rendered


class ResumeRenderer:
    def __init__(self, template: Path = TEMPLATE) -> None:
        self._template = template

    def fit(self, profile: Profile, plan: ResumePlan, priority_terms: list[str] | None = None) -> RenderResult:
        """Compile to one page. Mutates nothing: drops happen on a copy."""
        picks = {p.item_id: list(p.bullet_ids) for p in plan.selected}
        order = [p.item_id for p in plan.selected]
        dropped: list[str] = []
        for size in FONT_SIZES:
            pdf, pages = self._compile(profile, plan, picks, order, size, priority_terms)
            if pages <= MAX_PAGES:
                return RenderResult(pdf, pages, size, dropped, self._last_data)
        size = FONT_SIZES[-1]
        while True:
            victim = self._lowest(plan, picks, order)
            if victim is None:
                raise RenderError("Can't fit one page even with one bullet per item. Drop an item in review.")
            dropped.append(victim)
            pdf, pages = self._compile(profile, plan, picks, order, size, priority_terms)
            if pages <= MAX_PAGES:
                break
        # Dropping one long bullet can free room for a shorter one dropped
        # earlier: try putting bullets back, strongest first.
        original = {p.item_id: list(p.bullet_ids) for p in plan.selected}
        for bid in sorted(
            (d for d in dropped if d not in original), key=lambda b: -plan.bullet_scores.get(b, 0.0)
        ):
            iid = next(i for i, bids in original.items() if bid in bids)
            if iid not in order:
                continue
            picks[iid] = [b for b in original[iid] if b in picks[iid] or b == bid]
            trial_pdf, trial_pages = self._compile(profile, plan, picks, order, size, priority_terms)
            if trial_pages <= MAX_PAGES:
                pdf = trial_pdf
                dropped.remove(bid)
            else:
                picks[iid].remove(bid)
        # Recompile the kept state so pdf and data match exactly.
        pdf, _ = self._compile(profile, plan, picks, order, size, priority_terms)
        return RenderResult(pdf, 1, size, dropped, self._last_data)

    def _lowest(self, plan: ResumePlan, picks: dict[str, list[str]], order: list[str]) -> str | None:
        """Remove and return the weakest bullet from an item that keeps at
        least one; if every item is down to one bullet, the weakest item."""
        score = lambda bid: plan.bullet_scores.get(bid, 0.0)
        candidates = [
            (score(bid), -pos, bid, iid)
            for iid in order
            if len(picks[iid]) > 1
            for pos, bid in enumerate(picks[iid])
        ]
        if candidates:
            _, _, bid, iid = min(candidates)
            picks[iid].remove(bid)
            return bid
        if len(order) <= 1:
            return None
        item_score = {p.item_id: p.score for p in plan.selected}
        weakest = min(order, key=lambda iid: (item_score.get(iid, 0.0), -order.index(iid)))
        order.remove(weakest)
        return weakest

    def _compile(self, profile, plan, picks, order, size, priority_terms) -> tuple[bytes, int]:
        import typst
        from pypdf import PdfReader

        data = build_data(profile, plan, picks, order, size, priority_terms)
        self._last_data = data
        try:
            pdf = typst.compile(
                str(self._template),
                sys_inputs={"data": json.dumps(data)},
                ignore_system_fonts=True,  # same output on every machine
            )
        except Exception as e:  # typst raises its own error types
            raise RenderError(f"Typst failed: {e}") from e
        return pdf, len(PdfReader(io.BytesIO(pdf)).pages)

    def preview_png(self, data: dict, ppi: int = 100) -> bytes:
        import typst

        png = typst.compile(
            str(self._template), format="png", ppi=ppi,
            sys_inputs={"data": json.dumps(data)}, ignore_system_fonts=True,
        )
        return png if isinstance(png, bytes) else png[0]


def build_data(
    profile: Profile,
    plan: ResumePlan,
    picks: dict[str, list[str]],
    order: list[str],
    font_size: float,
    priority_terms: list[str] | None = None,
) -> dict:
    exp_ids = {i.id for i in profile.experiences}
    # Jobs stay in warehouse (usually reverse-chronological) order; projects
    # in relevance order.
    experiences = [i for i in profile.experiences if i.id in order]
    projects = [profile.find_item(iid) for iid in order if iid not in exp_ids]
    return {
        "name": profile.personal.name or "Your Name",
        "font_size": font_size,
        "contact": contact_line(profile),
        "sections": [
            {"kind": "education", "entries": [
                {"school": e.school, "degree": e.degree, "dates": e.dates, "details": list(e.details)}
                for e in _unique_education(profile)
            ]},
            {"kind": "items", "title": "Experience", "entries": [_entry(i, picks, plan) for i in experiences]},
            {"kind": "items", "title": "Projects", "entries": [_entry(i, picks, plan) for i in projects if i]},
            {"kind": "skills", "entries": _ordered_skills(profile.skills, priority_terms or [])},
        ],
    }


def _entry(item: Item, picks: dict[str, list[str]], plan: ResumePlan) -> dict:
    by_id = {b.id: b for b in item.bullets}
    return {
        "title": item.title,
        "org": item.org,
        "dates": item.dates,
        "location": item.location,
        "tech": list(item.tech) if item.id.startswith("proj.") else [],
        "bullets": [plan.edits.get(bid, by_id[bid].text) for bid in picks.get(item.id, []) if bid in by_id],
    }


def _unique_education(profile: Profile):
    """Merged PDFs can list the same school twice; keep the first."""
    seen: set[str] = set()
    for e in profile.education:
        key = " ".join(re.findall(r"[a-z]+", e.school.lower())[:3])
        if key not in seen:
            seen.add(key)
            yield e


# Links that identify the person (not a single project) go in the header.
_PROFILE_LINK = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:linkedin\.com/in/[^/]+|github\.com/[^/]+|[^/]+\.[a-z]{2,})/?$", re.I
)


def contact_line(profile: Profile) -> list[dict]:
    p = profile.personal
    items: list[dict] = []
    if p.phone:
        items.append({"text": p.phone, "url": None})
    if p.email:
        items.append({"text": p.email, "url": f"mailto:{p.email}"})
    for link in p.links:
        if _PROFILE_LINK.match(link):
            label = re.sub(r"^(?:https?://)?(?:www\.)?", "", link).rstrip("/")
            url = link if link.startswith(("http://", "https://")) else f"https://{link}"
            items.append({"text": label, "url": url})
    return items


def _ordered_skills(skills: list[str], priority_terms: list[str]) -> list[str]:
    """Skills the job asks for first, the rest after, in warehouse order."""
    wanted = {t.lower() for t in priority_terms}
    return [s for s in skills if s.lower() in wanted] + [s for s in skills if s.lower() not in wanted]
