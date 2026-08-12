from gridrecall_api.repository import CockroachResolutionRepository
from gridrecall_api.schemas import IncidentMemory
from gridrecall_api.service import GridRecallDemoService


class FakeCursor:
    def __init__(self, row=None) -> None:
        self._row = row

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, memory_id) -> None:
        self.memory_id = memory_id
        self.calls: list[tuple[str, tuple | None]] = []

    def execute(self, statement: str, params: tuple | None = None) -> FakeCursor:
        normalized = " ".join(statement.split())
        self.calls.append((normalized, params))
        row = (self.memory_id,) if "RETURNING id" in normalized else None
        return FakeCursor(row)


class FakeDatabase:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.transactions = 0

    def run_transaction(self, operation):
        self.transactions += 1
        return operation(self.connection)


def test_resolution_chain_is_written_in_one_transaction() -> None:
    service = GridRecallDemoService()
    state = service.run_first_incident()
    incident = state.incidents[0]
    memory: IncidentMemory = state.memories[0]
    connection = FakeConnection(memory.id)
    database = FakeDatabase(connection)
    repository = CockroachResolutionRepository(database)  # type: ignore[arg-type]

    repository.record_resolution(state.sites[0], incident, memory)

    statements = [statement for statement, _ in connection.calls]
    assert database.transactions == 1
    assert any("INSERT INTO sites" in statement for statement in statements)
    assert any("INSERT INTO incidents" in statement for statement in statements)
    assert any("INSERT INTO recommendations" in statement for statement in statements)
    assert sum("INSERT INTO repair_attempts" in statement for statement in statements) == 2
    assert any("INSERT INTO outcomes" in statement for statement in statements)
    assert any("INSERT INTO incident_memories" in statement for statement in statements)
