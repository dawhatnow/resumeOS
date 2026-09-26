import pytest


@pytest.fixture(autouse=True)
def _isolated_resume_home(tmp_path, monkeypatch):
    """Unit tests never read the real ~/.resume (aliases, config, dictionary, caches)."""
    home = tmp_path / "resume-home"
    home.mkdir()
    monkeypatch.setenv("RESUME_HOME", str(home))
    for var in ("RESUME_LLM_PROVIDER", "RESUME_LLM_MODEL", "RESUME_PROOFREAD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("RESUME_SEMANTIC", "0")  # no model downloads; semantic tests use a fake
    return home
