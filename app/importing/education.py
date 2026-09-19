import re

from app.importing.text_utils import is_bullet, strip_bullet
from app.models import EducationEntry

_DATE_TOKEN = r"(?:[A-Za-z]+\.?\s*\d{4}|\d{4})"
_DATE_RANGE = rf"{_DATE_TOKEN}\s*[–\-]\s*(?:Present|{_DATE_TOKEN})"
_TRAILING_DATE_RE = re.compile(rf"((?:Expected\s+)?{_DATE_RANGE}|(?:Expected\s+)?{_DATE_TOKEN})\s*$")


class EducationParser:
    """Parses an Education section into entries: school line, then a degree
    line (with a trailing date/date-range split off), then detail bullets.
    Handles wrapped continuation lines the same way ItemParser does."""

    def parse(self, lines: list[str]) -> list[EducationEntry]:
        entries: list[EducationEntry] = []
        current: EducationEntry | None = None
        state = "school"  # school -> degree -> details

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            if is_bullet(line):
                if current is not None:
                    current.details.append(strip_bullet(line))
                    state = "details"
                continue

            if current is None:
                current = EducationEntry(school=line)
                entries.append(current)
                state = "school"
            elif state == "school":
                current.degree, current.dates = self._split_degree_dates(line)
                state = "degree"
            elif state == "degree":
                current.degree = f"{current.degree} {line}".strip()
            elif state == "details" and current.details:
                current.details[-1] = f"{current.details[-1]} {line}".strip()

        return entries

    def _split_degree_dates(self, line: str) -> tuple[str, str | None]:
        match = _TRAILING_DATE_RE.search(line)
        if not match:
            return line, None
        return line[: match.start()].strip(" ,;"), match.group(1).strip()
