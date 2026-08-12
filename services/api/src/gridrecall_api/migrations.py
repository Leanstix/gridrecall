import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psycopg


def apply_migrations(
    database_url: str,
    migrations_dir: Path,
    *,
    connect: Callable[..., Any] = psycopg.connect,
) -> list[str]:
    if not database_url:
        raise ValueError("DATABASE_URL is required")
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No migrations found in {migrations_dir}")

    applied: list[str] = []
    with connect(database_url, autocommit=True) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version STRING PRIMARY KEY,
                checksum STRING NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        for migration in files:
            content = migration.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            existing = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version = %s",
                (migration.name,),
            ).fetchone()
            if existing:
                if existing[0] != checksum:
                    raise RuntimeError(f"Applied migration changed: {migration.name}")
                continue
            connection.execute(content, prepare=False)
            connection.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                (migration.name, checksum),
            )
            applied.append(migration.name)
    return applied


def main() -> None:
    project_root = Path(__file__).resolve().parents[4]
    applied = apply_migrations(
        os.environ.get("DATABASE_URL", ""),
        project_root / "migrations",
    )
    print("Applied migrations:", ", ".join(applied) if applied else "none")


if __name__ == "__main__":
    main()
