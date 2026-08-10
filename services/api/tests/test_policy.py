from gridrecall_api.policy import SafetyPolicyEngine
from gridrecall_api.schemas import ActionType


def test_policy_blocks_underqualified_electrical_action() -> None:
    result = SafetyPolicyEngine().validate(
        ActionType.ISOLATE_COMPONENT,
        qualification="field_technician",
    )

    assert result.allowed is False
    assert result.status == "blocked"


def test_policy_allows_catalogue_action_with_human_approval() -> None:
    result = SafetyPolicyEngine().validate(
        ActionType.INSPECT_VENTILATION,
        qualification="field_technician",
    )

    assert result.allowed is True
    assert result.status == "human approval required"
