"""LLM providers for bullet rewriting. Swappable; the default makes zero calls.

Ollama, Groq, Gemini, OpenRouter (and most others) all accept the OpenAI
chat-completions format, so one class talks to any of them. Pick one in
~/.resume/config.toml:

    [llm]
    provider = "ollama"      # ollama | groq | gemini | openrouter | none
    model = "phi3.5"         # optional; each provider has a default
    # base_url = "..."       # optional, for any other OpenAI-compatible server
    # api_key_env = "..."    # optional, env var holding the key

Env overrides: RESUME_LLM_PROVIDER, RESUME_LLM_MODEL. API keys are read
from environment variables only, never from the config file.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ProviderError(Exception):
    """Unreachable server, missing key, bad response — message is user-facing."""


@dataclass(frozen=True)
class Preset:
    base_url: str
    model: str
    key_env: str | None
    local: bool
    timeout: float


# Default models are examples that worked when written; providers rename
# models often, so set `model` in config.toml if one stops working.
PRESETS: dict[str, Preset] = {
    "ollama": Preset("http://127.0.0.1:11434/v1", "phi3.5", None, True, 900.0),
    "groq": Preset("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY", False, 120.0),
    "gemini": Preset(
        "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "GEMINI_API_KEY", False, 120.0
    ),
    "openrouter": Preset("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY", False, 120.0),
}


class LLMProvider:
    name = "none"
    model = ""
    local = True

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError

    @property
    def label(self) -> str:
        return f"{self.name}/{self.model}" if self.model else self.name


class NullProvider(LLMProvider):
    """No LLM configured: rewriting is off, bullets stay as written."""

    def complete(self, system: str, user: str) -> str:
        raise ProviderError("No LLM configured. Set [llm] provider in ~/.resume/config.toml (e.g. \"ollama\").")


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, name: str, base_url: str, model: str, api_key: str | None, *, local: bool, timeout: float):
        self.name, self.model, self.local = name, model, local
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def complete(self, system: str, user: str) -> str:
        import httpx

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            r = httpx.post(f"{self._base_url}/chat/completions", json=body, headers=headers, timeout=self._timeout)
        except httpx.ConnectError:
            hint = " Start it with `ollama serve`." if self.name == "ollama" else ""
            raise ProviderError(f"Can't reach {self.name} at {self._base_url}.{hint}") from None
        except httpx.TimeoutException:
            raise ProviderError(f"{self.label} took longer than {self._timeout:.0f}s. Try fewer bullets (rewrite exp.2).") from None
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} request failed: {e}") from None
        if r.status_code in (401, 403):
            raise ProviderError(f"{self.name} rejected the API key (HTTP {r.status_code}).")
        if r.status_code == 404:
            raise ProviderError(f"{self.name} doesn't know model '{self.model}'. Set `model` in ~/.resume/config.toml.")
        if r.status_code == 429:
            raise ProviderError(f"{self.name} rate limit hit (free tier). Wait a minute and retry.")
        if r.status_code >= 400:
            raise ProviderError(f"{self.name} returned HTTP {r.status_code}: {r.text[:200]}")
        try:
            return r.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError):
            raise ProviderError(f"{self.name} sent a response I couldn't read.") from None


def config_path() -> Path:
    root = os.environ.get("RESUME_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".resume") / "config.toml"


def load_provider(path: Path | None = None) -> LLMProvider:
    """Provider from config.toml + env. No config at all → Ollama defaults."""
    cfg: dict = {}
    path = path or config_path()
    if path.exists():
        try:
            cfg = tomllib.loads(path.read_text()).get("llm", {})
        except tomllib.TOMLDecodeError as e:
            raise ProviderError(f"Can't read {path}: {e}") from None
    name = os.environ.get("RESUME_LLM_PROVIDER") or cfg.get("provider", "ollama")
    name = str(name).lower()
    if name in {"none", "off", ""}:
        return NullProvider()
    preset = PRESETS.get(name)
    base_url = cfg.get("base_url") or (preset.base_url if preset else None)
    if not base_url:
        raise ProviderError(f"Unknown provider '{name}'. Use one of {', '.join(PRESETS)}, or set base_url.")
    model = os.environ.get("RESUME_LLM_MODEL") or cfg.get("model") or (preset.model if preset else "")
    if not model:
        raise ProviderError(f"Set `model` for provider '{name}' in {path}.")
    key_env = cfg.get("api_key_env") or (preset.key_env if preset else None)
    api_key = os.environ.get(key_env) if key_env else None
    if key_env and not api_key:
        raise ProviderError(f"{name} needs an API key: export {key_env}=... (get one free on their site).")
    return OpenAICompatibleProvider(
        name, base_url, model, api_key,
        local=preset.local if preset else False,
        timeout=float(cfg.get("timeout", preset.timeout if preset else 120.0)),
    )
