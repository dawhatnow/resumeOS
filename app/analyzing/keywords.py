class KeywordMatcher:
    """Scans a job description against a skills dictionary (profile vocabulary
    + common tech terms) with aliases (Postgres = PostgreSQL, JS = JavaScript,
    k8s = Kubernetes). Terms under "requirements" become must-have; under
    "nice to have" become bonus. Pure code, no LLM."""

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases = aliases or {}

    def match(self, clean_text: str, vocabulary: list[str]) -> list[str]:
        raise NotImplementedError("Keyword matching not yet implemented")
