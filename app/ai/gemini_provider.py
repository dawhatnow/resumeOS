from app.ai.provider import AIProvider
from app.models import Bullet, TailoredLine


class GeminiProvider(AIProvider):
    """Gemini free tier. Check current rate limits before relying on it."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model = model

    def rewrite_bullets(self, picks: list[tuple[Bullet, list[str]]]) -> list[TailoredLine]:
        raise NotImplementedError("Gemini provider not yet implemented")
