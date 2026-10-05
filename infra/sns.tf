# B10 — Triage result -> notify (PDF ⑤).
# The topic is always created. The email subscription is optional (report_email may be "").
# After it's added, AWS emails a confirmation link — click it, or nothing arrives.

resource "aws_sns_topic" "triage_reports" {
  name = "${local.name_prefix}-triage-reports"
}

resource "aws_sns_topic_subscription" "email" {
  count = var.report_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.triage_reports.arn
  protocol  = "email"
  endpoint  = var.report_email
}
