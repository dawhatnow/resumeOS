from app.models import Bullet


class SemanticMatcher:
    """Embeds JD requirement lines and profile bullets with a small local
    model (sentence-transformers) to catch matches keyword rules miss, e.g.
    "distributed systems" vs a CRDT sync project. Zero tokens, runs locally."""

    def similarity(self, requirement: str, bullet: Bullet) -> float:
        raise NotImplementedError("Local embedding similarity not yet implemented")
