import re

from app.analyzing.cleaner import JobDescriptionCleaner
from app.analyzing.keywords import KeywordMatcher
from app.analyzing.terms import TermIndex
from app.models import JobAnalysis, JobPosting, Profile


class JobAnalyzer:
    def __init__(self) -> None:
        self._cleaner = JobDescriptionCleaner()
        self._keywords = KeywordMatcher()

    def analyze(self, posting: JobPosting, profile: Profile) -> JobAnalysis:
        posting.clean_text = self._cleaner.clean(posting.raw_text)
        lines = [l.strip() for l in posting.clean_text.split("\n")[:4]]
        if not posting.title and lines and 0 < len(lines[0]) <= 80 and not lines[0].endswith("."):
            posting.title = lines[0]
        if not posting.company:
            posting.company = _company_line(lines[1:3])
        vocabulary = profile_vocabulary(profile)
        must, nice, keywords, groups = self._keywords.extract(posting.clean_text, vocabulary)
        index = TermIndex(vocabulary)
        inventory = inventory_keys(profile, index)
        missing = [
            term for term in must if not (requirement_keys(term, groups, index) & inventory)
        ]
        must_lines, nice_lines = self._keywords.requirement_lines(posting.clean_text)
        return JobAnalysis(
            must_have=must, nice_to_have=nice, keywords=keywords, missing=missing, alternatives=groups,
            must_lines=must_lines, nice_lines=nice_lines,
        )


def profile_vocabulary(profile: Profile) -> list[str]:
    return list(dict.fromkeys(profile.vocabulary + profile.skills))


def requirement_keys(term: str, groups: list[list[str]], index: TermIndex) -> set[str]:
    """Keys that satisfy a must-have: itself, or any alternative listed with it."""
    key = index.key(term)
    keys = {key}
    for group in groups:
        group_keys = {index.key(t) for t in group}
        if key in group_keys:
            keys |= group_keys
    return keys


def inventory_keys(profile: Profile, index: TermIndex) -> set[str]:
    """Every canonical term the warehouse can back up (plus what it implies)."""
    found = {index.key(t) for t in profile_vocabulary(profile)}
    for term in profile_vocabulary(profile):
        found.update(index.find(term))  # "HTML/CSS" → html, css
    found.update(index.find(profile.summary or ""))
    for edu in profile.education:
        found.update(index.find(" ".join([edu.degree or "", *edu.details])))
    for item in profile.all_items():
        found.update(index.key(t) for t in item.tech)
        found.update(index.find(item.title))
        for bullet in item.bullets:
            found.update(index.find(bullet.text))
    return index.expand(found)


def _company_line(lines: list[str]) -> str | None:
    """'ShyftLabs — Toronto, ON' / 'Moneris | Etobicoke' / 'at Stripe' near the
    top of a pasted posting → the company name. None if it isn't that shape."""
    for line in lines:
        m = re.match(r"^(?:at\s+)?([A-Z][\w&.,' -]{1,40}?)\s*(?:[—–|·]|\s-\s)", line)
        if m and len(line) <= 80:
            return m.group(1).strip(" ,")
    return None
