class JobDescriptionCleaner:
    """Drops boilerplate sections (benefits, EEO statements, "about us", perks,
    how to apply) and splits what's left into requirements / nice-to-have /
    responsibilities by heading pattern. Pure code, no LLM."""

    def clean(self, raw_text: str) -> str:
        raise NotImplementedError("JD cleaning not yet implemented")
