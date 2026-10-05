#!/usr/bin/env bash
# B7 — Publish one incident.ready event to the custom bus (end-to-end smoke test).
# Usage: bash scripts/send_test_event.sh [incident_id] [loaded_run_id]
source "$(dirname "$0")/_common.sh"

INCIDENT_ID="${1:-INC-SMOKE-0001}"
RUN_ID="${2:-$("$PY" -c 'import uuid; print(uuid.uuid4())')}"
BUS="$(tf_out event_bus_name)"

DETAIL=$("$PY" -c 'import json,re,sys,uuid; incident,run=sys.argv[1:]; assert re.fullmatch(r"[A-Za-z0-9_-]+",incident), "Invalid incident ID"; print(json.dumps({"incident_id":incident,"run_id":str(uuid.UUID(run)),"previous_report_key":None}))' "$INCIDENT_ID" "$RUN_ID")
ENTRIES=$("$PY" -c 'import json,sys; print(json.dumps([{"EventBusName":sys.argv[1],"Source":"sop-rca.enrichment","DetailType":"incident.ready","Detail":sys.argv[2]}]))' "$BUS" "$DETAIL")

aws events put-events --entries "$ENTRIES"
echo "Sent incident_id=$INCIDENT_ID run_id=$RUN_ID"
echo "Watch:  aws logs tail /aws/lambda/sop-rca-invoke-agent --follow"
echo "Report: aws s3 ls s3://$(tf_out data_bucket)/reports/ --recursive"
