# sop-rca infra — initial PoC components

Terraform for sections A and B of the component list. Everything is tagged `project=sop-rca`.
Run everything from **Git Bash** at the `sop-rca/` folder. Region: **eu-north-1** (verified reachable;
model access confirmed for `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`).

## What gets created

| # | Component | File | When |
|---|---|---|---|
| A2 | AWS Budgets (2 × monthly, actual + forecast) and Cost Anomaly Detection | `budgets.tf` | Step 2, first |
| B5 | S3 skill-bundle bucket `sop-rca-knowledge-<acct>-<region>` | `s3.tf` | Step 3 |
| B6 | S3 data bucket `sop-rca-data-<acct>-<region>` (`raw/`, `evidence/`, `reports/`, `agent-code/`) | `s3.tf` | Step 3 |
| — | DynamoDB evidence table `sop-rca-evidence` (on-demand) | `dynamodb.tf` | Step 3 |
| B10 | SNS topic (+ optional email subscription) | `sns.tf` | Step 3 |
| B11 | IAM agent role (least privilege) | `iam.tf` | Step 3 |
| B7 | EventBridge bus `sop-rca-incidents` + rule `incident.ready` | `eventbridge.tf` | Step 3 |
| B8 | ECR repo `sop-rca-triage-agent` (fallback path only) | `ecr.tf` | Step 3 |
| B9 | AgentCore Runtime `sop_rca_triage` | `agentcore.tf` | Step 5 |
| B12 | CloudWatch log groups, 7-day retention | `agentcore.tf`, `eventbridge.tf` | Step 5 |
| B13 | Lambda shim + EventBridge target | `eventbridge.tf` | Step 5 |
| O1 | CloudWatch Transaction Search: log resource policy for X-Ray, X-Ray trace segment destination = CloudWatchLogs, X-Ray indexing rule `Default` (100 %). **Account-wide and region-wide, not scoped to `project=sop-rca`.** Approved by the owner 2026-10-05; set `enable_observability = false` to skip | `observability.tf` | Step 5 |
| O2 | Lambda active tracing + X-Ray write permissions on the shim role; `logs:PutResourcePolicy` (this runtime's log groups only) on the agent role | `eventbridge.tf`, `iam.tf` | Step 5 |

**Not created (deliberately):** Bedrock Knowledge Bases, OpenSearch Serverless, MSK, VPC/NAT.

## Deploy mode: code (default) vs container

`deploy_mode = "code"` uses AgentCore's **direct code deployment**: a Python zip in S3, no
Docker. This was chosen specifically to avoid the Windows/Docker ARM64 build step.
`deploy_mode = "container"` (the ECR path from the original plan) is kept as a fallback —
flip the variable and `apply` again if zip packaging keeps failing; nothing else changes.

## Not in Terraform (A1, manual, once)

- Root user MFA on, root access keys deleted.
- IAM Identity Center user (or IAM user) with **only** the permissions needed for this PoC, then `aws configure sso --profile poc` (or `aws configure --profile poc`).

## Run order

```bash
# 0. Preflight (read-only). Confirms identity, region, model access.
AWS_PROFILE=poc AWS_REGION=eu-north-1 bash scripts/preflight.sh
MODEL_ID=eu.anthropic.claude-sonnet-4-5-20250929-v1:0 bash scripts/preflight.sh   # one test call

# 1. Configure
cp infra/terraform.tfvars.example infra/terraform.tfvars   # fill in / confirm values
terraform -chdir=infra init -upgrade

# 2. Cost guardrails FIRST
terraform -chdir=infra apply \
  -target=aws_budgets_budget.monthly \
  -target='aws_ce_anomaly_monitor.services' \
  -target='aws_ce_anomaly_subscription.daily'

# 3. Everything except the runtime (deploy_agent_runtime = false)
terraform -chdir=infra plan -out=tfplan && terraform -chdir=infra apply tfplan
#    -> if report_email is set, confirm the SNS subscription email

# 4. Knowledge + agent artifact
bash scripts/sync_knowledge.sh ./knowledge          # when knowledge/ exists
bash scripts/build_agent_zip.sh ./agent             # deploy_mode = "code" (default)
#   -- or, if you switch deploy_mode to "container" --
# bash scripts/build_push_agent.sh v0

# 5. Runtime + shim: set deploy_agent_runtime = true in terraform.tfvars
terraform -chdir=infra plan -out=tfplan && terraform -chdir=infra apply tfplan

# 6. Smoke test
bash scripts/load_test_incident.sh INC-SMOKE-0001
bash scripts/send_test_event.sh INC-SMOKE-0001
aws logs tail /aws/lambda/sop-rca-invoke-agent --follow

# 7. Tear down
terraform -chdir=infra destroy
bash scripts/verify_destroy.sh
```

## Observability (traces and service map)

### Investigation agent smoke test

For the raw network-alarm demo, run from PowerShell:

```powershell
.\scripts\simulate_network_alarm.ps1 -Aws
```

This generates multi-vendor LINK-1 down/clear notifications, normalizes them using
the transport dictionary rules, supplies synthetic supporting telemetry, loads
evidence, then sends the matching `incident.ready` event. See `simulator/README.md`
for scope and raw/evidence/audit output paths. It uses existing resources only.

The investigation agent expects normalized, run-scoped evidence, rather than the
old `INC-SMOKE-0001` fixture. With the working default profile selected:

```bash
export AWS_PROFILE=default AWS_REGION=eu-north-1
uv run python -m evidence.demo --output runs/aws-demo-incident.json
uv run python -m evidence.load runs/aws-demo-incident.json --storage dynamodb --table sop-rca-evidence
# Use the incident_id and run_id printed by the successful loader:
bash scripts/send_test_event.sh <incident_id> <run_id>
```

The evidence loader creates data in the existing table; it does not create a
resource or publish an event. Never send a different run UUID: the agent reads
only the loaded run. The resulting report is at
`reports/<incident_id>/<run_id>.json`. A passing investigation has `status=validated`,
no validation errors, cited SOP steps and an audited tool trace. Data is synthetic
and conclusions remain provisional. The report format no longer uses the old
smoke-only `skill_loaded` flag; real knowledge access is visible in section-read
audits and S3 spans.

SNS email now includes the formatted investigation JSON (findings, SOP citations,
impact, escalation and proposals) with incident metadata and the S3 pointer, per
the owner's request. Internal tool traces remain in S3. If the report itself
exceeds the conservative 256 KiB message cap even when compacted, the email
explicitly says it was omitted and retains the S3 location. Runtime logs record
the SNS message ID, byte count and `report_json_included` flag.

For direct code updates, upload to a new `agent-code/` key and set `agent_code_key`
to that exact key before planning. This bucket has versioning off; overwriting
the same key alone does not give Terraform a change to deploy.

The shim's SDK read timeout is 870 seconds within its 900-second Lambda timeout.
SDK automatic retries are disabled for invocation: a 60-second timeout can repeat
a successful, longer investigation and publish duplicate emails. This does not
provide general event idempotency; upstream duplicate events can still rerun it.

Sources: AgentCore docs "Add observability to your Amazon Bedrock AgentCore resources" and "Direct code deployment for Python".
- `aws_bedrockagentcore_agent_runtime` has **no** observability block (checked in the provider schema). The agent is instrumented
  by (a) `aws-opentelemetry-distro>=0.18.0` in `agent/requirements.txt` and (b) the entry point
  `["opentelemetry-instrument", "main.py"]` (`agent_code_entry_point`). AgentCore injects its own ADOT environment variables for
  agents it hosts, so we set no `OTEL_*` variables. **Rebuild and upload the zip before applying an entry-point change.**
- Transaction Search (`observability.tf`) is a one-time account/region setting. Verify: `aws xray get-trace-segment-destination`
  should report `CloudWatchLogs`, status `ACTIVE`.
- Where to look: CloudWatch console, **GenAI Observability** (Bedrock AgentCore tab), and **Application Signals > Transaction search**.

## Known risks to check on the first run

- `terraform validate` has **not** been run yet (no network access to install Terraform in
  the sandbox that wrote these files). Run `terraform -chdir=infra validate` on your laptop
  before planning.
- [Unverified] AgentCore runtime log group name `<runtime_id>-DEFAULT`. If apply reports it
  already exists, import it (command in `agentcore.tf`).
- Cost Anomaly Detection allows 1 SERVICE monitor per account. If apply fails on it, set
  `create_anomaly_monitor = false`.
- [Unverified] Whether the inference-profile and foundation-model ARNs in `iam.tf` are
  enough for an `eu.*` profile in eu-north-1. If the agent gets AccessDenied from Bedrock,
  check CloudTrail for the exact ARN it was denied on.
- `deploy_mode = "code"`: the zip's dependencies must be built for `aarch64-manylinux2014`
  (AgentCore Runtime is ARM64-only). `scripts/build_agent_zip.sh` handles this with uv's
  `--python-platform` flag — see that script's comments for why plain Windows `pip` fails.
- Keep this repo **outside OneDrive** (or exclude `infra/.terraform/` and `infra/*.tfstate*`
  from sync). A cloud-synced state file can get locked or silently duplicated mid-apply.
