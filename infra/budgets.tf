# A2 — Cost guardrails. Apply these FIRST:
#   terraform apply -target=aws_budgets_budget.monthly -target=aws_ce_anomaly_monitor.services -target=aws_ce_anomaly_subscription.daily
# (BUILD SPEC v3 §11: budgets are created before anything else.)

resource "aws_budgets_budget" "monthly" {
  for_each = { for v in var.budget_limits_usd : tostring(v) => v }

  name         = "${local.name_prefix}-monthly-${each.key}usd"
  budget_type  = "COST"
  limit_amount = format("%.2f", each.value)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Actual spend crosses the limit.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  # Forecast says the month will cross the limit.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}

resource "aws_ce_anomaly_monitor" "services" {
  count = var.create_anomaly_monitor ? 1 : 0

  name              = "${local.name_prefix}-service-monitor"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "daily" {
  count = var.create_anomaly_monitor ? 1 : 0

  name             = "${local.name_prefix}-anomaly-alerts"
  frequency        = "DAILY"
  monitor_arn_list = [aws_ce_anomaly_monitor.services[0].arn]

  subscriber {
    type    = "EMAIL"
    address = var.budget_email
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      match_options = ["GREATER_THAN_OR_EQUAL"]
      values        = [tostring(var.anomaly_threshold_usd)]
    }
  }
}
