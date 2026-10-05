# B8 — Container registry, fallback path. Default deploy_mode = "code" doesn't use this
# (direct code deployment needs no image). Created either way — an empty repo costs nothing —
# so switching to deploy_mode = "container" needs no new apply for the registry itself.
# Not listed in BUILD SPEC v3 §11; approved as an addition.
# If ever used: AgentCore requires a linux/arm64 image on 0.0.0.0:8080 with POST /invocations and GET /ping.

resource "aws_ecr_repository" "agent" {
  name                 = "${local.name_prefix}-triage-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # PoC: destroy even if images remain

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# Keep only the last 5 images.
resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}
