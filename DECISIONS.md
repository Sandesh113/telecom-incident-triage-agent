# DECISIONS

### Phase 1
- **Topology is static reference-file content only, not a queryable store.** ,
  SOP-01/02/03/05 to point at REF-CORE.5-6, REF-TX.1 and REF-RAN.4 instead of a topology service. Consequences in code: no `topology`
  collection, no topology loader, no `get_topology` implementation, no topology versioning or `at_time` lookup. The earlier Phase 1
  topology design (per-run topology versions, opaque `topo-1+<hash>` for scenario overrides, `TOPO:` evidence IDs) was removed.
  This departs from BUILD SPEC v3 §5.1, §5.4, §6 (`get_topology`), §8.2 validators 4 and 6, and SKILL.md `allowed-tools`; those are
  listed in ISSUES.md as still to be reconciled. The spec's S4 `topology_overrides` has no consumer any more.
- **Every collection is keyed by run UUID**, so runs never mix. ASSUMPTION (keeps runs isolated).
- **Generic document store:** `put/get/query/versions/delete_run`, equality filter only. DynamoDB keys `pk=RUN#<run>`, `sk=<collection>#<id>#<version>`,
  doc stored as a JSON string (boto3 rejects floats). This supersedes the `INCIDENT#...` key shape sketched in `dynamodb.tf` comments for the
  walking skeleton (the skeleton never reads the table).
- **Read-only wrapper** for the agent: enforces  rule 8 in code as well as IAM.
- **Removed with the topology service:** `store/topology.py`, `tests/test_topology.py`, and (not requested, but they only served topology) `store/cli.py`,
  `harness/scenario_inputs.resolve_topology`, `Manifest.topology_version`, topology loading in `harness/new_run.py`.
- **Scenario inputs location:** read from `SOP_RCA_SCENARIO_INPUTS`, else `knowledge/scenarios/` (spec §3), else the top folder.
  The copy of scenario_inputs/oracle/dictionary into `knowledge/` was blocked (see PROGRESS.md) and is left for the human to decide.
- **Validators 4 and 6 relaxed to "cites the relevant reference-file ID"; 8 agent tools.** USER DECISION (2026-10-05). Full text and cost in ISSUES.md #15.
- **Concrete demo relationships live as static tables in the reference files** (ran-rf.md, core-control-plane.md; link-to-cell was already in transport.md). USER DECISION.
  Gaps and one misplaced table are logged in ISSUES.md #16-17.
- **Word source updated to match** (clean docx only): ISSUES.md #14.

### 2026-10-05 — Local investigation candidate
- **Scope:** implementation-plan steps 1-2 (normalized incident contract and realistic evidence), then build and test the agent before deployment. USER DECISION. These are not narration steps 1-2; real network-alarm ingestion is not implemented here.
- **Evidence isolation:** one incident per run UUID, ready marker written last, UTC half-open windows, completeness bounded to the incident window. VERIFIED against SQLite and DynamoDB/moto. Live DynamoDB loading is not yet verified.
- **Model integration:** Strands 1.57.2, eight explicit application tools and the SDK's structured-output formatter, approved Sonnet model, full SKILL resident in the system prompt. VERIFIED by local Bedrock inference. No topology service or scenario/oracle input.
- **Guardrails:** read-only evidence wrapper, 40 application-tool calls, one correction attempt, typed provisional report, retrieved citation checks and required approval for proposed changes. VERIFIED by tests. Structural validation does not prove the reasoning; static-reference relationship validity remains a model/evaluator judgement per issue #15.
- **Deployment boundary:** local ARM64 ZIP build uses `BUILD_ONLY=true`; no upload, Terraform apply or AWS evidence mutation. Existing live smoke skeleton remains deployed. USER DECISION.

### 2026-10-05 — Investigation deployment
- **Deploy and test on AWS:** USER AUTHORIZATION after the local tests passed. Uploaded the exact local ZIP under a SHA-256-derived `agent-code/` key, changed the gitignored `agent_code_key`, reviewed and applied a saved Terraform plan. VERIFIED: AgentCore DEFAULT is READY on version 3.
- **Matching event/run pointer:** test-event script accepts the evidence loader's run UUID. Fresh synthetic bundles are loaded into the existing project-tagged DynamoDB table; no new resources, knowledge changes, scenarios or oracle uploads.
- **Long-running invocation timeout:** SDK read timeout 870 seconds, total_max_attempts=1. VERIFIED regression test; deployed through a separate Lambda-only Terraform plan. The initial 60-second setting repeated agent requests and SNS publishes on the same trace. This fixes SDK retries, not general upstream event idempotency.

### 2026-10-05 — Network alarm simulation
- **Operator-side replay, existing AWS pipeline:** raw multi-vendor alarm generation and normalization run in one local command. Evidence is loaded before an alarm-derived incident.ready event is published. No new Lambda, rule, service, topology store or AWS resource. This preserves SKILL's boundary: normalization belongs outside the agent.
- **Scope is transport:** dictionary 0.2 LINK_DOWN/UP and aliases are verified against current ROUTING, SOP-03 and REF-TX.1–2. Other dictionary families and KPI-derived routing are not implemented by this adapter. The dictionary's older applies_to metadata is unchanged; only these matching transport rules are used.
- **Synthetic telemetry:** reuse the independently curated, verified transport measurements and shift their event clock to the replay window. Raw alarms alone cannot establish per-cell outcomes/customer impact; those are explicit synthetic support feeds, not conclusions baked into a model prompt.
- **Safety and provenance:** fresh run UUID, raw capture before normalization, conflicting/unknown alarms fail before AWS writes, simulated ingest headers for accelerated replay, account/project checks before publishing. Raw records and dictionary remain outside agent packaging and knowledge sync.

### 2026-10-05 — SNS email report content
- **Inline investigation JSON:** overrides the earlier pointer-only SNS convention (including CLAUDE rule 8's notification format). Include the complete report findings with incident/run metadata, status and validation errors in plain-text email; preserve the S3 pointer. Tool traces and correction-attempt diagnostics stay in S3.
- **Message-size guard:** retain compatibility with the topic's default 256 KiB payload size; try formatted then compact JSON. If still too large, explicitly state omission and point to the complete S3 report. No topic configuration or email subscription change. Unit tests verify exact report preservation and byte-size fallback.

