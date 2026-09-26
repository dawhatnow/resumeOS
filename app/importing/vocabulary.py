import re

from app.models import Item


class VocabularyBuilder:
    """Collects every tech/skill term declared in the profile (skills list +
    each item's explicit tech list)."""

    def build(self, skills: list[str], items: list[Item]) -> list[str]:
        item_tech = {t for item in items for t in item.tech}
        return sorted(set(skills) | item_tech)


class BulletTechTagger:
    """Tags each bullet with which vocabulary terms actually appear in its
    text, so a bullet's own tech[] reflects what it demonstrably mentions."""

    def tag(self, items: list[Item], vocabulary: list[str]) -> None:
        patterns = [
            (term, re.compile(rf"\b{re.escape(term.lower())}\b"))
            for term in sorted(vocabulary, key=len, reverse=True)
        ]
        for item in items:
            for bullet in item.bullets:
                lowered = bullet.text.lower()
                bullet.tech = [term for term, pat in patterns if pat.search(lowered)]
