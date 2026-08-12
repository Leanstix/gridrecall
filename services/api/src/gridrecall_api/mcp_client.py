import asyncio
import json
from collections.abc import Callable
from typing import Any

from gridrecall_api.schemas import IncidentContext

ToolRunner = Callable[[str, dict[str, Any]], Any]


class CockroachManagedMcpClient:
    """Read-only client for CockroachDB Cloud's managed MCP endpoint."""

    def __init__(
        self,
        url: str,
        cluster_id: str,
        api_key: str,
        *,
        runner: ToolRunner | None = None,
    ) -> None:
        if not all((url, cluster_id, api_key)):
            raise ValueError("MCP URL, cluster ID, and API key are required")
        self.url = url
        self.cluster_id = cluster_id
        self._api_key = api_key
        self._runner = runner

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "mcp-cluster-id": self.cluster_id,
        }

    def get_cluster(self) -> Any:
        return self.call_tool("get_cluster", {})

    def list_tables(self, database: str = "gridrecall") -> Any:
        return self.call_tool("list_tables", {"database": database, "limit": 100})

    def select(self, query: str) -> Any:
        normalized = query.lstrip().upper()
        if not normalized.startswith("SELECT"):
            raise ValueError("Managed MCP application access is restricted to SELECT")
        if ";" in query.rstrip().rstrip(";"):
            raise ValueError("Managed MCP accepts exactly one statement")
        return self.call_tool("select_query", {"query": query})

    def investigation_context(self, context: IncidentContext, limit: int = 10) -> Any:
        safe_limit = max(1, min(limit, 20))
        model = self._sql_literal(context.inverter_model)
        query = f"""
            SELECT
                incident.id,
                site.name AS site_name,
                asset.model AS asset_model,
                incident.fault_type,
                incident.symptoms,
                incident.status,
                outcome.outcome_score,
                outcome.time_to_restore_minutes
            FROM gridrecall.public.incidents AS incident
            JOIN gridrecall.public.sites AS site ON site.id = incident.site_id
            JOIN gridrecall.public.grid_assets AS asset ON asset.id = incident.asset_id
            LEFT JOIN gridrecall.public.outcomes AS outcome ON outcome.incident_id = incident.id
            WHERE incident.site_id = '{context.site_id}' OR asset.model = '{model}'
            ORDER BY incident.opened_at DESC
            LIMIT {safe_limit}
        """.strip()
        return self.select(query)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._runner is not None:
            return self._runner(name, arguments)
        return asyncio.run(self._call_remote(name, arguments))

    async def _call_remote(self, name: str, arguments: dict[str, Any]) -> Any:
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        async with httpx2.AsyncClient(
            headers=self.headers,
            timeout=httpx2.Timeout(20.0, read=30.0),
            follow_redirects=True,
        ) as http_client:
            transport = streamable_http_client(self.url, http_client=http_client)
            async with Client(transport) as client:
                result = await client.call_tool(name, arguments)
        if result.is_error:
            raise RuntimeError(f"CockroachDB MCP tool {name} returned an error")
        if result.structured_content is not None:
            return result.structured_content
        content: list[Any] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is None:
                continue
            try:
                content.append(json.loads(text))
            except json.JSONDecodeError:
                content.append(text)
        return content

    @staticmethod
    def _sql_literal(value: str) -> str:
        return value.replace("'", "''")
