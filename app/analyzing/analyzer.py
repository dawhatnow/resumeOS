from app.analyzing.cleaner import JobDescriptionCleaner
from app.analyzing.embeddings import SemanticMatcher
from app.analyzing.keywords import KeywordMatcher
from app.models import JobAnalysis, JobPosting, Profile


class JobAnalyzer:
    """Facade for the Analyze stage (design spec: JobPosting -> JobAnalysis).
    No LLM: cleans the JD, keyword-matches it against the profile vocabulary,
    and backstops with local embeddings for near-miss phrasing."""

    def __init__(self) -> None:
        self._cleaner = JobDescriptionCleaner()
        self._keyword_matcher = KeywordMatcher()
        self._semantic_matcher = SemanticMatcher()

    def analyze(self, posting: JobPosting, profile: Profile) -> JobAnalysis:
        raise NotImplementedError("Job analysis not yet implemented")
