# Observability: the one-time account setting "CloudWatch Transaction Search".
#
# Why: AgentCore Runtime, the Lambda shim and Bedrock calls emit spans/traces. To see them as a
# trace and service map in CloudWatch (GenAI Observability / Application Signals) the account must
# send X-Ray trace segments to CloudWatch Logs instead of the default X-Ray store.
# Docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html
#
# WARNING - these three resources are ACCOUNT-WIDE and REGION-WIDE singletons, not scoped to
# project=sop-rca. They change X-Ray behaviour for everything in this account in var.region.
# Approved by the owner on 2026-10-05 (CLAUDE.md rule 6). Set enable_observability = false to skip.
#
# [Unverified] what `terraform destroy` does to the destination (reverts to "XRay" or leaves
# "CloudWatchLogs"). Check `aws xray get-trace-segment-destination` after the first destroy.

locals {
  # The two log groups X-Ray writes spans to once Transaction Search is on.
  span_log_group_arns = [
    "arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:aws/spans:*",
    "arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/application-signals/data:*",
  ]
}

# 1. Let X-Ray write to those log groups. Must exist before the destination is switched.
data "aws_iam_policy_document" "transaction_search" {
  statement {
    sid       = "TransactionSearchXRayAccess"
    effect    = "Allow"
    actions   = ["logs:PutLogEvents"]
    resources = local.span_log_group_arns

    principals {
      type        = "Service"
      identifiers = ["xray.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:xray:${var.region}:${local.account_id}:*"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "transaction_search" {
  count = var.enable_observability ? 1 : 0

  policy_name     = "${local.name_prefix}-transaction-search"
  policy_document = data.aws_iam_policy_document.transaction_search.json
}

# 2. Send trace segments to CloudWatch Logs (this is "enable Transaction Search").
resource "aws_xray_trace_segment_destination" "this" {
  count = var.enable_observability ? 1 : 0

  destination = "CloudWatchLogs"

  depends_on = [aws_cloudwatch_log_resource_policy.transaction_search]
}

# 3. Index a percentage of spans so they are searchable. The account already has a rule named
#    "Default" (0 %); this manages it. [Unverified] whether the first apply updates it in place
#    or needs `terraform import`; the import ID is the rule name: Default.
resource "aws_xray_indexing_rule" "default" {
  count = var.enable_observability ? 1 : 0

  name = "Default"

  rule {
    probabilistic {
      desired_sampling_percentage = var.trace_indexing_percentage
    }
  }

  depends_on = [aws_xray_trace_segment_destination.this]
}
