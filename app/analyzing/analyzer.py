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
        if not posting.title:
            first = posting.clean_text.split("\n", 1)[0].strip()
            if 0 < len(first) <= 80 and not first.endswith("."):
                posting.title = first
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
