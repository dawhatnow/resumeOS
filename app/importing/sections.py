SECTION_ALIASES = {
    "summary": ("summary", "objective", "profile"),
    "experience": ("experience", "work experience", "professional experience", "employment"),
    "projects": ("projects", "personal projects", "side projects"),
    "skills": ("technical skills", "skills", "skills & tools", "core competencies"),
    "education": ("education",),
    "awards": (
        "awards & honors", "awards & honours", "awards and honors", "awards",
        "honors", "honours", "achievements", "certifications", "leadership",
        "volunteering", "publications", "extracurricular activities", "activities",
    ),
}

KNOWN_SECTIONS = {"header", "summary", "experience", "projects", "skills", "education"}


class SectionSplitter:
    """Splits raw resume text into named sections by matching heading lines
    against known aliases (case-insensitive). Anything before the first
    recognized heading goes into "header" (name/contact block)."""

    def split(self, text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"header": []}
        current = "header"
        for raw_line in text.splitlines():
            heading = self._canonical_heading(raw_line)
            if heading:
                current = heading
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(raw_line)
        return sections

    def _canonical_heading(self, line: str) -> str | None:
        stripped = line.strip().lower().rstrip(":")
        if not stripped or len(stripped) > 40:
            return None
        for canon, aliases in SECTION_ALIASES.items():
            if stripped in aliases:
                return canon
        return None
