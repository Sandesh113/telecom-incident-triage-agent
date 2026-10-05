"""Load a validated bundle. Mark the incident ready last; never publish an event here."""
import argparse
import json
from pathlib import Path

from store import open_store
from .contract import Bundle, ready_event


def load_bundle(store, bundle: Bundle) -> dict:
    run = str(bundle.incident.run_id)
    incident = bundle.incident.model_dump(mode="json")
    if store.query(run, "incidents"):
        raise ValueError("run already contains an incident; choose a new UUID")
    store.put(run, "incidents", incident["incident_id"], {**incident, "status": "loading"})
    for name in ("events_normalized", "observations", "kpi_windows", "changes", "impact_records"):
        for record in getattr(bundle, name):
            doc = record.model_dump(mode="json")
            key = doc.get("event_id") or doc["evidence_id"]
            store.put(run, name, key, doc)
    store.put(run, "incidents", incident["incident_id"], {**incident, "status": "ready"})
    return ready_event(bundle.incident)


def main():
    parser = argparse.ArgumentParser(description="Load normalized evidence; no alarm normalization or event publication")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--storage", choices=["sqlite", "dynamodb"], default="sqlite")
    parser.add_argument("--sqlite", default="runs/investigation.sqlite")
    parser.add_argument("--table", default="sop-rca-evidence")
    args = parser.parse_args()
    bundle = Bundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    options = {"path": args.sqlite} if args.storage == "sqlite" else {"table_name": args.table}
    store = open_store(args.storage, **options)
    try:
        event = load_bundle(store, bundle)
        print(json.dumps(event, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
