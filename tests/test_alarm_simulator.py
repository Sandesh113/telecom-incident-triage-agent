import copy
from datetime import timedelta
from pathlib import Path

import pytest

from evidence.contract import utc
from simulator.transport import alarm_feed, dictionary, normalize, telemetry_bundle
from store import open_store
from evidence.load import load_bundle
from agent.knowledge import Knowledge
from agent.tools import InvestigationTools

ROOT = Path(__file__).resolve().parents[1]
START = utc("2026-10-05T10:00:00Z")


@pytest.fixture
def mapping():
    return dictionary(ROOT / "simulator" / "data" / "alarms.yaml")


@pytest.mark.parametrize("vendor", ["mixed", "vendor_a", "vendor_b"])
def test_vendor_alarm_replay_matches_deployed_tools(mapping, vendor):
    feed = alarm_feed(START, vendor)
    events, audit = normalize(feed, mapping)
    assert audit["raw_notifications"] == audit["normalized_events"] == 6
    assert [e.resulting_state for e in events] == ["down", "up"] * 3
    assert {e.routing_trigger for e in events} == {"LINK_DOWN", "LINK_UP"}
    assert {e.target_object_id for e in events} == {"LINK-1"}
    assert events[0].raw["alarm_id"] == events[1].raw["alarm_id"]
    assert events[0].event_id != events[1].event_id
    assert events[1].alarm_state == "cleared"
    bundle = telemetry_bundle(events, START)
    store = open_store("sqlite", path=":memory:")
    try:
        ready = load_bundle(store, bundle)
        tools = InvestigationTools(store, Knowledge.local(ROOT / "knowledge"),
                                   str(bundle.incident.run_id), bundle.incident.incident_id)
        assert tools.get_link_events("LINK-1")["transitions_counted"] == 6
        assert tools.get_customer_impact(bundle.incident.incident_id)["distinct_customers"] == 120
        assert ready["Detail"]["run_id"] == str(bundle.incident.run_id)
    finally:
        store.close()


def test_same_notification_is_deduplicated_not_lifecycle(mapping):
    feed = alarm_feed(START, "vendor_a", 1)
    feed.append(copy.deepcopy(feed[0]))
    events, audit = normalize(feed, mapping)
    assert len(events) == 2
    assert audit["duplicate_notifications"] == [events[0].event_id]


def test_conflicting_notification_refused(mapping):
    feed = alarm_feed(START, "vendor_a", 1)
    duplicate = copy.deepcopy(feed[0])
    duplicate["record"]["perceivedSeverity"] = "critical"
    feed.append(duplicate)
    with pytest.raises(ValueError, match="conflicting"):
        normalize(feed, mapping)


def test_explicit_up_and_clear_are_one_transition(mapping):
    feed = alarm_feed(START, "vendor_b", 1)
    explicit = copy.deepcopy(feed[1])
    explicit["record"].update(evt="explicit-up", code="LAG-UP", ts=feed[1]["record"]["ts"] + 1000)
    explicit["ingest_time"] = (START + timedelta(minutes=1, seconds=2)).isoformat()
    feed.append(explicit)
    events, audit = normalize(feed, mapping)
    assert len(events) == 3
    assert len(audit["duplicate_transitions"]) == 1
    assert events[-1].transition_duplicate_of == events[1].event_id


def test_unknown_alarm_never_fabricates_a_trigger(mapping):
    feed = alarm_feed(START)
    feed[0]["record"]["specificProblem"] = "unknown fault"
    with pytest.raises(ValueError, match="unsupported alarm"):
        normalize(feed, mapping)


def test_unmapped_object_refused_before_incident(mapping):
    feed = alarm_feed(START)
    feed[0]["record"]["affectedObject"] = "lnk-99"
    with pytest.raises(ValueError, match="LINK-1"):
        normalize(feed, mapping)


def test_late_receipt_preserved(mapping):
    feed = alarm_feed(START, "vendor_a", 1)
    feed[0]["ingest_time"] = (START + timedelta(minutes=6)).isoformat()
    events, _ = normalize(feed, mapping)
    assert events[0].late_event


def test_offset_vendor_time_converts_to_utc(mapping):
    feed = alarm_feed(START, "vendor_a", 1)
    feed[0]["record"]["eventTime"] = "2026-10-05T11:00:00+01:00"
    events, _ = normalize(feed, mapping)
    assert utc(events[0].event_time) == START
