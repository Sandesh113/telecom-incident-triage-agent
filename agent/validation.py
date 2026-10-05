"""Deterministic checks, including the approved static-reference citation deviation.

These checks establish structural consistency, not truth of model reasoning.
"""
import copy
import re

from evidence.contract import utc

from .schema import Report


def guard(report):
    report = copy.deepcopy(report)
    overrides = []
    for action in report["proposed_actions"]:
        required = action["type"] == "change"
        if action["requires_approval"] != required:
            overrides.append(f"requires_approval corrected for {action['target_object']}")
        action["requires_approval"] = required
    return Report.model_validate(report).model_dump(mode="json"), overrides


def validate(report, tools):
    errors = []
    report = Report.model_validate(report).model_dump(mode="json")
    incident = tools.incident
    records = [r for c in ("events_normalized", "observations", "kpi_windows", "changes", "impact_records") for r in tools.rows(c)]
    ids = {r.get("event_id") or r["evidence_id"]: r for r in records}
    traces = [t for t in tools.trace if "error" not in t]
    seen = {i for t in traces for i in t["evidence_ids"]}
    read = {t["arguments"]["node_id"] for t in traces if t["tool"] == "read_section"}
    # Reading a document node returns its children too.
    for node in list(read):
        text = tools.knowledge.read_section(node)
        read.update(re.findall(r"^#{1,3} \[([A-Z0-9.\-]+)\]", text, re.M))
    hypotheses = {h["hypothesis_id"]: h for h in report["hypotheses"]}
    if len(hypotheses) != len(report["hypotheses"]):
        errors.append("duplicate hypothesis IDs")
    known_objects = set(incident.affected_objects)
    for r in records:
        known_objects.update(r[k] for k in ("object_id", "reporting_object_id", "target_object_id") if r.get(k))
    for h in hypotheses.values():
        if h["cause_object"] not in known_objects:
            errors.append(f"unknown cause object {h['cause_object']}")
        for eid in h["supporting_event_ids"] + h["conflicting_event_ids"]:
            if eid not in ids or eid not in seen:
                errors.append(f"evidence {eid} absent or not retrieved")
        for kid in h["knowledge_ids"]:
            if kid not in tools.knowledge.nodes or kid not in read:
                errors.append(f"knowledge {kid} absent or not read")
        if h["status"] == "supported":
            if not h["supporting_event_ids"]:
                errors.append(f"{h['hypothesis_id']} supported without evidence")
            required = {"REF-TX.1"} if h["mechanism"] == "transport_link_flap" else (
                {"REF-RAN.4"} if h["mechanism"].startswith("rf_") else {"REF-CORE.5", "REF-CORE.6"})
            if not required.intersection(h["knowledge_ids"]):
                errors.append(f"{h['hypothesis_id']} needs a relationship citation from {sorted(required)}")
    if set(report["affected_objects"]) != set(incident.affected_objects) or len(report["affected_objects"]) != len(incident.affected_objects):
        errors.append("affected_objects must exactly match incident metadata")
    attrs = report["attribution"]
    if len(attrs) != len(incident.affected_objects) or {a["object_id"] for a in attrs} != set(incident.affected_objects):
        errors.append("each affected object needs exactly one attribution")
    for a in attrs:
        if len(set(a["hypothesis_ids"])) != len(a["hypothesis_ids"]):
            errors.append("duplicate attributed hypothesis")
        for hid in a["hypothesis_ids"]:
            if hid not in hypotheses:
                errors.append(f"unknown hypothesis {hid}")
        if a["state"] in ("single", "multiple"):
            if (a["state"] == "single" and len(a["hypothesis_ids"]) != 1) or (a["state"] == "multiple" and len(a["hypothesis_ids"]) < 2):
                errors.append("attribution state/count mismatch")
            for hid in a["hypothesis_ids"]:
                h = hypotheses.get(hid, {})
                if h.get("status") != "supported" or not set(a["event_ids"]).intersection(h.get("supporting_event_ids", [])):
                    errors.append(f"{a['object_id']} lacks evidence for {hid}")
            symptoms = [utc(r["event_time"]) for r in records if r.get("object_id") == a["object_id"] and r.get("kind") == "service_outcome" and r.get("values", {}).get("outcome") == "degraded"]
            for hid in a["hypothesis_ids"]:
                support = [utc(ids[e]["event_time"]) for e in hypotheses.get(hid, {}).get("supporting_event_ids", []) if e in ids and ids[e].get("event_time")]
                if support and symptoms and min(support) > min(symptoms):
                    errors.append("supporting evidence follows symptom onset")
        for eid in a["event_ids"]:
            if eid not in ids or eid not in seen:
                errors.append(f"invalid attribution evidence {eid}")
    if set(report["unexplained_objects"]) != {a["object_id"] for a in attrs if a["state"] == "unexplained"}:
        errors.append("unexplained list differs from attribution")
    events = tools.rows("events_normalized")
    flags = set(incident.flags) | {f for r in events for f in r["flags"]}
    if not flags.issubset(report["routing"]["flags"]):
        errors.append("incident flags dropped")
    triggers = {r["routing_trigger"] for r in events if r["routing_role"] == "route"}
    if set(report["routing"]["triggers"]) != triggers:
        errors.append("routing triggers differ from enriched events")
    if report["routing"]["routing_gap"] != (not triggers):
        errors.append("routing_gap differs from evidence")
    if set(report["routing"]["context_event_ids"]) != {r["event_id"] for r in events if r["routing_role"] == "context"}:
        errors.append("context event list differs from evidence")
    routing = {"N7_TIMEOUT": "SOP-01", "PCF_POLICY_REQUEST_FAILURE": "SOP-01", "PCF_UNREACHABLE": "SOP-01", "VOICE_SETUP_FAILURE_RISE": "SOP-01",
               "HSS_UNREACHABLE": "SOP-02", "UDM_UNREACHABLE": "SOP-02", "SUBSCRIBER_DATA_TIMEOUT": "SOP-02", "REGISTRATION_FAILURE_RISE": "SOP-02", "AUTHENTICATION_FAILURE_RISE": "SOP-02",
               "LINK_DOWN": "SOP-03", "LINK_UP": "SOP-03", "TRANSPORT_LINK_FLAP": "SOP-03", "SOP04_ELIGIBLE": "SOP-04",
               "CNE_INCIDENT": "SOP-05", "CALL_DROP_RISE": "SOP-05", "CUSTOMER_COMPLAINT": "SOP-05"}
    selected = {routing[t] for t in triggers if t in routing}
    if not selected.issubset(report["routing"]["triggered_sops"]):
        errors.append("a triggered SOP was dropped")
    for sop in selected:
        required_steps = {n for n in tools.knowledge.nodes if re.fullmatch(re.escape(sop) + r"\.\d+", n)}
        if not required_steps.issubset({s["step_id"] for s in report["sop_steps"]}):
            errors.append(f"required steps missing for {sop}")
    for step in report["sop_steps"]:
        if step["step_id"] not in read:
            errors.append(f"SOP step not read: {step['step_id']}")
        for eid in step["event_ids"]:
            if eid not in ids or eid not in seen:
                errors.append(f"invalid step evidence {eid}")
        # A complete, empty change query has no record IDs to cite. Retain the
        # actual query audit rather than requiring fabricated IDs/missing data.
        complete_empty_changes = step["step_id"] == "SOP-03.4" and any(
            t["tool"] == "get_changes" and t.get("availability") == "known_empty" and
            set(incident.affected_objects).issubset(t["arguments"]["object_ids"])
            for t in traces)
        if not step["event_ids"] and not step["missing_fields"] and not complete_empty_changes:
            errors.append(f"{step['step_id']} needs evidence or missing_fields")
        for a in step["assessments"]:
            if a["hypothesis_id"] not in hypotheses:
                errors.append("step assessment refers to unknown hypothesis")
    for control in report["controls_used"]:
        if "REF-TX.1" not in read or set(control["qualified_by"]) != {"not_on_affected_path", "no_shared_upstream", "no_rf_exposure"}:
            errors.append("control lacks reference citation/qualification reasons")
    impact_reads = [t for t in traces if t["tool"] == "get_customer_impact"]
    if not impact_reads:
        errors.append("customer impact was never retrieved")
    else:
        start, end = report["impact"]["window_start"], report["impact"]["window_end"]
        if utc(end) - utc(start) != __import__('datetime').timedelta(minutes=15):
            errors.append("impact window must be 15 minutes")
        rows = [r for r in tools.rows("impact_records") if utc(start) <= utc(r["event_time"]) < utc(end)]
        complete = tools.complete("impact_records", tools.window({"start": start, "end": end}))
        customers = len({r["customer_id"] for r in rows}) if complete else None
        enterprises = len({r["enterprise_id"] for r in rows if r.get("enterprise_id")}) if complete else None
        level = ("severe" if customers >= 500 or enterprises >= 2 else "significant" if customers >= 100 or enterprises else "below_tiers") if complete else "impact_tier_unknown"
        if (customers, enterprises, level) != (report["impact"]["distinct_customers"], report["impact"]["distinct_enterprise_customers"], report["impact"]["level"]):
            errors.append("impact counts/tier do not match evidence")
        if level in ("severe", "significant") and not report["escalation"]["required"]:
            errors.append("impact requires escalation")
    if set(report["late_events"]) != {r["event_id"] for r in events if r["late_event"]}:
        errors.append("late event list differs from evidence")
    for kid in report["escalation"]["rule_ids"]:
        if kid not in tools.knowledge.nodes or kid not in read:
            errors.append(f"escalation citation absent or not read: {kid}")
    if "transition_observability_incomplete" in flags:
        steps = [s for s in report["sop_steps"] if s["step_id"] == "SOP-03.1"]
        if not steps or steps[0]["outcome"] != "unable_to_check":
            errors.append("unobservable transitions require unable_to_check")
    if "subscriber_function_unknown" in flags:
        unknown = {r["event_id"] for r in events if "subscriber_function_unknown" in r["flags"]}
        for h in hypotheses.values():
            if h["mechanism"] == "udm_function_fault" or h["cause_object"].startswith(("HSS", "UDM")):
                if unknown.intersection(h["supporting_event_ids"]):
                    errors.append("unknown subscriber event attributed to named function")
    if tools.calls > tools.budget:
        errors.append("tool budget exceeded")
    for action in report["proposed_actions"]:
        if action not in tools.proposals:
            errors.append("action was not registered through propose_action")
    return sorted(set(errors))


def version_report(report, previous=None):
    if previous is None:
        report["report_version"], report["supersedes"] = 1, None
        return
    def material(r):
        return (sorted((h["cause_object"], h["mechanism"], h["status"]) for h in r["hypotheses"]),
                sorted((a["object_id"], a["state"]) for a in r["attribution"]), r["impact"]["level"], r["escalation"])
    changed = material(report) != material(previous)
    report["report_version"] = previous["report_version"] + int(changed)
    report["supersedes"] = previous["report_version"] if changed else previous.get("supersedes")
