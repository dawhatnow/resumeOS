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
        posting = self._router.resolve(source, pasted=pasted)
        analysis = self._analyzer.analyze(posting, profile)
        plan = self._planner.plan(analysis, profile, self._meaning(analysis, profile))
        return posting, analysis, plan

    def _meaning(self, analysis: JobAnalysis, profile: Profile) -> dict[str, tuple[float, str]] | None:
        from app.analyzing.semantic import SemanticMatcher, semantic_enabled

        matcher = self._semantic
        if matcher is False or (matcher is None and not semantic_enabled()):
            return None
        bullets = {b.id: b.text for item in profile.all_items() for b in item.bullets}
        try:
            return (matcher or SemanticMatcher()).bonuses(bullets, analysis.must_lines, analysis.nice_lines)
        except Exception:  # model download blocked, ONNX issue… keywords alone still work
            return None
