import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.knowledge import Knowledge
from agent.tools import InvestigationTools, ToolBudgetExceeded
from agent.validation import guard, validate, version_report
from evidence.contract import Bundle
from evidence.demo import demo_bundle
from evidence.load import load_bundle
from store import StoreError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def investigation(store):
    bundle = demo_bundle()
    event = load_bundle(store, bundle)
    tools = InvestigationTools(store, Knowledge.local(ROOT / "knowledge"),
                               str(bundle.incident.run_id), bundle.incident.incident_id)
    return bundle, tools, event


def read_evidence(tools):
    tools.get_incident_events(tools.incident.incident_id)
    for node in ["ROUTING"] + [f"RULES.{i}" for i in range(1, 10)] + ["SOP-03", "REF-TX.1", "REF-TX.2"]:
        tools.read_section(node)
    tools.get_link_events("LINK-1")
    tools.get_changes(["CELL-A", "CELL-B", "CELL-E", "CELL-F"])
    for cell in ("CELL-A", "CELL-B", "CELL-E", "CELL-F"):
        tools.get_kpis(cell)
    tools.get_customer_impact(tools.incident.incident_id)


def draft(tools):
    """Handwritten report for validator tests ONLY; never passed to the production model."""
    read_evidence(tools)
    event_ids = [r["event_id"] for r in tools.rows("events_normalized")]
    return {"report_version": 1, "supersedes": None, "late_events": [], "affected_objects": ["CELL-A", "CELL-B"],
            "routing": {"triggers": ["LINK_DOWN", "LINK_UP"], "triggered_sops": ["SOP-03"], "added_sops": [], "context_event_ids": [], "flags": [], "routing_gap": False},
            "hypotheses": [{"hypothesis_id": "H1", "cause_object": "LINK-1", "mechanism": "transport_link_flap",
                            "cause": "Suspected link flap", "status": "supported", "supporting_event_ids": event_ids,
                            "conflicting_event_ids": [], "knowledge_ids": ["SOP-03.1", "REF-TX.1", "REF-TX.2"]}],
            "sop_steps": [{"step_id": f"SOP-03.{i}", "observation": "Test observation", "event_ids": event_ids,
                           "metrics": {"transitions_counted": 6} if i == 1 else {},
                           "outcome": "continuing_flap" if i == 1 else None, "missing_fields": [],
                           "assessments": [{"hypothesis_id": "H1", "result": "supports", "explanation": "Test assessment"}]} for i in range(1, 5)],
            "controls_used": [], "unexplained_objects": [],
            "attribution": [{"object_id": cell, "state": "single", "hypothesis_ids": ["H1"], "event_ids": event_ids} for cell in ("CELL-A", "CELL-B")],
            "impact": {"window_start": tools.incident.window.start, "window_end": tools.incident.window.end,
                       "distinct_customers": 120, "distinct_enterprise_customers": 0, "level": "significant"},
            "escalation": {"required": True, "reasons": ["Customer impact"], "rule_ids": ["RULES.5"]}, "proposed_actions": []}


def test_contract_and_backend_roundtrip(investigation):
    bundle, tools, event = investigation
    assert event["Detail"]["run_id"] == str(bundle.incident.run_id)
    assert len(tools.rows("impact_records")) == 120
    assert tools.get_link_events("LINK-1")["transitions_counted"] == 6
    assert tools.get_customer_impact(bundle.incident.incident_id)["level"] == "significant"
    assert tools.get_changes(["CELL-A"])["availability"] == "known_empty"


def test_evidence_reads_on_strands_worker_thread(investigation):
    from concurrent.futures import ThreadPoolExecutor
    bundle, tools, _ = investigation
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(tools.get_incident_events, bundle.incident.incident_id).result()
    assert result["evidence_ids"]


def test_wider_window_does_not_claim_complete_evidence(investigation):
    bundle, tools, _ = investigation
    wider = {"start": "2026-10-04T09:45:00Z", "end": bundle.incident.window.end}
    assert tools.get_changes(["CELL-A"], wider)["availability"] == "unavailable"
    assert tools.get_customer_impact(bundle.incident.incident_id, wider)["level"] == "impact_tier_unknown"


def test_complete_empty_change_query_can_support_empty_step(investigation):
    _, tools, _ = investigation
    report = draft(tools)
    step = next(s for s in report["sop_steps"] if s["step_id"] == "SOP-03.4")
    step["event_ids"] = []
    assert validate(report, tools) == []
    for trace in tools.trace:
        if trace["tool"] == "get_changes":
            trace["availability"] = "unavailable"
    assert "SOP-03.4 needs evidence or missing_fields" in validate(report, tools)


def test_contract_rejects_invalid_bundle_before_writes(store):
    data = demo_bundle().model_dump(mode="json")
    data["events_normalized"].append(data["events_normalized"][0])
    with pytest.raises(ValidationError, match="duplicate evidence"):
        Bundle.model_validate(data)
    assert store.query(data["incident"]["run_id"], "incidents") == []


def test_partial_load_is_not_readable(store):
    bundle = demo_bundle()
    doc = bundle.incident.model_dump(mode="json")
    store.put(str(bundle.incident.run_id), "incidents", doc["incident_id"], {**doc, "status": "loading"})
    with pytest.raises(ValueError, match="incomplete"):
        InvestigationTools(store, Knowledge.local(ROOT / "knowledge"), str(bundle.incident.run_id), doc["incident_id"])


def test_run_cannot_mix_incidents(investigation):
    bundle, tools, _ = investigation
    other = bundle.model_copy(deep=True)
    other.incident.incident_id = "INC-other"
    with pytest.raises(ValueError, match="run already"):
        load_bundle(tools.store._inner, other)
    with pytest.raises(ValueError, match="cross-incident"):
        tools.get_incident_events("INC-other")
    with pytest.raises(StoreError, match="read-only"):
        tools.store.delete_run(tools.run_id)


def test_knowledge_sections_and_forbidden_paths():
    knowledge = Knowledge.local(ROOT / "knowledge")
    assert "VONR-SVC" in knowledge.read_section("REF-CORE.6")
    assert "Frequencies configured" in knowledge.read_section("REF-RAN.4")
    assert "REF-CORE.7" not in knowledge.read_section("REF-CORE.6")
    for path in ("scenarios/scenario_inputs.yaml", "dictionary/alarms.yaml", "../SKILL.md", "reference/../../ISSUES.md"):
        with pytest.raises(ValueError, match="forbidden"):
            knowledge.read(path)


def test_budget_and_no_action_execution(investigation):
    _, tools, _ = investigation
    proposal = tools.propose_action("Inspect link", "change", "LINK-1")
    assert proposal["executed"] is False
    assert proposal["proposal"]["requires_approval"] is True
    tools.budget = tools.calls
    with pytest.raises(ToolBudgetExceeded):
        tools.list_sections()


def test_missing_impact_never_means_zero(investigation):
    _, tools, _ = investigation
    tools.incident.evidence_complete["impact_records"] = False
    impact = tools.get_customer_impact(tools.incident.incident_id)
    assert impact["level"] == "impact_tier_unknown"
    assert impact["distinct_customers"] is None


def test_unknown_initial_state_does_not_count_first_report(investigation):
    _, tools, _ = investigation
    result = tools.get_link_events("LINK-1", {"start": "2026-10-04T09:58:00Z", "end": "2026-10-04T10:13:00Z"})
    assert result["initial_state_unknown"] is True
    assert result["transitions_counted"] == 5


def test_valid_report_and_crafted_failures(investigation):
    _, tools, _ = investigation
    good = draft(tools)
    assert validate(good, tools) == []
    for field, value, expected in [("impact", {**good["impact"], "distinct_customers": 999}, "impact counts"),
                                   ("attribution", good["attribution"][:1], "each affected"),
                                   ("late_events", ["fabricated"], "late event")]:
        bad = copy.deepcopy(good)
        bad[field] = value
        assert any(expected in error for error in validate(bad, tools))
    bad = copy.deepcopy(good)
    bad["hypotheses"][0]["supporting_event_ids"] = ["fake"]
    assert any("absent" in error for error in validate(bad, tools))
    bad = copy.deepcopy(good)
    bad["hypotheses"][0]["knowledge_ids"] = ["REF-TX.2"]
    assert any("relationship citation" in error for error in validate(bad, tools))


def test_guard_and_versioning(investigation):
    _, tools, _ = investigation
    report = draft(tools)
    report["proposed_actions"] = [{"description": "Review rollback", "target_object": "LINK-1", "type": "change", "requires_approval": False}]
    corrected, overrides = guard(report)
    assert corrected["proposed_actions"][0]["requires_approval"] is True
    assert overrides
    version_report(corrected)
    assert corrected["report_version"] == 1
    next_report = copy.deepcopy(corrected)
    version_report(next_report, corrected)
    assert next_report["report_version"] == 1
    next_report["escalation"]["required"] = False
    version_report(next_report, corrected)
    assert (next_report["report_version"], next_report["supersedes"]) == (2, 1)


def test_agent_has_exactly_skill_tools(investigation):
    _, tools, _ = investigation
    names = {tool.tool_name for tool in tools.strand_tools()}
    assert names == {"list_sections", "read_section", "get_incident_events", "get_kpis", "get_changes",
                     "get_link_events", "get_customer_impact", "propose_action"}


def test_s3_knowledge_never_fetches_forbidden_key():
    from io import BytesIO
    class Client:
        keys = []
        def get_object(self, *, Bucket, Key):
            self.keys.append(Key)
            assert not any(word in Key for word in ("scenario", "dictionary", "oracle"))
            return {"Body": BytesIO((ROOT / "knowledge" / Key).read_bytes())}
    client = Client()
    knowledge = Knowledge.s3(client, "fake")
    knowledge.read_section("REF-CORE.6")
    with pytest.raises(ValueError):
        knowledge.read("scenarios/evaluation_oracle.yaml")
    assert client.keys == ["SKILL.md", "catalog.json", "reference/core-control-plane.md"]


def test_runtime_repairs_invalid_report_once(investigation, monkeypatch):
    from types import SimpleNamespace
    from agent import runtime
    from agent.schema import Report
    _, tools, _ = investigation
    good = draft(tools)
    bad = copy.deepcopy(good)
    bad["impact"]["distinct_customers"] = 999
    requests = []
    class FakeAgent:
        def __init__(self, **kwargs):
            pass
        def __call__(self, request, **kwargs):
            requests.append(request)
            return SimpleNamespace(structured_output=Report.model_validate(bad if len(requests) == 1 else good))
    monkeypatch.setattr(runtime, "InvestigationTools", lambda *args: tools)
    output = runtime.investigate(tools.store, tools.knowledge, tools.run_id, tools.incident.incident_id,
                                 agent_factory=FakeAgent)
    assert output["status"] == "validated"
    assert len(output["attempts"]) == 2
    assert "impact counts/tier" in requests[1]


@pytest.mark.parametrize("invalid_field, invalid_value", [("distinct_customers", 999), ("window_start", "invalid-time")])
def test_runtime_keeps_invalid_report_for_human(investigation, monkeypatch, invalid_field, invalid_value):
    from types import SimpleNamespace
    from agent import runtime
    from agent.schema import Report
    _, tools, _ = investigation
    bad = draft(tools)
    bad["impact"][invalid_field] = invalid_value
    class FakeAgent:
        def __init__(self, **kwargs):
            pass
        def __call__(self, request, **kwargs):
            return SimpleNamespace(structured_output=Report.model_validate(bad))
    monkeypatch.setattr(runtime, "InvestigationTools", lambda *args: tools)
    output = runtime.investigate(tools.store, tools.knowledge, tools.run_id, tools.incident.incident_id,
                                 agent_factory=FakeAgent)
    assert output["status"] == "needs_human"
    assert len(output["attempts"]) == 2


def test_publication_writes_report_and_includes_json_in_sns(investigation):
    from agent.main import publish
    bundle, tools, _ = investigation
    class Sink:
        def __init__(self):
            self.calls = []
        def put_object(self, **kwargs):
            self.calls.append(kwargs)
        def publish(self, **kwargs):
            self.calls.append(kwargs)
            return {"MessageId": "test-message-id"}
    s3, sns = Sink(), Sink()
    output = {"run_id": tools.run_id, "incident_id": bundle.incident.incident_id,
              "synthetic": True, "provisional": True, "status": "validated", "report": draft(tools)}
    key = publish(output, s3, sns, "fake-data", "fake-topic")
    assert key == f"reports/{bundle.incident.incident_id}/{tools.run_id}.json"
    assert json.loads(s3.calls[0]["Body"])["report"]["impact"]["distinct_customers"] == 120
    assert f"s3://fake-data/{key}" in sns.calls[0]["Message"]
    assert "customer_ids" not in sns.calls[0]["Message"]
    email_json = json.loads(sns.calls[0]["Message"].split("Investigation report JSON:\n", 1)[1])
    assert email_json["report"] == output["report"]
    assert email_json["incident_id"] == output["incident_id"]
    assert "tool_trace" not in email_json
    output["incident_id"] = "../unsafe"
    with pytest.raises(ValueError):
        publish(output, s3, sns, "fake-data", "fake-topic")
    assert len(s3.calls) == len(sns.calls) == 1


def test_oversized_email_retains_s3_pointer(investigation):
    from agent.main import notification_message
    bundle, tools, _ = investigation
    output = {"run_id": tools.run_id, "incident_id": bundle.incident.incident_id,
              "synthetic": True, "provisional": True, "status": "needs_human",
              "report": {"observation": "é" * 300000}}
    message, included = notification_message(output, "fake-data", "reports/test.json")
    assert not included
    assert "exceeds" in message
    assert "s3://fake-data/reports/test.json" in message
    assert len(message.encode("utf-8")) < 262144
