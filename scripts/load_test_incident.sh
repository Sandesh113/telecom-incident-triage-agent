#!/usr/bin/env bash
# Load one minimal test incident into the evidence table, for the end-to-end smoke test.
# This is NOT scenario data (no S1-S8 names here) — just enough for the walking-skeleton
# agent to prove the plumbing works. Real enrichment writes the table in Phase 4.
# Usage: bash scripts/load_test_incident.sh [incident_id]
source "$(dirname "$0")/_common.sh"

INCIDENT_ID="${1:-INC-SMOKE-0001}"
TABLE="$(tf_out evidence_table_name)"

ITEM=$("$PY" -c '
import json, sys
incident_id = sys.argv[1]
item = {
    "pk": {"S": f"INCIDENT#{incident_id}"},
    "sk": {"S": "META"},
    "run_id": {"S": "preflight-smoke-test"},
    "status": {"S": "ready"},
}
print(json.dumps(item))
' "$INCIDENT_ID")

aws dynamodb put-item --table-name "$TABLE" --item "$ITEM"
ok "Loaded $INCIDENT_ID into $TABLE"
echo "Next: bash scripts/send_test_event.sh $INCIDENT_ID"
