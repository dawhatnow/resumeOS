"""Resume look: theme, accent colour, section order. Layout only — never content.

Saved in ~/.resume/style.yaml so the next resume starts from your last choice.
"""

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

THEMES = {
    # font, base sizes (fit loop steps down), margins (x, y in inches), heading style, spacing
    "classic": {"font": "New Computer Modern", "sizes": (10.5, 10.0), "margin": (0.55, 0.45), "heading": "smallcaps", "leading": 0.48},
    "modern": {"font": "Lato", "sizes": (10.0, 9.5), "margin": (0.6, 0.5), "heading": "caps", "leading": 0.5},
    "compact": {"font": "Libertinus Serif", "sizes": (10.0, 9.5), "margin": (0.45, 0.38), "heading": "bold", "leading": 0.5},
}
ACCENTS = {"navy": "#1f3a5f", "teal": "#0f6b6b", "burgundy": "#7a1f33", "forest": "#2d5a3d", "black": "#222222"}
ORDERS = {
    "education-first": ["education", "experience", "projects", "skills"],
    "experience-first": ["experience", "projects", "skills", "education"],
}
THEME_BLURBS = {
    "classic": "serif, small-caps headings — traditional",
    "modern": "Lato sans-serif, spaced uppercase headings",
    "compact": "tighter spacing and margins — fits more",
}


@dataclass
class ResumeStyle:
    theme: str = "classic"
    accent: str = "navy"
    order: str = "education-first"

    def valid(self) -> "ResumeStyle":
        return ResumeStyle(
            theme=self.theme if self.theme in THEMES else "classic",
            accent=self.accent if self.accent in ACCENTS else "navy",
            order=self.order if self.order in ORDERS else "education-first",
        )

    @property
    def spec(self) -> dict:
        return THEMES[self.valid().theme]

    def describe(self) -> str:
        s = self.valid()
        return f"{s.theme} · {s.accent} · {s.order}"


def style_path() -> Path:
    root = os.environ.get("RESUME_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".resume") / "style.yaml"


def load_style() -> ResumeStyle:
    try:
        data = yaml.safe_load(style_path().read_text()) or {}
        return ResumeStyle(**{k: str(v) for k, v in data.items() if k in {"theme", "accent", "order"}}).valid()
    except (OSError, yaml.YAMLError, TypeError):
        return ResumeStyle()


def save_style(style: ResumeStyle) -> None:
    path = style_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(asdict(style.valid()), sort_keys=False))
