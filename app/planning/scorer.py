from app.models import Bullet, Item, JobAnalysis


class BulletScorer:
    """Scores an item/bullet: must-have overlap x3 + bonus overlap x1 +
    embedding similarity + a small recency boost."""

    def score_item(self, item: Item, analysis: JobAnalysis) -> float:
        raise NotImplementedError("Scoring not yet implemented")

    def score_bullet(self, bullet: Bullet, analysis: JobAnalysis) -> float:
        raise NotImplementedError("Scoring not yet implemented")
