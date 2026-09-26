"""Truth guard: rewritten bullet text may only say what the warehouse backs up.

Pure code, no LLM. Runs on every edit made in review and (later) on every
AI rewrite, before anything reaches the PDF. A rewrite may reword, reorder,
and use the job's vocabulary, but it may not add facts: no new numbers, and
no tech that the bullet's own job/project doesn't already back up.
"""

import re

from app.analyzing.analyzer import inventory_keys, profile_vocabulary
from app.analyzing.terms import TermIndex
from app.models import Profile

MAX_GROWTH = 1.3  # rewrite may be up to 30% longer than the source…
MAX_CHARS = 260  # …and never longer than ~2.5 printed lines
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def numbers_in(text: str) -> set[str]:
    """"12,000" and "12000" are the same number; "3.5" keeps its point."""
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


class TruthGuard:
    def __init__(self, profile: Profile) -> None:
        self._profile = profile
        self._index = TermIndex(profile_vocabulary(profile))
        self._inventory = inventory_keys(profile, self._index)

    def check_bullet(self, bullet_id: str, new_text: str) -> list[str]:
        """Reasons the rewrite is not allowed; empty list means it passes."""
        source = self._profile.find_bullet(bullet_id)
        if source is None:
            return [f"{bullet_id} is not a bullet in the warehouse."]
        text = new_text.strip()
        if not text:
            return ["The bullet is empty."]
        problems: list[str] = []

        invented = sorted(numbers_in(text) - numbers_in(source.text), key=len, reverse=True)
        if invented:
            problems.append(f"New number(s) not in the original bullet: {', '.join(invented)}")

        backed = self._item_keys(bullet_id)
        unknown = [k for k in self._index.find(text) if k not in backed]
        if unknown:
            names = ", ".join(self._index.display(k) for k in unknown)
            where = "your warehouse" if any(k not in self._inventory for k in unknown) else "this job/project"
            problems.append(f"Mentions tech not backed by {where}: {names}")

        limit = self.max_chars(bullet_id)
        if len(text) > limit:
            problems.append(f"Too long: {len(text)} characters (limit {limit} for this bullet).")
        return problems

    def _item_keys(self, bullet_id: str) -> set[str]:
        """Terms the bullet's own job/project backs up: its title, declared
        tech, and every bullet under it (plus what those imply)."""
        item = next(i for i in self._profile.all_items() if any(b.id == bullet_id for b in i.bullets))
        keys = set(self._index.find(item.title)) | {self._index.key(t) for t in item.tech}
        for bullet in item.bullets:
            keys.update(self._index.find(bullet.text))
        return self._index.expand(keys)

    def check_rewrite(self, bullet_id: str, new_text: str, job_terms: list[str]) -> list[str]:
        """Stricter check for AI rewrites: check_bullet, plus nothing valuable
        may be lost — every number and every job-relevant term in the
        original must survive. (Your own edits may trim; the AI may not.)"""
        problems = self.check_bullet(bullet_id, new_text)
        source = self._profile.find_bullet(bullet_id)
        if source is None:
            return problems
        lost_numbers = sorted(numbers_in(source.text) - numbers_in(new_text))
        if lost_numbers:
            problems.append(f"Dropped number(s) from the original: {', '.join(lost_numbers)}")
        wanted = {self._index.key(t) for t in job_terms}
        kept = set(self._index.find(new_text))
        lost_terms = [k for k in self._index.find(source.text) if k in wanted and k not in kept]
        if lost_terms:
            names = ", ".join(self._index.display(k) for k in lost_terms)
            problems.append(f"Dropped job keyword(s) from the original: {names}")
        return problems

    def max_chars(self, bullet_id: str) -> int:
        source = self._profile.find_bullet(bullet_id)
        return min(MAX_CHARS, max(int(len(source.text) * MAX_GROWTH), 80))

    def allowed_terms(self, bullet_id: str, wanted: list[str]) -> list[str]:
        """Of the job's terms, the ones this bullet's job/project backs up —
        what a rewrite may truthfully name."""
        backed = self._item_keys(bullet_id)
        return [t for t in wanted if self._index.key(t) in backed]
