"""M2 facade: JD source + warehouse → posting, analysis, plan. No LLM."""

from app.analyzing.analyzer import JobAnalyzer
from app.fetching.router import JobSourceRouter
from app.models import JobAnalysis, JobPosting, Profile, ResumePlan
from app.planning.planner import ResumePlanner


class JobMatcher:
    def __init__(self, semantic=None) -> None:
        """semantic: a SemanticMatcher, False to disable, None = on if installed."""
        self._router = JobSourceRouter()
        self._analyzer = JobAnalyzer()
        self._planner = ResumePlanner()
        self._semantic = semantic

    def run(self, source: str, profile: Profile, *, pasted: str | None = None) -> tuple[JobPosting, JobAnalysis, ResumePlan]:
        posting = self.fetch(source, pasted=pasted)
        analysis = self.analyze(posting, profile)
        plan = self.plan(analysis, profile, self.meaning(analysis, profile))
        return posting, analysis, plan

    # The stages, separately, so the CLI can show live progress for each.

    def fetch(self, source: str, *, pasted: str | None = None) -> JobPosting:
        return self._router.resolve(source, pasted=pasted)

    def analyze(self, posting: JobPosting, profile: Profile) -> JobAnalysis:
        return self._analyzer.analyze(posting, profile)

    def meaning_enabled(self) -> bool:
        from app.analyzing.semantic import semantic_enabled

        return self._semantic is not False and (self._semantic is not None or semantic_enabled())

    def meaning(self, analysis: JobAnalysis, profile: Profile) -> dict[str, tuple[float, str]] | None:
        from app.analyzing.semantic import SemanticMatcher

        if not self.meaning_enabled():
            return None
        bullets = {b.id: b.text for item in profile.all_items() for b in item.bullets}
        try:
            return (self._semantic or SemanticMatcher()).bonuses(bullets, analysis.must_lines, analysis.nice_lines)
        except Exception:  # model download blocked, ONNX issue… keywords alone still work
            return None

    def plan(self, analysis: JobAnalysis, profile: Profile, meaning=None) -> ResumePlan:
        return self._planner.plan(analysis, profile, meaning)
