import re
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

_CID_NOISE_RE = re.compile(r"\(cid:\d+\)")


class PdfTextExtractor:
    """Pulls plain text out of a PDF. Uses pdfplumber at a tight x_tolerance:
    pypdf (and pdfplumber's default tolerance) drop spaces around styled or
    hyperlinked text spans on many resume templates, running words together."""

    def extract(self, path: Path) -> str:
        with pdfplumber.open(str(path)) as pdf:
            pages = [page.extract_text(x_tolerance=0.5) or "" for page in pdf.pages]
        return _CID_NOISE_RE.sub("", "\n".join(pages))


class LinkAnnotationExtractor:
    """Pulls clickable-link URLs (LinkedIn, GitHub, etc.) from PDF annotations.
    These are invisible to plain text extraction when the visible label is
    just "LinkedIn" or "GitHub" rather than the URL itself."""

    def extract(self, path: Path) -> list[str]:
        reader = PdfReader(str(path))
        links = []
        for page in reader.pages:
            for annot in page.get("/Annots") or []:
                uri = annot.get_object().get("/A", {}).get("/URI")
                if uri and not uri.lower().startswith("mailto:"):
                    links.append(str(uri))  # pypdf returns a str subclass PyYAML can't serialize
        return links
