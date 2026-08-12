from contextlib import AbstractContextManager
from pathlib import Path

from gridrecall_api.migrations import apply_migrations


class FakeCursor:
    def __init__(self, row=None) -> None:
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection(AbstractContextManager):
    def __init__(self) -> None:
        self.calls = []

    def __exit__(self, *args) -> None:
        return None

    def execute(self, statement, params=None, **kwargs):
        self.calls.append((statement, params, kwargs))
        return FakeCursor()


def test_migration_runner_records_checksum(tmp_path: Path) -> None:
    migration = tmp_path / "001_test.sql"
    migration.write_text("CREATE TABLE example (id UUID PRIMARY KEY);", encoding="utf-8")
    connection = FakeConnection()

    applied = apply_migrations(
        "postgresql://unused",
        tmp_path,
        connect=lambda *args, **kwargs: connection,
    )

    assert applied == ["001_test.sql"]
    assert any("CREATE TABLE example" in call[0] for call in connection.calls)
    insert = next(call for call in connection.calls if "INSERT INTO schema_migrations" in call[0])
    assert insert[1][0] == "001_test.sql"
    assert len(insert[1][1]) == 64
