"""Dictionary-driven transport alarm replay with the deployed incident contract.

This implements LINK_DOWN/UP only, not the full enrichment specification.
"""
import argparse
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from evidence.contract import Bundle, Event, utc
from evidence.demo import demo_bundle
from evidence.load import load_bundle
from store import open_store

ROOT = Path(__file__).resolve().parents[1]


def dictionary(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if str(data["dictionary_version"]) != "0.2":
        raise ValueError("transport adapter requires dictionary 0.2")
    return data


def canonical(value, rules):
    for entry in rules["explicit"]:
        if value == entry["alias"]:
            return entry["canonical"]
    for entry in rules["patterns"]:
        match = re.fullmatch(entry["pattern"], value)
        if not match:
            continue
        groups = match.groupdict()
        for name, transforms in entry.get("transforms", {}).items():
            for transform in transforms:
                if transform == "int":
                    groups[name] = str(int(groups[name]))
                elif transform == "zero_pad_2":
                    groups[name] = groups[name].zfill(2)
                elif transform in ("upper", "lower"):
                    groups[name] = getattr(groups[name], transform)()
                else:
                    raise ValueError("unsupported alias transform")
        return entry["template"].format(**groups)
    if value == "LINK-1":
        return value
    raise ValueError(f"unresolved or unsupported demo object: {value}")


def normalize(records, mapping):
    """Raw records plus replay ingest headers -> typed events and ingestion audit."""
    down = next(m for m in mapping["mappings"] if m["event_type"] == "LINK_DOWN")
    up = next(m for m in mapping["mappings"] if m["event_type"] == "LINK_UP")
    explicit_up = next(p["vendor_b_explicit"] for p in up["produced_by"] if isinstance(p, dict))
    output, seen, duplicates = [], {}, []
    for envelope in records:
        vendor, raw = envelope["source_system"], envelope["record"]
        if vendor not in ("vendor_a", "vendor_b"):
            raise ValueError("unsupported source")
        source = mapping["sources"][vendor]
        fields = source["fields"]
        state = source["state_map"][raw[fields["state"]]]
        name = raw[fields["raw_name"]]
        types = [t for t, names in down["raw_names_by_object_type"].items() if name in names.get(vendor, [])]
        if types:
            object_type = types[0]
            kind = "LINK_UP" if state == "cleared" else "LINK_DOWN"
        elif vendor == "vendor_b" and name in explicit_up:
            object_type = dict(zip(explicit_up, ("port", "bfd_session", "lag_member", "aggregate_link")))[name]
            kind = "LINK_UP"
        else:
            raise ValueError(f"unsupported alarm retained in raw capture: {vendor}/{name}")
        target = canonical(raw[fields["target_object"]], mapping["aliases"])
        reporting = canonical(raw[fields["reporting_object"]], mapping["aliases"])
        if target != "LINK-1" or object_type != "aggregate_link":
            raise ValueError("this evidence preset supports LINK-1 aggregate alarms only")
        value = raw[fields["event_time"]]
        time = (datetime.fromtimestamp(value / 1000, timezone.utc) if vendor == "vendor_b"
                else datetime.fromisoformat(value.replace("Z", "+00:00")))
        if time.tzinfo is None:
            raise ValueError("raw timestamp needs a timezone")
        time = time.astimezone(timezone.utc).isoformat()
        prefix = "A" if vendor == "vendor_a" else "B"
        event_id = prefix + ":" + str(raw[fields["notification_id"]])
        lifecycle = prefix + ":" + str(raw[fields["alarm_id"]])
        provenance = {"record": copy.deepcopy(raw), "alarm_id": lifecycle,
                      "severity": source["severity_map"][raw[fields["severity"]]],
                      "synthetic": True}
        event = Event(event_id=event_id, event_time=time, ingest_time=envelope["ingest_time"],
                      source_system=vendor, event_type=kind, reporting_object_id=reporting,
                      target_object_id=target, target_object_type=object_type,
                      routing_trigger=kind, routing_role="route", alarm_state=state,
                      resulting_state="down" if kind == "LINK_DOWN" else "up",
                      late_event=utc(envelope["ingest_time"]) - utc(time) > timedelta(minutes=5), raw=provenance)
        if event_id in seen:
            if event.model_dump() != seen[event_id].model_dump():
                raise ValueError("conflicting payloads for the same notification ID")
            duplicates.append(event_id)
            continue
        seen[event_id] = event
        output.append(event)
    output.sort(key=lambda e: (utc(e.event_time), e.event_id))
    tolerance = timedelta(seconds=up["dedup_rule"]["time_tolerance_seconds"])
    for index, event in enumerate(output):
        if event.resulting_state != "up":
            continue
        prior = [p for p in output[:index] if p.resulting_state == "up" and
                 p.target_object_id == event.target_object_id and p.target_object_type == event.target_object_type and
                 utc(event.event_time) - utc(p.event_time) <= tolerance and not p.transition_duplicate_of]
        if prior:
            preferred = next((p for p in prior if p.raw["alarm_id"] == event.raw["alarm_id"]), prior[0])
            event.transition_duplicate_of = preferred.event_id
    return output, {"raw_notifications": len(records), "normalized_events": len(output),
                    "duplicate_notifications": duplicates,
                    "duplicate_transitions": [e.event_id for e in output if e.transition_duplicate_of]}


def alarm_feed(start, vendor="mixed", cycles=3):
    records = []
    for cycle in range(cycles):
        source = ("vendor_a" if cycle % 2 == 0 else "vendor_b") if vendor == "mixed" else vendor
        for offset, state in ((0, "raised"), (1, "cleared")):
            event_time = start + timedelta(minutes=cycle * 2 + offset)
            notification = f"link-cycle-{cycle}-{state}"
            if source == "vendor_a":
                raw = {"notificationId": notification, "alarmId": f"link-cycle-{cycle}",
                       "specificProblem": "LAG down", "managedObject": "lnk-01", "affectedObject": "lnk-01",
                       "perceivedSeverity": "major", "notificationType": state, "eventTime": event_time.isoformat()}
            else:
                raw = {"evt": notification, "aid": f"link-cycle-{cycle}", "code": "LAG-DOWN",
                       "node": "lnk-01", "peer": "lnk-01", "sev": 4,
                       "state": "ACTIVE" if state == "raised" else "CLEARED",
                       "ts": int(event_time.timestamp() * 1000)}
            records.append({"source_system": source, "ingest_time": (event_time + timedelta(seconds=1)).isoformat(),
                            "record": raw})
    return records


def telemetry_bundle(events, start):
    # Reuse independently curated measurements from the verified transport demo.
    # Its pre-normalized alarms are discarded; incident events come solely from the feed.
    template = demo_bundle().model_dump(mode="json")
    delta = start - utc(template["incident"]["window"]["start"])
    def shift(value):
        return (utc(value) + delta).isoformat()
    for collection in ("observations", "kpi_windows", "impact_records"):
        for record in template[collection]:
            if "event_time" in record:
                record["event_time"] = shift(record["event_time"])
            if "window" in record:
                record["window"] = {k: shift(v) for k, v in record["window"].items()}
    template["incident"]["incident_id"] = "INC-" + uuid4().hex[:12]
    template["incident"]["run_id"] = str(uuid4())
    template["incident"]["window"] = {"start": start.isoformat(), "end": (start + timedelta(minutes=15)).isoformat()}
    template["events_normalized"] = [e.model_dump(mode="json") for e in events]
    return Bundle.model_validate(template)


def main():
    parser = argparse.ArgumentParser(description="Replay synthetic LINK-1 alarms through the existing pipeline")
    parser.add_argument("--vendor", choices=["mixed", "vendor_a", "vendor_b"], default="mixed")
    parser.add_argument("--cycles", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--start-time", help="UTC event-clock start; default is 15 minutes before now")
    parser.add_argument("--dictionary", type=Path, default=ROOT / "simulator" / "data" / "alarms.yaml")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--aws", action="store_true", help="Load the existing table and publish incident.ready")
    parser.add_argument("--profile", default="default")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--table", default="sop-rca-evidence")
    parser.add_argument("--bus", default="sop-rca-incidents")
    args = parser.parse_args()
    start = utc(args.start_time) if args.start_time else datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=15)
    output = args.output_dir or ROOT / "runs" / "alarm-replays" / str(uuid4())
    output = output.resolve()
    if not output.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("replay files must stay in private runs/, never knowledge or the deployment package")
    output.mkdir(parents=True, exist_ok=False)
    feed = alarm_feed(start, args.vendor, args.cycles)
    (output / "raw-alarms.json").write_text(json.dumps(feed, indent=2), encoding="utf-8")
    events, audit = normalize(feed, dictionary(args.dictionary))
    bundle = telemetry_bundle(events, start)
    (output / "bundle.json").write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    (output / "ingestion-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if args.aws:
        import boto3
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        if session.client("sts").get_caller_identity()["Account"] != "270293010572":
            raise ValueError("AWS account differs from the approved PoC account")
        resource = session.resource("dynamodb")
        table = resource.Table(args.table)
        tags = resource.meta.client.list_tags_of_resource(ResourceArn=table.table_arn)["Tags"]
        events_client = session.client("events")
        bus = events_client.describe_event_bus(Name=args.bus)
        bus_tags = events_client.list_tags_for_resource(ResourceARN=bus["Arn"])["Tags"]
        for name, entries in (("table", tags), ("event bus", bus_tags)):
            if {t["Key"]: t["Value"] for t in entries}.get("project") != "sop-rca":
                raise ValueError(f"{name} is outside the sop-rca project")
        store = open_store("dynamodb", resource=resource, table_name=args.table)
    else:
        store = open_store("sqlite", path=output / "evidence.sqlite")
    try:
        event = load_bundle(store, bundle)
    finally:
        store.close()
    (output / "ready-event.json").write_text(json.dumps(event, indent=2), encoding="utf-8")
    if args.aws:
        entry = {**event, "EventBusName": args.bus, "Detail": json.dumps(event["Detail"])}
        result = events_client.put_events(Entries=[entry])
        (output / "eventbridge-result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        if result["FailedEntryCount"]:
            raise RuntimeError("EventBridge rejected the event; receipt saved, evidence remains ready")
    print(json.dumps({"output_dir": str(output), "mode": "aws" if args.aws else "local", **event["Detail"], **audit}, indent=2))


if __name__ == "__main__":
    main()
