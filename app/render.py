from pathlib import Path

from app.models import TailoredResume


class ResumeRenderer:
    """The Render stage: fills a single-column Typst template, compiles it,
    and runs the fit loop — if the PDF is over one page, drop the
    lowest-scored bullet and recompile until it fits. The AI never touches
    layout; only this class controls formatting."""

    def __init__(self, template_path: Path) -> None:
        self._template_path = template_path

    def render(self, resume: TailoredResume, output_path: Path) -> Path:
        raise NotImplementedError("Typst rendering + fit loop not yet implemented")
