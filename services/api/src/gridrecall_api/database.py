import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

from psycopg import Connection
from psycopg.errors import SerializationFailure
from psycopg_pool import ConnectionPool

ResultT = TypeVar("ResultT")


class CockroachDatabase:
    """Lazy CockroachDB pool with bounded transaction retries.

    The pool stays closed until application startup or the first operation. This keeps
    imports and credential-free tests from opening network connections.
    """

    def __init__(
        self,
        database_url: str,
        *,
        min_size: int = 0,
        max_size: int = 4,
        max_retries: int = 4,
        pool: Any | None = None,
    ) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self.max_retries = max_retries
        self._pool = pool or ConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"autocommit": False},
        )

    def open(self) -> None:
        self._pool.open(wait=True)

    def close(self) -> None:
        self._pool.close()

    def check(self) -> bool:
        self._ensure_open()
        with self._pool.connection() as connection:
            return connection.execute("SELECT 1").fetchone() == (1,)

    def run_transaction(self, operation: Callable[[Connection[Any]], ResultT]) -> ResultT:
        """Run a transaction and retry CockroachDB SQLSTATE 40001 conflicts."""

        self._ensure_open()
        for attempt in range(self.max_retries + 1):
            try:
                with self._pool.connection() as connection:
                    with connection.transaction():
                        return operation(connection)
            except SerializationFailure:
                if attempt >= self.max_retries:
                    raise
                delay = min(0.5, 0.025 * (2**attempt)) + random.uniform(0, 0.01)
                time.sleep(delay)
        raise RuntimeError("unreachable transaction retry state")

    def _ensure_open(self) -> None:
        if getattr(self._pool, "closed", False):
            self.open()
