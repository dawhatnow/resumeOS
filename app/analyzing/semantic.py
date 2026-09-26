"""Meaning-based bullet relevance with a small local embedding model.

Keywords miss bullets that describe the right work in other words ("monthly
ingestion from the StatCan API" vs "data pipelines"). This adds a bounded
bonus for bullets that are close in meaning to the JD's requirement lines.
It only ranks: coverage (what an ATS sees) stays keyword-based.

Optional: pip install "resumeOS[embeddings]" (fastembed + ONNX, no PyTorch).
The model (~65 MB) downloads once into ~/.resume/cache/embeddings/models;
bullet vectors are cached next to it. Nothing leaves your machine after that.
Off with `[match] semantic = false` in config.toml or RESUME_SEMANTIC=0.
"""

import hashlib
import json
import os
import tomllib
from pathlib import Path

MODEL = "BAAI/bge-small-en-v1.5"
# bge-small similarities are compressed: unrelated text sits ~0.45–0.55,
# related ~0.65–0.8. Below FLOOR counts as nothing, at CEIL as a full match.
FLOOR, CEIL = 0.60, 0.80
MUST_BONUS = 2.0  # a keyword must-have is worth 3, so keywords still lead
NICE_BONUS = 1.0


def _home() -> Path:
    root = os.environ.get("RESUME_HOME")
    return Path(root).expanduser() if root else Path.home() / ".resume"


def semantic_enabled() -> bool:
    import importlib.util

    env = os.environ.get("RESUME_SEMANTIC")
    if env is not None:
        return env.lower() not in {"0", "false", "off", "no"}
    cfg = _home() / "config.toml"
    if cfg.exists():
        try:
            if tomllib.loads(cfg.read_text()).get("match", {}).get("semantic") is False:
                return False
        except tomllib.TOMLDecodeError:
            pass
    return importlib.util.find_spec("fastembed") is not None


def _scaled(sim: float) -> float:
    return max(0.0, min(1.0, (sim - FLOOR) / (CEIL - FLOOR)))


class SemanticMatcher:
    def __init__(self, embed=None) -> None:
        """embed: texts → list of vectors. Default loads fastembed lazily;
        tests pass a fake."""
        self._embed_fn = embed
        self._cache_path = _home() / "cache" / "embeddings" / f"vectors-{MODEL.replace('/', '_')}.json"
        self._cache: dict[str, list[float]] | None = None

    def bonuses(
        self, bullets: dict[str, str], must_lines: list[str], nice_lines: list[str]
    ) -> dict[str, tuple[float, str]]:
        """bullet id → (bonus, closest requirement line)."""
        import numpy as np

        if not bullets or not (must_lines or nice_lines):
            return {}
        ids = list(bullets)
        B = self._vectors([bullets[i] for i in ids], cache=True)
        out: dict[str, tuple[float, str]] = {}
        best_line = {i: ("", 0.0) for i in ids}
        bonus = {i: 0.0 for i in ids}
        for lines, weight in ((must_lines, MUST_BONUS), (nice_lines, NICE_BONUS)):
            if not lines:
                continue
            L = self._vectors(lines, cache=False)
            sims = B @ L.T
            for row, bid in enumerate(ids):
                j = int(np.argmax(sims[row]))
                s = float(sims[row, j])
                bonus[bid] = max(bonus[bid], weight * _scaled(s))
                if s > best_line[bid][1]:
                    best_line[bid] = (lines[j], s)
        for bid in ids:
            out[bid] = (round(bonus[bid], 3), best_line[bid][0] if bonus[bid] > 0 else "")
        self._save()
        return out

    # --- vectors ---

    def _vectors(self, texts: list[str], *, cache: bool):
        import numpy as np

        if cache:
            store = self._load()
            keys = [hashlib.sha256(t.encode()).hexdigest()[:24] for t in texts]
            missing = [t for t, k in zip(texts, keys) if k not in store]
            if missing:
                for k, v in zip(
                    [hashlib.sha256(t.encode()).hexdigest()[:24] for t in missing], self._embed(missing)
                ):
                    store[k] = [float(x) for x in v]
            M = np.array([store[k] for k in keys], dtype=float)
        else:
            M = np.array(list(self._embed(texts)), dtype=float)
        return M / np.clip(np.linalg.norm(M, axis=1, keepdims=True), 1e-9, None)

    def _embed(self, texts: list[str]):
        if self._embed_fn is None:
            from fastembed import TextEmbedding

            model = TextEmbedding(MODEL, cache_dir=str(_home() / "cache" / "embeddings" / "models"))
            self._embed_fn = lambda ts: list(model.embed(ts))
        return self._embed_fn(texts)

    def _load(self) -> dict[str, list[float]]:
        if self._cache is None:
            try:
                self._cache = json.loads(self._cache_path.read_text())
            except (OSError, ValueError):
                self._cache = {}
        return self._cache

    def _save(self) -> None:
        if self._cache is None:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._cache))
        except OSError:
            pass
