from app.paths import ResumePathResolver


def test_plain_linux_path_unchanged():
    assert str(ResumePathResolver().resolve("/root/resume.pdf")) == "/root/resume.pdf"


def test_expands_home_dir():
    resolved = str(ResumePathResolver().resolve("~/resume.pdf"))
    assert resolved.startswith("/") and resolved.endswith("/resume.pdf")
    assert "~" not in resolved


def test_windows_path_converts_to_wsl_mount():
    resolved = ResumePathResolver().resolve(r"C:\Users\daman\Downloads\resume.pdf")
    assert str(resolved) == "/mnt/c/Users/daman/Downloads/resume.pdf"


def test_file_uri_with_percent_encoding():
    resolved = ResumePathResolver().resolve("file:///C:/Users/daman/Downloads/resume%20(3).pdf")
    assert str(resolved) == "/mnt/c/Users/daman/Downloads/resume (3).pdf"


def test_strips_surrounding_quotes():
    resolved = ResumePathResolver().resolve('"/root/resume.pdf"')
    assert str(resolved) == "/root/resume.pdf"
