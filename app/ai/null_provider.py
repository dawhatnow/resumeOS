from app.ai.provider import AIProvider
from app.models import Bullet, TailoredLine


class NullProvider(AIProvider):
    """The provider behind --no-rewrite: passes every bullet through
    unchanged. Zero LLM calls, by construction."""

    def rewrite_bullets(self, picks: list[tuple[Bullet, list[str]]]) -> list[TailoredLine]:
        return [TailoredLine(source_id=bullet.id, text=bullet.text) for bullet, _keywords in picks]
