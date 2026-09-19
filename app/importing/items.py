import re
from abc import ABC, abstractmethod

from app.importing.text_utils import extract_numbers, is_bullet, strip_bullet
from app.models import Bullet, Item

_DATE_TOKEN = r"(?:[A-Za-z]+\.?\s*\d{4}|\d{4})"
_DATE_RANGE = rf"{_DATE_TOKEN}\s*[–\-]\s*(?:Present|{_DATE_TOKEN})"

EXPERIENCE_HEADER_RE = re.compile(rf"^(?P<title>.+?)\s*@\s*(?P<org>.+?)\s+(?P<dates>{_DATE_RANGE})\s*$")

PROJECT_TECH_RE = re.compile(
    r"(?:[§#|/]\s*)?\b(?:Code|Github|GitHub|Devpost|Live|Demo)\b\s+"
    r"(?P<tech>(?:[\w+#./-]+(?:\s[\w+#./-]+)*\s*,\s*)+[\w+#./-]+(?:\s[\w+#./-]+)*)\s*$"
)


class ItemParser(ABC):
    """Parses a section's lines into a list of Items (experience or project
    entries) with their bullets. Non-bullet lines are ambiguous — they're
    either a new item's header or the word-wrapped continuation of whatever
    came before — so a line only starts a new item when a subclass recognizes
    it as a genuine header; otherwise it's folded onto the previous bullet or
    the current item's location field."""

    def parse(self, lines: list[str], id_prefix: str) -> list[Item]:
        items: list[Item] = []
        current: Item | None = None
        last_bullet: Bullet | None = None

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            if is_bullet(line):
                if current is None:
                    continue
                last_bullet = self._append_bullet(current, line)
                continue

            header = self._parse_header(line)
            if header is None and current is None:
                header = self._fallback_item(line)

            if header is not None:
                header.id = f"{id_prefix}.{len(items) + 1}"
                current = header
                items.append(current)
                last_bullet = None
            elif last_bullet is not None:
                last_bullet.text = f"{last_bullet.text} {line}".strip()
                last_bullet.numbers = extract_numbers(last_bullet.text)
            else:
                current.location = f"{current.location} {line}".strip() if current.location else line

        return items

    def _append_bullet(self, item: Item, line: str) -> Bullet:
        text = strip_bullet(line)
        bullet = Bullet(id=f"{item.id}.{len(item.bullets) + 1}", text=text, numbers=extract_numbers(text))
        item.bullets.append(bullet)
        return bullet

    @abstractmethod
    def _parse_header(self, line: str) -> Item | None:
        """Return a new Item if this line is a confident, positive signal
        of a new entry starting; otherwise None (treated as continuation)."""

    @abstractmethod
    def _fallback_item(self, line: str) -> Item:
        """Best-effort Item when no positive header signal exists but we
        still need to start the very first item in the section."""


class ExperienceItemParser(ItemParser):
    """Header lines look like 'Title @ Org May 2026 – Aug 2026'."""

    def _parse_header(self, line: str) -> Item | None:
        match = EXPERIENCE_HEADER_RE.match(line)
        if not match:
            return None
        return Item(
            id="",
            title=match.group("title").strip(),
            org=match.group("org").strip(),
            dates=match.group("dates").strip(),
        )

    def _fallback_item(self, line: str) -> Item:
        return Item(id="", title=line)


class ProjectItemParser(ItemParser):
    """Header lines carry an inline tech list after a link label, e.g.
    'Bin Inventory Verification Service § Code Python, PyTorch, AWS'."""

    def _parse_header(self, line: str) -> Item | None:
        match = PROJECT_TECH_RE.search(line)
        if not match:
            return None
        title = line[: match.start()].strip(" -–§#|/")
        tech = [t.strip() for t in match.group("tech").split(",") if t.strip()]
        return Item(id="", title=title, tech=tech)

    def _fallback_item(self, line: str) -> Item:
        return Item(id="", title=line.strip())
