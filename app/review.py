from app.models import ResumePlan


class PlanReviewer:
    """The Review stage: shows selected items with reasons, excluded items
    with why, warnings, and a must-have coverage summary, then lets the user
    approve, toggle items, or reorder via a checkbox UI (Rich + questionary).
    No chat, so no tokens spent on edit round-trips."""

    def review(self, plan: ResumePlan) -> ResumePlan:
        raise NotImplementedError("Review screen not yet implemented")
