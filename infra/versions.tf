# Terraform and provider versions.
# aws_bedrockagentcore_agent_runtime needs a recent 6.x AWS provider.
# Run `terraform init -upgrade` once; the .terraform.lock.hcl then pins the exact version.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4"
    }
  }

  # Local state for the PoC. Keep terraform.tfstate out of git.
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile

  # Every resource gets project=sop-rca, so `make destroy` can be verified
  # with the Resource Groups Tagging API.
  default_tags {
    tags = {
      project    = var.project
      managed_by = "terraform"
      owner      = var.owner_tag
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
  partition  = data.aws_partition.current.partition

  # Lower-case, globally unique-ish names for S3.
  name_prefix = var.project
  bucket_suffix = "${local.account_id}-${var.region}"
}
