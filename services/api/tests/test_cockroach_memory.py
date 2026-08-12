from datetime import UTC, datetime
from uuid import uuid4

from gridrecall_api.cockroach_memory import CockroachVectorMemory
from gridrecall_api.schemas import ActionType
from gridrecall_api.simulator import overheating_context, seed_sites


class FakeCursor:
    def __init__(self, rows) -> None:
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, memory_row, attempt_rows) -> None:
        self.memory_row = memory_row
        self.attempt_rows = attempt_rows
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, statement: str, params: tuple):
        normalized = " ".join(statement.split())
        self.calls.append((normalized, params))
        if "FROM repair_attempts" in normalized:
            return FakeCursor(self.attempt_rows)
        return FakeCursor([self.memory_row])


class FakeDatabase:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def run_transaction(self, operation):
        return operation(self.connection)


class FakeEmbeddings:
    def embed(self, text: str) -> list[float]:
        return [0.5] * 1024


def test_vector_memory_uses_cosine_search_and_outcomes() -> None:
    context = overheating_context(seed_sites()[1])
    memory_id = uuid4()
    incident_id = uuid4()
    memory_row = (
        memory_id,
        incident_id,
        "Ajegunle Mini-Grid",
        context.inverter_model,
        context.fault_type,
        context.symptoms,
        context.search_text,
        0.93,
        "Clearing blocked ventilation restored output.",
        True,
        datetime.now(UTC),
        0.96,
    )
    attempts = [
        (
            ActionType.APPROVED_INVERTER_RESET.value,
            False,
            "Reset did not restore output.",
            9,
        ),
        (
            ActionType.INSPECT_VENTILATION.value,
            True,
            "Ventilation cleared.",
            11,
        ),
    ]
    connection = FakeConnection(memory_row, attempts)
    database = FakeDatabase(connection)
    memory = CockroachVectorMemory(database, FakeEmbeddings())  # type: ignore[arg-type]

    result = memory.retrieve(context)

    assert result[0].memory.id == memory_id
    assert result[0].memory.successful_action == ActionType.INSPECT_VENTILATION
    assert result[0].memory.failed_actions == [ActionType.APPROVED_INVERTER_RESET]
    assert result[0].influence_score > 0.9
    query, params = connection.calls[0]
    assert "embedding <=> %s::VECTOR" in query
    assert params[1:3] == (context.inverter_model, context.fault_type)
