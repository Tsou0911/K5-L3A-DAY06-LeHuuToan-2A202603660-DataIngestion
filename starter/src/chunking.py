"""Fixed-size and paragraph-aware chunking with page-level provenance."""
from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, text: str, number: int) -> Chunk:
    return Chunk(
        chunk_id=f"{page.document_id}:p{page.page}:c{number}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=dict(page.metadata),
    )


def _split_at_words(text: str, size: int, overlap: int = 0) -> list[str]:
    """Split long text near word boundaries, with character overlap if requested."""
    text = text.strip()
    if not text:
        return []
    result: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + max(1, size // 2), end)
            if boundary > start:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            result.append(piece)
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap)
        # Move overlap start to the beginning of a word when possible.
        if next_start > start:
            space = text.find(" ", next_start, min(next_start + 80, end))
            if space != -1:
                next_start = space + 1
        start = next_start
    return result


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split text into overlapping character windows near word boundaries."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    return [_chunk(page, text, i) for i, text in
            enumerate(_split_at_words(page.text, size, overlap), start=1)]


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Pack paragraphs up to max_size; split only oversized paragraphs."""
    if max_size < 1:
        raise ValueError("max_size must be positive")
    paragraphs = [part.strip() for part in page.text.split("\n") if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_size:
            pieces.append(paragraph)
        else:
            pieces.extend(_split_at_words(paragraph, max_size))
    packed: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}" if current else piece
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                packed.append(current)
            current = piece
    if current:
        packed.append(current)
    return [_chunk(page, text, i) for i, text in enumerate(packed, start=1)]
