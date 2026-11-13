"""Embed prepared chunk sets and upsert them into Docker PostgreSQL/pgvector."""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .embeddings import SentenceTransformerEmbedder
from .models import Chunk
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
STRATEGIES = {
    "A_fixed": "chunks_A_fixed.jsonl",
    "B_paragraph": "chunks_B_paragraph.jsonl",
    "C_paragraph_metadata": "chunks_C_paragraph_metadata.jsonl",
}


def load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            chunks.append(Chunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                source=row["source"],
                page=int(row["page"]),
                text=row["text"],
                metadata=row.get("metadata") or {},
            ))
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "results" / "prepared")
    parser.add_argument("--model", default=None, help="embedding model; defaults to EMBEDDING_MODEL in .env")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    model_name = args.model or os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    for filename in STRATEGIES.values():
        if not (args.input_dir / filename).is_file():
            parser.error(f"Prepared chunk file missing: {args.input_dir / filename}. Run scripts/prepare_corpus.py first.")

    embedder = SentenceTransformerEmbedder(model_name)
    store = PgVectorStore(embedder.dimensions)
    summary: dict[str, object] = {
        "model": embedder.model_name,
        "dimensions": embedder.dimensions,
        "database": "PostgreSQL + pgvector",
        "strategies": {},
    }
    for strategy, filename in STRATEGIES.items():
        chunks = load_chunks(args.input_dir / filename)
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        store.upsert(strategy, chunks, vectors)
        summary["strategies"][strategy] = {"chunks": len(chunks), "pages": len({c.page for c in chunks})}
        print(f"{strategy}: stored {len(chunks)} chunks ({len({c.page for c in chunks})} pages)")

    output = ROOT / "results" / "ingestion_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Embedding model: {embedder.model_name} ({embedder.dimensions} dimensions)")
    print(f"Summary: {output}")
    print("Note: this step stores vectors; filtered retrieval and benchmark scoring are separate steps.")


if __name__ == "__main__":
    main()
