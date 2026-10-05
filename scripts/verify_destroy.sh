#!/usr/bin/env bash
# After `terraform destroy`: prove nothing tagged project=sop-rca remains (BUILD SPEC v3 §11).
# Paste the output into PROGRESS.md.
source "$(dirname "$0")/_common.sh"

echo "Tagged resources in $AWS_REGION:"
aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=sop-rca \
  --query 'ResourceTagMappingList[].ResourceARN' --output text
echo "Tagged global resources (us-east-1: budgets, cost anomaly, IAM):"
aws resourcegroupstaggingapi get-resources --region us-east-1 --tag-filters Key=project,Values=sop-rca \
  --query 'ResourceTagMappingList[].ResourceARN' --output text
echo "Expected: both lists empty. Also check: aws budgets describe-budgets --account-id \$(aws sts get-caller-identity --query Account --output text)"
