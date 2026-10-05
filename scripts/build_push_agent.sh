#!/usr/bin/env bash
# B8 — Build the agent image for linux/arm64 (AgentCore requirement) and push it to ECR.
# Usage: bash scripts/build_push_agent.sh [tag] [context-dir]
#   tag defaults to v0; context-dir defaults to agent_skeleton/ (later: the real agent/)
source "$(dirname "$0")/_common.sh"

TAG="${1:-v0}"
CONTEXT="${2:-$REPO_ROOT/agent_skeleton}"
REPO_URL="$(tf_out ecr_repository_url)"
REGISTRY="${REPO_URL%%/*}"

echo "Logging in to $REGISTRY"
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"

echo "Building $REPO_URL:$TAG (linux/arm64) from $CONTEXT"
docker buildx build --platform linux/arm64 -t "$REPO_URL:$TAG" --push "$CONTEXT"

echo "Pushed. Image digest:"
aws ecr describe-images --repository-name "${REPO_URL#*/}" --image-ids imageTag="$TAG" \
  --query 'imageDetails[0].imageDigest' --output text
echo "Next: set deploy_agent_runtime = true and agent_image_tag = \"$TAG\" in infra/terraform.tfvars, then terraform apply."
