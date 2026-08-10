from dataclasses import dataclass

from gridrecall_api.schemas import ActionType


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    status: str
    reason: str


class SafetyPolicyEngine:
    _minimum_qualification = {
        ActionType.CONTINUE_MONITORING: "observer",
        ActionType.INSPECT_VENTILATION: "field_technician",
        ActionType.APPROVED_INVERTER_RESET: "field_technician",
        ActionType.INSPECT_CONNECTIONS: "electrical_technician",
        ActionType.REDUCE_NONCRITICAL_LOAD: "field_technician",
        ActionType.ISOLATE_COMPONENT: "electrical_technician",
        ActionType.DISPATCH_TECHNICIAN: "observer",
        ActionType.ESCALATE_ENGINEER: "observer",
    }
    _qualification_rank = {
        "observer": 0,
        "field_technician": 1,
        "electrical_technician": 2,
        "certified_engineer": 3,
    }

    def validate(self, action: ActionType, qualification: str) -> PolicyDecision:
        minimum = self._minimum_qualification[action]
        actual_rank = self._qualification_rank.get(qualification, -1)
        minimum_rank = self._qualification_rank[minimum]
        if actual_rank < minimum_rank:
            return PolicyDecision(
                allowed=False,
                status="blocked",
                reason=f"Requires {minimum}; assigned user is {qualification}.",
            )
        return PolicyDecision(
            allowed=True,
            status="human approval required",
            reason=f"Approved catalogue action for a {qualification}.",
        )
