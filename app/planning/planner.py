from app.models import JobAnalysis, Profile, ResumePlan
from app.planning.scorer import BulletScorer


class ResumePlanner:
    """Facade for the Plan stage (design spec: JobAnalysis + Profile ->
    ResumePlan). Picks top items per section within a budget (e.g. 3
    experiences, 2-3 projects, 3-4 bullets each), reorders skills so matched
    ones come first, and records a one-line reason per pick. No LLM."""

    def __init__(self, budget: dict[str, int] | None = None) -> None:
        self._scorer = BulletScorer()
        self._budget = budget or {"experiences": 3, "projects": 3, "bullets_per_item": 4}

    def plan(self, analysis: JobAnalysis, profile: Profile) -> ResumePlan:
        raise NotImplementedError("Planning not yet implemented")
