"""M2 facade: JD source + warehouse → posting, analysis, plan. No LLM."""

from app.analyzing.analyzer import JobAnalyzer
from app.fetching.router import JobSourceRouter
from app.models import JobAnalysis, JobPosting, Profile, ResumePlan
from app.planning.planner import ResumePlanner


class JobMatcher:
    def __init__(self) -> None:
        self._router = JobSourceRouter()
        self._analyzer = JobAnalyzer()
        self._planner = ResumePlanner()

    def run(self, source: str, profile: Profile, *, pasted: str | None = None) -> tuple[JobPosting, JobAnalysis, ResumePlan]:
        posting = self._router.resolve(source, pasted=pasted)
        analysis = self._analyzer.analyze(posting, profile)
        plan = self._planner.plan(analysis, profile)
        return posting, analysis, plan
