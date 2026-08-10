# Three-minute demo blueprint

This script is deliberately centred on one proof: a measured outcome from one site changes the next recommendation at another site.

## 0:00–0:20 — Problem

Open the fleet dashboard in its reset state.

> Mini-grid maintenance knowledge is distributed across sites and people. When that knowledge is lost, technicians repeat failed repairs and outages last longer. GridRecall turns each incident into outcome-scored operational memory.

## 0:20–1:05 — First incident

Click **Run the Ajegunle incident**.

Point out:

- Rising inverter temperature and falling output despite normal irradiance.
- No relevant previous outcome memory.
- The conservative approved inverter reset.
- The reset failed.
- Ventilation inspection found and cleared an obstruction.
- Both the failed and successful action were stored, not just the final answer.

## 1:05–2:05 — Memory changes behaviour

Click **Run the related Kura incident**.

Point out:

- The same model shows similar symptoms at another site.
- GridRecall retrieves the Ajegunle case.
- The recorded outcome demotes the failed reset.
- Ventilation inspection becomes the first recommendation.
- The technician restores service in one step.
- The dashboard shows the avoided action and improvement.

## 2:05–2:40 — Technology

Show the architecture diagram or repository briefly.

> CockroachDB is both the transactional source of truth and vector retrieval layer. Distributed Vector Indexing finds semantically similar incidents, while the Managed MCP Server gives the investigation agent controlled access to site, asset, policy and outcome data. Bedrock produces a structured recommendation, and deterministic rules enforce safety and permissions.

## 2:40–3:00 — Close

Return to the comparison panel.

> GridRecall does not merely remember a conversation. It remembers what happened, what was tried and what actually worked. Every fault makes the next repair faster.

Do not claim the simulator's time or energy figures are measured field results. Label them as controlled demonstration outputs until real partner data is available.
