from dataclasses import asdict
from pathlib import Path

import yaml

from app.models import Bullet, EducationEntry, Item, Personal, Profile

DEFAULT_PROFILE_PATH = Path.home() / ".resume" / "profile.yaml"


class ProfileStore:
    """Persists the career profile to ~/.resume/profile.yaml — the one
    place setup writes to and every job run reads from."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PROFILE_PATH

    def exists(self) -> bool:
        return self._path.exists()

    def save(self, profile: Profile) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w") as f:
            yaml.safe_dump(asdict(profile), f, sort_keys=False, allow_unicode=True)
        return self._path

    def load(self) -> Profile:
        if not self.exists():
            raise FileNotFoundError(f"No profile found at {self._path}. Run `resume import` first.")
        with self._path.open() as f:
            data = yaml.safe_load(f) or {}
        return self._profile_from_dict(data)

    def _profile_from_dict(self, data: dict) -> Profile:
        return Profile(
            personal=Personal(**data.get("personal", {})),
            summary=data.get("summary"),
            experiences=[self._item_from_dict(d) for d in data.get("experiences", [])],
            projects=[self._item_from_dict(d) for d in data.get("projects", [])],
            education=[EducationEntry(**d) for d in data.get("education", [])],
            skills=data.get("skills", []),
            vocabulary=data.get("vocabulary", []),
            other_sections=data.get("other_sections", {}),
            raw_text=data.get("raw_text", ""),
        )

    def _item_from_dict(self, d: dict) -> Item:
        return Item(
            id=d["id"],
            title=d["title"],
            org=d.get("org"),
            dates=d.get("dates"),
            location=d.get("location"),
            tech=d.get("tech", []),
            bullets=[Bullet(**b) for b in d.get("bullets", [])],
        )


class CacheStore:
    """Caches fetched job postings (by URL hash) and rewritten bullets (by
    hash of bullet + keywords) under ~/.resume/cache/, so re-runs and
    similar jobs don't repeat work or LLM calls."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.home() / ".resume" / "cache")

    def get_job(self, url_hash: str):
        raise NotImplementedError("Job cache not yet implemented")

    def put_job(self, url_hash: str, posting) -> None:
        raise NotImplementedError("Job cache not yet implemented")

    def get_rewrite(self, bullet_hash: str):
        raise NotImplementedError("Rewrite cache not yet implemented")

    def put_rewrite(self, bullet_hash: str, line) -> None:
        raise NotImplementedError("Rewrite cache not yet implemented")


class HistoryStore:
    """Saves each generation's posting/analysis/plan/resume JSON and PDF
    under ~/.resume/history/<id>/, so a crash mid-run can resume from the
    last saved checkpoint."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.home() / ".resume" / "history")

    def save(self, generation) -> Path:
        raise NotImplementedError("History persistence not yet implemented")

    def load(self, generation_id: str):
        raise NotImplementedError("History persistence not yet implemented")

    def list_ids(self) -> list[str]:
        raise NotImplementedError("History persistence not yet implemented")
