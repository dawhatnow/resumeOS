"""Rewrite approved bullets toward the job's wording. AI proposes, code enforces.

One batched call for all bullets; each answer goes through the TruthGuard;
failures get one retry that says exactly what was wrong; anything still
failing keeps its original text. Results are proposals for the review
screen — never written to profile.yaml.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.provider import LLMProvider, ProviderError
from app.guard import TruthGuard
from app.models import JobAnalysis, JobPosting, Profile

SYSTEM = """You tailor resume bullets so an applicant tracking system (ATS) matches them to a job.

Rules — breaking any of them gets the bullet thrown away:
1. Keep every fact. Add no new facts, results, numbers, tools, or claims.
2. Keep EVERY number from the original, exactly as written (metrics are the most valuable part). Add no other numbers.
3. Only name technologies that are in the original text or in its "may_use" list. Keep every "may_use" term the original already mentions.
4. Where it is truthful, use the job's exact wording from "may_use" (ATS matches exact keywords).
5. One sentence, starting with a strong past-tense verb. No "I", no buzzword filler.
6. Stay under "max_chars" characters. Shorter is better.
7. If a bullet already reads well for this job, return it unchanged.

Reply with JSON only: {"bullets": [{"id": "<id>", "text": "<rewritten bullet>"}]}, every id exactly once."""


class RewriteCache:
    """~/.resume/cache/rewrites/<hash>.json — same model + same bullet + same
    job wording → no new call. Keyed on everything the answer depends on,
    including the prompt, so changing any of them misses the cache."""

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            base = os.environ.get("RESUME_HOME")
            root = (Path(base).expanduser() if base else Path.home() / ".resume") / "cache" / "rewrites"
        self._root = root

    def key(self, model: str, entry: dict, job_title: str) -> str:
        blob = json.dumps([SYSTEM, model, job_title, entry["original"], entry["may_use"], entry["max_chars"]])
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def get(self, key: str) -> str | None:
        path = self._root / f"{key}.json"
        try:
            return json.loads(path.read_text())["text"]
        except (OSError, ValueError, KeyError):
            return None

    def put(self, key: str, text: str) -> None:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            (self._root / f"{key}.json").write_text(json.dumps({"text": text}))
        except OSError:
            pass  # a cache that can't write is just a miss next time


@dataclass
class RewriteResult:
    accepted: dict[str, str] = field(default_factory=dict)  # id → new text, passed the guard
    rejected: dict[str, list[str]] = field(default_factory=dict)  # id → why (kept original)
    unchanged: list[str] = field(default_factory=list)
    calls: int = 0
    cached: int = 0  # answers reused from ~/.resume/cache/rewrites


class BulletWriter:
    def __init__(self, provider: LLMProvider, profile: Profile, cache: RewriteCache | None = None) -> None:
        self._provider = provider
        self._profile = profile
        self._guard = TruthGuard(profile)
        self._cache = cache if cache is not None else RewriteCache()

    def rewrite(
        self, bullet_ids: list[str], analysis: JobAnalysis, posting: JobPosting, on_text=None
    ) -> RewriteResult:
        """Raises ProviderError if the LLM can't be reached at all."""
        result = RewriteResult()
        wanted = list(dict.fromkeys(analysis.must_have + analysis.nice_to_have + analysis.keywords))
        todo = [bid for bid in bullet_ids if self._profile.find_bullet(bid)]
        keys = {
            bid: self._cache.key(self._provider.label, self._bullet_payload(bid, wanted, None), posting.title or "")
            for bid in todo
        }
        for bid in list(todo):
            hit = self._cache.get(keys[bid])
            if hit is None:
                continue
            original = self._profile.find_bullet(bid).text
            if _same(hit, original):
                result.unchanged.append(bid)
            elif not self._guard.check_rewrite(bid, hit, wanted):  # re-verify: warehouse may have changed
                result.accepted[bid] = hit
            else:
                continue  # stale cache entry: ask again
            result.cached += 1
            todo.remove(bid)
        feedback: dict[str, dict] = {}
        for attempt in range(2):  # first try, then one retry for failures
            if not todo:
                break
            payload = {
                "job_title": posting.title or "",
                "job_keywords": analysis.must_have + analysis.nice_to_have,
                "bullets": [self._bullet_payload(bid, wanted, feedback.get(bid)) for bid in todo],
            }
            raw = self._provider.complete(SYSTEM, json.dumps(payload, ensure_ascii=False), on_text=on_text)
            result.calls += 1
            answers = _parse(raw)
            retry: list[str] = []
            for bid in todo:
                text = _clean(answers.get(bid, ""))
                original = self._profile.find_bullet(bid).text
                if not text:
                    problems = ["No rewrite returned for this bullet."]
                elif _same(text, original):
                    result.unchanged.append(bid)
                    self._cache.put(keys[bid], original)
                    continue
                else:
                    problems = self._guard.check_rewrite(bid, text, wanted)
                    if not problems:
                        result.accepted[bid] = text
                        self._cache.put(keys[bid], text)
                        continue
                if attempt == 0:
                    feedback[bid] = {"previous_attempt": text, "problems": problems}
                    retry.append(bid)
                else:
                    result.rejected[bid] = problems
            todo = retry
        return result

    def _bullet_payload(self, bid: str, wanted: list[str], feedback: dict | None) -> dict:
        entry = {
            "id": bid,
            "original": self._profile.find_bullet(bid).text,
            "may_use": self._guard.allowed_terms(bid, wanted),
            "max_chars": self._guard.max_chars(bid),
        }
        if feedback:
            entry.update(feedback)
        return entry


def _parse(raw: str) -> dict[str, str]:
    """{"bullets": [{id, text}]} → {id: text}. Tolerates code fences and chatter."""
    for candidate in (raw, *re.findall(r"\{.*\}", raw, re.S)):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        items = data.get("bullets", data) if isinstance(data, dict) else data
        if isinstance(items, list):
            return {str(i.get("id")): str(i.get("text", "")) for i in items if isinstance(i, dict)}
        if isinstance(items, dict):  # {"exp.1.1": "text", ...}
            return {str(k): str(v) for k, v in items.items() if isinstance(v, str)}
    raise ProviderError("The model didn't return usable JSON. Try again, or another model.")


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip().lstrip("•-* ").strip()
    return text[:1].upper() + text[1:] if text else text


def _same(a: str, b: str) -> bool:
    norm = lambda s: re.sub(r"[\W_]+", " ", s).strip().lower()
    return norm(a) == norm(b)
