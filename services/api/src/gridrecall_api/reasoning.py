import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from gridrecall_api.memory import RankedMemory
from gridrecall_api.schemas import ActionType, IncidentContext


@dataclass(frozen=True)
class ReasoningResult:
    action: ActionType
    explanation: str
    confidence: float
    provider: str
    model_id: str | None = None


class RecommendationReasoner(Protocol):
    def recommend(
        self,
        context: IncidentContext,
        evidence: list[RankedMemory],
        candidate_action: ActionType,
        avoided_actions: list[ActionType],
    ) -> ReasoningResult: ...


class CaseBasedReasoner:
    """Credential-free reasoner used by tests and the local replayable demo."""

    def recommend(
        self,
        context: IncidentContext,
        evidence: list[RankedMemory],
        candidate_action: ActionType,
        avoided_actions: list[ActionType],
    ) -> ReasoningResult:
        if evidence:
            explanation = (
                f"A similar {context.inverter_model} incident at "
                f"{evidence[0].memory.site_name} was resolved with this action. "
                "Its failed attempts were demoted using the recorded outcome."
            )
            confidence = min(0.96, 0.55 + evidence[0].influence_score * 0.4)
        else:
            explanation = (
                "No sufficiently relevant successful incident memory exists, so GridRecall "
                "starts with the conservative approved playbook."
            )
            confidence = 0.61
        return ReasoningResult(
            action=candidate_action,
            explanation=explanation,
            confidence=confidence,
            provider="case-based-local",
        )


class _BedrockOutput(BaseModel):
    recommended_action: ActionType
    reasoning: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class BedrockNovaReasoner:
    """Constrained Amazon Nova recommendation adapter using Bedrock Converse."""

    _system_prompt = """You are GridRecall, an evidence-grounded solar mini-grid maintenance
assistant. Select exactly one action from the supplied approved action catalogue. Never invent
repair steps, never claim to control equipment, and do not override safety or technician approval.
Prefer successful outcomes from similar incidents and avoid previously failed actions. Return only
valid JSON with recommended_action, reasoning, and confidence (a number from 0 to 1)."""

    def __init__(self, region: str, model_id: str, client: Any | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region)
        self._client = client
        self.model_id = model_id

    def recommend(
        self,
        context: IncidentContext,
        evidence: list[RankedMemory],
        candidate_action: ActionType,
        avoided_actions: list[ActionType],
    ) -> ReasoningResult:
        candidate_actions = [candidate_action.value, ActionType.ESCALATE_ENGINEER.value]
        evidence_payload = [
            {
                "site": item.memory.site_name,
                "asset_model": item.memory.inverter_model,
                "fault_type": item.memory.fault_type,
                "successful_action": item.memory.successful_action.value,
                "failed_actions": [action.value for action in item.memory.failed_actions],
                "outcome_score": item.memory.outcome_score,
                "influence_score": round(item.influence_score, 4),
                "resolution": item.memory.resolution_summary,
            }
            for item in evidence
        ]
        prompt = {
            "current_incident": {
                "site": context.site_name,
                "asset_model": context.inverter_model,
                "fault_type": context.fault_type,
                "symptoms": context.symptoms,
                "telemetry": context.telemetry.model_dump(mode="json"),
            },
            "retrieved_outcome_memories": evidence_payload,
            "candidate_actions": list(dict.fromkeys(candidate_actions)),
            "retrieval_candidate": candidate_action.value,
            "actions_to_avoid": [action.value for action in avoided_actions],
        }
        response = self._client.converse(
            modelId=self.model_id,
            system=[{"text": self._system_prompt}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": json.dumps(prompt, separators=(",", ":"))}],
                }
            ],
            inferenceConfig={"maxTokens": 500, "temperature": 0, "topP": 0.9},
        )
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        text = next((block["text"] for block in blocks if "text" in block), "")
        try:
            parsed = _BedrockOutput.model_validate_json(self._extract_json(text))
        except (ValidationError, ValueError) as exc:
            raise RuntimeError("Bedrock returned an invalid structured recommendation") from exc
        if parsed.recommended_action not in {candidate_action, ActionType.ESCALATE_ENGINEER}:
            raise RuntimeError("Bedrock selected an action outside the retrieval candidates")
        if parsed.recommended_action in avoided_actions:
            raise RuntimeError("Bedrock selected an action that outcome memory marked as failed")
        return ReasoningResult(
            action=parsed.recommended_action,
            explanation=parsed.reasoning,
            confidence=parsed.confidence,
            provider="amazon-bedrock",
            model_id=self.model_id,
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        stripped = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
        return fenced.group(1) if fenced else stripped
