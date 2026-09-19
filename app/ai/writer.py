from app.ai.provider import AIProvider
from app.guard import TruthGuard
from app.models import Bullet, TailoredLine


class ResumeWriter:
    """The Write stage: the only place an LLM call happens, and only ever
    once (plus at most one retry per rejected bullet). Every line the
    provider returns is checked by the truth guard before being accepted;
    a bullet that fails twice falls back to its original wording rather
    than being dropped or left broken."""

    def __init__(self, provider: AIProvider, guard: TruthGuard) -> None:
        self._provider = provider
        self._guard = guard

    def write(self, picks: list[tuple[Bullet, list[str]]]) -> list[TailoredLine]:
        rewritten = self._provider.rewrite_bullets(picks)
        return [
            self._accept_or_retry(line, bullet, keywords)
            for line, (bullet, keywords) in zip(rewritten, picks)
        ]

    def _accept_or_retry(self, line: TailoredLine, bullet: Bullet, keywords: list[str]) -> TailoredLine:
        if not self._guard.check_tailored_line(line):
            return line

        retried = self._provider.rewrite_bullets([(bullet, keywords)])[0]
        if self._guard.check_tailored_line(retried):
            return TailoredLine(source_id=bullet.id, text=bullet.text)  # guard rejected twice: use the original
        return retried
