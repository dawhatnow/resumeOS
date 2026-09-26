from app.analyzing.analyzer import profile_vocabulary, requirement_keys
from app.analyzing.terms import TermIndex
from app.models import Item, JobAnalysis, PlannedPick, Profile, ResumePlan
from app.planning.scorer import BulletScorer


class ResumePlanner:
    def __init__(self, budget: dict[str, int] | None = None) -> None:
        self._budget = budget or {"experiences": 3, "projects": 3, "bullets_per_item": 4}

    def plan(
        self, analysis: JobAnalysis, profile: Profile, semantic: dict[str, tuple[float, str]] | None = None
    ) -> ResumePlan:
        """semantic: bullet id → (meaning bonus, closest JD line), from SemanticMatcher."""
        index = TermIndex(profile_vocabulary(profile))
        scorer = BulletScorer(index, analysis, semantic)
        exp_picks, exp_scores = self._pick(profile.experiences, scorer, self._budget["experiences"])
        proj_picks, proj_scores = self._pick(profile.projects, scorer, self._budget["projects"])
        selected = exp_picks + proj_picks
        selected_ids = {p.item_id for p in selected}
        excluded = [item.id for item in profile.all_items() if item.id not in selected_ids]
        scores = {**exp_scores, **proj_scores}
        covered = self._covered_keys(profile, selected, scorer)
        bullet_scores = {b.id: scorer.score_bullet(b) for item in profile.all_items() for b in item.bullets}
        hit, total = self._coverage(analysis, covered, index)
        return ResumePlan(
            selected=selected,
            excluded=excluded,
            scores=scores,
            must_have_hit=hit,
            must_have_total=total,
            covered=[t for t in analysis.must_have + analysis.nice_to_have if index.key(t) in covered],
            bullet_scores=bullet_scores,
            semantic=bool(semantic),
        )

    def _pick(
        self,
        items: list[Item],
        scorer: BulletScorer,
        limit: int,
    ) -> tuple[list[PlannedPick], dict[str, float]]:
        ranked: list[PlannedPick] = []
        scores: dict[str, float] = {}
        per = self._budget["bullets_per_item"]
        for item in items:
            # sorted() is stable: equal scores keep warehouse order.
            chosen = sorted(item.bullets, key=scorer.score_bullet, reverse=True)[:per]
            item_score = scorer.score_item(item, chosen)
            hits = [scorer.display(k) for k in scorer.item_terms(item, chosen)]
            reason = f"matches: {', '.join(hits)}" if hits else "best available overlap"
            close = scorer.closest_line(chosen)
            if close:
                short = close if len(close) <= 60 else close[:57].rsplit(" ", 1)[0] + "…"
                reason += f" · close to “{short}”"
            ranked.append(
                PlannedPick(item_id=item.id, bullet_ids=[b.id for b in chosen], reason=reason, score=item_score)
            )
            scores[item.id] = item_score
        ranked.sort(key=lambda p: p.score, reverse=True)
        return ranked[:limit], scores

    def _covered_keys(self, profile: Profile, selected: list[PlannedPick], scorer: BulletScorer) -> set[str]:
        covered: set[str] = set()
        for pick in selected:
            item = profile.find_item(pick.item_id)
            if item is None:
                continue
            bullets = [b for b in (profile.find_bullet(bid) for bid in pick.bullet_ids) if b]
            covered.update(scorer.item_terms(item, bullets))
        return covered

    def _coverage(self, analysis: JobAnalysis, covered: set[str], index: TermIndex) -> tuple[int, int]:
        if not analysis.must_have:
            return 0, 0
        # Each either/or group counts as one requirement.
        units: list[set[str]] = []
        for term in analysis.must_have:
            unit = requirement_keys(term, analysis.alternatives, index)
            if unit not in units:
                units.append(unit)
        return sum(1 for unit in units if unit & covered), len(units)
