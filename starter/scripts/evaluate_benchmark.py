"""Retrieve benchmark questions and save auditable top-3 traces."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from src.embeddings import SentenceTransformerEmbedder  # noqa: E402
from src.evaluation import evaluate_query, summarize  # noqa: E402
from src.store import PgVectorStore  # noqa: E402

STRATEGIES = ("A_fixed", "B_paragraph", "C_paragraph_metadata")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=PROJECT / "benchmark" / "questions.jsonl")
    parser.add_argument("--split", choices=("dev", "test"), default="dev",
                        help="Run dev while choosing a strategy; run test only after fixing the choice.")
    parser.add_argument("--strategy", choices=STRATEGIES,
                        help="Required for --split test; evaluates only the already selected strategy.")
    parser.add_argument("--model", default=None, help="defaults to EMBEDDING_MODEL in .env")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    if args.split == "test" and not args.strategy:
        parser.error("Choose and freeze a strategy from dev results, then pass --strategy for test")
    if not args.questions.is_file():
        parser.error(f"Benchmark file not found: {args.questions}")

    load_dotenv(ROOT / ".env")
    model_name = args.model or os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    questions = [q for q in read_jsonl(args.questions) if q.get("split") == args.split]
    if not questions:
        parser.error(f"No {args.split} questions found in {args.questions}")

    print(f"Loading embedding model: {model_name}", flush=True)
    embedder = SentenceTransformerEmbedder(model_name)
    print(f"Connecting to PostgreSQL and preparing {len(questions)} {args.split} questions...", flush=True)
    store = PgVectorStore(embedder.dimensions)
    traces: list[dict] = []
    strategies = (args.strategy,) if args.split == "test" else STRATEGIES
    for index, question in enumerate(questions, start=1):
        print(f"Question {index}/{len(questions)}: {question.get('id', '?')}", flush=True)
        query_vector = embedder.embed_query(question["question"])
        for strategy in strategies:
            # Metadata filters are the treatment for strategy C only. For an
            # unfiltered question, C runs without a filter as required.
            filters = question.get("filter") if strategy == "C_paragraph_metadata" else None
            hits = store.search(strategy, query_vector, top_k=args.top_k, filters=filters)
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            trace["filter_applied"] = filters
            trace["expected_answer"] = question.get("expected_answer")
            trace["evidence_quote"] = question.get("evidence_quote")
            traces.append(trace)

    output_dir = ROOT / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / f"benchmark_{args.split}_traces.jsonl"
    with trace_path.open("w", encoding="utf-8", newline="\n") as stream:
        for trace in traces:
            stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
    summary = summarize(traces)
    summary_path = output_dir / f"benchmark_{args.split}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Split: {args.split}; questions: {len(questions)}; strategies: {len(strategies)}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Top-{args.top_k} traces: {trace_path}")
    print(f"Summary: {summary_path}")
    if args.split == "dev":
        print("Choose a strategy from dev results, then freeze it before running --split test --strategy NAME.")


if __name__ == "__main__":
    main()
