This guide describes the verified direct ZIP deployment and transport alarm demo. Run commands from the repository root in Git Bash, WSL, macOS or Linux unless marked PowerShell. It does not deploy anything automatically.

The alarm simulator currently restricts AWS writes to the original approved PoC account and resources tagged `project=sop-rca`. This is not yet a turnkey separate-account deployment guide: before using the simulator in a separate account, intentionally review that guard. Never copy the existing account's Terraform state to another account.

## 1. Prerequisites

Install AWS CLI v2, Terraform 1.6+, Python 3.13, uv and Git. The verified ZIP path does not require Docker. Put uv on PATH before using the Bash packaging script.

Use the working non-root AWS CLI profile; the existing PoC uses `default`. The verified Region is `eu-north-1`, and the configured model is Claude Sonnet 4.5. Changing accounts, regions, or models requires checking availability and access first.

```bash
export AWS_PROFILE=default
export AWS_REGION=eu-north-1
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"
aws sts get-caller-identity
aws configure list
```

The path-conversion settings prevent Git Bash from rewriting CloudWatch log group names. Keep this environment for subsequent commands: shared Bash scripts otherwise default to the `poc` profile.

## 2. Configure local variables

For a new deployment only, copy the example. Do not overwrite the existing deployment's local configuration.

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Edit `infra/terraform.tfvars`: set `aws_profile = "default"` to match the CLI environment, confirm the Region and model IDs, and replace the example email addresses. Use your own addresses for `budget_email` and `report_email`; `report_email` may be empty if you do not want an email subscription. Keep this file local and gitignored.

Start a new deployment with:

```hcl
deploy_agent_runtime = false
deploy_mode          = "code"
enable_observability = false
```

The current GitHub and working-project Terraform defaults enable observability with 100% indexing; older sanitised local copies may default to disabled and 10%. Set these values explicitly for a new deployment. The false value above leaves the account-wide Transaction Search resources unmanaged during initial setup. For the existing approved deployment, retain its reviewed observability configuration; do not toggle it off as part of a routine code update.

## 3. Run preflight

```bash
MODEL_ID=eu.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  bash scripts/preflight.sh
```

Review every printed check, including identity, AgentCore reachability and the actual model reply. The script can print failures without returning a failing exit code, so its exit code alone is not proof of success. Stop if credentials, Region or model access checks fail. Docker and Go are not required for the verified ZIP transport demo.

## 4. Validate locally

```bash
uv sync --locked --dev
uv run pytest -q
uv run python knowledge/tools/build_catalog.py
git diff --exit-code -- knowledge/catalog.json
terraform -chdir=infra init
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
uv run python -m simulator. transport
```

Local replay generates raw alarms, normalised evidence and an ingestion audit under ignored `runs/alarm-replays/`; it does not invoke the model or access AWS. Catalogue rebuilding must exit zero and match the committed index. Resolve formatting or validation failures before planning. If `fmt -check` lists files, run `terraform -chdir=infra fmt`, inspect the formatting diff, and repeat the check. Existing provider/dependency deprecation warnings should be distinguished from failures.

## 5. Create cost guardrails first

For a new deployment, review the targeted plan and its add/change/destroy summary before applying that saved plan:

```bash
terraform -chdir=infra plan -out=tfplan-budgets \
  -target=aws_budgets_budget.monthly \
  -target=aws_ce_anomaly_monitor.services \
  -target=aws_ce_anomaly_subscription.daily
terraform -chdir=infra apply tfplan-budgets
```

This targeted plan is a one-time bootstrap step for this PoC; subsequent stages use full plans. Terraform recommends targeting only for exceptional circumstances ([resource targeting](https://developer.hashicorp.com/terraform/cli/commands/plan)). Do not use `-auto-approve`. If an existing service anomaly monitor prevents creation, review it and set `create_anomaly_monitor = false` when it is managed elsewhere. Do not delete an unrelated monitor.

## 6. Create base infrastructure

Keep `deploy_agent_runtime = false` for the initial base deployment. Review the plan summary before applying:

```bash
terraform -chdir=infra plan -out=tfplan-base
terraform -chdir=infra apply tfplan-base
```

This creates the project's S3 buckets, DynamoDB evidence table, SNS, IAM, EventBridge and ECR fallback resources. Confirm the SNS email subscription through the confirmation email before expecting reports. The ECR repository is not used by the verified ZIP path.

## 7. Upload knowledge and agent code

```bash
bash scripts/sync_knowledge.sh ./knowledge
BUILD_ONLY=true bash scripts/build_agent_zip.sh ./agent
```

The knowledge pack consists of SKILL.md, catalog.json, shared-rules.md and Markdown files in sops/reference. Inspect these directories before syncing: the current script syncs their contents rather than enforcing a strict extension allowlist. Keep dictionaries, scenarios, evaluation oracles and private demo evidence out of them.

Packaging follows [AgentCore direct Python code deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html): it resolves Linux ARM64 dependencies for Python 3.13, restores Linux console-script wrappers and writes POSIX paths and permissions into `.build/agent_zip/main.zip`. It includes the agent, store and evidence contract, not the simulator or alarm dictionary.

Upload the package under a fresh key, then use that exact key in Terraform:

```bash
DATA_BUCKET=$(terraform -chdir=infra output -raw data_bucket)
CODE_KEY="agent-code/investigation-$(date -u +%Y%m%dT%H%M%SZ).zip"
aws s3 cp .build/agent_zip/main.zip "s3://$DATA_BUCKET/$CODE_KEY"
printf 'Set agent_code_key in infra/terraform.tfvars to: %s\n' "$CODE_KEY"
```

Set `agent_code_key` to the printed value. Use a fresh key for subsequent code updates too: overwriting an object at the same key alone does not create a Terraform configuration change.

The historical container script and skeleton Dockerfile remain in the repository. Building the current agent from `./agent` with that script is not supported because that directory has no Dockerfile. Use direct ZIP deployment; the current investigation agent's container path is not verified.

## 8. Create AgentCore and the invocation bridge

Set `deploy_agent_runtime = true` and confirm `agent_code_key` identifies the uploaded package. Review the summary before applying:

```bash
terraform -chdir=infra plan -out=tfplan-runtime
terraform -chdir=infra apply tfplan-runtime
```

Wait for the runtime to become ready before testing. If Terraform reports an existing runtime log group, inspect the exact name and import it into the matching Terraform resource address before replanning. Do not delete the log group to resolve the conflict.

For an existing deployment, retain runtime enablement, build/upload a fresh package, update its key, and review a new plan. Do not repeat the initial runtime-off stage.

## 9. Smoke test

Use the current transport simulator with the already selected AWS profile:

```bash
uv run python -m simulator.transport --aws --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --table "$(terraform -chdir=infra output -raw evidence_table_name)" \
  --bus "$(terraform -chdir=infra output -raw event_bus_name)"
```

For the existing Windows PoC, the PowerShell shortcut is:

```powershell
.\scripts\simulate_network_alarm.ps1 -Aws
```

That wrapper selects the `default` profile. The simulator checks the approved account and project tags, normalises vendor A/B LINK-1 alarms, loads matching synthetic evidence, then publishes `incident.ready` only after loading succeeds. It prints the incident ID, run UUID and local output folder.

```bash
aws logs tail /aws/lambda/sop-rca-invoke-agent --follow
```

Stop following logs with Ctrl+C, then list reports:

```bash
aws s3 ls "s3://$(terraform -chdir=infra output -raw data_bucket)/reports/" --recursive
```

Inspect the report for the exact incident/run printed by the simulator. Success means `status = validated`, no validation errors, cited SOP steps and section reads in the tool audit, a saved S3 report and an SNS email containing the investigation JSON plus its S3 pointer. An oversized inline report explicitly falls back to a pointer. HTTP 200 alone does not prove report validation. The old `skill_loaded` flag is no longer part of this report format.

Do not use `load_test_incident.sh` for the current investigation agent: it writes the old skeleton fixture. To resend an event for already loaded normalised evidence, pass both identifiers:

```bash
bash scripts/send_test_event.sh <incident_id> <loaded_run_id>
```

Resending can produce another investigation and email; general event idempotency is not implemented. The verified case is transport/SOP-03, not all five SOP families or a live NMS feed.

## 10. Optional distributed tracing

The existing demo has tracing enabled. For a new deployment, inspect `infra/observability.tf` and obtain approval for its account/Region-wide log resource policy, X-Ray trace destination and indexing rule before enabling them:

```hcl
enable_observability       = true
trace_indexing_percentage = 100
```

Review a new Terraform plan and summary before applying it. One hundred per cent indexing is the demo setting; choose a lower percentage for ongoing use. The agent package includes aws-opentelemetry-distro and uses the entry point `["opentelemetry-instrument", "main.py"]`. No additional OTEL environment variables are configured by this repository.

In the target Region, inspect CloudWatch GenAI Observability for the agent and Application Signals / Transaction Search for the request's trace and service map. Search within the smoke-test time window. Span count varies by investigation; the historical 17-span skeleton trace is not a current acceptance threshold.

## 11. Teardown

Only when explicitly ready to remove the deployment, capture required demo evidence first, review a destroy plan and its resource summary, then apply:

```bash
terraform -chdir=infra plan -destroy -out=tfplan-destroy
terraform -chdir=infra apply tfplan-destroy
bash scripts/verify_destroy.sh
```

Transaction Search resources are account-wide. Review their effect on other applications before teardown, and check the resulting configuration afterwards:

```bash
aws xray get-trace-segment-destination
aws xray get-indexing-rules
```

The tagged-resource check is useful but is not proof that every global or untaggable resource is gone. Inspect the Terraform result and account-wide settings, and record verification in PROGRESS.md. Preserve any required report evidence locally before removing its storage.

Never commit Terraform state, terraform.tfvars, credentials, `.env`, `.build/`, `runs/`, private `demo-evidence/` or the local virtual environment.
