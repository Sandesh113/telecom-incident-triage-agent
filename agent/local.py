"""Run the actual Strands agent locally. Bedrock is the only remote operation."""
import argparse
import json
from pathlib import Path

from evidence.contract import Bundle
from evidence.load import load_bundle
from store import open_store
from .knowledge import Knowledge
from .runtime import investigate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, default=Path("runs/investigation.json"))
    parser.add_argument("--profile", default="default")
    parser.add_argument("--region", default="eu-north-1")
    args = parser.parse_args()
    import boto3
    from strands.models import BedrockModel
    bundle = Bundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    store = open_store("sqlite", path=":memory:")
    load_bundle(store, bundle)
    model = BedrockModel(model_id="eu.anthropic.claude-sonnet-4-5-20250929-v1:0", max_tokens=6000,
                         boto_session=boto3.Session(profile_name=args.profile, region_name=args.region))
    try:
        output = investigate(store, Knowledge.local(Path(__file__).resolve().parents[1] / "knowledge"),
                             str(bundle.incident.run_id), bundle.incident.incident_id, model=model)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"output": str(args.output), "status": output["status"],
                          "tool_calls": len(output["tool_trace"]), "validation_errors": output["validation_errors"],
                          "latency_seconds": output["latency_seconds"]}, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
