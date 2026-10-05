# Deployment guide

This guide recreates the PoC in a separate AWS account. Commands assume Git Bash, WSL, macOS or Linux.

## 1. Prerequisites

Install AWS CLI v2, Terraform 1.6+, Python 3.13, `uv`, and Git. Docker is needed only for the optional container path.

Configure a non-root AWS CLI profile. Use IAM Identity Center or another temporary-credential workflow where possible. The target Region must support Amazon Bedrock AgentCore and the selected model. The verified PoC Region is `eu-north-1`.

## 2. Configure local variables

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

Replace both email placeholders. Confirm the AWS profile, Region and model IDs. Keep `terraform.tfvars` local; it is ignored by Git.

Transaction Search is disabled by default because it changes an account-wide, Region-wide X-Ray setting. Leave it disabled for the first deployment.

## 3. Run preflight

```bash
AWS_PROFILE=poc AWS_REGION=eu-north-1 bash scripts/preflight.sh

MODEL_ID=eu.anthropic.claude-sonnet-4-5-20250929-v1:0 \
AWS_PROFILE=poc AWS_REGION=eu-north-1 \
  bash scripts/preflight.sh
```

Stop if identity, Region, AgentCore or model invocation fails.

## 4. Validate locally

```bash
uv sync --locked --dev
uv run pytest -q

python knowledge/tools/build_catalog.py
git diff --exit-code -- knowledge/catalog.json

terraform -chdir=infra init
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
```

## 5. Create cost guardrails first

Review the targeted plan before applying:

```bash
terraform -chdir=infra plan \
  -target=aws_budgets_budget.monthly \
  -target=aws_ce_anomaly_monitor.services \
  -target=aws_ce_anomaly_subscription.daily

terraform -chdir=infra apply \
  -target=aws_budgets_budget.monthly \
  -target=aws_ce_anomaly_monitor.services \
  -target=aws_ce_anomaly_subscription.daily
```

An AWS account can have only one service anomaly monitor. Set `create_anomaly_monitor = false` if an existing monitor is already managed elsewhere.

## 6. Create base infrastructure

Keep `deploy_agent_runtime = false` for the first apply:

```bash
terraform -chdir=infra plan -out=tfplan
terraform -chdir=infra apply tfplan
```

This creates S3, DynamoDB, SNS, IAM, EventBridge and ECR resources. Confirm the optional SNS email subscription before expecting notifications.

## 7. Upload knowledge and agent code

```bash
bash scripts/sync_knowledge.sh ./knowledge
bash scripts/build_agent_zip.sh ./agent
```

The packaging script resolves dependencies for Linux ARM64, removes Windows binaries, restores Linux console-script wrappers and writes POSIX paths and permissions into the ZIP.

For the container fallback:

```bash
bash scripts/build_push_agent.sh v0 ./agent
```

Set `deploy_mode = "container"` before the final Terraform apply.

## 8. Create AgentCore and the invocation bridge

Set `deploy_agent_runtime = true`, then review and apply:

```bash
terraform -chdir=infra plan -out=tfplan
terraform -chdir=infra apply tfplan
```

AgentCore may create its runtime log group before Terraform does. If Terraform reports that the group already exists, import the exact group named in the error and apply again.

## 9. Smoke test

```bash
bash scripts/load_test_incident.sh INC-SMOKE-0001
bash scripts/send_test_event.sh INC-SMOKE-0001

aws logs tail /aws/lambda/sop-rca-invoke-agent --follow
aws s3 ls "s3://$(terraform -chdir=infra output -raw data_bucket)/reports/" --recursive
```

Success means Lambda logs an AgentCore HTTP 200 response, the report appears in S3, the report says the skill loaded, and the SNS subscriber receives a notification.

## 10. Optional distributed tracing

Review `infra/observability.tf` before setting:

```hcl
enable_observability       = true
trace_indexing_percentage = 100
```

One hundred percent indexing is appropriate only for a short demonstration. Lower it for ongoing use. Apply and inspect CloudWatch GenAI Observability and Application Signals Transaction Search.

## 11. Teardown

```bash
terraform -chdir=infra destroy
bash scripts/verify_destroy.sh
```

Transaction Search resources are account-wide and may require an additional manual check:

```bash
aws xray get-trace-segment-destination
aws xray get-indexing-rules
```

Never commit `terraform.tfstate`, `terraform.tfvars`, `.env`, `.build/` or a local virtual environment.
