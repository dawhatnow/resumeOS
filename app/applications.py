"""Application history: every exported resume, kept as a folder you can reopen.

~/.resume/applications/<YYYY-MM-DD_company_role>/
  job.yaml      the posting as fetched/pasted (so reopening never refetches)
  plan.yaml     reviewed picks, edits, AI rewrites, style
  resume.yaml   exactly what was printed (the template's input) + what was left out
  diff.yaml     vs the warehouse: items included / not, bullets dropped to fit, edited
  resume.pdf
  meta.yaml     id, company, title, coverage, status, timestamps, desktop path

Separate from profile.yaml on purpose: the warehouse is inventory, these are
compiles of it.
"""

import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from app.models import JobPosting, PlannedPick, Profile, ResumePlan
from app.style import ResumeStyle

STATUSES = ("exported", "applied", "interview", "offer", "rejected", "withdrawn")


def applications_root() -> Path:
    root = os.environ.get("RESUME_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".resume") / "applications"


def _slug(text: str | None, limit: int = 30) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:limit].rstrip("_")


@dataclass
class Application:
    id: str
    company: str | None
    title: str | None
    created: str
    updated: str
    status: str = "exported"
    coverage: str = ""
    desktop_path: str | None = None
    folder: Path | None = field(default=None, repr=False)

    @property
    def pdf(self) -> Path:
        return self.folder / "resume.pdf"


class ApplicationStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or applications_root()

    # --- ids ---

    def new_id(self, posting: JobPosting, when: datetime | None = None) -> str:
        when = when or datetime.now()
        parts = [when.strftime("%Y-%m-%d"), _slug(posting.company, 20), _slug(posting.title, 30)]
        base = "_".join(p for p in parts if p) or when.strftime("%Y-%m-%d")
        candidate, n = base, 2
        while (self.root / candidate).exists():
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    # --- write ---

    def save(
        self,
        posting: JobPosting,
        plan: ResumePlan,
        style: ResumeStyle,
        result,
        profile: Profile,
        *,
        desktop_path: Path | None = None,
        app_id: str | None = None,
    ) -> Application:
        """Create a new application, or update app_id in place (reopen → export)."""
        now = datetime.now().isoformat(timespec="seconds")
        existing = self.get(app_id) if app_id else None
        app_id = app_id or self.new_id(posting)
        folder = self.root / app_id
        folder.mkdir(parents=True, exist_ok=True)

        _dump(folder / "job.yaml", {
            "url": posting.url, "source": posting.source, "company": posting.company,
            "title": posting.title, "raw_text": posting.raw_text,
        })
        _dump(folder / "plan.yaml", {
            "selected": [asdict(p) for p in plan.selected],
            "excluded": list(plan.excluded),
            "coverage": plan.coverage,
            "edits": dict(plan.edits),
            "rewritten": list(plan.rewritten),
            "style": asdict(style.valid()),
        })
        _dump(folder / "resume.yaml", {"data": result.data, "dropped_to_fit": list(result.dropped)})
        _dump(folder / "diff.yaml", _diff(profile, plan, result))
        (folder / "resume.pdf").write_bytes(result.pdf)
        app = Application(
            id=app_id,
            company=posting.company,
            title=posting.title,
            created=existing.created if existing else now,
            updated=now,
            status=existing.status if existing else "exported",
            coverage=plan.coverage,
            desktop_path=str(desktop_path) if desktop_path else (existing.desktop_path if existing else None),
            folder=folder,
        )
        self._write_meta(app)
        return app

    def set_status(self, app_id: str, status: str) -> Application:
        if status not in STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}")
        app = self.require(app_id)
        app.status = status
        app.updated = datetime.now().isoformat(timespec="seconds")
        self._write_meta(app)
        return app

    def _write_meta(self, app: Application) -> None:
        meta = {k: v for k, v in asdict(app).items() if k != "folder"}
        _dump(app.folder / "meta.yaml", meta)

    # --- read ---

    def list(self) -> list[Application]:
        if not self.root.is_dir():
            return []
        apps = [a for a in (self.get(d.name) for d in self.root.iterdir() if d.is_dir()) if a]
        return sorted(apps, key=lambda a: (a.created, a.id), reverse=True)

    def get(self, app_id: str | None) -> Application | None:
        if not app_id:
            return None
        folder = self.root / app_id
        meta = _load(folder / "meta.yaml")
        if not meta:
            return None
        known = {k: meta.get(k) for k in ("id", "company", "title", "created", "updated", "status", "coverage", "desktop_path")}
        known["status"] = known["status"] or "exported"
        known["coverage"] = known["coverage"] or ""
        return Application(**known, folder=folder)

    def require(self, app_id: str) -> Application:
        """Exact id, a number from `resume ls` (1 = newest), or a unique part of the id."""
        app = self.get(app_id)
        if app:
            return app
        apps = self.list()
        if app_id.isdigit() and 1 <= int(app_id) <= len(apps):
            return apps[int(app_id) - 1]
        matches = [a for a in apps if app_id.lower() in a.id.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(f"No application matches '{app_id}'. See: resume ls")
        raise KeyError(f"'{app_id}' matches {len(matches)} applications: {', '.join(a.id for a in matches[:5])}")

    def load_posting(self, app: Application) -> JobPosting:
        job = _load(app.folder / "job.yaml")
        return JobPosting(
            url=job.get("url") or "", source=job.get("source") or "saved",
            company=job.get("company"), title=job.get("title"), raw_text=job.get("raw_text") or "",
        )

    def load_plan(self, app: Application, profile: Profile) -> tuple[ResumePlan, ResumeStyle, list[str]]:
        """The reviewed plan, checked against today's warehouse. Returns
        (plan, style, notes) — notes list anything that no longer exists."""
        raw = _load(app.folder / "plan.yaml")
        notes: list[str] = []
        selected = []
        for p in raw.get("selected", []):
            if profile.find_item(p["item_id"]) is None:
                notes.append(f"{p['item_id']} is no longer in the warehouse; skipped")
                continue
            kept = [b for b in p.get("bullet_ids", []) if profile.find_bullet(b)]
            if len(kept) < len(p.get("bullet_ids", [])):
                notes.append(f"{p['item_id']}: {len(p['bullet_ids']) - len(kept)} bullet(s) no longer exist")
            selected.append(PlannedPick(item_id=p["item_id"], bullet_ids=kept, reason=p.get("reason", ""), score=p.get("score", 0.0)))
        edits = {k: v for k, v in (raw.get("edits") or {}).items() if profile.find_bullet(k)}
        plan = ResumePlan(
            selected=selected,
            excluded=[i for i in raw.get("excluded", []) if profile.find_item(i)],
            edits=edits,
            rewritten=[b for b in raw.get("rewritten", []) if b in edits],
        )
        style = ResumeStyle(**(raw.get("style") or {})).valid()
        return plan, style, notes

    def load_render_data(self, app: Application) -> dict:
        return (_load(app.folder / "resume.yaml") or {}).get("data") or {}

    def copy_pdf(self, app: Application, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(app.pdf, dest)
        return dest


def _diff(profile: Profile, plan: ResumePlan, result) -> dict:
    printed_items = {p.item_id for p in plan.selected}
    return {
        "included_items": [p.item_id for p in plan.selected],
        "not_included_items": [i.id for i in profile.all_items() if i.id not in printed_items],
        "dropped_to_fit": list(result.dropped),
        "edited_bullets": sorted(plan.edits),
        "ai_rewritten_bullets": sorted(plan.rewritten),
    }


def _dump(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _load(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}
