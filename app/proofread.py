"""Proofread resume text: spelling, grammar, and resume style. Local only.

Engines (config.toml `[proofread] engine = "auto" | "languagetool" | "basic" | "off"`):
- languagetool: LanguageTool (en-CA) running locally on Java. Spelling and
  grammar. Optional: pip install "resumeOS[grammar]". First use downloads it
  once (~260 MB) into ~/.resume/cache/languagetool; nothing is sent anywhere.
- basic: offline word-list spell check (no Java needed). Spelling only.
- auto (default): languagetool if it's installed and Java is available, else basic.

Style rules are plain code and always run. Tech names, acronyms, product
names, and words in ~/.resume/dictionary.txt are never flagged as typos.
"""

import os
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from app.models import Profile


@dataclass
class Issue:
    where: str  # bullet id, item id (title), or "summary"
    text: str  # the full text that was checked
    start: int
    end: int
    kind: str  # "spelling" | "grammar" | "style"
    message: str
    suggestions: list[str] = field(default_factory=list)

    @property
    def snippet(self) -> str:
        return self.text[self.start:self.end]


# --- style rules (resume conventions, not English grammar) ---

_WEAK_OPENERS = re.compile(
    r"^(responsible for|helped( to)?|worked on|assisted( with| in)?|participated in|involved in|"
    r"duties included|tasked with|in charge of)\b",
    re.I,
)
_FIRST_PERSON = re.compile(r"\b(I|me|my|we|our|us)\b")
_PLACEHOLDER = re.compile(r"\[[^\]]*\]|\b(TODO|TBD|XXX|FIXME)\b|\?\?+")
_BUZZWORDS = re.compile(
    r"\b(synergy|synergies|go-getter|hard-working|hardworking|team player|detail-oriented|"
    r"results-driven|self-starter|think outside the box|dynamic individual)\b",
    re.I,
)
_PRESENT_VERBS = {
    "build", "develop", "design", "lead", "manage", "create", "implement", "maintain", "own", "run",
    "write", "analyze", "analyse", "deliver", "drive", "support", "work", "teach", "train", "coordinate",
}
MAX_BULLET_CHARS = 260


def style_issues(where: str, text: str, *, current_role: bool) -> list[Issue]:
    issues: list[Issue] = []

    def add(m_start: int, m_end: int, message: str, suggestions: list[str] | None = None) -> None:
        issues.append(Issue(where, text, m_start, m_end, "style", message, suggestions or []))

    if m := _WEAK_OPENERS.match(text):
        add(m.start(), m.end(), "Weak opener — start with what you did (Built, Led, Cut…).")
    for m in _FIRST_PERSON.finditer(text):
        add(m.start(), m.end(), "Drop first person on a resume.")
    for m in _PLACEHOLDER.finditer(text):
        add(m.start(), m.end(), "Looks like a placeholder — fill in the real value.")
    for m in _BUZZWORDS.finditer(text):
        add(m.start(), m.end(), "Buzzword — show it with a result instead.")
    for m in re.finditer(r"  +|\s+(?=[,.;:])", text):
        add(m.start(), m.end(), "Extra space.", [" " if m.group().startswith("  ") else ""])
    if (m := re.match(r"[A-Za-z]+", text)) and not current_role:
        word = m.group().lower()
        if word in _PRESENT_VERBS or word.endswith("ing") or (word[:-1] in _PRESENT_VERBS and word.endswith("s")):
            add(m.start(), m.end(), "Past role — use past tense (Built, Led…).")
    if text[:1].islower():
        add(0, 1, "Start with a capital letter.", [text[:1].upper()])
    if len(text) > MAX_BULLET_CHARS:
        add(0, len(text), f"Long bullet ({len(text)} chars) — aim for under {MAX_BULLET_CHARS}.")
    return issues


def repeated_openers(bullets: dict[str, str]) -> list[Issue]:
    """Same first word on 2+ bullets of one job/project."""
    by_item: dict[str, dict[str, list[str]]] = {}
    for bid, text in bullets.items():
        m = re.match(r"[A-Za-z]+", text)
        if m and "." in bid:
            by_item.setdefault(bid.rsplit(".", 1)[0], {}).setdefault(m.group().lower(), []).append(bid)
    issues = []
    for groups in by_item.values():
        for word, ids in groups.items():
            for bid in ids[1:]:
                text = bullets[bid]
                issues.append(Issue(bid, text, 0, len(word), "style",
                                    f"“{text[:len(word)]}” also starts {ids[0]} — vary the verb."))
    return issues


# --- spelling / grammar engines ---

# Common tech/business words ordinary dictionaries don't know.
TECH_WORDS = {
    "backend", "frontend", "config", "configs", "metadata", "onboarding", "analytics", "dataset", "datasets",
    "runtime", "wireframes", "wireframe", "lakehouse", "queryable", "pytest", "rps", "structs", "struct",
    "val", "repo", "repos", "api", "apis", "sdk", "cli", "ui", "ux", "devops", "microservice", "microservices",
    "kubernetes", "postgres", "async", "middleware", "webhook", "webhooks", "codebase", "dashboarding",
    "scalable", "latency", "throughput", "hackathon", "subreddit", "ingestion", "upsert", "failover",
    "dockerized", "containerized", "serverless", "runbook", "runbooks", "stakeholder", "stakeholders",
}
_PREFIXES = {"multi", "non", "co", "pre", "re", "sub", "self", "ad", "hoc", "mid", "cross", "semi", "anti", "post", "inter", "intra", "de", "un", "bi", "tri", "e"}
# Rules too pedantic for resume fragments.
_DISABLED_RULES = {"EN_COMPOUNDS_MULTI_PAGE", "UPPERCASE_SENTENCE_START", "PUNCTUATION_PARAGRAPH_END", "EN_QUOTES", "DASH_RULE"}


def dictionary_path() -> Path:
    root = os.environ.get("RESUME_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".resume") / "dictionary.txt"


def load_dictionary(path: Path | None = None) -> set[str]:
    path = path or dictionary_path()
    if not path.exists():
        return set()
    return {w.strip().lower() for w in path.read_text().splitlines() if w.strip() and not w.startswith("#")}


def add_to_dictionary(word: str, path: Path | None = None) -> Path:
    path = path or dictionary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    words = load_dictionary(path)
    if word.lower() not in words:
        with path.open("a") as f:
            f.write(word.strip() + "\n")
    return path


def _looks_like_a_name(token: str, is_first_word: bool) -> bool:
    """Product names, acronyms, versions: FastAPI, ONNX, TWAP, C++20, Genesys."""
    if any(c.isdigit() for c in token):
        return True
    letters = [c for c in token if c.isalpha()]
    if sum(c.isupper() for c in letters) >= 2:
        return True
    return token[:1].isupper() and not is_first_word


class _SpellEngine:
    name = "basic"

    def __init__(self) -> None:
        from spellchecker import SpellChecker

        self._checker = SpellChecker(distance=1)  # typos are 1 edit away; distance 2 is ~10x slower

    def check(self, text: str) -> list[tuple[int, int, str, str, list[str]]]:
        out = []
        for m in re.finditer(r"[A-Za-z][A-Za-z'’]*(?:-[A-Za-z]+)*", text):
            word = m.group().rstrip("'’").removesuffix("’s").removesuffix("'s")
            if len(word) < 3:
                continue
            lower = word.lower()
            if "-" in lower:  # multi-page, ad-hoc, real-time: every part must be a word or prefix
                if all(part in _PREFIXES or self._checker.known([part]) or self._canadian(part)
                       for part in lower.split("-") if part):
                    continue
            elif self._checker.known([lower]) or self._canadian(lower):
                continue
            fix = self._checker.correction(lower)
            suggestions = [fix if word.islower() else fix.capitalize()] if fix and fix != lower else []
            out.append((m.start(), m.start() + len(word), "spelling", "Possible spelling mistake.", suggestions))
        return out

    def _canadian(self, word: str) -> bool:
        """colour, centre, modelling, analyse, organise… count as correct."""
        variants = {
            re.sub(r"our(s|ed|ing)?$", r"or\1", word),
            re.sub(r"re(s|d)?$", r"er\1", word),
            word.replace("lling", "ling").replace("lled", "led"),
            re.sub(r"is(e|ed|es|ing|ation)$", r"iz\1", word),
            re.sub(r"ys(e|ed|es|ing)$", r"yz\1", word),
            word.replace("ogue", "og"),
        } - {word}
        return bool(self._checker.known(variants))

    def close(self) -> None:
        pass


class _LanguageToolEngine:
    name = "languagetool"

    def __init__(self) -> None:
        languagetool_cache()  # sets LTP_PATH before the library reads it
        try:
            import language_tool_python
        except ImportError:
            raise RuntimeError('not installed — pip install "resumeOS[grammar]"') from None

        self._tool = language_tool_python.LanguageTool("en-CA")
        self._tool.disabled_rules.update(_DISABLED_RULES)

    def check(self, text: str) -> list[tuple[int, int, str, str, list[str]]]:
        out = []
        for m in self._tool.check(text):
            if m.rule_id.startswith("EN_COMPOUNDS"):
                continue
            spelling = m.rule_id.startswith("MORFOLOGIK") or (m.category or "").upper() == "TYPOS"
            kind = "spelling" if spelling else "style" if (m.category or "").upper() == "STYLE" else "grammar"
            out.append((m.offset, m.offset + m.error_length, kind, m.message, list(m.replacements[:3])))
        return out

    def close(self) -> None:
        self._tool.close()


def java_available() -> bool:
    return shutil.which("java") is not None


def languagetool_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("language_tool_python") is not None


def languagetool_cache() -> Path:
    """Keep LanguageTool's download under ~/.resume/cache like everything else.
    Moves an earlier download from ~/.cache instead of fetching 260 MB again."""
    root = os.environ.get("RESUME_HOME")
    cache = (Path(root).expanduser() if root else Path.home() / ".resume") / "cache" / "languagetool"
    legacy = Path.home() / ".cache" / "language_tool_python"
    if not cache.exists() and legacy.is_dir() and any(legacy.iterdir()):
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(cache))
    os.environ.setdefault("LTP_PATH", str(cache))
    return Path(os.environ["LTP_PATH"])


def first_languagetool_run() -> bool:
    cache = languagetool_cache()
    return not cache.exists() or not any(cache.iterdir())


def configured_engine() -> str:
    root = os.environ.get("RESUME_HOME")
    path = (Path(root).expanduser() if root else Path.home() / ".resume") / "config.toml"
    engine = "auto"
    if path.exists():
        try:
            engine = tomllib.loads(path.read_text()).get("proofread", {}).get("engine", "auto")
        except tomllib.TOMLDecodeError:
            pass
    engine = os.environ.get("RESUME_PROOFREAD", engine).lower()
    if engine == "auto":
        return "languagetool" if java_available() and languagetool_installed() else "basic"
    return engine


class Proofreader:
    """check(texts) → issues. Build once and reuse: LanguageTool takes a few
    seconds to start."""

    def __init__(self, profile: Profile, engine: str | None = None, dictionary: set[str] | None = None) -> None:
        from app.analyzing.analyzer import profile_vocabulary
        from app.analyzing.terms import LEXICON

        self._profile = profile
        self.note = ""
        known = {w.lower() for term in profile_vocabulary(profile) for w in re.findall(r"[A-Za-z]+", term)}
        known |= {w.lower() for d, aliases in LEXICON.items() for t in [d, *aliases] for w in re.findall(r"[A-Za-z]+", t)}
        self._ignore = known | TECH_WORDS | (dictionary if dictionary is not None else load_dictionary())
        self._engine = None
        name = engine or configured_engine()
        if name == "languagetool":
            try:
                self._engine = _LanguageToolEngine()
            except Exception as e:  # not installed, no/old Java, download blocked, …
                reason = str(e) if isinstance(e, RuntimeError) else e.__class__.__name__
                self.note = f"LanguageTool unavailable ({reason}); using basic spell check."
                name = "basic"
        if name == "basic":
            self._engine = _SpellEngine()
        self.engine = self._engine.name if self._engine else "off"

    def ignore(self, word: str) -> None:
        self._ignore.add(word.lower())

    def check(self, texts: dict[str, str]) -> list[Issue]:
        current = {i.id for i in self._profile.all_items() if i.dates and re.search(r"present|now|current", i.dates, re.I)}
        issues: list[Issue] = []
        for where, text in texts.items():
            if not text:
                continue
            item_id = where.rsplit(".", 1)[0] if where.count(".") >= 2 else where
            if where.count(".") >= 2:  # bullets only
                issues += style_issues(where, text, current_role=item_id in current)
            if self._engine is None:
                continue
            first_word_end = (re.match(r"\S+", text) or re.match("", text)).end()
            for start, end, kind, message, suggestions in self._engine.check(text):
                token = text[start:end]
                if kind == "spelling":
                    word = token.strip("'’")
                    if word.lower() in self._ignore or _looks_like_a_name(word, start < first_word_end):
                        continue
                    if any(part.lower() in self._ignore for part in re.split(r"[-/]", word)) and "-" in word:
                        continue
                issues.append(Issue(where, text, start, end, kind, message, suggestions))
        issues += repeated_openers({w: t for w, t in texts.items() if w.count(".") >= 2})
        order = {w: n for n, w in enumerate(texts)}
        issues.sort(key=lambda i: (order.get(i.where, 0), i.start))
        return issues

    def close(self) -> None:
        if self._engine:
            self._engine.close()


def warehouse_texts(profile: Profile) -> dict[str, str]:
    texts: dict[str, str] = {}
    if profile.summary:
        texts["summary"] = profile.summary
    for item in profile.all_items():
        texts[item.id] = item.title
        for bullet in item.bullets:
            texts[bullet.id] = bullet.text
    return texts


def apply_fix(text: str, issue: Issue, replacement: str) -> str:
    return text[:issue.start] + replacement + text[issue.end:]
