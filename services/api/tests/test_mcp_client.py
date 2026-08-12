import pytest

from gridrecall_api.mcp_client import CockroachManagedMcpClient
from gridrecall_api.simulator import overheating_context, seed_sites


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return {"rows": []}


def test_managed_mcp_is_cluster_scoped_and_read_only() -> None:
    runner = RecordingRunner()
    cluster_id = "00000000-0000-4000-8000-000000000000"
    client = CockroachManagedMcpClient(
        "https://cockroachlabs.cloud/mcp",
        cluster_id,
        "test-key-not-a-real-secret",
        runner=runner,
    )

    result = client.investigation_context(overheating_context(seed_sites()[0]))

    assert result == {"rows": []}
    assert client.headers["mcp-cluster-id"] == cluster_id
    assert client.headers["Authorization"].startswith("Bearer ")
    tool, arguments = runner.calls[0]
    assert tool == "select_query"
    assert arguments["query"].startswith("SELECT")
    assert "LIMIT 10" in arguments["query"]


def test_managed_mcp_rejects_non_select_statements() -> None:
    client = CockroachManagedMcpClient(
        "https://cockroachlabs.cloud/mcp",
        "cluster-id",
        "test-key-not-a-real-secret",
        runner=RecordingRunner(),
    )

    with pytest.raises(ValueError, match="restricted to SELECT"):
        client.select("DELETE FROM incidents")
