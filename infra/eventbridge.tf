# B7 — EventBridge custom bus + rule (PDF ①: incident event -> agent).
# B13 — Lambda shim between EventBridge and AgentCore.
#
# Why the shim: InvokeAgentRuntime is a SigV4 data-plane call, and EventBridge has no native
# AgentCore target. The alternative (API destination) needs OAuth/JWT on the runtime, which
# adds Cognito. A ~40-line Lambda using IAM is simpler for a PoC.
#
# Event contract (published by enrichment, or scripts/send_test_event.sh):
#   source      = "sop-rca.enrichment"
#   detail-type = "incident.ready"
#   detail      = { "incident_id": "...", "run_id": "<uuid>", "previous_report_key": null }

resource "aws_cloudwatch_event_bus" "incidents" {
  name = "${local.name_prefix}-incidents"
}

resource "aws_cloudwatch_event_rule" "incident_ready" {
  name           = "${local.name_prefix}-incident-ready"
  event_bus_name = aws_cloudwatch_event_bus.incidents.name
  description    = "Route incident.ready events to the triage agent"

  event_pattern = jsonencode({
    source        = ["sop-rca.enrichment"]
    "detail-type" = ["incident.ready"]
  })
}

# ---------------- Lambda shim (only when the runtime exists) ----------------

data "archive_file" "shim" {
  type        = "zip"
  source_file = "${path.module}/lambda_shim/handler.py"
  output_path = "${path.module}/.build/lambda_shim.zip"
}

data "aws_iam_policy_document" "shim_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  name               = "${local.name_prefix}-invoke-shim-role"
  assume_role_policy = data.aws_iam_policy_document.shim_trust.json
}

resource "aws_cloudwatch_log_group" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  name              = "/aws/lambda/${local.name_prefix}-invoke-agent"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.shim[0].arn}:*"]
  }
  statement {
    sid     = "InvokeTriageAgentOnly"
    actions = ["bedrock-agentcore:InvokeAgentRuntime"]
    resources = [
      aws_bedrockagentcore_agent_runtime.triage[0].agent_runtime_arn,
      "${aws_bedrockagentcore_agent_runtime.triage[0].agent_runtime_arn}/*", # runtime endpoints
    ]
  }
  # Needed for Active tracing: without these the Lambda silently drops its trace segments.
  # X-Ray does not support resource-level permissions, so "*" is the only valid resource.
  statement {
    sid       = "WriteXRayTraces"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  name   = "${local.name_prefix}-invoke-shim-policy"
  role   = aws_iam_role.shim[0].id
  policy = data.aws_iam_policy_document.shim[0].json
}

resource "aws_lambda_function" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  function_name    = "${local.name_prefix}-invoke-agent"
  role             = aws_iam_role.shim[0].arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  architectures    = ["arm64"]
  filename         = data.archive_file.shim.output_path
  source_code_hash = data.archive_file.shim.output_base64sha256
  timeout          = 900 # an agent run can take minutes; EventBridge invokes async
  memory_size      = 256

  # Active tracing: the shim shows up in the trace and passes the trace header to AgentCore.
  tracing_config {
    mode = var.enable_observability ? "Active" : "PassThrough"
  }

  environment {
    variables = {
      AGENT_RUNTIME_ARN = aws_bedrockagentcore_agent_runtime.triage[0].agent_runtime_arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.shim, aws_iam_role_policy.shim]
}

# Do not let async Lambda retry a long, token-costly agent run twice.
resource "aws_lambda_function_event_invoke_config" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  function_name                = aws_lambda_function.shim[0].function_name
  maximum_retry_attempts       = 0
  maximum_event_age_in_seconds = 3600
}

resource "aws_cloudwatch_event_target" "shim" {
  count = var.deploy_agent_runtime ? 1 : 0

  rule           = aws_cloudwatch_event_rule.incident_ready.name
  event_bus_name = aws_cloudwatch_event_bus.incidents.name
  target_id      = "invoke-triage-agent"
  arn            = aws_lambda_function.shim[0].arn

  retry_policy {
    maximum_retry_attempts       = 2
    maximum_event_age_in_seconds = 3600
  }
}

resource "aws_lambda_permission" "eventbridge" {
  count = var.deploy_agent_runtime ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.shim[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.incident_ready.arn
}
