import json

from gridrecall_api.config import get_settings
from gridrecall_api.embeddings import BedrockTitanEmbeddingProvider
from gridrecall_api.mcp_client import CockroachManagedMcpClient
from gridrecall_api.schemas import ActionType
from gridrecall_api.service import build_demo_service


def main() -> None:
    settings = get_settings()
    if not settings.production_ready:
        raise RuntimeError(
            "Production verification requires DATABASE_URL, BEDROCK_REASONING_MODEL_ID, "
            "COCKROACH_MCP_CLUSTER_ID, and COCKROACH_MCP_API_KEY"
        )

    embeddings = BedrockTitanEmbeddingProvider(
        region=settings.aws_region,
        model_id=settings.bedrock_embedding_model_id,
        dimensions=1024,
    )
    embedding = embeddings.embed("GridRecall production integration verification")
    mcp = CockroachManagedMcpClient(
        settings.cockroach_mcp_url,
        settings.cockroach_mcp_cluster_id or "",
        settings.cockroach_mcp_api_key or "",
    )
    mcp.get_cluster()
    mcp.list_tables("gridrecall")

    service = build_demo_service(settings)
    service.open()
    try:
        service.reset()
        service.run_first_incident()
        state = service.run_second_incident()
    finally:
        service.close()

    second = state.incidents[-1].recommendation
    passed = all(
        [
            len(embedding) == 1024,
            state.phase == "memory_proven",
            second.action == ActionType.INSPECT_VENTILATION,
            ActionType.APPROVED_INVERTER_RESET in second.avoided_actions,
            second.reasoning_provider == "amazon-bedrock",
            second.managed_context_used,
        ]
    )
    report = {
        "passed": passed,
        "titan_dimensions": len(embedding),
        "phase": state.phase,
        "second_action": second.action.value,
        "failed_reset_avoided": ActionType.APPROVED_INVERTER_RESET
        in second.avoided_actions,
        "reasoning_provider": second.reasoning_provider,
        "managed_mcp_context_used": second.managed_context_used,
        "operational_memories": state.metrics.operational_memories,
    }
    print(json.dumps(report, indent=2))
    if not passed:
        raise RuntimeError("GridRecall production integration verification failed")


if __name__ == "__main__":
    main()
