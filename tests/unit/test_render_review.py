import io

from pypdf import PdfReader

from app.cli_ui import default_pdf_name, unique_path
from app.guard import TruthGuard, numbers_in
from app.models import Bullet, EducationEntry, Item, JobPosting, Personal, PlannedPick, Profile, ResumePlan
from app.render import ResumeRenderer, contact_line
from app.review import PlanReviewer


def _profile(bullets_per_item: int = 3, text_len: int = 1) -> Profile:
    def bullets(prefix: str) -> list[Bullet]:
        return [
            Bullet(id=f"{prefix}.{i}", text=f"Built service {i} in Python with 12 workers. " * text_len)
            for i in range(1, bullets_per_item + 1)
        ]

    return Profile(
        personal=Personal(name="Jane Doe", email="jane@example.com", links=["github.com/jane", "github.com/jane/repo"]),
        experiences=[
            Item(id="exp.1", title="Backend Engineer", org="Acme", dates="2024 – Now", bullets=bullets("exp.1")),
            Item(id="exp.2", title="Data Analyst", org="Contoso", tech=["SQL"], bullets=bullets("exp.2")),
        ],
        projects=[Item(id="proj.1", title="Queue", tech=["Python", "Redis"], bullets=bullets("proj.1"))],
        education=[
            EducationEntry(school="University of Guelph", degree="BComp"),
            EducationEntry(school="University of Guelph, Guelph, ON Sept 2022", degree="BComp (dup)"),
        ],
        skills=["Python", "SQL", "Redis"],
        vocabulary=["Python", "SQL", "Redis"],
    )


def _plan(profile: Profile) -> ResumePlan:
    picks = [PlannedPick(item_id=i.id, bullet_ids=[b.id for b in i.bullets], reason="", score=3.0 - n)
             for n, i in enumerate(profile.all_items())]
    scores = {b.id: float(n) for n, b in enumerate(b for i in profile.all_items() for b in i.bullets)}
    return ResumePlan(selected=picks, bullet_scores=scores)


# --- truth guard ---

def test_guard_accepts_an_honest_reword():
    p = _profile()
    assert TruthGuard(p).check_bullet("exp.1.1", "Built Python service 1 using 12 workers.") == []


def test_guard_rejects_new_numbers_and_foreign_tech():
    p = _profile()
    problems = TruthGuard(p).check_bullet("exp.1.1", "Built service 1 in Python with 40 workers on Kubernetes.")
    assert any("40" in x for x in problems)
    assert any("Kubernetes" in x and "warehouse" in x for x in problems)


def test_guard_rejects_tech_from_a_different_item():
    # Redis is in the warehouse (proj.1) but not in exp.1's evidence.
    problems = TruthGuard(_profile()).check_bullet("exp.1.1", "Built service 1 in Python and Redis with 12 workers.")
    assert problems == ["Mentions tech not backed by this job/project: Redis"]


def test_guard_rejects_unknown_id_empty_and_too_long():
    g = TruthGuard(_profile())
    assert g.check_bullet("exp.9.9", "x")
    assert g.check_bullet("exp.1.1", "  ") == ["The bullet is empty."]
    assert any("Too long" in x for x in g.check_bullet("exp.1.1", "Built service 1 in Python " * 10))


def test_numbers_normalise_thousands_separators():
    assert numbers_in("10,000 jobs in 3.5s") == {"10000", "3.5"}


# --- renderer ---

def test_render_fits_one_page_by_dropping_lowest_scored_bullets():
    p = _profile(bullets_per_item=10, text_len=5)
    plan = _plan(p)
    result = ResumeRenderer().fit(p, plan)
    assert len(PdfReader(io.BytesIO(result.pdf)).pages) == 1
    assert result.dropped, "this much text can't fit without drops"
    kept = {b for e in result.data["sections"][1]["entries"] + result.data["sections"][2]["entries"] for b in e["bullets"]}
    assert kept
    # the lowest-scored bullet (exp.1.1, score 0) goes before any higher one
    assert "exp.1.1" in result.dropped
    assert plan.selected[0].bullet_ids[0] == "exp.1.1", "fit() must not mutate the plan"


def test_render_uses_edits_and_keeps_markup_literal():
    p = _profile()
    plan = _plan(p)
    plan.edits["exp.1.1"] = "Shipped #1 service & cut $cost *fast* @team <x>"
    result = ResumeRenderer().fit(p, plan)
    text = " ".join(PdfReader(io.BytesIO(result.pdf)).pages[0].extract_text().split())
    assert "Shipped #1 service & cut $cost *fast* @team <x>" in text


def test_render_dedupes_education_and_filters_header_links():
    p = _profile()
    data = ResumeRenderer().fit(p, _plan(p)).data
    assert [e["school"] for e in data["sections"][0]["entries"]] == ["University of Guelph"]
    assert [c["text"] for c in contact_line(p)] == ["jane@example.com", "github.com/jane"]


def test_pdf_name_and_no_overwrite(tmp_path):
    name = default_pdf_name(_profile(), JobPosting(url="", source="paste", title="Sr. Engineer (Backend)"))
    assert name == "Jane_Doe_Sr_Engineer_Backend.pdf"
    (tmp_path / "a.pdf").write_bytes(b"x")
    assert unique_path(tmp_path, "a").name == "a-2.pdf"
    assert unique_path(tmp_path, "../../etc/b.pdf") == tmp_path / "b.pdf"


# --- review ---

def _review(profile: Profile, plan: ResumePlan, *commands: str):
    feed = iter(commands)
    return PlanReviewer(profile, plan, prompt=lambda *a, **k: next(feed)).run()


def test_review_toggle_move_add_drop_and_approve():
    p = _profile()
    plan = _plan(p)
    plan.selected = plan.selected[:2]  # proj.1 benched
    plan.excluded = ["proj.1"]
    out = _review(p, plan, "exp.1.2", "up exp.1.3", "drop exp.2", "add proj.1", "")
    ids = {pk.item_id: pk.bullet_ids for pk in out.selected}
    assert ids["exp.1"] == ["exp.1.3", "exp.1.1"]
    assert "exp.2" not in ids and "proj.1" in ids
    assert plan.selected[0].bullet_ids == ["exp.1.1", "exp.1.2", "exp.1.3"], "review works on a copy"


def test_review_edit_is_truth_checked():
    p = _profile()
    out = _review(
        p, _plan(p),
        "edit exp.1.1", "Built service 1 in Python with 99 workers.",  # rejected: new number
        "edit exp.1.2", "Built Python service 2 using 12 workers.",  # accepted
        "",
    )
    assert out.edits == {"exp.1.2": "Built Python service 2 using 12 workers."}


def test_review_quit_returns_none():
    p = _profile()
    assert _review(p, _plan(p), "quit") is None


# --- styles ---

def test_style_themes_render_one_page_with_their_font(_isolated_resume_home):
    from app.style import ResumeStyle

    p = _profile()
    for theme, font in (("classic", "NewCM"), ("modern", "Lato"), ("compact", "Libertinus")):
        result = ResumeRenderer().fit(p, _plan(p), style=ResumeStyle(theme, "teal", "experience-first"))
        reader = PdfReader(io.BytesIO(result.pdf))
        page = reader.pages[0]
        fonts = " ".join(str(f.get_object()["/BaseFont"]) for f in page["/Resources"]["/Font"].values())
        assert len(reader.pages) == 1 and font in fonts, (theme, fonts)
        assert [s["kind"] for s in result.data["sections"]][:2] == ["items", "items"]  # experience first
        assert result.data["style"]["accent"] == "#0f6b6b"


def test_style_saved_and_bad_values_fall_back(_isolated_resume_home):
    from app.style import ResumeStyle, load_style, save_style, style_path

    assert load_style() == ResumeStyle()
    save_style(ResumeStyle("modern", "forest", "experience-first"))
    assert load_style() == ResumeStyle("modern", "forest", "experience-first")
    style_path().write_text("theme: neon\naccent: rainbow\n")
    assert load_style() == ResumeStyle()


def test_review_style_command(_isolated_resume_home):
    from app.style import load_style

    p = _profile()
    feed = iter(["style", "2", "3", "2", "preview", ""])
    seen = []
    reviewer = PlanReviewer(p, _plan(p), prompt=lambda *a, **k: next(feed),
                            previewer=lambda plan, style: seen.append(style.describe()) or "ok")
    assert reviewer.run() is not None
    assert reviewer.style.describe() == "modern · burgundy · experience-first"
    assert seen == ["modern · burgundy · experience-first"]
    assert load_style() == reviewer.style
