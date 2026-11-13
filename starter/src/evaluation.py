"""Strict retrieval evidence checks; manual coherence/grounding stays human-rated."""
from typing import Any


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Mark a retrieval hit only when source, page, and verified quote all match."""
    sources = question.get("gold_source_ids") or [question.get("gold_source_id")]
    pages = question.get("gold_pages") or [question.get("gold_page")]
    valid_sources = {str(value) for value in sources if value is not None}
    valid_pages = {str(value) for value in pages if value is not None}
    quote = str(question.get("evidence_quote") or "").strip().casefold()

    def matches(hit: dict[str, Any]) -> bool:
        metadata = hit.get("metadata") or {}
        source_values = {str(hit.get("document_id", "")), str(hit.get("source", "")),
                         str(metadata.get("document_id", "")), str(metadata.get("source", ""))}
        page = str(hit.get("page", metadata.get("page", "")))
        text = str(hit.get("text", "")).casefold()
        return bool(valid_sources & source_values) and page in valid_pages and bool(quote and quote in text)

    flags = [matches(hit) for hit in hits[:3]]
    return {
        "id": question.get("id"),
        "split": question.get("split"),
        "question": question.get("question"),
        "hits": hits[:3],
        "hit_at_1": bool(flags and flags[0]),
        "evidence_hit_at_3": any(flags),
        "gold_match_by_rank": flags,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate retrieval hit counts by strategy and dev/test split."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trace in traces:
        groups.setdefault((str(trace.get("strategy", "unknown")),
                           str(trace.get("split", "unknown"))), []).append(trace)
    summary: dict[str, Any] = {}
    for (strategy, split), rows in sorted(groups.items()):
        total = len(rows)
        summary[f"{strategy}/{split}"] = {
            "n": total,
            "hit_at_1": {"hits": sum(bool(row.get("hit_at_1")) for row in rows), "total": total},
            "evidence_hit_at_3": {
                "hits": sum(bool(row.get("evidence_hit_at_3")) for row in rows), "total": total,
            },
        }
    return summary
