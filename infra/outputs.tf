output "account_id" {
  value = local.account_id
}

output "region" {
  value = var.region
}

output "knowledge_bucket" {
  description = "Skill bundle bucket (SKILL.md, catalog.json, shared-rules.md, sops/, reference/)"
  value       = local.knowledge_bucket.bucket
}

output "data_bucket" {
  description = "raw/, evidence/, reports/"
  value       = local.data_bucket.bucket
}

output "ecr_repository_url" {
  description = "Only used when deploy_mode = \"container\"."
  value       = aws_ecr_repository.agent.repository_url
}

output "evidence_table_name" {
  value = aws_dynamodb_table.evidence.name
}

output "agent_code_s3_uri" {
  description = "Where scripts/build_agent_zip.sh uploads the zip (deploy_mode = \"code\")."
  value       = "s3://${local.data_bucket.bucket}/${var.agent_code_key}"
}

output "event_bus_name" {
  value = aws_cloudwatch_event_bus.incidents.name
}

output "sns_topic_arn" {
  value = aws_sns_topic.triage_reports.arn
}

output "agent_role_arn" {
  value = aws_iam_role.agent.arn
}

output "agent_runtime_arn" {
  value = var.deploy_agent_runtime ? aws_bedrockagentcore_agent_runtime.triage[0].agent_runtime_arn : null
}

output "deploy_mode" {
  value = var.deploy_mode
}
