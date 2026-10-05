#!/usr/bin/env bash
# Phase 0 preflight (BUILD SPEC v3 §12). Read-only: creates nothing.
#   A1 identity, A3 region, A4 model access + one test call, laptop tools.
# Usage: AWS_PROFILE=poc AWS_REGION=eu-west-2 bash scripts/preflight.sh
source "$(dirname "$0")/_common.sh"
set +e  # report every check, don't stop at the first failure

echo "== Laptop tools (D) =="
for t in aws terraform docker python go git uv; do
  if command -v "$t" >/dev/null 2>&1; then
    if [[ "$t" == go ]]; then v=$(go version); else v=$($t --version 2>&1 | head -1); fi
    ok "$t: $v"
  else warn "$t not found"; fi
done
if command -v docker >/dev/null 2>&1; then
  docker buildx version >/dev/null 2>&1 && ok "docker buildx available (needed for linux/arm64 image)" || warn "docker buildx missing"
fi

echo; echo "== A1 Identity (profile: $AWS_PROFILE) =="
if ID=$(aws sts get-caller-identity --output json 2>&1); then
  ok "$(echo "$ID" | tr -d '\n ' )"
  echo "$ID" | grep -q ':root"' && fail "You are using ROOT credentials. Stop and use an IAM Identity Center / IAM user profile."
else
  fail "No working credentials: $ID"; echo "STOP (BUILD SPEC: stop on missing credentials)."; exit 1
fi

echo; echo "== A3 Region: $AWS_REGION =="
if aws bedrock list-foundation-models --by-provider anthropic --query 'length(modelSummaries)' --output text >/dev/null 2>&1; then
  ok "Bedrock control plane reachable in $AWS_REGION"
else
  fail "Bedrock not reachable in $AWS_REGION"
fi
if aws bedrock-agentcore-control list-agent-runtimes --max-results 1 >/dev/null 2>&1; then
  ok "AgentCore control plane reachable in $AWS_REGION"
else
  fail "AgentCore not reachable in $AWS_REGION (or the CLI is too old: update AWS CLI v2). Consider another region."
fi

echo; echo "== A4 Claude Sonnet-class inference profiles in $AWS_REGION =="
aws bedrock list-inference-profiles --type-equals SYSTEM_DEFINED \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic.claude') && contains(inferenceProfileId,'sonnet')].[inferenceProfileId,status]" \
  --output table
echo "Pick the newest eu.* (or global.*) Sonnet profile above. Set in infra/terraform.tfvars:"
echo "  bedrock_model_id            = <profile id, e.g. eu.anthropic.claude-sonnet-...>"
echo "  bedrock_foundation_model_id = <same id without the 'eu.'/'global.' prefix>"

MODEL_ID="${MODEL_ID:-}"
if [[ -z "$MODEL_ID" ]]; then
  echo; warn "Set MODEL_ID=<profile id> and re-run to make one test call."; exit 0
fi

echo; echo "== A4 Test call to $MODEL_ID =="
OUT=$(aws bedrock-runtime converse --model-id "$MODEL_ID" \
  --messages '[{"role":"user","content":[{"text":"Reply with the single word OK."}]}]' \
  --inference-config '{"maxTokens":10}' \
  --query 'output.message.content[0].text' --output text 2>&1)
if [[ $? -eq 0 ]]; then
  ok "Model replied: $OUT"
else
  fail "$OUT"
  echo "  If this is AccessDenied/ResourceNotFound for an Anthropic model, submit the one-time"
  echo "  Anthropic use-case form (Bedrock console > Model catalog > the model), wait a few minutes,"
  echo "  and re-run. STOP until this passes (BUILD SPEC: stop on missing model access)."
fi
