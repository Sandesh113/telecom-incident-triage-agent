# PROGRESS

## 2026-10-05 — Initial PoC components (README run order steps 0-4)
- Preflight (profile `default`, eu-north-1): identity OK, Bedrock + AgentCore reachable, model call OK
  (first call returned a transient AccessDeniedException; two retries returned "OK";
  `get-foundation-model-availability` = AUTHORIZED).
- `terraform init -upgrade` + `validate`: OK (one deprecation warning: DynamoDB `hash_key`).
- Budgets applied first (targeted): 4 added (2 budgets $13/$26, anomaly monitor + subscription).
- Full plan: 20 to add / 0 change / 0 destroy -> applied. State = 24 resources; re-plan shows no changes.
- Agent package: `agent_skeleton/app.py` -> `agent/main.py` (+ requirements.txt). Built with
  `scripts/build_agent_zip.sh` (29.7 MB, 4245 entries, main.py at root, no backslashes, no pywin32,
  6 aarch64 .so) and uploaded to s3://sop-rca-data-270293010572-eu-north-1/agent-code/main.zip.
- `knowledge/` does not exist yet, so nothing synced; the skeleton tolerates a missing SKILL.md.

## Next
- Set `deploy_agent_runtime = true`, plan, show summary, apply; then smoke test.
- Confirm the SNS subscription email at oslonorway257@gmail.com.

## 2026-10-05 — Runtime + shim + smoke test
- `deploy_agent_runtime = true`; plan 9 add / 0 change / 0 destroy. Apply created everything except the
  runtime log group (AgentCore had already created `/aws/bedrock-agentcore/runtimes/sop_rca_triage-SJz3UmH0wM-DEFAULT`).
  Imported it per agentcore.tf, re-plan 0/1/0 (retention 0 -> 7 days), applied.
- Smoke test INC-SMOKE-0001 (run_id db32d97b-da1c-4a5b-9c4a-82207f145255):
  - EventBridge -> Lambda shim -> AgentCore runtime: shim logged `Agent finished: status=200`, duration 5.4 s.
  - Report written: s3://sop-rca-data-270293010572-eu-north-1/reports/INC-SMOKE-0001/db32d97b-....json
    (model reply present, `skill_loaded: false` as expected — knowledge/ not synced yet).
  - Evidence item INCIDENT#INC-SMOKE-0001/META present in sop-rca-evidence.
  - SNS email subscription for oslonorway257@gmail.com has a full SubscriptionArn (confirmed).
    Actual email receipt NOT verified from this side — check the inbox.
## Next
- Real agent (Phase 5), knowledge/ + sync_knowledge.sh, git init + `phase-N` commits (no repo yet).
- Tear down with `terraform destroy` + `scripts/verify_destroy.sh` when done to stop costs.

## 2026-10-05 — Knowledge pack (Phase 0 catalog requirement)
- Built `knowledge/` per BUILD SPEC v3 §3: SKILL.md, shared-rules.md, sops/SOP-01..05.md, reference/*.md (4), tools/build_catalog.py.
- `python knowledge/tools/build_catalog.py` -> exit 0; 10 documents, 79 sections, 89 IDs, all unique, all references resolve.
  Rebuilt catalog.json is identical to the one in files1.zip (after the path fix in DECISIONS.md).
- Independent check: all 14 IDs referenced in SKILL.md (REF-CORR.6, REF-RAN.2, REF-TX.1, ROUTING, RULES.1-9, SOP-03.1) exist in catalog.json.
- `scripts/sync_knowledge.sh ./knowledge`: 12 objects uploaded, only allowed paths (no scenarios/dictionary/oracle); script's forbidden-content check = OK.
- Smoke test re-run (run_id 7771f761-796c-4619-a460-2e01c026f8f4): `skill_loaded: true`, `skill_chars: 6982`, shim status 200.
- SOP Markdown vs `Telecom_Incident_Triage_SOPs_v0.5_clean.docx`: content matches (redline-accepted == clean over §1-§7;
  no number/threshold missing; differences are only added IDs/summaries and Word-only front matter, §8, §9). No regeneration needed.

## 2026-10-05 — Phase 1 (store + run manifest; topology removed): IN PROGRESS
Topology is now **static reference-file content only** (user decision, matching the AWS blog's pattern); it is not a queryable store,
so the Phase 1 acceptance criterion "topology topo-1 queryable at_time" no longer applies. See DECISIONS.md.
- Environment: `uv sync` (run by the human with `!`; the same call from my shell was denied by the auto-mode classifier, "Sensitive-Source
  Provenance"). 29 packages, CPython 3.13.16. The copy of scenario_inputs/oracle/dictionary into `knowledge/` was NOT done.
- First test run (before topology removal): 94 passed, 1 skipped, 1 failed. The failure was a real bug: DynamoDB `begins_with(sk, "")` is
  invalid (empty key value) in `delete_run`; fixed in `store/dynamodb_store.py`. Not re-run before the topology removal.
- Code now: `pyproject.toml`; `store/` (`base.py` 9 collections, `sqlite_store.py`, `dynamodb_store.py`, `readonly.py`);
  `harness/` (`scenario_inputs.py` load/inherits/phases, `manifest.py` private `runs/manifests/<uuid>.json`, `new_run.py`);
  `tests/` (`test_store_contract.py` both backends, `test_manifest.py`).
- Removed on request: `store/topology.py`, `tests/test_topology.py`. Also removed (dependents): `store/cli.py`, topology loading in the harness.
- Knowledge edits by the user (5 files: reference/correlation-patterns.md, sops/SOP-01, 02, 03, 05; 8 lines changed), then:
  - `python knowledge/tools/build_catalog.py` -> exit 0; 10 documents, 79 sections (unchanged: the edits touched body text, not headings/summaries).
    REF-CORE.5, REF-CORE.6, REF-TX.1, REF-RAN.4 all resolve; every unbracketed REF-* reference in the 5 edited files resolves.
  - `scripts/sync_knowledge.sh ./knowledge`: the 5 edited files uploaded; bucket = 12 objects, allowed paths only (OK).
  - `uv run pytest -q` after topology removal: **41 passed** (store contract on SQLite + DynamoDB/moto, manifest). Includes the delete_run fix.
  - SOP Markdown vs `Telecom_Incident_Triage_SOPs_v0.5_clean.docx`: the Word file still says "topology" in exactly 5 paragraphs that
    the Markdown now words differently (listed in ISSUES.md #10). The Word source has NOT been changed.
- Not done: no `phase-1` commit yet; no `git add` of store/, harness/, tests/, pyproject.toml, uv.lock, the 5 knowledge edits.

## 2026-10-05 — Phase 1 close-out checks (reference tables, Word update)
- User added static tables: ran-rf.md (RF neighbours/carrier/PCI, inside REF-RAN.4), core-control-plane.md (function dependencies, inside **REF-CORE.1**),
  and edited SKILL.md (8 tools, no `get_topology`, step 8 cites REF IDs). Verified the tables match the scenario inputs' cells/neighbours/carriers/PCIs and core relations.
- Word (clean docx) updated: 5 SOP paragraphs + §8; 8 paragraphs changed, valid docx, other parts byte-identical (ISSUES.md #14). Redline docx not edited.
- Spec deviation recorded (validators 4 and 6 relaxed; 8 tools): ISSUES.md #15.
- `build_catalog.py` exit 0 (10 docs, 79 sections); 17 IDs referenced by SKILL.md all resolve; no `get_topology` left in knowledge/*.md.
- `sync_knowledge.sh`: SKILL.md, catalog.json, shared-rules.md, core-control-plane.md, ran-rf.md uploaded; bucket = 12 objects, allowed paths only (OK).
- `uv run pytest -q`: **41 passed**.
- Not re-run: the AgentCore smoke test (SKILL.md changed since the last run).
- **Open before tagging phase-1:** ISSUES.md #16 (function-dependency table is in REF-CORE.1 but every citation points to REF-CORE.5-6) and #17 (facts missing from the tables, incl. S4's CELL-B carrier).

## 2026-10-05 — Phase 1 closed
- Owner moved the function-dependency table to [REF-CORE.6] and added a service-map table ([REF-CORE.6]) and a measurement-configuration table ([REF-RAN.4]).
- Verified by simulation of spec §6 `read_section`: REF-CORE.6 (34 lines) returns the dependency + service-map tables; REF-CORE.1 no longer has the table.
- `build_catalog.py` exit 0 (10 docs, 79 sections), 17 SKILL.md IDs resolve; `sync_knowledge.sh` uploaded 5 files, bucket = 12 objects, allowed paths only; `uv run pytest -q` = 41 passed.
- Phase 1 delivered: evidence-store interface (SQLite + DynamoDB/moto, read-only wrapper), private run manifest, no topology service (static reference tables), spec deviation logged (ISSUES.md #15).
- Open and deliberately untouched: ISSUES.md #17 (incl. S4 CELL-B carrier), redline docx not updated (#14), AgentCore smoke test not re-run since SKILL.md changed.

## 2026-10-05 — Observability (traces) live
- Researched first (AgentCore observability docs, installed provider schema): `aws_bedrockagentcore_agent_runtime` has no observability block; `AGENT_OBSERVABILITY_ENABLED`/`OTEL_*`
  are for agents hosted OUTSIDE AgentCore (the runtime injects its own ADOT defaults); the agent needs `aws-opentelemetry-distro>=0.18.0` + entry point `["opentelemetry-instrument","main.py"]`.
  Transaction Search was OFF (destination XRay, no X-Ray log policy). Owner approved the three account-wide resources, indexing 100 %.
- Build-script fix: uv on Windows wrote `bin/*.exe` launchers (unusable on Linux ARM64); `scripts/build_agent_zip.sh` now writes Linux wrapper scripts from entry_points.txt (LF, mode 755). Zip: 38.8 MB, no .exe/.dll/.pyd.
- Plan 3 add / 4 change / 0 destroy -> applied (the owner's go-ahead was an echo of my own question; see ISSUES.md #19). Runtime now version 2, entry point `opentelemetry-instrument main.py`, Lambda tracing Active.
  Verified: `get-trace-segment-destination` = CloudWatchLogs / ACTIVE; indexing rule Default = 100 %; log policy `sop-rca-transaction-search` exists; `aws/spans` exists; re-plan = no changes.
- Smoke test run_id 5b236db0-255a-47b1-b5b1-e0d8615cd921: shim status 200, report written, skill_loaded true.
  `aws/spans` holds 17 spans under ONE trace id (Lambda trace 1-6ac2f6e3-4fcec19b201d79a20d575521): Lambda (sop-rca-invoke-agent, Init, Dwell Time, Overhead) +
  agent runtime (POST /invocations, invoke_agent Strands Agents, execute_event_loop_cycle, chat eu.anthropic.claude-sonnet-4-5..., S3.GetObject, S3.PutObject, SNS publish).
  EventBridge is NOT a span in the trace (the test event carries no trace header). Console UI paths not yet seen by me: [Unverified].

## 2026-10-05 — Local evidence and investigation candidate (not deployed)
- Implemented normalized incident/evidence contract and ready-last loader in `evidence/`; curated synthetic LINK-1 incident with six transitions, before/after KPIs for CELL-A/B and controls CELL-E/F, 120 distinct impact records and complete-empty changes. No scenario/oracle/dictionary input.
- Implemented approved knowledge readers, eight scoped tools, typed report, deterministic checks, bounded correction, local Bedrock runner and AgentCore S3/SNS adapter. Agent evidence access is read-only; actions are never executed.
- `uv sync` completed. Final `uv run pytest -q`: **77 passed, 1 dependency deprecation warning, 34.71 seconds**. Includes both storage backends, worker-thread reads, scope restrictions, missing evidence, bounded completeness, complete-empty query auditing, repair/needs-human handling and publication with fake clients.
- First real inference exposed SQLite thread affinity under Strands worker threads. Fixed and regression-tested. A subsequent real Bedrock run validated a cited transport hypothesis with 120 customers and 28 tool calls (117.99 seconds). Later runs exposed an overly strict validator: SOP-03.4 was rejected for having no record IDs even though its complete change query returned known_empty. Fixed by recording query availability in the tool audit and accepting this specific complete-empty result; unavailable results remain rejected. Final rerun tracked below.
- Linux ARM64 local package builds at approximately 38.8 MB, Linux launchers, no upload. Final candidate ZIP: `.build/agent_zip/main.zip`.
- Nothing changed in knowledge, terraform.tfvars or AWS resources. No evidence loaded to live DynamoDB, no EventBridge event sent, no SNS notification. This is not an end-to-end deployment result and does not close all BUILD SPEC phases.
- Final real Bedrock run: `runs/investigation-accepted.json`, status **validated**, **26 tool calls**, **66.81 seconds**, no validation errors. Synthetic run eae5755b-459d-41e1-8531-81ec82211e87, incident INC-fc0a489d9d37. The report/trace remain local in ignored runs/. All four numbered SOP-03 steps present; no failed tool calls. Package candidate has not been tested on Linux/AgentCore; local package inspection is not a deployed smoke test.

## 2026-10-05 — Investigation agent deployed and AWS smoke test passed
- Owner authorized deployment and AWS testing. Preflight passed on default profile, account 270293010572, eu-north-1; approved model test returned OK.
- Uploaded the exact 38,793,934-byte ZIP to `agent-code/investigation-0a8b0debb56e07a9.zip` (SHA-256 0a8b0debb56e07a9682923b04a80ee6abc5e4a141fd0bba5ae2460a5ea11e181). Bucket versioning is off; unique key drives the Terraform update and preserves the old main.zip.
- Plan **0 add / 2 change / 0 destroy**, shown before saved-plan apply, no auto-approve. Apply **0 add / 1 change / 0 destroy**: runtime version 3; shim IAM policy resolved unchanged. DEFAULT endpoint READY.
- First AWS run INC-821a709cede5 / 073e253d-9011-49f2-9a5b-a90f53fdd67d validated, but trace showed repeated invocations/SNS publishes. Root cause: SDK's 60-second default read timeout versus a longer investigation. Fixed shim to read_timeout=870 and total_max_attempts=1, closing the response stream. Regression test passed; separate plan **0 add / 1 change / 0 destroy**, shown then applied, Lambda only.
- Final test: incident **INC-d043826e643a**, run **14f64930-feb0-4c32-a316-95ca9b5fa691**. Fresh normalized synthetic bundle loaded into the existing tagged table; EventBridge event cc870ca8-19f5-51b1-07c6-cc46f20785b8 accepted with FailedEntryCount=0. Script now accepts the loaded run UUID.
- Lambda request 70f39d08-8c3c-4747-a809-88ba6728e0e6 logged `Agent finished: status=200`. Report **validated**, **27 tool calls**, **69.17 seconds**, **0 tool errors**, **0 validation errors**. LINK-1 transport hypothesis, CELL-A/B attribution, all SOP-03 steps, 120 customers/significant impact, escalation required; provisional synthetic data.
- Report: `s3://sop-rca-data-270293010572-eu-north-1/reports/INC-d043826e643a/14f64930-feb0-4c32-a316-95ca9b5fa691.json`. Local copy `runs/aws-smoke-fixed-report.json`; Lambda log and sanitized span diagnostics alongside it. Not synced to knowledge.
- Trace **1-6ac3b36e-33a567407ea618ad5c98ad9b**: one POST /invocations (HTTP 200), S3 knowledge reads, DynamoDB Query, Bedrock chat, section/evidence tools, one S3.PutObject and one SNS Publish (HTTP 200). SNS subscription confirmed for the configured email. Actual inbox receipt is not CLI-verifiable.
- Final Terraform plan: **no changes**, exit 0. No new resources or knowledge edits. Real network-alarm ingestion, multi-scenario evaluation, previous-report retrieval and general event idempotency remain outside this increment.

## 2026-10-05 — Raw network-alarm replay verified on AWS
- Read current SKILL, ROUTING, SOP trigger definitions, SOP-03 and transport references, plus Ready dictionary 0.2. Implemented `simulator/transport.py`: vendor A/B raw LINK-1 alarm feed, transport normalization, aliases, notification dedup, clear-to-UP mapping, explicit UP dedup, late flags and provenance. Restricted to LINK-1 aggregate transport alarms; not the full dictionary/enrichment phase.
- Reused independently curated synthetic supporting telemetry (not expected diagnoses): affected CELL-A/B, measured controls CELL-E/F, initial link state, before/after KPIs, 120 customers, complete-empty changes. Shifted event-time windows and simulated ingest headers for accelerated replay; no scenario/oracle inputs.
- Local mode loads SQLite without AWS calls. AWS mode checks account and project tags, loads the existing DynamoDB table, then publishes the matching ready event to the existing bus. No Terraform changes, new resources, knowledge changes or agent redeploy.
- `uv run pytest -q`: **88 passed**, one existing SDK deprecation warning, **75.91 seconds**. New simulator tests cover both vendor formats, lifecycle preservation, clear mapping, duplicate IDs, conflicting payloads, explicit-UP duplicates, UTC conversion, late flags and unsupported inputs. CLI local replay and PowerShell shortcut also exercised successfully.
- AWS replay: **INC-cce391fa5f4b**, run **7ebf295f-a5ea-443b-b43f-577a9d45c8ff**. Six raw notifications -> six normalized LINK_DOWN/UP events -> matching incident.ready. EventBridge accepted with zero failed entries.
- Report **validated**, **26 tool calls**, **0 validation errors**, **71.70 seconds**; transport_link_flap, all four SOP-03 steps, 120 customers. Lambda completed HTTP 200. Trace **1-6ac3b691-753a96b059a4925f4e8b68e6** has one successful invocation and one SNS Publish (HTTP 200).
- Raw input, bundle, audit, event receipt, report, Lambda log and sanitized trace saved under `runs/alarm-replay-aws-check/` (ignored; not knowledge). S3 report at `reports/INC-cce391fa5f4b/7ebf295f-a5ea-443b-b43f-577a9d45c8ff.json` in the existing data bucket.
- Re-run from PowerShell: `.\scripts\simulate_network_alarm.ps1 -Aws`. The wrapper finds the existing WinGet uv if it is absent from PATH. The transport alarm-to-report demo now works; actual NMS integration, other SOP-family generators and the full build-spec scenario/evaluator definition of done remain pending.

## 2026-10-05 — Investigation JSON in SNS email
- Owner requested JSON in the email body, superseding the pointer-only convention. Added formatted incident/status/validation metadata and complete `report` findings to SNS; internal tool traces/attempts remain in S3. Conservative byte-size guard tries compact JSON then explicit pointer-only fallback for oversized findings.
- Targeted publication/oversize tests: **4 passed** (both storage fixtures), one existing dependency warning. Preview verified that email report findings equal the saved report exactly.
- Built and uploaded `agent-code/email-json-5f9158d32aacc896.zip`. Plan **0 add / 2 change / 0 destroy**, shown before saved-plan apply; apply **0 add / 1 change / 0 destroy** (runtime only, shim policy unchanged). AgentCore DEFAULT READY on version **4**. Final Terraform plan: no changes, exit 0. No subscription/IAM permission expansion or knowledge changes.
- Fresh raw-alarm test: incident **INC-0a680a0ebef6**, run **830f4279-3ed2-486c-b13b-49f5fb7ec7f2**. Report **validated**, no validation errors, **69.02 seconds**. SNS receipt **5445a444-ea4c-5715-ac3f-c779518934a4**, runtime log **report_json_included=True message_bytes=9526**. The identical receipt appears in both plain and OTEL log representations; these are duplicate log representations, not two publishes.
- Saved report, reconstructed exact email body and SNS receipt log under `runs/email-json-aws-check/`. API acceptance verified; actual inbox rendering remains for the recipient to confirm. Older notifications remain unchanged.
