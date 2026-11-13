"""Read and normalize source data while preserving physical page numbers."""
import unicodedata
from pathlib import Path
from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract every physical PDF page. Empty pages remain in output for audit."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF ingestion requires pypdf; install requirements.txt") from exc
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for index, pdf_page in enumerate(reader.pages, start=1):
        text = normalize_text(pdf_page.extract_text() or "")
        pages.append(DocumentPage(document_id, source, index, text, {"empty": not bool(text)}))
    return pages


def normalize_text(text: str) -> str:
    """Clean PDF layout noise while preserving paragraph boundaries and wording."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    # PDF extractors often emit one line per visual row. Join these rows within
    # a paragraph; blank lines remain paragraph boundaries. Keep hyphens intact
    # because they may be meaningful in names, dates, or compound words.
    paragraphs: list[str] = []
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = " ".join(raw_line.split())
        if line:
            lines.append(line)
        elif lines:
            paragraphs.append(" ".join(lines))
            lines = []
    if lines:
        paragraphs.append(" ".join(lines))
    return "\n\n".join(paragraphs).strip()
