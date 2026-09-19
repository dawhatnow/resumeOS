from pathlib import Path

from app.importing.contact_parser import ContactInfoParser
from app.importing.education import EducationParser
from app.importing.items import ExperienceItemParser, ProjectItemParser
from app.importing.sections import KNOWN_SECTIONS, SectionSplitter
from app.importing.skills import SkillsParser
from app.importing.text_extraction import LinkAnnotationExtractor, PdfTextExtractor
from app.importing.vocabulary import BulletTechTagger, VocabularyBuilder
from app.models import Profile


class ProfileImporter:
    """Facade for the whole Import stage (design spec: Resume file -> Profile).
    Orchestrates text extraction and every section-specific parser, and is
    the one class app.cli talks to."""

    def __init__(self) -> None:
        self._text_extractor = PdfTextExtractor()
        self._link_extractor = LinkAnnotationExtractor()
        self._contact_parser = ContactInfoParser()
        self._section_splitter = SectionSplitter()
        self._experience_parser = ExperienceItemParser()
        self._project_parser = ProjectItemParser()
        self._education_parser = EducationParser()
        self._skills_parser = SkillsParser()
        self._vocabulary_builder = VocabularyBuilder()
        self._bullet_tagger = BulletTechTagger()

    def import_pdf(self, path: Path) -> Profile:
        self._validate(path)

        text = self._text_extractor.extract(path)
        links = self._link_extractor.extract(path)
        return self.import_text(text, extra_links=links)

    def import_text(self, text: str, extra_links: list[str] | None = None) -> Profile:
        personal = self._contact_parser.parse(text, extra_links=extra_links)
        sections = self._section_splitter.split(text)

        experiences = self._experience_parser.parse(sections.get("experience", []), "exp")
        projects = self._project_parser.parse(sections.get("projects", []), "proj")
        education = self._education_parser.parse(sections.get("education", []))
        skills = self._skills_parser.parse(sections.get("skills", []))

        summary_lines = [l.strip() for l in sections.get("summary", []) if l.strip()]
        summary = " ".join(summary_lines) or None

        all_items = experiences + projects
        vocabulary = self._vocabulary_builder.build(skills, all_items)
        self._bullet_tagger.tag(all_items, vocabulary)

        other_sections = {
            k: v for k, v in sections.items() if k not in KNOWN_SECTIONS and any(l.strip() for l in v)
        }

        return Profile(
            personal=personal,
            summary=summary,
            experiences=experiences,
            projects=projects,
            education=education,
            skills=skills,
            vocabulary=vocabulary,
            other_sections=other_sections,
            raw_text=text,
        )

    def _validate(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"No file found at {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, got {path.suffix or 'no extension'}")
