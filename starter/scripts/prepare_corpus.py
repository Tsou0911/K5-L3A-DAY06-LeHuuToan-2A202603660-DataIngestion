"""Extract, normalize, and chunk the lab PDF into auditable JSONL files."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))

from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.ingestion import load_pdf  # noqa: E402


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "data" / "Lịch_sử_Việt_Nam.pdf")
    parser.add_argument("--document-id", default="viwiki-lich-su-viet-nam")
    parser.add_argument("--source", default="Lịch sử Việt Nam (PDF)")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "prepared")
    parser.add_argument("--size", type=int, default=1200, help="chunk size in characters")
    parser.add_argument("--overlap", type=int, default=150, help="overlap in characters")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        parser.error(f"PDF not found: {pdf}")
    if args.size < 1 or not 0 <= args.overlap < args.size:
        parser.error("Require size > 0 and 0 <= overlap < size")

    pages = load_pdf(pdf, args.document_id, args.source)
    section_ranges = [
    (2, 4, "Thời tiền sử"),
    (5, 6, "Thời kỳ nguyên sử"),
    (7, 13, "Thời kỳ Bắc thuộc"),
    (14, 25, "Thời kỳ phong kiến"),
    (27, 29, "Thời kỳ Pháp thuộc"),
    (31, 38, "Thời kỳ hiện đại"),
    ]

    content_pages = []
    for page in pages:
        include = page.page <= 38 and len(page.text.strip()) >= 1500
        page.metadata["include_in_corpus"] = include

        if include:
            for first_page, last_page, section in section_ranges:
                if first_page <= page.page <= last_page:
                    page.metadata["section"] = section
                    break
            content_pages.append(page)
    page_rows = [{
        "document_id": page.document_id,
        "source": page.source,
        "page": page.page,
        "text": page.text,
        "metadata": page.metadata,
    } for page in pages]
    write_jsonl(args.output / "pages.jsonl", page_rows)

    configs = {
        "A_fixed": [chunk for page in content_pages
                    for chunk in fixed_size(page, args.size, args.overlap)],
        "B_paragraph": [chunk for page in content_pages
                        for chunk in by_paragraph(page, args.size)],
        "C_paragraph_metadata": [chunk for page in content_pages
                                 for chunk in by_paragraph(page, args.size)],
    }
    for name, chunks in configs.items():
        rows = [{
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source": chunk.source,
            "page": chunk.page,
            "text": chunk.text,
            "metadata": chunk.metadata,
        } for chunk in chunks]
        write_jsonl(args.output / f"chunks_{name}.jsonl", rows)
        print(f"{name}: {len(chunks)} chunks -> {args.output / f'chunks_{name}.jsonl'}")

    print(f"PDF pages: {len(pages)}; qualified content pages: {len(content_pages)}")
    print(f"Normalized pages -> {args.output / 'pages.jsonl'}")
    if len(content_pages) < 30:
        print("WARNING: fewer than 30 pages contain extractable text; check the corpus requirement.")
    print("Section labels assigned to mapped pages; boundary pages are left unlabeled.")

if __name__ == "__main__":
    main()
