import re

from app.models import Personal

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s,]+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(
    r"(?<![\w@./])[a-zA-Z0-9-]+\.(?:com|io|dev|net|org|co|me|ai)\b(?:/[^\s,]*)?",
    re.IGNORECASE,
)


class ContactInfoParser:
    """Extracts name/email/phone/links from resume text via regex."""

    def parse(self, text: str, extra_links: list[str] | None = None) -> Personal:
        email_match = _EMAIL_RE.search(text)
        phone_match = _PHONE_RE.search(text)
        found_links = _URL_RE.findall(text) + _BARE_DOMAIN_RE.findall(text) + (extra_links or [])

        return Personal(
            name=self._first_line(text),
            email=email_match.group(0) if email_match else None,
            phone=phone_match.group(0) if phone_match else None,
            links=list(dict.fromkeys(found_links)),
        )

    def _first_line(self, text: str) -> str | None:
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line
        return None
