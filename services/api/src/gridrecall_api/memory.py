from dataclasses import dataclass
from typing import Protocol

from gridrecall_api.embeddings import EmbeddingProvider, cosine_similarity
from gridrecall_api.schemas import IncidentContext, IncidentMemory, MemoryEvidence


@dataclass(frozen=True)
class RankedMemory:
    memory: IncidentMemory
    similarity: float
    influence_score: float

    def as_evidence(self) -> MemoryEvidence:
        return MemoryEvidence(
            memory_id=self.memory.id,
            site_name=self.memory.site_name,
            similarity=round(self.similarity, 3),
            influence_score=round(self.influence_score, 3),
            successful_action=self.memory.successful_action,
            failed_actions=self.memory.failed_actions,
            summary=self.memory.resolution_summary,
        )


class MemoryRetriever(Protocol):
    def retrieve(self, context: IncidentContext, limit: int = 3) -> list[RankedMemory]: ...


class InMemoryOperationalMemory:
    def __init__(self, embeddings: EmbeddingProvider) -> None:
        self._embeddings = embeddings
        self._memories: list[IncidentMemory] = []

    def clear(self) -> None:
        self._memories.clear()

    def all(self) -> list[IncidentMemory]:
        return list(self._memories)

    def remember(self, memory: IncidentMemory) -> None:
        self._memories.append(memory)

    def retrieve(self, context: IncidentContext, limit: int = 3) -> list[RankedMemory]:
        query_embedding = self._embeddings.embed(context.search_text)
        query_symptoms = set(context.symptoms)
        ranked: list[RankedMemory] = []

        for memory in self._memories:
            if not memory.safe:
                continue
            raw_similarity = cosine_similarity(query_embedding, memory.embedding)
            similarity = (raw_similarity + 1) / 2
            equipment_match = float(memory.inverter_model == context.inverter_model)
            symptom_union = query_symptoms | set(memory.symptoms)
            symptom_overlap = (
                len(query_symptoms & set(memory.symptoms)) / len(symptom_union)
                if symptom_union
                else 0.0
            )
            fault_match = float(memory.fault_type == context.fault_type)
            influence = (
                0.4 * similarity
                + 0.2 * equipment_match
                + 0.15 * symptom_overlap
                + 0.1 * fault_match
                + 0.15 * memory.outcome_score
            )
            ranked.append(
                RankedMemory(
                    memory=memory,
                    similarity=similarity,
                    influence_score=min(1.0, influence),
                )
            )

        ranked.sort(key=lambda item: item.influence_score, reverse=True)
        return ranked[:limit]
