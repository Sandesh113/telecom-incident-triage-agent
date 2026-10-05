# B5 — Skill bundle bucket (PDF ② reasoning layer, ③ reference layer).
#   Holds ONLY: SKILL.md, catalog.json, shared-rules.md, sops/, reference/
#   Never upload scenarios/ or dictionary/ here (BUILD SPEC v3 §4, §11).
#   Upload with scripts/sync_knowledge.sh, not by hand.
#
# B6 — Data bucket (our addition), one bucket with prefixes:
#   raw/       landing zone for the sink (later phase)
#   evidence/  fixture/evidence files the agent tools read
#   reports/   finished triage reports the agent writes

locals {
  buckets = {
    knowledge = "${local.name_prefix}-knowledge-${local.bucket_suffix}"
    data      = "${local.name_prefix}-data-${local.bucket_suffix}"
  }
}

resource "aws_s3_bucket" "this" {
  for_each = local.buckets

  bucket        = each.value
  force_destroy = true # PoC: lets `terraform destroy` empty the bucket
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = aws_s3_bucket.this

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3: no KMS key cost
    }
  }
}

# Expire raw landing data after 14 days to keep storage near zero.
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.this["data"].id

  rule {
    id     = "expire-raw"
    status = "Enabled"
    filter {
      prefix = "raw/"
    }
    expiration {
      days = 14
    }
  }
}

# Deny any request that is not over TLS.
data "aws_iam_policy_document" "tls_only" {
  for_each = aws_s3_bucket.this

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      each.value.arn,
      "${each.value.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  policy = data.aws_iam_policy_document.tls_only[each.key].json

  depends_on = [aws_s3_bucket_public_access_block.this]
}
