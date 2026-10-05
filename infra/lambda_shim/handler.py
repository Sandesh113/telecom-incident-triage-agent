"""EventBridge -> AgentCore Runtime shim.

EventBridge delivers an `incident.ready` event; this function forwards its `detail`
to the triage agent with InvokeAgentRuntime and logs the outcome.
It holds no business logic: the agent writes the report to S3 and publishes to SNS.
"""

import json
import logging
import os
import uuid

import boto3
from botocore.config import Config

log = logging.getLogger()
log.setLevel(logging.INFO)

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
# Investigations can exceed the SDK's 60-second default. A retry can execute
# the agent again and publish a duplicate notification after the first succeeds.
client = boto3.client("bedrock-agentcore", config=Config(
    connect_timeout=10, read_timeout=870,
    retries={"total_max_attempts": 1, "mode": "standard"},
))


def lambda_handler(event, context):
    detail = event.get("detail", {})
    incident_id = detail.get("incident_id")
    if not incident_id:
        log.error("Event has no detail.incident_id; dropping: %s", json.dumps(event))
        return {"status": "rejected", "reason": "missing incident_id"}

    # runtimeSessionId must be 33-256 chars. A fresh UUID per run keeps runs isolated.
    session_id = f"{incident_id}-{uuid.uuid4()}"[:256]
    if len(session_id) < 33:
        session_id = session_id.ljust(33, "0")

    payload = {
        "incident_id": incident_id,
        "run_id": detail.get("run_id"),
        "previous_report_key": detail.get("previous_report_key"),
        "event_id": event.get("id"),
    }

    log.info("Invoking agent: incident=%s session=%s", incident_id, session_id)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode("utf-8"),
    )

    # The response body is a stream; read it fully so the run completes and we can log it.
    stream = resp["response"]
    try:
        body = stream.read().decode("utf-8", errors="replace")
    finally:
        stream.close()
    log.info("Agent finished: status=%s body=%s", resp.get("statusCode"), body[:2000])
    return {"status": "ok", "session_id": session_id}
