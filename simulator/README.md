# Network-alarm replay

This simulator closes the transport demo's input gap without adding an AWS resource.
Dictionary 0.2 is bundled at `simulator/data/alarms.yaml` for operator-side use;
no parent-folder files are needed to run the transport replay.
It runs on the operator's laptop and replays raw vendor notifications through a
small normalization adapter, loads incident evidence, then publishes `incident.ready`
to the existing EventBridge bus. Lambda, AgentCore, Bedrock, S3 and SNS are unchanged.
It is a synthetic alarm-to-report demo, not integration with a real network NMS.

## Run

From the repository root, with uv and the existing AWS login available:

```powershell
# Local replay, no AWS calls:
uv run python -m simulator.transport

# Full AWS demo using the working profile:
uv run python -m simulator.transport --aws --profile default

# Windows shortcut; also locates the existing WinGet uv installation:
.\scripts\simulate_network_alarm.ps1 -Aws
```

The command prints the private output folder, incident ID, run UUID and ingestion
counts. Outputs stay in ignored `runs/alarm-replays/<uuid>/`:

- `raw-alarms.json`: raw notification records and simulated ingest-clock headers.
- `bundle.json`: normalized events plus synthetic observations/KPIs/impact evidence.
- `ingestion-audit.json`: notification and transition deduplication audit.
- `ready-event.json`: the event emitted only after evidence loads successfully.
- `eventbridge-result.json`: AWS receipt, when `--aws` is selected.

The investigation report goes to the existing S3 path
`reports/<incident_id>/<run_id>.json`, followed by the normal SNS notification.
The simulator checks the AWS account and project tags before writing evidence or
publishing. Local mode uses SQLite. Raw files, dictionary and simulator code are
never uploaded to the knowledge bucket or included in the agent package.

## Why these alarms fit the SOPs

SKILL requires enriched triggers and forbids the agent from normalizing alarm names.
The dictionary's LINK_DOWN/UP mappings and aliases agree with current ROUTING,
SOP-03 and REF-TX.1–2:

| Source notification | Adapter result |
|---|---|
| Vendor A `LAG down`, `raised` | LINK_DOWN, active, aggregate_link |
| Vendor A `LAG down`, `cleared` | LINK_UP, cleared; severity remains separate |
| Vendor B `LAG-DOWN`, ACTIVE/CLEARED | LINK_DOWN/LINK_UP |
| Vendor B explicit `LAG-UP` | LINK_UP; duplicate clear/UP transitions marked within 2 seconds |
| `lnk-01` | canonical LINK-1 |

The default is three down/clear cycles over six minutes: six state transitions,
not six cycles. Both notifications in a lifecycle survive; identical notification
IDs are deduplicated. Raw provenance, separate lifecycle ID and severity are kept
under `raw`. Unknown or conflicting alarms stop before loading/publishing, and
their raw capture remains on disk. This is a restricted adapter, not a general
unmapped-alarm ingestion service.

The supporting telemetry reuses the verified synthetic transport measurements:
CELL-A/B degrade, CELL-E/F remain stable, 120 distinct customer records, initial
LINK-1 state up, and a complete-empty change window. These are simulated evidence,
not facts inferred from alarms or an embedded expected diagnosis. Reference-file
tables provide the relationships. The model determines the hypothesis from tools.

`--vendor vendor_a|vendor_b|mixed`, `--cycles 1|2|3` and `--start-time <UTC>` allow
controlled replay. Only flap length/vendor changes; the telemetry preset still
contains 120 affected customers. Default logical window ends at the current time;
ingest headers are part of the synthetic replay clock, not upload timestamps.
No wall-clock waiting is required to replay 15 minutes of measurements.

## Limits

This adapter supports LINK-1 aggregate-link alarms only. It does not implement the
full dictionary's core/RF mappings, KPI-derived trigger episodes, conditional
routing, real-time correlation, late-report revision or S1–S8 evaluation. It does
not change issue #17. Each additional SOP family needs compatible required-data
generators and tests before claiming coverage. General event idempotency is also
still pending. A real NMS feed would replace raw generation and supply its actual
timestamps, inventory and telemetry.
