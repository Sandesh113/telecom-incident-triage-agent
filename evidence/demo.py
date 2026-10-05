"""Curated synthetic observations, not an S1–S8 compiler or an expected-answer fixture."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from .contract import Bundle


def demo_bundle() -> Bundle:
    records = []
    for i, state in enumerate(("down", "up", "down", "up", "down", "up")):
        time = f"2026-10-04T10:0{i}:00Z"
        records.append({"event_id": f"A:link-{i}", "event_time": time, "ingest_time": time,
                        "source_system": "vendor_a", "event_type": "LINK_" + state.upper(),
                        "reporting_object_id": "LINK-1", "target_object_id": "LINK-1",
                        "target_object_type": "aggregate_link", "routing_trigger": "LINK_" + state.upper(),
                        "routing_role": "route", "resulting_state": state,
                        "raw": {"synthetic": True, "notificationId": f"link-{i}"}})
    kpis = []
    for cell, failures in (("CELL-A", 18), ("CELL-B", 16), ("CELL-E", 1), ("CELL-F", 1)):
        for label, start, end, count in (("before", "09:45", "10:00", 1), ("after", "10:00", "10:15", failures)):
            kpis.append({"evidence_id": f"KPI:{cell}:{label}", "object_id": cell, "kpi": "call_drop",
                         "window": {"start": f"2026-10-04T{start}:00Z", "end": f"2026-10-04T{end}:00Z"},
                         "attempts": 200, "failures": count})
    observations = [{"evidence_id": "OBS:link-prior", "object_id": "LINK-1",
                     "event_time": "2026-10-04T09:59:00Z", "kind": "link_state", "values": {"state": "up"}}]
    for cell in ("CELL-A", "CELL-B", "CELL-E", "CELL-F"):
        observations.append({"evidence_id": f"OBS:{cell}:outcome", "object_id": cell,
                             "event_time": "2026-10-04T10:06:00Z", "kind": "service_outcome",
                             "values": {"outcome": "degraded" if cell in ("CELL-A", "CELL-B") else "stable",
                                        "no_shared_upstream": cell in ("CELL-E", "CELL-F"),
                                        "no_rf_exposure": True, "synthetic": True}})
    impacts = [{"evidence_id": f"IMP:{i:03d}", "customer_id": f"CUST-{i:03d}",
                "object_id": "CELL-A" if i % 2 else "CELL-B", "event_time": "2026-10-04T10:06:00Z"}
               for i in range(1, 121)]
    return Bundle.model_validate({"incident": {"incident_id": "INC-" + uuid4().hex[:12],
            "run_id": str(uuid4()), "window": {"start": "2026-10-04T10:00:00Z", "end": "2026-10-04T10:15:00Z"},
            "affected_objects": ["CELL-A", "CELL-B"], "synthetic": True,
            "evidence_complete": {"changes": True, "impact_records": True, "events_normalized": True}},
            "events_normalized": records, "observations": observations, "kpi_windows": kpis,
            "changes": [], "impact_records": impacts})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("runs/demo-incident.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(demo_bundle().model_dump(mode="json"), indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
