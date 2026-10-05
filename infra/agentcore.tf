# B9 — Amazon Bedrock AgentCore Runtime ("A" in the PDF) running the Strands triage agent.
# Created only when deploy_agent_runtime = true, because the artifact (zip or image) must
# already exist before Terraform can reference it.
#
# deploy_mode = "code" (default): direct code deployment, no Docker.
#   Build with scripts/build_agent_zip.sh, which uploads to
#   s3://<data_bucket>/agent-code/main.zip (var.agent_code_key).
# deploy_mode = "container": an image in ECR, built with scripts/build_push_agent.sh.

resource "aws_bedrockagentcore_agent_runtime" "triage" {
  count = var.deploy_agent_runtime ? 1 : 0

  agent_runtime_name = local.agent_runtime_name
  description        = "SOP-grounded telecom incident triage agent (Strands)"
  role_arn           = aws_iam_role.agent.arn

  agent_runtime_artifact {
    dynamic "code_configuration" {
      for_each = var.deploy_mode == "code" ? [1] : []
      content {
        entry_point = var.agent_code_entry_point
        runtime     = var.agent_code_runtime
        code {
          s3 {
            bucket     = local.data_bucket.bucket
            prefix     = var.agent_code_key
            version_id = var.agent_code_version_id
          }
        }
      }
    }

    dynamic "container_configuration" {
      for_each = var.deploy_mode == "container" ? [1] : []
      content {
        container_uri = "${aws_ecr_repository.agent.repository_url}:${var.agent_image_tag}"
      }
    }
  }

  network_configuration {
    network_mode = "PUBLIC" # no VPC, no NAT gateway (NAT is forbidden by BUILD SPEC v3 §11)
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  # Read by the agent code. No secrets here.
  environment_variables = {
    BEDROCK_MODEL_ID    = var.bedrock_model_id
    SKILL_BUCKET        = local.knowledge_bucket.bucket
    DATA_BUCKET         = local.data_bucket.bucket
    EVIDENCE_PREFIX     = "evidence/"
    REPORTS_PREFIX      = "reports/"
    EVIDENCE_TABLE_NAME = aws_dynamodb_table.evidence.name
    SNS_TOPIC_ARN       = aws_sns_topic.triage_reports.arn
    LOG_LEVEL           = "INFO"
  }

  depends_on = [aws_iam_role_policy.agent]
}

# B12 — 7-day retention for the runtime's log group.
# [Unverified] AgentCore names it /aws/bedrock-agentcore/runtimes/<runtime_id>-DEFAULT.
# If apply fails with "ResourceAlreadyExistsException", import it:
#   terraform import 'aws_cloudwatch_log_group.agent_runtime[0]' /aws/bedrock-agentcore/runtimes/<runtime_id>-DEFAULT
resource "aws_cloudwatch_log_group" "agent_runtime" {
  count = var.deploy_agent_runtime ? 1 : 0

  name              = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.triage[0].agent_runtime_id}-DEFAULT"
  retention_in_days = var.log_retention_days
}
