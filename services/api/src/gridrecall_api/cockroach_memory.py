from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection

from gridrecall_api.database import CockroachDatabase
from gridrecall_api.memory import RankedMemory
from gridrecall_api.repository import CockroachResolutionRepository
from gridrecall_api.schemas import (
    ActionType,
    IncidentContext,
    IncidentMemory,
    RepairAttempt,
)


class CockroachVectorMemory:
    """Outcome-aware semantic retrieval using CockroachDB's vector index."""

    def __init__(self, database: CockroachDatabase, embeddings: Any) -> None:
        self._database = database
        self._embeddings = embeddings

    def retrieve(self, context: IncidentContext, limit: int = 3) -> list[RankedMemory]:
        query_vector = self._embeddings.embed(context.search_text)
        vector_literal = CockroachResolutionRepository._vector_literal(query_vector)
        return self._database.run_transaction(
            lambda connection: self._retrieve(connection, context, vector_literal, limit)
        )

    def _retrieve(
        self,
        connection: Connection[Any],
        context: IncidentContext,
        vector_literal: str,
        limit: int,
    ) -> list[RankedMemory]:
        rows = connection.execute(
            """
            SELECT
                memory.id,
                memory.source_incident_id,
                site.name,
                memory.asset_model,
                memory.fault_type,
                incident.symptoms,
                memory.search_text,
                memory.outcome_score,
                memory.resolution_summary,
                memory.safe,
                memory.created_at,
                1 - (memory.embedding <=> %s::VECTOR) AS cosine_similarity
            FROM incident_memories AS memory
            JOIN sites AS site ON site.id = memory.site_id
            JOIN incidents AS incident ON incident.id = memory.source_incident_id
            WHERE memory.safe = true
              AND memory.asset_model = %s
              AND memory.fault_type = %s
            ORDER BY memory.embedding <=> %s::VECTOR, memory.outcome_score DESC
            LIMIT %s
            """,
            (
                vector_literal,
                context.inverter_model,
                context.fault_type,
                vector_literal,
                limit,
            ),
        ).fetchall()
        ranked: list[RankedMemory] = []
        for row in rows:
            attempts = self._load_attempts(connection, row[1])
            similarity = max(0.0, min(1.0, float(row[11])))
            outcome_score = float(row[7])
            symptom_overlap = self._symptom_overlap(context.symptoms, row[5])
            influence = min(
                1.0,
                0.4 * similarity
                + 0.2
                + 0.15 * symptom_overlap
                + 0.1
                + 0.15 * outcome_score,
            )
            memory = IncidentMemory(
                id=self._uuid(row[0]),
                source_incident_id=self._uuid(row[1]),
                site_name=str(row[2]),
                inverter_model=str(row[3]),
                fault_type=str(row[4]),
                symptoms=list(row[5]),
                search_text=str(row[6]),
                embedding=[],
                attempts=attempts,
                outcome_score=outcome_score,
                resolution_summary=str(row[8]),
                safe=bool(row[9]),
                created_at=(
                    row[10]
                    if isinstance(row[10], datetime)
                    else datetime.fromisoformat(row[10])
                ),
            )
            ranked.append(
                RankedMemory(
                    memory=memory,
                    similarity=similarity,
                    influence_score=influence,
                )
            )
        return ranked

    @staticmethod
    def _load_attempts(
        connection: Connection[Any],
        incident_id: UUID | str,
    ) -> list[RepairAttempt]:
        rows = connection.execute(
            """
            SELECT action, succeeded, observation, duration_minutes
            FROM repair_attempts
            WHERE incident_id = %s
            ORDER BY sequence_number
            """,
            (incident_id,),
        ).fetchall()
        return [
            RepairAttempt(
                action=ActionType(row[0]),
                succeeded=bool(row[1]),
                observation=str(row[2]),
                duration_minutes=int(row[3]),
            )
            for row in rows
        ]

    @staticmethod
    def _symptom_overlap(left: Sequence[str], right: Sequence[str]) -> float:
        left_set = set(left)
        right_set = set(right)
        union = left_set | right_set
        return len(left_set & right_set) / len(union) if union else 0.0

    @staticmethod
    def _uuid(value: UUID | str) -> UUID:
        return value if isinstance(value, UUID) else UUID(str(value))
