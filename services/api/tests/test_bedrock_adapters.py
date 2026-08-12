import json
from io import BytesIO

import pytest

from gridrecall_api.embeddings import BedrockTitanEmbeddingProvider
from gridrecall_api.reasoning import BedrockNovaReasoner
from gridrecall_api.schemas import ActionType
from gridrecall_api.simulator import overheating_context, seed_sites


class FakeBedrockClient:
    def __init__(self, recommendation: ActionType = ActionType.INSPECT_VENTILATION) -> None:
        self.recommendation = recommendation
        self.invoke_request: dict | None = None
        self.converse_request: dict | None = None

    def invoke_model(self, **kwargs):
        self.invoke_request = kwargs
        return {
            "body": BytesIO(
                json.dumps(
                    {"embedding": [0.25] * 1024, "inputTextTokenCount": 13}
                ).encode()
            )
        }

    def converse(self, **kwargs):
        self.converse_request = kwargs
        return {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": json.dumps(
                                {
                                    "recommended_action": self.recommendation.value,
                                    "reasoning": "Outcome memory supports ventilation inspection.",
                                    "confidence": 0.91,
                                }
                            )
                        }
                    ]
                }
            }
        }


def test_titan_adapter_requests_normalized_1024_dimension_vector() -> None:
    client = FakeBedrockClient()
    provider = BedrockTitanEmbeddingProvider(region="us-east-1", client=client)

    vector = provider.embed("Inverter temperature rising")

    assert len(vector) == 1024
    assert client.invoke_request is not None
    body = json.loads(client.invoke_request["body"])
    assert body["dimensions"] == 1024
    assert body["normalize"] is True


def test_nova_adapter_parses_constrained_json_recommendation() -> None:
    client = FakeBedrockClient()
    reasoner = BedrockNovaReasoner(
        region="us-east-1",
        model_id="us.amazon.nova-lite-v1:0",
        client=client,
    )

    result = reasoner.recommend(
        context=overheating_context(seed_sites()[0]),
        evidence=[],
        candidate_action=ActionType.INSPECT_VENTILATION,
        avoided_actions=[ActionType.APPROVED_INVERTER_RESET],
    )

    assert result.action == ActionType.INSPECT_VENTILATION
    assert result.provider == "amazon-bedrock"
    assert result.model_id == "us.amazon.nova-lite-v1:0"
    assert client.converse_request is not None


def test_nova_adapter_rejects_action_outside_retrieval_candidates() -> None:
    client = FakeBedrockClient(recommendation=ActionType.INSPECT_CONNECTIONS)
    reasoner = BedrockNovaReasoner(
        region="us-east-1",
        model_id="us.amazon.nova-lite-v1:0",
        client=client,
    )

    with pytest.raises(RuntimeError, match="outside the retrieval candidates"):
        reasoner.recommend(
            context=overheating_context(seed_sites()[0]),
            evidence=[],
            candidate_action=ActionType.INSPECT_VENTILATION,
            avoided_actions=[],
        )
