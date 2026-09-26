import re
import urllib.parse
from pathlib import Path


class ResumePathResolver:
    """Turns whatever a user pastes into a prompt (a file:// URI, a Windows
    path copied under WSL, a quoted path, ~) into a real filesystem Path."""

    _WINDOWS_PATH_RE = re.compile(r"^([A-Za-z]):[\\/](.*)")

    def resolve(self, raw: str) -> Path:
        raw = raw.strip().strip('"').strip("'")
        raw = self._strip_file_uri(raw)
        raw = self._convert_windows_path(raw)
        return Path(raw).expanduser()

    def _strip_file_uri(self, raw: str) -> str:
        if not raw.startswith("file://"):
            return raw
        raw = urllib.parse.unquote(urllib.parse.urlparse(raw).path)
        if re.match(r"^/[A-Za-z]:", raw):
            raw = raw[1:]  # "/C:/Users/..." -> "C:/Users/..."
        return raw

    def _convert_windows_path(self, raw: str) -> str:
        match = self._WINDOWS_PATH_RE.match(raw)
        if not match:
            return raw
        drive, rest = match.groups()
        return f"/mnt/{drive.lower()}/{rest.replace(chr(92), '/')}"


def desktop_dir() -> Path:
    """Where finished PDFs go. RESUME_OUTPUT_DIR wins; under WSL, the real
    Windows Desktop (often OneDrive\\Desktop); else ~/Desktop; else cwd."""
    import os
    import shutil
    import subprocess

    override = os.environ.get("RESUME_OUTPUT_DIR")
    if override:
        return Path(override).expanduser()
    if shutil.which("powershell.exe"):
        try:
            out = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
            path = ResumePathResolver().resolve(out) if out else None
            if path and path.is_dir():
                return path
        except (OSError, subprocess.SubprocessError):
            pass
    home_desktop = Path.home() / "Desktop"
    return home_desktop if home_desktop.is_dir() else Path.cwd()


def windows_path(path: Path) -> str | None:
    """/mnt/c/Users/x → C:\\Users\\x, so WSL users can find the file."""
    m = re.match(r"^/mnt/([a-z])/(.*)", str(path))
    return f"{m.group(1).upper()}:\\{m.group(2).replace('/', chr(92))}" if m else None


def open_file(path: Path) -> bool:
    """Open a file in the user's default app (Windows viewer under WSL).
    Returns False if there's no way to do it here."""
    import shutil
    import subprocess

    win = windows_path(path)
    try:
        if win and shutil.which("explorer.exe"):
            # explorer.exe returns 1 even on success; don't check.
            subprocess.Popen(["explorer.exe", win], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        for opener in ("wslview", "xdg-open", "open"):
            if shutil.which(opener):
                subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
    except OSError:
        pass
    return False
