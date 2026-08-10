from gridrecall_api.embeddings import LocalHashEmbeddingProvider
from gridrecall_api.memory import InMemoryOperationalMemory
from gridrecall_api.schemas import (
    ActionType,
    IncidentMemory,
    RepairAttempt,
)
from gridrecall_api.simulator import overheating_context, seed_sites


def test_retrieval_prefers_matching_equipment_and_successful_outcome() -> None:
    embeddings = LocalHashEmbeddingProvider()
    memory = InMemoryOperationalMemory(embeddings)
    sites = seed_sites()
    context = overheating_context(sites[0])
    matching = IncidentMemory(
        source_incident_id=sites[0].id,
        site_name=sites[0].name,
        inverter_model=context.inverter_model,
        fault_type=context.fault_type,
        symptoms=context.symptoms,
        search_text=context.search_text,
        embedding=embeddings.embed(context.search_text),
        attempts=[
            RepairAttempt(
                action=ActionType.INSPECT_VENTILATION,
                succeeded=True,
                observation="Cleared obstruction.",
                duration_minutes=10,
            )
        ],
        outcome_score=0.95,
        resolution_summary="Ventilation inspection restored output.",
    )
    memory.remember(matching)

    result = memory.retrieve(overheating_context(sites[1]))

    assert result[0].memory.id == matching.id
    assert result[0].influence_score > 0.8
