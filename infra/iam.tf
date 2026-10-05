# B11 — IAM. Least privilege:
#   Agent role: read the skill bundle (allowed paths only) and evidence/, write reports/,
#               invoke ONE chosen model, publish to ONE SNS topic, write its own logs.
#   EventBridge -> Lambda permission and the Lambda shim role are in eventbridge.tf.
# Based on the AgentCore Runtime execution-role example in the AWS developer guide.

locals {
  agent_runtime_name = replace("${local.name_prefix}_triage", "-", "_") # AgentCore names: letters, digits, underscore
  knowledge_bucket   = aws_s3_bucket.this["knowledge"]
  data_bucket        = aws_s3_bucket.this["data"]
}

data "aws_iam_policy_document" "agent_trust" {
  statement {
    sid     = "AssumeRolePolicy"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:bedrock-agentcore:${var.region}:${local.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "agent" {
  name               = "${local.name_prefix}-agent-runtime-role"
  assume_role_policy = data.aws_iam_policy_document.agent_trust.json
}

data "aws_iam_policy_document" "agent" {
  # --- Pull the image (container mode only; harmless no-op in code mode) ---
  statement {
    sid       = "ECRImageAccess"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [aws_ecr_repository.agent.arn]
  }
  statement {
    sid       = "ECRTokenAccess"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # --- Read the code zip (code mode only; harmless no-op in container mode) ---
  statement {
    sid       = "ReadAgentCodePackage"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${local.data_bucket.arn}/agent-code/*"]
  }

  # --- Logs (AgentCore writes to /aws/bedrock-agentcore/runtimes/<id>-<endpoint>) ---
  statement {
    sid       = "LogsGroup"
    actions   = ["logs:DescribeLogStreams", "logs:CreateLogGroup"]
    resources = ["arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }
  statement {
    sid       = "LogsDescribe"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:*"]
  }
  statement {
    sid       = "LogsWrite"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
  }

  # --- Per-agent span delivery (AgentCore docs, execution role): lets AgentCore allow X-Ray to
  #     write spans into this agent's own log group. Scoped to this runtime's log groups only. ---
  statement {
    sid       = "LogsResourcePolicyForSpans"
    actions   = ["logs:PutResourcePolicy"]
    resources = ["arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/${local.agent_runtime_name}-*"]
  }

  # --- Tracing and metrics ---
  statement {
    sid       = "XRay"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  # --- Workload identity tokens (required by the runtime) ---
  statement {
    sid = "GetAgentAccessToken"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
      "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
    ]
    resources = [
      "arn:${local.partition}:bedrock-agentcore:${var.region}:${local.account_id}:workload-identity-directory/default",
      "arn:${local.partition}:bedrock-agentcore:${var.region}:${local.account_id}:workload-identity-directory/default/workload-identity/${local.agent_runtime_name}-*",
    ]
  }

  # --- ONE model only: the inference profile and the foundation model it routes to ---
  statement {
    sid     = "BedrockInvokeChosenModel"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:${local.partition}:bedrock:${var.region}:${local.account_id}:inference-profile/${var.bedrock_model_id}",
      "arn:${local.partition}:bedrock:*::foundation-model/${var.bedrock_foundation_model_id}",
    ]
  }

  # --- Skill bundle: read only the allowed paths ---
  statement {
    sid     = "ReadSkillBundle"
    actions = ["s3:GetObject"]
    resources = [
      "${local.knowledge_bucket.arn}/SKILL.md",
      "${local.knowledge_bucket.arn}/catalog.json",
      "${local.knowledge_bucket.arn}/shared-rules.md",
      "${local.knowledge_bucket.arn}/sops/*",
      "${local.knowledge_bucket.arn}/reference/*",
    ]
  }
  statement {
    sid       = "ListSkillBundle"
    actions   = ["s3:ListBucket"]
    resources = [local.knowledge_bucket.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["", "SKILL.md", "catalog.json", "shared-rules.md", "sops/*", "reference/*"]
    }
  }

  # --- Evidence: read; Reports: write ---
  statement {
    sid       = "ReadEvidence"
    actions   = ["s3:GetObject"]
    resources = ["${local.data_bucket.arn}/evidence/*"]
  }
  statement {
    sid       = "ReadWriteReports"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${local.data_bucket.arn}/reports/*"]
  }
  statement {
    sid       = "ListEvidenceAndReports"
    actions   = ["s3:ListBucket"]
    resources = [local.data_bucket.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["evidence/*", "reports/*"]
    }
  }

  # --- Notify ---
  statement {
    sid       = "PublishReport"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.triage_reports.arn]
  }

  # --- Evidence store: read-only. Reports go to S3 (ReadWriteReports above); only a
  #     pointer goes through SNS. The agent never writes evidence. ---
  statement {
    sid     = "EvidenceTableRead"
    actions = ["dynamodb:GetItem", "dynamodb:Query"]
    resources = [
      aws_dynamodb_table.evidence.arn,
      "${aws_dynamodb_table.evidence.arn}/index/*",
    ]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "${local.name_prefix}-agent-runtime-policy"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent.json
}
