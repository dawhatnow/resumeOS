from dataclasses import dataclass

from app.importing.text_utils import extract_numbers
from app.models import Bullet, Profile, ResumePlan, TailoredLine

MAX_BULLET_LENGTH = 220


@dataclass
class GuardViolation:
    rule: str
    message: str


class TruthGuard:
    """Pure-Python checks that run after planning and after writing. Nothing
    reaches the PDF without passing these — the AI proposes, this enforces.

    Rules (design spec):
      1. Every source_id exists in the profile.
      2. Every skill listed is in the profile's vocabulary.
      3. Every number in a rewritten bullet appears in its source bullet.
      4. Every tech term in a rewritten bullet appears in the profile vocabulary.
      5. Rewritten bullets stay under a length limit (keeps one line).
    """

    def __init__(self, profile: Profile, max_bullet_length: int = MAX_BULLET_LENGTH) -> None:
        self._profile = profile
        self._max_bullet_length = max_bullet_length

    def check_plan(self, plan: ResumePlan) -> list[GuardViolation]:
        violations: list[GuardViolation] = []
        valid_ids = self._all_valid_ids()
        for pick in plan.selected:
            if pick.item_id not in valid_ids:
                violations.append(GuardViolation("source_id", f"Unknown item id: {pick.item_id}"))
            for bullet_id in pick.bullet_ids:
                if bullet_id not in valid_ids:
                    violations.append(GuardViolation("source_id", f"Unknown bullet id: {bullet_id}"))
        return violations

    def check_skills(self, skills: list[str]) -> list[GuardViolation]:
        vocabulary = {term.lower() for term in self._profile.vocabulary}
        return [
            GuardViolation("vocabulary", f"Skill not in profile vocabulary: {skill}")
            for skill in skills
            if skill.lower() not in vocabulary
        ]

    def check_tailored_line(self, line: TailoredLine) -> list[GuardViolation]:
        """Checks rules 3 and 5 (numbers, length) — both fully decidable from
        the bullet text alone. Rule 4 (invented tech terms) needs a
        tech-term extractor over arbitrary rewritten text, which only
        matters once the Write stage exists to produce that text; see
        check_tech()."""
        source = self._profile.find_bullet(line.source_id)
        if source is None:
            return [GuardViolation("source_id", f"Unknown source bullet id: {line.source_id}")]

        return self._check_numbers(line, source) + self._check_length(line)

    def check_tech(self, line: TailoredLine) -> list[GuardViolation]:
        """Rule 4: every tech term in a rewritten bullet must appear in the
        profile vocabulary. Not yet implemented — requires reliably
        extracting "tech-looking tokens" from free rewritten text (distinct
        from BulletTechTagger, which only needs to find *known* vocabulary
        terms, not spot unknown ones) which is only worth building once the
        Write stage exists to produce real rewritten text to test against."""
        raise NotImplementedError("Tech-term extraction not yet implemented")

    def _all_valid_ids(self) -> set[str]:
        ids = set()
        for item in self._profile.all_items():
            ids.add(item.id)
            ids.update(bullet.id for bullet in item.bullets)
        return ids

    def _check_numbers(self, line: TailoredLine, source: Bullet) -> list[GuardViolation]:
        source_numbers = set(extract_numbers(source.text))
        invented = [n for n in extract_numbers(line.text) if n not in source_numbers]
        return [
            GuardViolation("numbers", f"Number not in source bullet: {n}")
            for n in invented
        ]

    def _check_length(self, line: TailoredLine) -> list[GuardViolation]:
        if len(line.text) > self._max_bullet_length:
            return [GuardViolation("length", f"Bullet exceeds {self._max_bullet_length} chars")]
        return []
