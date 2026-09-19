import re

_CATEGORY_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z &]{1,30}:\s*(.*)$")
_PAREN_RE = re.compile(r"^([\w./+-]+)\(([^)]*)\)$")


class SkillsParser:
    """Parses a 'Technical Skills' style section into a flat, deduped list.

    A category label (e.g. "Frameworks & Tools:") is only recognized at the
    START of a physical line, matching how resumes actually format these
    sections — checking anywhere in the joined text is unsafe: a category's
    last skill often isn't comma-terminated, so "...Golang\\nFrameworks &
    Tools:..." would otherwise regex-merge into a bogus "Golang Frameworks &
    Tools" heading and silently drop "Golang" as a skill (real bug, caught
    2026-09-19). Lines without a leading label are folded onto whichever
    category came before them, since a category's value can wrap onto the
    next line without repeating the label.
    """

    def parse(self, lines: list[str]) -> list[str]:
        chunks: list[str] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            header_match = _CATEGORY_LINE_RE.match(line)
            if header_match:
                chunks.append(header_match.group(1))
            elif chunks:
                chunks[-1] = f"{chunks[-1]} {line}".strip()
            else:
                chunks.append(line)

        skills: list[str] = []
        for chunk in chunks:
            for raw_tok in self._split_top_level_commas(chunk):
                for tok in self._expand_token(raw_tok):
                    if tok not in skills:
                        skills.append(tok)
        return skills

    def _split_top_level_commas(self, s: str) -> list[str]:
        """Split on commas that aren't inside parentheses, so
        'AWS(S3, ECS, ECR)' survives as one token for _expand_token."""
        parts = []
        depth = 0
        buf: list[str] = []
        for ch in s:
            if ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth = max(0, depth - 1)
                buf.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        parts.append("".join(buf))
        return parts

    def _expand_token(self, tok: str) -> list[str]:
        tok = tok.strip()
        if not tok:
            return []
        match = _PAREN_RE.match(tok)
        if not match:
            return [tok]
        base, inner = match.groups()
        return [base] + [s.strip() for s in inner.split(",") if s.strip()]
