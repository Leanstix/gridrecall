from threading import RLock
from uuid import uuid4

from gridrecall_api.embeddings import LocalHashEmbeddingProvider
from gridrecall_api.memory import InMemoryOperationalMemory
from gridrecall_api.policy import SafetyPolicyEngine
from gridrecall_api.schemas import (
    ActionType,
    DemoMetrics,
    DemoState,
    Incident,
    IncidentContext,
    IncidentMemory,
    IncidentStatus,
    Recommendation,
    RepairAttempt,
)
from gridrecall_api.simulator import overheating_context, seed_sites

ACTION_TITLES = {
    ActionType.APPROVED_INVERTER_RESET: "Perform an approved inverter reset",
    ActionType.INSPECT_VENTILATION: "Inspect and clear the ventilation path",
}


class GridRecallDemoService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.embeddings = LocalHashEmbeddingProvider()
        self.memory = InMemoryOperationalMemory(self.embeddings)
        self.policy = SafetyPolicyEngine()
        self.sites = seed_sites()
        self.incidents: list[Incident] = []
        self.phase = "ready"
        self.message = "Inject the first incident to begin the operational-memory demonstration."

    def reset(self) -> DemoState:
        with self._lock:
            self.memory.clear()
            self.incidents.clear()
            for site in self.sites:
                site.status = "healthy"
            self.phase = "ready"
            self.message = "Demo reset. No operational incident memories exist yet."
            return self.state()

    def recommend(
        self,
        context: IncidentContext,
        qualification: str = "field_technician",
    ) -> Recommendation:
        evidence = self.memory.retrieve(context)
        influential = [item for item in evidence if item.influence_score >= 0.55]
        if influential:
            action = influential[0].memory.successful_action
            avoided = list(
                dict.fromkeys(
                    failed
                    for item in influential
                    for failed in item.memory.failed_actions
                    if failed != action
                )
            )
            explanation = (
                f"A similar {context.inverter_model} incident at "
                f"{influential[0].memory.site_name} was resolved with this action. "
                "Its failed attempts were demoted using the recorded outcome."
            )
            confidence = min(0.96, 0.55 + influential[0].influence_score * 0.4)
        else:
            action = ActionType.APPROVED_INVERTER_RESET
            avoided = []
            explanation = (
                "No sufficiently relevant successful incident memory exists, so GridRecall "
                "starts with the conservative approved playbook."
            )
            confidence = 0.61

        policy = self.policy.validate(action, qualification)
        if not policy.allowed:
            action = ActionType.ESCALATE_ENGINEER
            policy = self.policy.validate(action, qualification)

        return Recommendation(
            action=action,
            title=ACTION_TITLES.get(action, action.value.replace("_", " ").title()),
            explanation=explanation,
            confidence=round(confidence, 2),
            safety_status=policy.status,
            escalation_condition=(
                "Escalate immediately if temperature exceeds 85 C, smoke is observed, "
                "or isolation is required."
            ),
            evidence=[item.as_evidence() for item in influential],
            avoided_actions=avoided,
        )

    def run_first_incident(self) -> DemoState:
        with self._lock:
            if self.memory.all():
                return self.state()
            site = self.sites[0]
            site.status = "incident"
            context = overheating_context(site)
            recommendation = self.recommend(context)
            attempts = [
                RepairAttempt(
                    action=ActionType.APPROVED_INVERTER_RESET,
                    succeeded=False,
                    observation=(
                        "Reset completed, but temperature continued rising and output stayed low."
                    ),
                    duration_minutes=9,
                ),
                RepairAttempt(
                    action=ActionType.INSPECT_VENTILATION,
                    succeeded=True,
                    observation=(
                        "Dust obstruction cleared from the intake. Temperature and output returned "
                        "to their normal operating range."
                    ),
                    duration_minutes=18,
                ),
            ]
            incident = Incident(
                id=uuid4(),
                context=context,
                status=IncidentStatus.RESOLVED,
                recommendation=recommendation,
                attempts=attempts,
                time_to_restore_minutes=27,
                unavailable_energy_avoided_kwh=18.6,
            )
            self.incidents.append(incident)
            memory = IncidentMemory(
                source_incident_id=incident.id,
                site_name=site.name,
                inverter_model=context.inverter_model,
                fault_type=context.fault_type,
                symptoms=context.symptoms,
                search_text=context.search_text,
                embedding=self.embeddings.embed(context.search_text),
                attempts=attempts,
                outcome_score=0.82,
                resolution_summary=(
                    "An approved reset failed. Clearing an obstructed inverter ventilation path "
                    "restored safe temperature and normal power output."
                ),
            )
            self.memory.remember(memory)
            site.status = "restored"
            self.phase = "first_resolved"
            self.message = (
                "Ajegunle restored. GridRecall stored the failed reset and successful ventilation "
                "inspection as outcome-scored memory."
            )
            return self.state()

    def run_second_incident(self) -> DemoState:
        with self._lock:
            if not self.memory.all():
                self.run_first_incident()
            if len(self.incidents) >= 2:
                return self.state()
            site = self.sites[1]
            site.status = "incident"
            context = overheating_context(site, variation=0.7)
            recommendation = self.recommend(context)
            attempt = RepairAttempt(
                action=recommendation.action,
                succeeded=True,
                observation=(
                    "The technician inspected ventilation first, cleared the obstruction, and "
                    "restored output without repeating the ineffective reset."
                ),
                duration_minutes=11,
            )
            incident = Incident(
                context=context,
                status=IncidentStatus.RESOLVED,
                recommendation=recommendation,
                attempts=[attempt],
                time_to_restore_minutes=11,
                unavailable_energy_avoided_kwh=31.4,
            )
            self.incidents.append(incident)
            self.memory.remember(
                IncidentMemory(
                    source_incident_id=incident.id,
                    site_name=site.name,
                    inverter_model=context.inverter_model,
                    fault_type=context.fault_type,
                    symptoms=context.symptoms,
                    search_text=context.search_text,
                    embedding=self.embeddings.embed(context.search_text),
                    attempts=[attempt],
                    outcome_score=0.94,
                    resolution_summary=(
                        "Cross-site memory prioritised ventilation inspection, avoiding a failed "
                        "reset and restoring output in one diagnostic step."
                    ),
                )
            )
            site.status = "restored"
            self.phase = "memory_proven"
            self.message = (
                "Kura restored in one step. Ajegunle's outcome memory changed the recommendation "
                "and prevented the failed reset from being repeated."
            )
            return self.state()

    def state(self) -> DemoState:
        resolved = [item for item in self.incidents if item.status == IncidentStatus.RESOLVED]
        metrics = DemoMetrics(
            incidents_resolved=len(resolved),
            minutes_of_outage_avoided=sum(item.minutes_saved for item in resolved),
            failed_actions_not_repeated=sum(
                len(item.recommendation.avoided_actions) for item in resolved
            ),
            unavailable_energy_avoided_kwh=round(
                sum(item.unavailable_energy_avoided_kwh for item in resolved), 1
            ),
            operational_memories=len(self.memory.all()),
        )
        next_action = {
            "ready": "Run the Ajegunle incident",
            "first_resolved": "Run the related Kura incident",
            "memory_proven": "Reset and replay the demo",
        }[self.phase]
        return DemoState(
            phase=self.phase,
            message=self.message,
            sites=self.sites,
            incidents=self.incidents,
            memories=self.memory.all(),
            metrics=metrics,
            next_action=next_action,
        )


def build_demo_service() -> GridRecallDemoService:
    return GridRecallDemoService()
