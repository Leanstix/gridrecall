-- GridRecall operational-memory schema for CockroachDB 25.4+.
-- Titan Text Embeddings V2 produces 1024-dimensional vectors by default.

SET CLUSTER SETTING feature.vector_index.enabled = true;

CREATE TABLE IF NOT EXISTS sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING NOT NULL,
    community STRING NOT NULL,
    capacity_kw DECIMAL(10, 2) NOT NULL CHECK (capacity_kw > 0),
    status STRING NOT NULL DEFAULT 'healthy',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grid_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id),
    asset_type STRING NOT NULL,
    manufacturer STRING NOT NULL,
    model STRING NOT NULL,
    serial_number STRING UNIQUE,
    configuration JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    INDEX assets_site_model_idx (site_id, model)
);

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES sites(id),
    asset_id UUID NOT NULL REFERENCES grid_assets(id),
    fault_type STRING NOT NULL,
    status STRING NOT NULL CHECK (status IN ('open', 'investigating', 'resolved')),
    symptoms STRING[] NOT NULL,
    telemetry_snapshot JSONB NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    version INT8 NOT NULL DEFAULT 1,
    INDEX incidents_site_status_idx (site_id, status, opened_at DESC)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id),
    selected_action STRING NOT NULL,
    explanation STRING NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    safety_status STRING NOT NULL,
    model_id STRING,
    prompt_version STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    INDEX recommendations_incident_idx (incident_id, created_at DESC)
);

CREATE TABLE IF NOT EXISTS technician_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL REFERENCES recommendations(id),
    technician_id STRING NOT NULL,
    qualification STRING NOT NULL,
    decision STRING NOT NULL CHECK (decision IN ('approved', 'rejected', 'modified')),
    reason STRING,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repair_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id),
    recommendation_id UUID REFERENCES recommendations(id),
    action STRING NOT NULL,
    sequence_number INT8 NOT NULL,
    succeeded BOOL NOT NULL,
    observation STRING NOT NULL,
    duration_minutes INT8 NOT NULL CHECK (duration_minutes >= 0),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (incident_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL UNIQUE REFERENCES incidents(id),
    service_restored BOOL NOT NULL,
    time_to_restore_minutes INT8,
    unavailable_energy_avoided_kwh DECIMAL(12, 3) NOT NULL DEFAULT 0,
    repeat_fault_within_7_days BOOL,
    safety_compliant BOOL NOT NULL,
    technician_feedback STRING,
    outcome_score DECIMAL(5, 4) NOT NULL CHECK (outcome_score BETWEEN 0 AND 1),
    measured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incident_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_incident_id UUID NOT NULL UNIQUE REFERENCES incidents(id),
    site_id UUID NOT NULL REFERENCES sites(id),
    asset_model STRING NOT NULL,
    fault_type STRING NOT NULL,
    search_text STRING NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    resolution_summary STRING NOT NULL,
    outcome_score DECIMAL(5, 4) NOT NULL CHECK (outcome_score BETWEEN 0 AND 1),
    safe BOOL NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    INDEX memories_filter_idx (asset_model, fault_type, safe, outcome_score DESC)
);

CREATE VECTOR INDEX IF NOT EXISTS memories_embedding_idx
    ON incident_memories (asset_model, fault_type, embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS memory_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL REFERENCES recommendations(id),
    memory_id UUID NOT NULL REFERENCES incident_memories(id),
    vector_similarity DECIMAL(5, 4) NOT NULL,
    influence_score DECIMAL(5, 4) NOT NULL,
    rank INT8 NOT NULL,
    UNIQUE (recommendation_id, memory_id)
);

CREATE TABLE IF NOT EXISTS safety_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action STRING NOT NULL UNIQUE,
    minimum_qualification STRING NOT NULL,
    requires_human_approval BOOL NOT NULL DEFAULT true,
    active BOOL NOT NULL DEFAULT true,
    rule_version INT8 NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Example hybrid retrieval: vector relevance plus operational filters and outcome quality.
-- The application provides $1 as a VECTOR(1024) query value.
--
-- SELECT id, source_incident_id, resolution_summary, outcome_score,
--        1 - (embedding <=> $1) AS cosine_similarity
-- FROM incident_memories
-- WHERE safe = true
--   AND asset_model = $2
--   AND fault_type = $3
-- ORDER BY embedding <=> $1, outcome_score DESC
-- LIMIT 5;
