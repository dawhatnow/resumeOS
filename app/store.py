import os
from dataclasses import asdict
from pathlib import Path

import yaml

from app.models import Bullet, EducationEntry, Item, Personal, Profile

DEFAULT_PROFILE_PATH = Path.home() / ".resume" / "profile.yaml"


def default_profile_path() -> Path:
    """~/.resume/profile.yaml, or $RESUME_HOME/profile.yaml for a throwaway demo."""
    root = os.environ.get("RESUME_HOME")
    if root:
        return Path(root).expanduser() / "profile.yaml"
    return DEFAULT_PROFILE_PATH


class ProfileStore:
    """Persists the career warehouse to ~/.resume/profile.yaml."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_profile_path()

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
