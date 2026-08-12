from contextlib import contextmanager

from gridrecall_api.database import CockroachDatabase


class FakeCursor:
    def fetchone(self) -> tuple[int]:
        return (1,)


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    @contextmanager
    def transaction(self):
        yield

    def execute(self, statement: str) -> FakeCursor:
        self.statements.append(statement)
        return FakeCursor()


class FakePool:
    def __init__(self) -> None:
        self.closed = False
        self.connection_instance = FakeConnection()

    def open(self, wait: bool = False) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_database_health_check_and_transaction() -> None:
    pool = FakePool()
    database = CockroachDatabase("postgresql://unused", pool=pool)

    assert database.check() is True
    result = database.run_transaction(lambda connection: connection.execute("SELECT 2"))

    assert isinstance(result, FakeCursor)
    assert pool.connection_instance.statements == ["SELECT 1", "SELECT 2"]
