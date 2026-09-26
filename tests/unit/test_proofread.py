from app.models import Bullet, Item, Profile
from app.proofread import Proofreader, add_to_dictionary, apply_fix, load_dictionary, style_issues


def _profile() -> Profile:
    return Profile(
        experiences=[
            Item(id="exp.1", title="Engineer", dates="2021 – 2023", bullets=[]),
            Item(id="exp.2", title="Founder", dates="2024 – Present", bullets=[]),
        ],
        skills=["Supabase", "PostgreSQL"],
        vocabulary=["Supabase", "PostgreSQL"],
    )


def _check(texts, dictionary=None):
    return Proofreader(_profile(), engine="basic", dictionary=dictionary or set()).check(texts)


def test_typos_found_with_suggestions():
    issues = _check({"exp.1.1": "Devloped a dashbord on Supabase for the sales team."})
    found = {i.snippet: i.suggestions for i in issues if i.kind == "spelling"}
    assert found == {"Devloped": ["Developed"], "dashbord": ["dashboard"]}


def test_tech_names_acronyms_canadian_and_hyphens_are_not_typos():
    text = ("Built ONNX and FastAPI services on Genesys with pytest, a lakehouse, and real-time "
            "multi-page ad-hoc reports in colour for the centre, modelling C++20 code.")
    assert [i for i in _check({"exp.1.1": text}) if i.kind == "spelling"] == []


def test_personal_dictionary(tmp_path):
    path = tmp_path / "dictionary.txt"
    add_to_dictionary("Hocuspocus", path)
    add_to_dictionary("hocuspocus", path)
    assert load_dictionary(path) == {"hocuspocus"}
    assert _check({"exp.1.1": "Synced via hocuspocus."}, dictionary={"hocuspocus"}) == []


def test_style_rules():
    texts = {
        "exp.1.1": "Responsible for the  backend; I built it in [X] days.",
        "exp.1.2": "Leading a team of 4.",
        "exp.2.1": "Leading a team of 4.",  # current role: present tense is fine
    }
    msgs = [(i.where, i.snippet, i.message.split(" —")[0]) for i in _check(texts) if i.kind == "style"]
    assert ("exp.1.1", "Responsible for", "Weak opener") in msgs
    assert ("exp.1.1", "I", "Drop first person on a resume.") in msgs
    assert ("exp.1.1", "[X]", "Looks like a placeholder") in msgs
    assert any(w == "exp.1.1" and m == "Extra space." for w, _, m in msgs)
    assert ("exp.1.2", "Leading", "Past role") in msgs
    assert not any(w == "exp.2.1" and m.startswith("Past role") for w, _, m in msgs)


def test_repeated_openers_within_one_item():
    issues = _check({"exp.1.1": "Built A.", "exp.1.2": "Built B.", "exp.2.1": "Built C."})
    assert [(i.where, i.snippet) for i in issues if "vary the verb" in i.message] == [("exp.1.2", "Built")]


def test_apply_fix():
    issue = style_issues("exp.1.1", "Wrote  docs.", current_role=True)[0]
    assert apply_fix(issue.text, issue, issue.suggestions[0]) == "Wrote docs."
