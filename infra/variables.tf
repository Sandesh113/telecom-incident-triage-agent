# ---------- Account and region (A1, A3) ----------

variable "aws_profile" {
  description = "AWS CLI profile Terraform uses (from `aws configure sso` or `aws configure`)."
  type        = string
  default     = "poc"
}

variable "region" {
  description = "Target region. Verified for this PoC: eu-north-1 (AgentCore + Bedrock reachable, model access confirmed)."
  type        = string
  default     = "eu-north-1"
}

variable "project" {
  description = "Project tag and name prefix. BUILD SPEC v3 uses sop-rca."
  type        = string
  default     = "sop-rca"
}

variable "owner_tag" {
  description = "Owner tag value."
  type        = string
  default     = "sandesh"
}

variable "budget_email" {
  description = "Email for AWS Budgets and Cost Anomaly Detection alerts. Required: these guardrails are created first."
  type        = string
}

variable "report_email" {
  description = <<-EOT
    Email for the SNS triage-report subscription. Optional: leave "" to create the topic
    without a subscription and add one later (console, or `aws sns subscribe`) once you
    have the address you want reports sent to.
  EOT
  type        = string
  default     = ""
}

# ---------- Cost guardrails (A2) ----------

variable "budget_limits_usd" {
  description = "Monthly budget thresholds in USD (AWS Budgets bills in USD). ~£10 and ~£20."
  type        = list(number)
  default     = [13, 26]
}

variable "create_anomaly_monitor" {
  description = "Create a Cost Anomaly Detection SERVICE monitor. Set false if the account already has one (quota is 1 per dimension)."
  type        = bool
  default     = true
}

variable "anomaly_threshold_usd" {
  description = "Alert when an anomaly's absolute impact exceeds this many USD."
  type        = number
  default     = 5
}

# ---------- Model (A4) ----------

variable "bedrock_model_id" {
  description = <<-EOT
    Model ID or inference profile ID the agent calls, e.g. an eu.* Claude Sonnet-class
    inference profile. Discover it with scripts/preflight.sh; do not guess.
  EOT
  type        = string
}

variable "bedrock_foundation_model_id" {
  description = <<-EOT
    The underlying foundation-model ID behind bedrock_model_id (without the eu./us./global. prefix).
    Needed because an inference profile routes to the foundation model in several regions,
    and IAM must allow InvokeModel on both.
  EOT
  type        = string
}

# ---------- Agent runtime (B8, B9, B13) ----------

variable "deploy_agent_runtime" {
  description = <<-EOT
    Two-step deploy. Leave false for the first apply (creates S3, DynamoDB, ECR and
    everything else). Push the agent code (or image), then set true and apply again to
    create the AgentCore Runtime and the EventBridge -> Lambda shim -> AgentCore wiring.
  EOT
  type        = bool
  default     = false
}

variable "deploy_mode" {
  description = <<-EOT
    How the agent artifact is packaged for AgentCore Runtime.
      "code"      - direct code deployment: a Python zip in S3 (no Docker). Default: avoids
                    the Windows/Docker ARM64 build step.
      "container" - a container image in ECR (scripts/build_push_agent.sh). Kept as a
                    fallback if zip packaging keeps failing.
  EOT
  type    = string
  default = "code"
  validation {
    condition     = contains(["code", "container"], var.deploy_mode)
    error_message = "deploy_mode must be \"code\" or \"container\"."
  }
}

variable "agent_image_tag" {
  description = "Tag of the agent image in ECR. Only used when deploy_mode = \"container\"."
  type        = string
  default     = "v0"
}

variable "agent_code_key" {
  description = "Key of the agent zip inside the data bucket's agent-code/ prefix. Only used when deploy_mode = \"code\"."
  type        = string
  default     = "agent-code/main.zip"
}

variable "agent_code_version_id" {
  description = <<-EOT
    S3 object version of the agent zip to deploy. Leave null to always use the latest
    version (fine for a PoC with versioning off; set explicitly once you want a pinned,
    reproducible deploy).
  EOT
  type    = string
  default = null
}

variable "agent_code_entry_point" {
  description = <<-EOT
    Entry point for direct code deployment. The default runs main.py under ADOT auto-instrumentation,
    which needs aws-opentelemetry-distro in agent/requirements.txt (the docs' entry point for observability).
    If that package is removed from the zip, use ["main.py"] instead or the runtime will not start.
  EOT
  type        = list(string)
  default     = ["opentelemetry-instrument", "main.py"]
}

variable "agent_code_runtime" {
  description = "Python runtime for direct code deployment. Must match the --python-version used when packaging."
  type        = string
  default     = "PYTHON_3_13"
  validation {
    condition     = contains(["PYTHON_3_10", "PYTHON_3_11", "PYTHON_3_12", "PYTHON_3_13"], var.agent_code_runtime)
    error_message = "agent_code_runtime must be one of PYTHON_3_10..PYTHON_3_13."
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention."
  type        = number
  default     = 7
}

# ---------- Observability (observability.tf) ----------

variable "enable_observability" {
  description = <<-EOT
    Create the account-wide CloudWatch Transaction Search setting (log resource policy, trace segment
    destination, indexing rule) and turn on active X-Ray tracing on the Lambda shim. The Transaction
    Search resources are NOT scoped to project=sop-rca. Set false to leave the account untouched.
  EOT
  type        = bool
  default     = true
}

variable "trace_indexing_percentage" {
  description = "Percentage of spans indexed for Transaction Search (0-100). 100 is for the demo; lower it to save cost."
  type        = number
  default     = 100
  validation {
    condition     = var.trace_indexing_percentage >= 0 && var.trace_indexing_percentage <= 100
    error_message = "trace_indexing_percentage must be between 0 and 100."
  }
}
