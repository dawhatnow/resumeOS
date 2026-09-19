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
