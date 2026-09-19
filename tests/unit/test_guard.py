import pytest

from app.guard import TruthGuard
from app.models import Bullet, Item, PlannedPick, Profile, ResumePlan, TailoredLine


def _profile():
    bullet = Bullet(id="exp.1.1", text="Cut latency from 12s to 400ms for 50000 customers.", numbers=["12", "400", "50000"])
    item = Item(id="exp.1", title="Engineer", org="Acme", bullets=[bullet])
    return Profile(experiences=[item], skills=["Python", "Go"], vocabulary=["Python", "Go"])


def test_check_plan_accepts_known_ids():
    guard = TruthGuard(_profile())
    plan = ResumePlan(selected=[PlannedPick(item_id="exp.1", bullet_ids=["exp.1.1"], reason="match")])
    assert guard.check_plan(plan) == []


def test_check_plan_rejects_unknown_id():
    guard = TruthGuard(_profile())
    plan = ResumePlan(selected=[PlannedPick(item_id="exp.1", bullet_ids=["exp.1.99"], reason="match")])
    violations = guard.check_plan(plan)
    assert len(violations) == 1
    assert violations[0].rule == "source_id"


def test_check_skills_flags_terms_outside_vocabulary():
    guard = TruthGuard(_profile())
    violations = guard.check_skills(["Python", "Rust"])
    assert len(violations) == 1
    assert "Rust" in violations[0].message


def test_check_tailored_line_flags_invented_number():
    guard = TruthGuard(_profile())
    line = TailoredLine(source_id="exp.1.1", text="Cut latency from 12s to 900ms.")
    violations = guard.check_tailored_line(line)
    assert any(v.rule == "numbers" for v in violations)


def test_check_tailored_line_accepts_faithful_rewrite():
    guard = TruthGuard(_profile())
    line = TailoredLine(source_id="exp.1.1", text="Reduced latency 12s -> 400ms across 50000 accounts.")
    assert guard.check_tailored_line(line) == []


def test_check_tailored_line_flags_unknown_source():
    guard = TruthGuard(_profile())
    line = TailoredLine(source_id="exp.99.1", text="Anything.")
    violations = guard.check_tailored_line(line)
    assert violations[0].rule == "source_id"


def test_check_tailored_line_flags_overlong_bullet():
    guard = TruthGuard(_profile(), max_bullet_length=20)
    line = TailoredLine(source_id="exp.1.1", text="Cut latency from 12s to 400ms for 50000 customers.")
    violations = guard.check_tailored_line(line)
    assert any(v.rule == "length" for v in violations)


def test_check_tech_is_not_yet_implemented():
    guard = TruthGuard(_profile())
    with pytest.raises(NotImplementedError):
        guard.check_tech(TailoredLine(source_id="exp.1.1", text="Uses Rust."))
