from collections.abc import Sequence
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from psycopg import Connection
from psycopg.types.json import Jsonb

from gridrecall_api.database import CockroachDatabase
from gridrecall_api.schemas import Incident, IncidentMemory, Site, utc_now


class ResolutionRepository(Protocol):
    def record_resolution(
        self,
        site: Site,
        incident: Incident,
        memory: IncidentMemory,
    ) -> None: ...


class NullResolutionRepository:
    def record_resolution(
        self,
        site: Site,
        incident: Incident,
        memory: IncidentMemory,
    ) -> None:
        return None


class CockroachResolutionRepository:
    """Persist a complete incident-to-outcome chain in one transaction."""

    def __init__(self, database: CockroachDatabase) -> None:
        self._database = database

    def record_resolution(
        self,
        site: Site,
        incident: Incident,
        memory: IncidentMemory,
    ) -> None:
        self._database.run_transaction(
            lambda connection: self._record(connection, site, incident, memory)
        )

    def _record(
        self,
        connection: Connection[Any],
        site: Site,
        incident: Incident,
        memory: IncidentMemory,
    ) -> None:
        asset_id = self._asset_id(site.id, site.inverter_model)
        connection.execute(
            """
            INSERT INTO sites (id, name, community, capacity_kw, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = excluded.name,
                community = excluded.community,
                capacity_kw = excluded.capacity_kw,
                status = excluded.status
            """,
            (site.id, site.name, site.community, site.capacity_kw, site.status),
        )
        connection.execute(
            """
            INSERT INTO grid_assets (
                id, site_id, asset_type, manufacturer, model, configuration
            )
            VALUES (%s, %s, 'inverter', %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                model = excluded.model,
                configuration = excluded.configuration
            """,
            (
                asset_id,
                site.id,
                self._manufacturer(site.inverter_model),
                site.inverter_model,
                Jsonb({"simulated": True}),
            ),
        )
        connection.execute(
            """
            INSERT INTO incidents (
                id, site_id, asset_id, fault_type, status, symptoms,
                telemetry_snapshot, opened_at, resolved_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = excluded.status,
                symptoms = excluded.symptoms,
                telemetry_snapshot = excluded.telemetry_snapshot,
                resolved_at = excluded.resolved_at,
                version = incidents.version + 1
            """,
            (
                incident.id,
                site.id,
                asset_id,
                incident.context.fault_type,
                incident.status.value,
                incident.context.symptoms,
                Jsonb(incident.context.telemetry.model_dump(mode="json")),
                incident.created_at,
                utc_now(),
            ),
        )
        recommendation = incident.recommendation
        connection.execute(
            """
            INSERT INTO recommendations (
                id, incident_id, selected_action, explanation, confidence,
                safety_status, model_id, prompt_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                selected_action = excluded.selected_action,
                explanation = excluded.explanation,
                confidence = excluded.confidence,
                safety_status = excluded.safety_status,
                model_id = excluded.model_id,
                prompt_version = excluded.prompt_version
            """,
            (
                recommendation.id,
                incident.id,
                recommendation.action.value,
                recommendation.explanation,
                recommendation.confidence,
                recommendation.safety_status,
                recommendation.model_id,
                "bedrock-v1" if recommendation.model_id else "case-based-v1",
            ),
        )
        for sequence, attempt in enumerate(incident.attempts, start=1):
            connection.execute(
                """
                INSERT INTO repair_attempts (
                    id, incident_id, recommendation_id, action, sequence_number,
                    succeeded, observation, duration_minutes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (incident_id, sequence_number) DO UPDATE SET
                    action = excluded.action,
                    succeeded = excluded.succeeded,
                    observation = excluded.observation,
                    duration_minutes = excluded.duration_minutes
                """,
                (
                    uuid4(),
                    incident.id,
                    recommendation.id,
                    attempt.action.value,
                    sequence,
                    attempt.succeeded,
                    attempt.observation,
                    attempt.duration_minutes,
                ),
            )
        connection.execute(
            """
            INSERT INTO outcomes (
                id, incident_id, service_restored, time_to_restore_minutes,
                unavailable_energy_avoided_kwh, safety_compliant, outcome_score
            )
            VALUES (%s, %s, true, %s, %s, true, %s)
            ON CONFLICT (incident_id) DO UPDATE SET
                service_restored = excluded.service_restored,
                time_to_restore_minutes = excluded.time_to_restore_minutes,
                unavailable_energy_avoided_kwh = excluded.unavailable_energy_avoided_kwh,
                safety_compliant = excluded.safety_compliant,
                outcome_score = excluded.outcome_score,
                measured_at = now()
            """,
            (
                uuid4(),
                incident.id,
                incident.time_to_restore_minutes,
                incident.unavailable_energy_avoided_kwh,
                memory.outcome_score,
            ),
        )
        stored_memory_id = connection.execute(
            """
            INSERT INTO incident_memories (
                id, source_incident_id, site_id, asset_model, fault_type,
                search_text, embedding, resolution_summary, outcome_score, safe
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::VECTOR, %s, %s, %s)
            ON CONFLICT (source_incident_id) DO UPDATE SET
                search_text = excluded.search_text,
                embedding = excluded.embedding,
                resolution_summary = excluded.resolution_summary,
                outcome_score = excluded.outcome_score,
                safe = excluded.safe
            RETURNING id
            """,
            (
                memory.id,
                incident.id,
                site.id,
                memory.inverter_model,
                memory.fault_type,
                memory.search_text,
                self._vector_literal(memory.embedding),
                memory.resolution_summary,
                memory.outcome_score,
                memory.safe,
            ),
        ).fetchone()[0]
        self._record_evidence(
            connection,
            recommendation.id,
            stored_memory_id,
            recommendation.evidence,
        )

    @staticmethod
    def _record_evidence(
        connection: Connection[Any],
        recommendation_id: UUID,
        current_memory_id: UUID,
        evidence: Sequence[Any],
    ) -> None:
        for rank, item in enumerate(evidence, start=1):
            if item.memory_id == current_memory_id:
                continue
            connection.execute(
                """
                INSERT INTO memory_evidence (
                    id, recommendation_id, memory_id, vector_similarity,
                    influence_score, rank
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (recommendation_id, memory_id) DO UPDATE SET
                    vector_similarity = excluded.vector_similarity,
                    influence_score = excluded.influence_score,
                    rank = excluded.rank
                """,
                (
                    uuid4(),
                    recommendation_id,
                    item.memory_id,
                    item.similarity,
                    item.influence_score,
                    rank,
                ),
            )

    @staticmethod
    def _asset_id(site_id: UUID, inverter_model: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"gridrecall:{site_id}:{inverter_model}")

    @staticmethod
    def _manufacturer(inverter_model: str) -> str:
        return inverter_model.split(maxsplit=1)[0]

    @staticmethod
    def _vector_literal(vector: Sequence[float]) -> str:
        return "[" + ",".join(f"{value:.10g}" for value in vector) + "]"
