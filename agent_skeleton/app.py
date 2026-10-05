"""Walking-skeleton agent for AgentCore Runtime.

Purpose: prove the AWS plumbing end to end BEFORE the real triage agent exists.
  EventBridge -> Lambda shim -> AgentCore Runtime (this container)
    -> read SKILL.md from the skill bucket
    -> one small Bedrock call through Strands
    -> write a report JSON to s3://DATA_BUCKET/reports/
    -> publish a short notice to SNS
It does NOT do triage. Phase 5 (agent/runtime.py) replaces it.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("skeleton")

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
SKILL_BUCKET = os.environ["SKILL_BUCKET"]
DATA_BUCKET = os.environ["DATA_BUCKET"]
REPORTS_PREFIX = os.environ.get("REPORTS_PREFIX", "reports/")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

s3 = boto3.client("s3")
sns = boto3.client("sns")
app = BedrockAgentCoreApp()


def load_skill() -> str:
    """Read SKILL.md; tolerate its absence so the skeleton runs before knowledge is synced."""
    try:
        obj = s3.get_object(Bucket=SKILL_BUCKET, Key="SKILL.md")
        return obj["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        log.warning("SKILL.md not in %s yet", SKILL_BUCKET)
        return ""


@app.entrypoint
def invoke(payload):
    incident_id = payload.get("incident_id", "unknown")
    run_id = payload.get("run_id") or "no-run-id"
    skill = load_skill()

    agent = Agent(
        model=BedrockModel(model_id=MODEL_ID, max_tokens=200),
        system_prompt="You are a smoke-test responder. Reply in one short sentence.",
    )
    reply = str(agent(f"Confirm you received incident {incident_id}. SKILL.md loaded: {bool(skill)}."))

    report = {
        "kind": "skeleton-smoke-test",
        "incident_id": incident_id,
        "run_id": run_id,
        "model_id": MODEL_ID,
        "skill_loaded": bool(skill),
        "skill_chars": len(skill),
        "model_reply": reply.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    key = f"{REPORTS_PREFIX}{incident_id}/{run_id}.json"
    s3.put_object(Bucket=DATA_BUCKET, Key=key, Body=json.dumps(report, indent=2).encode("utf-8"),
                  ContentType="application/json")

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"[sop-rca] Skeleton report {incident_id}"[:100],
        Message=f"Report written to s3://{DATA_BUCKET}/{key}\n\n{json.dumps(report, indent=2)}",
    )
    log.info("Wrote %s", key)
    return {"status": "ok", "report_key": key}


if __name__ == "__main__":
    app.run()
