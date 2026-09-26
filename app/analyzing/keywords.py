"""Find tech terms in JD text, split by section. Pure code, no LLM.

Terms come from the built-in lexicon *and* the warehouse vocabulary, so a
requirement the user lacks is still found (and can be reported missing).
"""

import re

from app.analyzing.terms import TermIndex

_MUST = (
    r"requirements|(?:basic |minimum |required |key )?qualifications|"
    r"what you.ll need|what you need|what we.re looking for|who we.re looking for|"
    r"what you (?:will |.ll )?bring|what gets you the role|required skills|"
    r"(?:soft |technical )?skills required|must[- ]haves?|who you are|about you|"
    r"skills(?: and| &) experience|your (?:skills|experience)|"
    r"(?:you have|you bring|skills)(?=\s*:?\s*$)"
)
_NICE = (
    r"nice[- ]to[- ]haves?|preferred(?: qualifications| skills)?|bonus(?: points)?|"
    r"pluses|good to have|assets(?=\s*:?\s*$)|desired(?: skills)?|extra credit|"
    r"(?:experience )?that would set you apart|exposure to"
)
_BODY = (
    r"responsibilities|key responsibilities|what you.ll (?:actually )?do|what you will do|"
    r"what (?:will )?we expect from you|about the (?:role|team|job|opportunity)|the role|"
    r"your role|the opportunity|(?:role|team)(?=\s*:?\s*$)|day[- ]to[- ]day|duties|overview|"
    r"job description|role description|our stack|tech stack"
)
_IGNORE = (
    r"benefits|perks|what we offer|what you.ll get|what you get|compensation|salary(?: range)?|"
    r"pay(?: range)?|about (?!you\b|the (?:role|team|job|opportunity)\b)\S+|who we are|"
    r"our values|equal opportunity|eeo|diversity|inclusion|how to apply|why join|"
    r"why you.ll love|the workplace"
)
_SECTIONS = [("nice", _NICE), ("ignore", _IGNORE), ("body", _BODY), ("must", _MUST)]
_HEADING_RES = [(name, re.compile(rf"^(?:{pattern})\b(?P<rest>.*)$", re.I)) for name, pattern in _SECTIONS]
_NICE_CUE = re.compile(
    r"\b(nice to have|preferred|is a plus|a plus|bonus|ideally|would be great|"
    r"an asset|set you apart|advantage)\b",
    re.I,
)
# "Bachelor's degree in Statistics, Computer Science…" names fields, not skills.
_DEGREE = re.compile(r"\b(bachelor|master|degree|diploma|ph\.?d|post-secondary)\b", re.I)
_BULLET = re.compile(r"^[-•*·▪◦]\s*")
_EMPHASIS = re.compile(r"^[*_#\s]+|[*_\s]+$")
_PREFIX_SPLIT = re.compile(r"\s[-–—]\s")
# Between two terms in a list: "A, B", "A/B", "A or B", "A, and/or B".
_LIST_GAP = re.compile(r"^[\s,/]*(?:\b(?:and/or|or|and)\b[\s,/]*)?$", re.I)
_OR = re.compile(r"\bor\b", re.I)
_OR_SIMILAR = re.compile(r"^[\s,]*or (?:similar|equivalent|comparable|other)\b", re.I)
_EXAMPLES = re.compile(r"\be\.g\.[\s,]*$", re.I)


class KeywordMatcher:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases = aliases

    def match(self, clean_text: str, vocabulary: list[str]) -> tuple[list[str], list[str], list[str]]:
        """Returns (must_have, nice_to_have, keywords) as display names."""
        must, nice, keywords, _ = self.extract(clean_text, vocabulary)
        return must, nice, keywords

    def extract(
        self, clean_text: str, vocabulary: list[str]
    ) -> tuple[list[str], list[str], list[str], list[list[str]]]:
        """match() plus alternative groups: ["Tableau", "Power BI"] from
        "Tableau, Power BI, or similar" — any one of a group satisfies it."""
        index = TermIndex(vocabulary, self._aliases)
        buckets = self._split_sections(clean_text)
        must = index.find(buckets["must"])
        nice = [k for k in index.find(buckets["nice"]) if k not in must]
        body = index.find(buckets["body"])
        if not must:
            must = [k for k in body if k not in nice]
        keywords = list(dict.fromkeys(must + nice + body))
        groups: list[list[str]] = []
        for line in (buckets["must"] + "\n" + buckets["nice"]).splitlines():
            groups.extend(_alternatives(line, index))
        show = index.display
        return (
            [show(k) for k in must],
            [show(k) for k in nice],
            [show(k) for k in keywords],
            [[show(k) for k in g] for g in groups],
        )

    def requirement_lines(self, clean_text: str) -> tuple[list[str], list[str]]:
        """(requirement + responsibility lines, nice-to-have lines) — whole
        sentences for meaning-based matching. Short fragments are dropped."""
        buckets = self._split_sections(clean_text)
        clean = lambda line: re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", line).strip(" *_")
        keep = lambda text: [clean(l) for l in text.splitlines() if len(l.split()) >= 4]
        return keep(buckets["must"]) + keep(buckets["body"]), keep(buckets["nice"])

    def _split_sections(self, clean_text: str) -> dict[str, str]:
        buckets: dict[str, list[str]] = {"must": [], "nice": [], "body": [], "ignore": []}
        current = "body"
        for raw in clean_text.splitlines():
            line = _BULLET.sub("", raw.strip())
            section, rest = _heading(line)
            if section:
                current = section
                if not rest:
                    continue
                line = rest
            if len(line) < 300 and _DEGREE.search(line):  # not a whole one-line JD
                continue
            target = current
            if target == "must" and _NICE_CUE.search(line):
                target = "nice"
            buckets[target].append(line)
        return {k: "\n".join(v) for k, v in buckets.items()}


def _heading(line: str) -> tuple[str | None, str]:
    """(section, inline content) if the line is a heading, else (None, "").

    A heading is either short and not a sentence ("Requirements",
    "*Nice to have:*", "Your Moneris Career - What you bring") or labels
    inline content ("Requirements: 3+ years…").
    """
    text = _EMPHASIS.sub("", line)
    short = len(text.split()) <= 8 and not text.endswith((".", ",", ";"))
    candidates = [text]
    if short:
        candidates += [_PREFIX_SPLIT.split(text)[-1]]
    for candidate in candidates:
        for name, pattern in _HEADING_RES:
            m = pattern.match(candidate)
            if not m:
                continue
            rest = _EMPHASIS.sub("", m.group("rest"))
            if rest.startswith((":", "–", "—")) or rest.startswith("- "):
                return name, rest.lstrip(":–—- ").strip()
            if short and len(rest.split()) <= 3:
                return name, ""
    return None, ""


def _alternatives(line: str, index: TermIndex) -> list[list[str]]:
    """Runs of listed terms that are either/or: joined by "or", followed by
    "or similar", or introduced by "e.g."."""
    spans = index.find_spans(line)
    groups: list[list[str]] = []
    run: list[tuple[int, int, str]] = []
    has_or = False

    def close() -> None:
        if len(run) < 2:
            return
        after = line[run[-1][1]:]
        before = line[: run[0][0]]
        if has_or or _OR_SIMILAR.match(after) or _EXAMPLES.search(before):
            groups.append(list(dict.fromkeys(k for _, _, k in run)))

    for span in spans:
        if run:
            gap = line[run[-1][1]: span[0]]
            if _LIST_GAP.match(gap):
                has_or = has_or or bool(_OR.search(gap))
                run.append(span)
                continue
            close()
        run, has_or = [span], False
    close()
    return groups
