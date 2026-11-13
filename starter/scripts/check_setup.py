"""Check that the Docker PostgreSQL service has pgvector enabled."""
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
database_url = os.getenv(
    "DATABASE_URL", "postgresql://day6:day6_local_only@localhost:55433/day6_lab"
)

try:
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
        vector_version = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        if vector_version is None:
            raise RuntimeError("pgvector extension is missing; recreate the database or run CREATE EXTENSION vector")
        print(f"PostgreSQL: {version.split(',')[0]}")
        print(f"pgvector: {vector_version[0]}")
        print(f"Database: {database_url.rsplit('/', 1)[-1]}")
        print("Setup OK. Docker PostgreSQL is reachable and pgvector is enabled.")
except psycopg.OperationalError as exc:
    raise SystemExit(
        "Cannot connect to PostgreSQL. Start Docker Desktop, then run "
        "'docker compose up -d --wait' from the starter directory.\n"
        f"Details: {exc}"
    ) from exc
