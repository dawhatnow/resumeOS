"""Drop obvious JD chrome. No LLM."""

import re

_BOILER_RE = re.compile(
    r"^(cookie|subscribe|sign in|log in|apply now|skip to|privacy policy|"
    r"terms of service|all rights reserved)\b",
    re.I,
)
_SPACE_RE = re.compile(r"[ \t]+")


class JobDescriptionCleaner:
    def clean(self, raw_text: str) -> str:
        lines = []
        for raw in raw_text.splitlines():
            line = _SPACE_RE.sub(" ", raw).strip()
            if not line or _BOILER_RE.match(line):
                continue
            lines.append(line)
        return "\n".join(lines)
