# Telecom Incident Triage Agent: AWS AgentCore PoC

A proof-of-concept AI agent that triages telecom network incidents, correlates alarms, walks through SOPs, and drafts a root-cause report for an engineer, built end-to-end on AWS Bedrock AgentCore.

> 🎬 **Live demo:** [Incident Triage Walkthrough](https://claude.ai/artifact/1ZW6cGpLxXsGpYrGd9Sn9V) An animated, narrated walk-through of the pipeline, built to explain the architecture without needing AWS console access.

---

## 🎯 Why this exists

Telecom NOC teams drown in correlated alarms during an incident, a single root cause (a flapping backhaul link, a failed policy function, an RF configuration change) can fan out into dozens of symptom alarms across cells, services, and customers. This PoC shows an AI agent that:

- Reads enriched incident events, not raw unstructured logs.
- Routes to the right Standard Operating Procedure (SOP) based on alarm triggers.
- Investigates each hypothesis against **cited, versioned domain knowledge**, not a black box.
- Produces a structured, auditable report: hypotheses, evidence, attribution, and impact tier, never a free-text guess, and never a network-changing action on its own.

It is deliberately scoped as a **PoC for a specific architectural pattern**, not a production system, see [Scope and limitations](#scope-and-limitations).

---

## 🏗️ Architecture

```
📡 EventBridge  →  ⚡ Lambda (shim)  →  🤖 Bedrock AgentCore Runtime  →  🧠 Bedrock (Claude)
                                          │
                                          ├─ reads:  📚 S3 knowledge bucket (SKILL.md, SOPs, reference files)
                                          ├─ reads:  🗃️ DynamoDB evidence table (incident events, KPIs, changes)
                                          └─ writes: 📄 S3 reports bucket  →  📧 SNS (report-ready notification)
```

| Stage | AWS service | Role |
|---|---|---|
| Trigger | **EventBridge** | Delivers an enriched incident event to the pipeline |
| Shim | **Lambda** | Thin invoker passes the event to the AgentCore runtime |
| Reasoning | **Bedrock AgentCore Runtime** | Hosts the agent (code deployment, no containers) |
| Model | **Bedrock Model used: Claude Sonnet 4.5** | Executes the SKILL.md procedure against the knowledge base |
| Knowledge | **S3 (knowledge bucket)** | SKILL.md + SOPs + reference files read-only to the agent |
| Evidence | **DynamoDB** | Incident events, KPIs, changes read-only to the agent |
| Output | **S3 (reports bucket) + SNS** | Draft report persisted; JSON report and S3 pointer sent to the engineer |

The verified demo starts with raw synthetic vendor A/B LINK-1 notifications.
The local simulator normalises them, loads matching evidence and publishes
`incident.ready`. SNS email includes the formatted investigation JSON and S3 link.
Only the transport/SOP-03 case has been verified end to end; the other SOPs are
available as knowledge, but their complete input generators/evaluations remain pending.

```powershell
uv sync
uv run pytest -q
.\scripts\simulate_network_alarm.ps1       # local replay
.\scripts\simulate_network_alarm.ps1 -Aws  # existing AWS resources and valid login required
```

This mirrors the AWS blog's three-layer knowledge design exactly:

1. **Reasoning layer** `SKILL.md`, resident in the agent's context. The fixed investigation procedure.
2. **Reference layer** domain markdown files (`core-control-plane.md`, `correlation-patterns.md`, `transport.md`, `ran-rf.md`) and SOPs, read on demand via `list_sections` / `read_section`.
3. **Retrieval layer** reserved for a future vector-backed knowledge base for long-tail knowledge; not implemented in this PoC.

**Knowledge retrieval is vectorless by design.** The agent navigates a `catalog.json` section index instead of RAG — every fact it cites traces back to a specific, versioned section ID (e.g. `REF-CORE.6`, `SOP-01.4`), which is what makes the output auditable.

---

## 🤖 What the agent actually does

Given an incident's enriched events, the agent:

1. Reads the incident's events and flags (late events, routing hints, enrichment caveats).
2. Selects candidate SOPs from routing triggers, never from its own judgment of alarm text.
3. Builds one or more hypotheses, each with a cause object and a named failure mechanism (e.g. `pcf_service_fault`, `transport_link_flap`, `rf_pci_collision`).
4. Runs each SOP's read-only evidence checks, recording `supports` / `weakens` / `inconclusive` / `unable_to_check` per hypothesis — never skipping a check silently.
5. Tests each hypothesis against the relevant reference-file relationship (function dependencies, backhaul mappings, RF neighbour tables) and executed change records — timing alone never proves causality.
6. Assigns every affected object an attribution state: `single`, `multiple`, `unresolved`, or `unexplained`.
7. Calculates an impact tier from distinct/enterprise customer counts.
8. Emits a structured JSON report with hypotheses, cited evidence, attribution, impact, and any proposed actions (always flagged `read_only` or `change`, with `requires_approval` set accordingly). The agent **never executes a network change** it only drafts a recommendation.

Five SOPs are covered in the current knowledge base: PCF/policy failures, HSS/UDM subscriber-data failures, backhaul link flaps, RF handover degradation, and multi-cause/customer-impact triage.

---

## 📁 Repository layout

```
sop-rca/
├── infra/              # Terraform the only way resources are created
│   ├── lambda_shim/     # EventBridge → AgentCore invoker
│   └── README.md        # Approved resource list, run order
├── agent/               # Agent source (main.py) deployed to AgentCore
├── knowledge/
│   ├── SKILL.md          # Resident reasoning procedure
│   ├── sops/              # SOP-01 .. SOP-05
│   ├── reference/          # Domain reference files (core, transport, RAN, correlation)
│   └── catalog.json        # Vectorless section index
├── scripts/             # build_agent_zip.sh, sync_knowledge.sh, send_test_event.sh, …
├── simulator/           # Raw alarm replay + operator-only dictionary
├── evidence/            # Normalised incident contract and loader
├── demo-evidence/       # Private captured evidence, gitignored
├── PROGRESS.md / DECISIONS.md / ISSUES.md
└── tests/               # Store, investigation, alarm replay and shim checks
```

---

## 🚀 Deployment model

- **Infrastructure:** Terraform only; every resource tagged `project=sop-rca`, plan reviewed before every apply, nothing created via CLI or console.
- **Agent deployment:** direct AgentCore *code* deployment: a Python zip shipped to S3, no Docker, no ECR in the default path (container deployment is kept only as a documented fallback).
- **Knowledge sync:** `scripts/sync_knowledge.sh` pushes only `SKILL.md`, `catalog.json`, `shared-rules.md`, `sops/`, and `reference/` to S3; the IAM role the agent runs under cannot read anything else.
- **Data separation:** scenario inputs, the evaluation oracle, and the alarm dictionary are enrichment-only and are never uploaded to S3 or made agent-readable; the agent is evaluated, not given the answer key.
- **Cost controls:** AWS Budgets and Cost Anomaly Detection are provisioned *before* any compute resource, with on-demand/serverless billing throughout (DynamoDB on-demand, no provisioned throughput, no NAT gateways or GPU endpoints).

## ✅ Verified on a live AWS deployment

This isn't a design doc; it's been run end-to-end on a real AWS account (`eu-north-1`):

- A synthetic incident event was sent through EventBridge and traced through Lambda → AgentCore → Bedrock → SNS/S3 on AWS X-Ray's service map.
- The agent produced a validated structured triage report, written to S3, with report JSON included in the SNS email.
- Supporting evidence (CloudWatch logs, the DynamoDB evidence item, the S3 report, the X-Ray trace) is captured under `demo-evidence/`.

---

## Scope and limitations 🔎

This is a proof of concept built to demonstrate one specific architectural pattern end-to-end, not a production NOC tool:

- Knowledge is static reference-file tables (topology, function dependencies, RF neighbour relations) rather than a live, queryable topology service — intentional, matching the blog's reference-layer pattern rather than adding a bespoke graph service.
- Evidence (events, KPIs, changes) comes from a fixed synthetic dataset for a demo network ("Albion Mobile"), not a live OSS/BSS feed.
- The agent only *drafts* a report and proposed actions; it cannot execute a network change, and every proposed action is explicitly typed `read_only` or `change` with an approval flag.
- Retrieval is vectorless; a long-tail knowledge base (the blog's third layer) is designed for but not implemented here.

---
