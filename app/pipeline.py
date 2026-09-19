from pathlib import Path

from app.ai.provider import AIProvider
from app.ai.writer import ResumeWriter
from app.analyzing.analyzer import JobAnalyzer
from app.fetching.router import JobFetcherRouter
from app.guard import TruthGuard
from app.models import Bullet, Generation, JobPosting, Profile, ResumePlan, TailoredResume
from app.planning.planner import ResumePlanner
from app.render import ResumeRenderer
from app.review import PlanReviewer


class ResumePipeline:
    """Orchestrates `resume new <url>` end to end: Fetch -> Analyze -> Plan
    -> Guard -> Review -> Write -> Render. Each stage is its own object so
    it can be tested, cached, or swapped independently; this class just
    calls them in order and wires one stage's output to the next one's
    input, matching the design spec's flowchart.

    To run with zero LLM calls (--no-rewrite), construct this with
    ai_provider=NullProvider() rather than passing a flag here — the
    provider is already the swappable seam for that."""

    def __init__(
        self,
        profile: Profile,
        ai_provider: AIProvider,
        renderer: ResumeRenderer,
        fetcher: JobFetcherRouter | None = None,
        analyzer: JobAnalyzer | None = None,
        planner: ResumePlanner | None = None,
        reviewer: PlanReviewer | None = None,
    ) -> None:
        self._profile = profile
        self._fetcher = fetcher or JobFetcherRouter()
        self._analyzer = analyzer or JobAnalyzer()
        self._planner = planner or ResumePlanner()
        self._guard = TruthGuard(profile)
        self._reviewer = reviewer or PlanReviewer()
        self._writer = ResumeWriter(ai_provider, self._guard)
        self._renderer = renderer

    def run(self, url: str, auto_approve: bool = False) -> Generation:
        posting = self._fetcher.fetch(url)
        analysis = self._analyzer.analyze(posting, self._profile)
        plan = self._planner.plan(analysis, self._profile)

        violations = self._guard.check_plan(plan)
        if violations:
            raise ValueError(f"Plan failed truth guard: {violations}")

        approved_plan = plan if auto_approve else self._reviewer.review(plan)

        picks = self._picks_from_plan(approved_plan)
        tailored_lines = self._writer.write(picks)
        resume = TailoredResume(lines=tailored_lines)

        pdf_path = self._renderer.render(resume, output_path=self._output_path(posting))
        return Generation(job=posting, plan=approved_plan, resume=resume, pdf_path=str(pdf_path))

    def _picks_from_plan(self, plan: ResumePlan) -> list[tuple[Bullet, list[str]]]:
        picks = []
        for pick in plan.selected:
            for bullet_id in pick.bullet_ids:
                bullet = self._profile.find_bullet(bullet_id)
                if bullet is not None:
                    picks.append((bullet, []))
        return picks

    def _output_path(self, posting: JobPosting) -> Path:
        company = (posting.company or "Company").replace(" ", "_")
        title = (posting.title or "Role").replace(" ", "_")
        return Path.cwd() / f"{company}_{title}_Resume.pdf"
