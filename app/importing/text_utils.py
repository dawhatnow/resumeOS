import re

_BULLET_PREFIX_RE = re.compile(r"^[•\-\*]\s*")
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\$?\d[\d,]*(?:\.\d+)?%?\+?")


def is_bullet(line: str) -> bool:
    return bool(_BULLET_PREFIX_RE.match(line.strip()))


def strip_bullet(line: str) -> str:
    return _BULLET_PREFIX_RE.sub("", line.strip()).strip()


def extract_numbers(text: str) -> list[str]:
    """Numeric claims in a bullet, for the truth guard to check against later.
    Excludes digits glued onto letters (ResNet18, S3) via the alnum lookbehind."""
    return _NUMBER_RE.findall(text)
