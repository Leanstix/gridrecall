from gridrecall_api.config import Settings
from gridrecall_api.reasoning import ReasoningResult
from gridrecall_api.service import GridRecallDemoService


class RecordingRepository:
    def __init__(self) -> None:
        self.resolutions = []

    def record_resolution(self, site, incident, memory) -> None:
        self.resolutions.append((site, incident, memory))


class RecordingContextProvider:
    def investigation_context(self, context, limit: int = 10):
        return {"source": "cockroachdb-managed-mcp", "site": context.site_name}


class RecordingReasoner:
    def __init__(self) -> None:
        self.contexts = []

    def recommend(
        self,
        context,
        evidence,
        candidate_action,
        avoided_actions,
        structured_context=None,
    ) -> ReasoningResult:
        self.contexts.append(structured_context)
        return ReasoningResult(
            action=candidate_action,
            explanation="Structured operational context evaluated.",
            confidence=0.88,
            provider="test-reasoner",
            managed_context_used=structured_context is not None,
        )


def test_resolution_persists_and_mcp_context_reaches_reasoner() -> None:
    repository = RecordingRepository()
    reasoner = RecordingReasoner()
    service = GridRecallDemoService(
        reasoner=reasoner,
        resolution_repository=repository,
        context_provider=RecordingContextProvider(),
    )

    state = service.run_first_incident()

    assert len(repository.resolutions) == 1
    assert reasoner.contexts[0]["source"] == "cockroachdb-managed-mcp"
    assert state.incidents[0].recommendation.managed_context_used is True


def test_settings_require_all_production_integrations() -> None:
    partial = Settings(
        database_url="postgresql://example",
        bedrock_reasoning_model_id="us.amazon.nova-lite-v1:0",
        _env_file=None,
    )
    complete = Settings(
        database_url="postgresql://example",
        bedrock_reasoning_model_id="us.amazon.nova-lite-v1:0",
        cockroach_mcp_cluster_id="cluster-id",
        cockroach_mcp_api_key="secret",
        _env_file=None,
    )

    assert partial.production_ready is False
    assert partial.demo_mode is True
    assert complete.production_ready is True
    assert complete.demo_mode is False
