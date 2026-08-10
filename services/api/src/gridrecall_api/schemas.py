from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ActionType(StrEnum):
    CONTINUE_MONITORING = "continue_monitoring"
    INSPECT_VENTILATION = "inspect_ventilation"
    APPROVED_INVERTER_RESET = "approved_inverter_reset"
    INSPECT_CONNECTIONS = "inspect_connections"
    REDUCE_NONCRITICAL_LOAD = "reduce_noncritical_load"
    ISOLATE_COMPONENT = "isolate_component"
    DISPATCH_TECHNICIAN = "dispatch_technician"
    ESCALATE_ENGINEER = "escalate_engineer"


class IncidentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class Site(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    community: str
    capacity_kw: float
    inverter_model: str
    status: str = "healthy"


class Telemetry(BaseModel):
    inverter_temperature_c: float
    power_output_kw: float
    solar_irradiance_w_m2: float
    battery_state_of_charge_pct: float
    ambient_temperature_c: float
    load_demand_kw: float
    alarms: list[str] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=utc_now)


class IncidentContext(BaseModel):
    site_id: UUID
    site_name: str
    inverter_model: str
    fault_type: str
    symptoms: list[str]
    telemetry: Telemetry

    @property
    def search_text(self) -> str:
        symptoms = ", ".join(self.symptoms)
        return (
            f"{self.fault_type}. Symptoms: {symptoms}. Inverter: {self.inverter_model}. "
            f"Temperature {self.telemetry.inverter_temperature_c} C, output "
            f"{self.telemetry.power_output_kw} kW, irradiance "
            f"{self.telemetry.solar_irradiance_w_m2} W/m2."
        )


class RepairAttempt(BaseModel):
    action: ActionType
    succeeded: bool
    observation: str
    duration_minutes: int


class MemoryEvidence(BaseModel):
    memory_id: UUID
    site_name: str
    similarity: float = Field(ge=0, le=1)
    influence_score: float = Field(ge=0, le=1)
    successful_action: ActionType
    failed_actions: list[ActionType]
    summary: str


class Recommendation(BaseModel):
    action: ActionType
    title: str
    explanation: str
    confidence: float = Field(ge=0, le=1)
    safety_status: str
    escalation_condition: str
    evidence: list[MemoryEvidence] = Field(default_factory=list)
    avoided_actions: list[ActionType] = Field(default_factory=list)


class IncidentMemory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_incident_id: UUID
    site_name: str
    inverter_model: str
    fault_type: str
    symptoms: list[str]
    search_text: str
    embedding: list[float]
    attempts: list[RepairAttempt]
    outcome_score: float = Field(ge=0, le=1)
    resolution_summary: str
    safe: bool = True
    created_at: datetime = Field(default_factory=utc_now)

    @computed_field
    @property
    def successful_action(self) -> ActionType:
        return next(attempt.action for attempt in self.attempts if attempt.succeeded)

    @computed_field
    @property
    def failed_actions(self) -> list[ActionType]:
        return [attempt.action for attempt in self.attempts if not attempt.succeeded]


class Incident(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    context: IncidentContext
    status: IncidentStatus = IncidentStatus.OPEN
    recommendation: Recommendation
    attempts: list[RepairAttempt] = Field(default_factory=list)
    time_to_restore_minutes: int | None = None
    baseline_restore_minutes: int = 52
    unavailable_energy_avoided_kwh: float = 0
    created_at: datetime = Field(default_factory=utc_now)

    @computed_field
    @property
    def minutes_saved(self) -> int:
        if self.time_to_restore_minutes is None:
            return 0
        return max(0, self.baseline_restore_minutes - self.time_to_restore_minutes)


class DemoMetrics(BaseModel):
    incidents_resolved: int = 0
    minutes_of_outage_avoided: int = 0
    failed_actions_not_repeated: int = 0
    unavailable_energy_avoided_kwh: float = 0
    operational_memories: int = 0


class DemoState(BaseModel):
    phase: str
    message: str
    sites: list[Site]
    incidents: list[Incident]
    memories: list[IncidentMemory]
    metrics: DemoMetrics
    next_action: str


class CustomRecommendationRequest(BaseModel):
    context: IncidentContext
    technician_qualification: str = "field_technician"
