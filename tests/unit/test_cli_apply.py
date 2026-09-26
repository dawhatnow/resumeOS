from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.importing.profile_builder import ProfileImporter
from app.store import ProfileStore
from app.warehouse import ProfileMerger

runner = CliRunner()

SWE = """Jane Doe
jane@example.com

Experience
Senior Backend Engineer @ Acme Jan 2023 – Present
• Shipped APIs in Go and PostgreSQL.

Projects
Task Queue § Code Python, Redis
• Queue in Python.

Technical Skills
Python, Go, PostgreSQL
"""

DS = """Jane Doe
jane@example.com

Experience
Data Analyst @ Contoso Jan 2019 – May 2020
• Analyzed A/B tests in SQL and pandas.

Projects
Churn Predictor § Code Python, pandas, scikit-learn
• Classification model in pandas.

Technical Skills
pandas, SQL, scikit-learn
"""


def _seed_mixed(store: ProfileStore) -> None:
    base = ProfileImporter().import_text(SWE)
    merged, _ = ProfileMerger().merge(base, ProfileImporter().import_text(DS))
    store.save(merged)


def test_new_from_file_prints_coverage(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profile.yaml")
    _seed_mixed(store)
    monkeypatch.setattr("app.cli.ProfileStore", lambda: store)
    jd = tmp_path / "jd.txt"
    jd.write_text("Data Scientist\nRequirements\npandas and SQL required.\n")
    result = runner.invoke(app, ["new", str(jd), "--no-pdf"])
    assert result.exit_code == 0
    assert "Must-haves:" in result.stdout
    assert "Keep" in result.stdout
    assert "Next:" in result.stdout


def test_new_without_warehouse(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cli.ProfileStore", lambda: ProfileStore(tmp_path / "missing.yaml"))
    result = runner.invoke(app, ["new", "https://example.com/job"])
    assert result.exit_code == 1
    assert "resume init" in result.output
