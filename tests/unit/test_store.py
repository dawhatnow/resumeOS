import pytest

from app.models import Bullet, EducationEntry, Item, Personal, Profile
from app.store import ProfileStore


def _profile():
    return Profile(
        personal=Personal(name="Jane Doe", email="jane@example.com", links=["https://github.com/jane"]),
        summary="A summary.",
        experiences=[Item(id="exp.1", title="Engineer", org="Acme", dates="2023 - Present",
                           tech=["Python"], bullets=[Bullet(id="exp.1.1", text="Did a thing.", numbers=["5"])])],
        education=[EducationEntry(school="State U", degree="BS CS", dates="2020", details=["GPA: 3.8"])],
        skills=["Python", "Go"],
        vocabulary=["Python", "Go"],
        other_sections={"awards": ["Employee of the Year"]},
        raw_text="raw text here",
    )


def test_save_creates_parent_dirs(tmp_path):
    store = ProfileStore(path=tmp_path / "nested" / "profile.yaml")
    saved_path = store.save(_profile())
    assert saved_path.exists()


def test_load_missing_profile_raises(tmp_path):
    store = ProfileStore(path=tmp_path / "profile.yaml")
    with pytest.raises(FileNotFoundError):
        store.load()


def test_round_trip_preserves_data(tmp_path):
    store = ProfileStore(path=tmp_path / "profile.yaml")
    original = _profile()
    store.save(original)

    loaded = store.load()

    assert loaded.personal.name == original.personal.name
    assert loaded.personal.links == original.personal.links
    assert loaded.experiences[0].bullets[0].text == "Did a thing."
    assert loaded.experiences[0].bullets[0].numbers == ["5"]
    assert loaded.education[0].school == "State U"
    assert loaded.skills == ["Python", "Go"]
    assert loaded.other_sections == {"awards": ["Employee of the Year"]}


def test_exists_reflects_file_presence(tmp_path):
    store = ProfileStore(path=tmp_path / "profile.yaml")
    assert not store.exists()
    store.save(_profile())
    assert store.exists()
