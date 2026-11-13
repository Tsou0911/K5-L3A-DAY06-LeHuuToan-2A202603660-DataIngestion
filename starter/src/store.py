"""PostgreSQL/pgvector store; each ingestion strategy has its own table."""
import json
import math
import os
import re
from typing import Any

from .models import Chunk


class PgVectorStore:
    def __init__(self, dimensions: int, database_url: str | None = None) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install requirements.txt to use PostgreSQL/pgvector") from exc
        self._psycopg = psycopg
        self._database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://day6:day6_local_only@localhost:55433/day6_lab"
        )
        self.dimensions = dimensions
        self._ensure_schema()

    @staticmethod
    def _table(strategy: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", strategy):
            raise ValueError("strategy must contain only letters, digits, and underscores")
        return "day06_" + strategy.lower()

    @staticmethod
    def _vector_literal(vector: list[float], dimensions: int) -> str:
        if len(vector) != dimensions:
            raise ValueError(f"Expected vector dimension {dimensions}, got {len(vector)}")
        if not all(math.isfinite(float(value)) for value in vector):
            raise ValueError("vector values must be finite")
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def _ensure_schema(self) -> None:
        with self._psycopg.connect(self._database_url, connect_timeout=5) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            # pgvector's HNSW opclass requires a fixed-dimensional vector
            # typmod. `dimensions` is an int validated in __init__, so safe in DDL.
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS day06_chunks (
                    strategy TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )
            """)
            # Migrate only the initial unbounded-vector table. Avoid issuing
            # ALTER TYPE on every run, which could rebuild or conflict with HNSW.
            typmod = conn.execute("""
                SELECT atttypmod FROM pg_attribute
                WHERE attrelid = 'day06_chunks'::regclass AND attname = 'embedding'
                  AND NOT attisdropped
            """).fetchone()[0]
            if typmod == -1:
                conn.execute(f"""
                    ALTER TABLE day06_chunks
                    ALTER COLUMN embedding TYPE vector({self.dimensions})
                    USING embedding::vector({self.dimensions})
                """)
            elif typmod != self.dimensions:
                raise ValueError(
                    f"Database vector dimension is {typmod}, model dimension is {self.dimensions}; "
                    "use a separate database/table when changing embedding models"
                )
            conn.execute("CREATE INDEX IF NOT EXISTS day06_chunks_document_idx ON day06_chunks (strategy, document_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS day06_chunks_metadata_idx ON day06_chunks USING gin (metadata)")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS day06_chunks_embedding_idx
                ON day06_chunks USING hnsw (embedding vector_cosine_ops)
            """)

    @staticmethod
    def _metadata(chunk: Chunk) -> dict[str, Any]:
        metadata = dict(chunk.metadata)
        metadata.update({"document_id": chunk.document_id, "source": chunk.source, "page": int(chunk.page)})
        return metadata

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        table = self._table(strategy)
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return
        rows = []
        for chunk, vector in zip(chunks, vectors):
            rows.append((strategy.lower(), chunk.chunk_id, chunk.document_id, chunk.source,
                         int(chunk.page), chunk.text, json.dumps(self._metadata(chunk), ensure_ascii=False),
                         self._vector_literal(vector, self.dimensions)))
        # `table` is validated above; use a strategy-scoped primary key while
        # keeping all strategy rows together for a single metadata index.
        with self._psycopg.connect(self._database_url, connect_timeout=5) as conn:
            ids = [chunk.chunk_id for chunk in chunks]
            conn.execute("DELETE FROM day06_chunks WHERE strategy = %s AND document_id = ANY(%s)",
                         (strategy.lower(), sorted({chunk.document_id for chunk in chunks})))
            with conn.cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO day06_chunks
                        (strategy, chunk_id, document_id, source, page, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id, source = EXCLUDED.source,
                        page = EXCLUDED.page, content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding
                """, rows)

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._table(strategy)  # validate strategy consistently with upsert
        if top_k < 1:
            raise ValueError("top_k must be positive")
        vector = self._vector_literal(query_vector, self.dimensions)
        filter_sql = " AND metadata @> %s::jsonb" if filters else ""
        params: list[Any] = [strategy.lower()]
        if filters:
            params.append(json.dumps(filters, ensure_ascii=False))
        params.extend([vector, top_k])
        with self._psycopg.connect(self._database_url, connect_timeout=5) as conn:
            rows = conn.execute(f"""
                SELECT chunk_id, document_id, source, page, content, metadata,
                       embedding <=> %s::vector AS distance
                FROM day06_chunks
                WHERE strategy = %s{filter_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (vector, strategy.lower(), *([json.dumps(filters, ensure_ascii=False)] if filters else []), vector, top_k)).fetchall()
        results = []
        for chunk_id, document_id, source, page, content, metadata, distance in rows:
            metadata = dict(metadata or {})
            results.append({"chunk_id": chunk_id, "text": content, "metadata": metadata,
                            "document_id": document_id, "source": source, "page": page,
                            "distance": float(distance), "score": 1.0 - float(distance)})
        return results
