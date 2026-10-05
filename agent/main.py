"""AgentCore adapter for the investigation agent. Local edits do not deploy this file."""
import json
import logging
import os
import re
from uuid import UUID

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent.knowledge import Knowledge
from agent.runtime import investigate
from store import open_store

app = BedrockAgentCoreApp()
log = logging.getLogger(__name__)


def notification_message(output, data_bucket, key):
    """Inline investigation JSON, without the large internal tool/attempt traces."""
    header = (f"Synthetic/provisional: {output['synthetic']} / {output['provisional']}\n"
              f"Status: {output['status']}\nReport: s3://{data_bucket}/{key}\n"
              "Suspected causes only. Proposed changes require engineer approval.\n\n")
    content = {k: output[k] for k in ("incident_id", "run_id", "synthetic", "provisional", "status")}
    content.update({"created_at": output.get("created_at"),
                    "validation_errors": output.get("validation_errors", []), "report": output.get("report")})
    for indent in (2, None):
        message = header + "Investigation report JSON:\n" + json.dumps(content, indent=indent, default=str)
        if len(message.encode("utf-8")) <= 262144:
            return message, True
    return header + "Report JSON exceeds the email message limit; the complete report is stored at the S3 location above.", False


def publish(output, s3, sns, data_bucket, topic):
    """Reports go to S3; SNS includes the investigation JSON and pointer."""
    UUID(output["run_id"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", output["incident_id"]):
        raise ValueError("invalid incident ID")
    key = f"reports/{output['incident_id']}/{output['run_id']}.json"
    s3.put_object(Bucket=data_bucket, Key=key, Body=json.dumps(output, indent=2, default=str).encode(),
                  ContentType="application/json")
    message, included = notification_message(output, data_bucket, key)
    receipt = sns.publish(TopicArn=topic, Subject=f"[sop-rca] Investigation {output['incident_id']}"[:100],
                          Message=message)
    log.info("SNS publish accepted: message_id=%s report_json_included=%s message_bytes=%s",
             receipt["MessageId"], included, len(message.encode("utf-8")))
    return key


@app.entrypoint
def invoke(payload):
    """Accept a ready incident pointer; fetch evidence through the read-only store."""
    import boto3
    from strands.models import BedrockModel
    run_id = str(UUID(payload["run_id"]))
    incident_id = payload["incident_id"]
    session = boto3.Session(region_name=os.environ.get("AWS_REGION", "eu-north-1"))
    s3 = session.client("s3")
    sns = session.client("sns")
    store = open_store("dynamodb", resource=session.resource("dynamodb"),
                       table_name=os.environ["EVIDENCE_TABLE_NAME"], read_only=True)
    try:
        knowledge = Knowledge.s3(s3, os.environ["SKILL_BUCKET"])
        model = BedrockModel(model_id=os.environ["BEDROCK_MODEL_ID"], max_tokens=6000, boto_session=session)
        if payload.get("previous_report_key"):
            raise ValueError("rerun report retrieval is not enabled in this deployment candidate")
        output = investigate(store, knowledge, run_id, incident_id, model=model)
        key = publish(output, s3, sns, os.environ["DATA_BUCKET"], os.environ["SNS_TOPIC_ARN"])
        return {"status": output["status"], "report_key": key}
    finally:
        store.close()


if __name__ == "__main__":
    app.run()
