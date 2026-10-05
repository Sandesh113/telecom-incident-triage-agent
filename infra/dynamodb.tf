# Evidence store (BUILD SPEC v3 §5.4), on-demand so there's no idle cost.
# One table, single-table design: pk/sk cover events_normalized, observations, kpi_windows,
# topology (versioned), changes, impact_records, incidents, unresolved_ids, unmapped_alarms
# and reports (versioned). A real build may split these; one table is enough for the PoC
# smoke test and the walking-skeleton agent.
#
# Key shape used by the walking-skeleton agent and scripts/load_test_incident.sh:
#   pk = "INCIDENT#<incident_id>"   sk = "META" | "EVENT#<event_id>" | "REPORT#v<n>"
# gsi1 lets a lookup go the other way (by run_id) without a table scan.

resource "aws_dynamodb_table" "evidence" {
  name         = "${local.name_prefix}-evidence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "run_id"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi1-run-id"
    hash_key        = "run_id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = false # PoC: keep cost at zero; turn on before anything you'd mind losing
  }
}
