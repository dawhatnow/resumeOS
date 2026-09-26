from app.analyzing.terms import TermIndex
from app.models import Bullet, Item, JobAnalysis

MUST_WEIGHT = 3.0
NICE_WEIGHT = 2.0
KEYWORD_WEIGHT = 1.0
# Per chosen bullet that hits anything; breaks ties toward items with more
# relevant evidence without rewarding sheer bullet count.
EVIDENCE_BONUS = 0.5


class BulletScorer:
    """Scores by canonical term keys. Terms come from bullet text (not the
    stored bullet.tech tags), so older imports with bad tags still score right."""

    def __init__(self, index: TermIndex, analysis: JobAnalysis) -> None:
        self._index = index
        self._weights: dict[str, float] = {}
        for weight, terms in (
            (KEYWORD_WEIGHT, analysis.keywords),
            (NICE_WEIGHT, analysis.nice_to_have),
            (MUST_WEIGHT, analysis.must_have),
        ):
            for term in terms:
                self._weights[index.key(term)] = weight

    def bullet_terms(self, bullet: Bullet) -> list[str]:
        return self._relevant(self._index.find(bullet.text))

    def score_bullet(self, bullet: Bullet) -> float:
        return sum(self._weights[k] for k in self.bullet_terms(bullet))

    def item_terms(self, item: Item, bullets: list[Bullet]) -> list[str]:
        """Job-relevant keys backed by the item header, its tech, or these bullets."""
        keys = self._index.find(item.title)
        keys += [self._index.key(t) for t in item.tech]
        for bullet in bullets:
            keys += self._index.find(bullet.text)
        return self._relevant(keys)

    def _relevant(self, keys: list[str]) -> list[str]:
        """Job-relevant keys, including implied ones (PostgreSQL → SQL)."""
        implied = [k2 for k in keys for k2 in sorted(self._index.expand([k]))]
        return [k for k in dict.fromkeys(keys + implied) if k in self._weights]

    def score_item(self, item: Item, bullets: list[Bullet]) -> float:
        unique = sum(self._weights[k] for k in self.item_terms(item, bullets))
        evidence = sum(EVIDENCE_BONUS for b in bullets if self.bullet_terms(b))
        return unique + evidence

    def display(self, key: str) -> str:
        return self._index.display(key)
