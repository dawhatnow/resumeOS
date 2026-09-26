from typer.testing import CliRunner

from app.cli import app
from app.models import Bullet, Item, Personal, Profile
from app.store import ProfileStore

runner = CliRunner()


def _seed(store: ProfileStore) -> None:
    store.save(
        Profile(
            personal=Personal(name="Jane Doe", email="jane@example.com"),
            experiences=[
                Item(
                    id="exp.1",
                    title="Engineer",
                    org="Acme",
                    bullets=[Bullet(id="exp.1.1", text="Did a thing.")],
                )
            ],
            projects=[Item(id="proj.1", title="Task Queue")],
        )
    )


def test_show_prints_counts_and_ids(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)

    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0
    assert "Warehouse: 1 jobs, 1 projects, 1 bullets" in result.stdout
    assert "[exp.1] Engineer @ Acme" in result.stdout
    assert "[proj.1] Task Queue" in result.stdout
    assert "Next:" in result.stdout


def test_show_without_warehouse_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cli.ProfileStore", lambda: ProfileStore(tmp_path / "profile.yaml"))
    result = runner.invoke(app, ["show"])
    assert result.exit_code == 1
    assert "resume init" in result.output


def test_add_bullet_via_cli(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)

    result = runner.invoke(app, ["add", "bullet", "exp.1", "--text", "Shipped the API."])
    assert result.exit_code == 0
    assert "[exp.1.2]" in result.stdout
    assert "Done:" in result.stdout
    assert "Next:" in result.stdout
    loaded = store.load()
    assert loaded.experiences[0].bullets[1].text == "Shipped the API."


def test_add_experience_via_prompts(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)

    result = runner.invoke(
        app,
        ["add", "experience"],
        input="Data Analyst\nContoso\n2019 – 2020\n\nRan A/B tests.\n\n",
    )
    assert result.exit_code == 0
    assert "[exp.2]" in result.stdout
    loaded = store.load()
    assert loaded.experiences[1].title == "Data Analyst"
    assert loaded.experiences[1].org == "Contoso"
    assert loaded.experiences[1].bullets[0].text == "Ran A/B tests."


def test_bare_resume_shows_status_and_next(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Status:" in result.stdout
    assert "[exp.1]" in result.stdout
    assert "Next:" in result.stdout


def test_init_skips_when_warehouse_exists(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)
    result = runner.invoke(app, ["init"], input="quit\n")
    assert result.exit_code == 0
    assert "Already set up" in result.stdout
    assert "[exp.1]" in result.stdout
    assert "What next?" in result.stdout


def test_init_imports_first_pdf(tmp_path, monkeypatch):
    from pathlib import Path

    store = ProfileStore(tmp_path / "profile.yaml")
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)
    pdf = Path(__file__).resolve().parents[2] / "samples" / "swe.pdf"
    result = runner.invoke(app, ["init", str(pdf)], input="n\nquit\n")
    assert result.exit_code == 0
    assert "Imported." in result.stdout
    assert "warehouse is ready" in result.stdout
    assert store.exists()
    assert store.load().personal.name == "Jane Doe"


def test_init_loop_paste_then_quit(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)
    result = runner.invoke(
        app,
        ["init"],
        input="paste\nNeed Python and Go.\n\nquit\n",
    )
    assert result.exit_code == 0
    assert "Keep" in result.stdout
    assert "What next?" in result.stdout


def test_import_merge_without_warehouse_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cli.ProfileStore", lambda: ProfileStore(tmp_path / "profile.yaml"))
    result = runner.invoke(app, ["import", "--merge", "/tmp/missing.pdf"])
    assert result.exit_code == 1
    assert "Nothing imported yet" in result.output
    assert "resume init" in result.output
