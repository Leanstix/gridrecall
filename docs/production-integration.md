# Production integration test

This checkpoint verifies the complete GridRecall memory loop against CockroachDB Cloud, its
Managed MCP Server, Amazon Titan Text Embeddings V2 and Amazon Nova Lite. Run it from AWS
CloudShell in `us-east-1` so Bedrock credentials come from the CloudShell role.

## Required configuration

Create `.env` from the example and fill these values locally. Never commit this file or paste its
secrets into chat.

```bash
cp .env.example .env
```

```dotenv
DATABASE_URL="postgresql://.../gridrecall?sslmode=verify-full..."
AWS_REGION=us-east-1
BEDROCK_REASONING_MODEL_ID=us.amazon.nova-lite-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
COCKROACH_MCP_URL=https://cockroachlabs.cloud/mcp
COCKROACH_MCP_CLUSTER_ID=your-cluster-id
COCKROACH_MCP_API_KEY=your-service-account-api-key
```

The MCP service account should be scoped to the GridRecall cluster and granted read access only.
Application writes use the validated SQL transaction layer, not MCP.

## Install and migrate

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "services/api[dev]"
python -m gridrecall_api.migrations
```

The migration command is idempotent and checksum-protected. It creates the relational schema and a
cosine vector index prefixed by asset model and fault type.

## Run the end-to-end verifier

```bash
python -m gridrecall_api.verify_production
```

The final output should contain:

```json
{
  "passed": true,
  "titan_dimensions": 1024,
  "phase": "memory_proven",
  "second_action": "inspect_ventilation",
  "failed_reset_avoided": true,
  "reasoning_provider": "amazon-bedrock",
  "managed_mcp_context_used": true,
  "operational_memories": 2
}
```

This command writes two simulated resolved incidents to the configured CockroachDB cluster. It does
not operate physical equipment. Re-running it adds another traceable demonstration run; resetting
the dashboard clears only working state and intentionally does not erase durable incident memory.

## Verify the HTTP API

```bash
uvicorn gridrecall_api.main:app --app-dir services/api/src --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/api/demo/reset
curl -s -X POST http://localhost:8000/api/demo/incidents/first
curl -s -X POST http://localhost:8000/api/demo/incidents/second
```

The health response must report `demo_mode: false` and all three integration flags as `true`.

## Failure meanings

| Failure | Likely cause |
|---|---|
| Database connection or certificate error | Incorrect `DATABASE_URL` or CA certificate path |
| Vector feature or index error | Cluster is older than v25.4 or SQL user lacks migration authority |
| MCP 401/403 | Invalid API key or insufficient service-account scope |
| MCP table/query error | Migration was not run against the `gridrecall` database |
| Bedrock access error | Wrong AWS region, model ID or execution-role permission |
| Structured recommendation error | Nova returned output outside the constrained JSON contract |

References: [CockroachDB vector indexes](https://www.cockroachlabs.com/docs/stable/vector-indexes.html),
[Managed MCP connection](https://www.cockroachlabs.com/docs/cockroachcloud/connect-to-the-cockroachdb-cloud-mcp-server),
and [Psycopg 3 application guide](https://www.cockroachlabs.com/docs/stable/build-a-python-app-with-cockroachdb-psycopg3).
