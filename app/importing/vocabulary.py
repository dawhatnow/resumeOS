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
        from app.analyzing.terms import TermIndex

        index = TermIndex(vocabulary)
        by_key = {index.key(term): term for term in vocabulary}
        for item in items:
            for bullet in item.bullets:
                bullet.tech = [by_key[k] for k in index.find(bullet.text) if k in by_key]
