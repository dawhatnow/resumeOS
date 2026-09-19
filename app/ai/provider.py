from abc import ABC, abstractmethod

from app.models import Bullet, TailoredLine


class AIProvider(ABC):
    """One interface, swappable backend (Ollama, Gemini, or none). The only
    thing an AIProvider is allowed to do is rewrite bullet text — it never
    sees layout, never picks which bullets are included, and never invents
    facts (the truth guard checks that after every call)."""

    @abstractmethod
    def rewrite_bullets(self, picks: list[tuple[Bullet, list[str]]]) -> list[TailoredLine]:
        """One batched call. picks is (bullet, matched_keywords) pairs;
        returns one TailoredLine per pick, same order."""
