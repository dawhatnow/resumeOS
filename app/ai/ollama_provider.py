from app.ai.provider import AIProvider
from app.models import Bullet, TailoredLine


class OllamaProvider(AIProvider):
    """Local Ollama model, zero cost. Requires Ollama running locally."""

    def __init__(self, model: str = "llama3") -> None:
        self._model = model

    def rewrite_bullets(self, picks: list[tuple[Bullet, list[str]]]) -> list[TailoredLine]:
        raise NotImplementedError("Ollama provider not yet implemented")
