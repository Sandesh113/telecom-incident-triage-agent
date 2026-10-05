# Incident evidence and local investigation

This is the normalized boundary between an incident producer and the agent. It does
not ingest network alarms or implement the alarm dictionary. The included demo is
synthetic, independently curated data; it does not load scenarios or the oracle.

`contract.py` validates a bundle with incident metadata, normalized events,
observations, KPI windows, changes and customer-impact records. IDs are unique
within a bundle, run IDs are UUIDs, times are UTC and windows are half-open.
`event_time` describes occurrence; `ingest_time` describes arrival. Events arriving
more than five minutes late must carry `late_event: true`. Routed events require a
normalized trigger. Completeness flags apply only within the incident window.

The loader writes metadata as `loading`, writes evidence, then writes `ready`.
It refuses a run that already contains an incident. A failed partial load is not
agent-readable; retry with a fresh UUID. Store keys use `RUN#<uuid>` and
`<collection>#<id>#<version>`, consistently with the Phase 1 store.
The returned `incident.ready` descriptor is not automatically sent to EventBridge.

From the repository root:

```powershell
uv sync
uv run python -m evidence.demo
uv run python -m evidence.load runs/demo-incident.json
uv run pytest -q
uv run python -m agent.local runs/demo-incident.json --output runs/investigation.json
```

The local agent loads the bundle into an in-memory SQLite store and reads local
approved knowledge files. Its sole remote operation is model inference through
Bedrock using the default profile and the approved Sonnet model. It neither loads
DynamoDB nor publishes reports or notifications to AWS. Output and tool traces go
into ignored `runs/`. It can perform up to 40 application-tool calls, followed by
at most one report correction attempt within that budget.

The eight application tools match SKILL.md. There is no topology service; the agent
reads relationship tables from reference sections. Actions are proposals only.
Checks validate schema, retrieved citation IDs, routing, required steps, attribution,
impact counts, escalation and change approval. They do not establish that every
natural-language inference is correct. Reports are explicitly provisional.

The AgentCore adapter reads approved knowledge from S3 and evidence through a
read-only DynamoDB store. It writes reports to S3 and sends status, investigation
report JSON and the S3 pointer through SNS (owner-requested email change). Publication is covered by local tests and the
2026-10-05 AWS smoke test on runtime version 3. Previous-report retrieval is not enabled.

Build the Linux ARM64 package without uploading, from Git Bash:

```bash
BUILD_ONLY=true AWS_PROFILE=default bash scripts/build_agent_zip.sh ./agent local-candidate
```

Keep scenario/oracle/dictionary files outside the package and knowledge bucket.
The existing smoke fixture uses a different evidence shape. For subsequent deployments,
prepare a normalized bundle in DynamoDB and a matching event, then inspect a
Terraform plan and perform an end-to-end test. Real alarm ingestion, full scenario
generation and scenario-oracle evaluation remain separate work.
