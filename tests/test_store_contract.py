"""The store contract. Runs against SQLite and DynamoDB (moto) through the `store` fixture."""

import pytest

from store import COLLECTIONS, ReadOnlyStore, StoreError, open_store

RUN = "11111111-1111-4111-8111-111111111111"
OTHER_RUN = "22222222-2222-4222-8222-222222222222"


def test_put_get_roundtrip_keeps_floats_exactly(store):
    doc = {"kpi": "voice_setup_failure_rate", "rate": 0.13902439, "attempts": 410, "nested": {"a": [1, 2.5]}}
    store.put(RUN, "kpi_windows", "K1", doc)
    assert store.get(RUN, "kpi_windows", "K1") == doc


def test_get_missing_returns_none(store):
    assert store.get(RUN, "changes", "nope") is None


def test_runs_are_isolated(store):
    store.put(RUN, "changes", "CHG-1", {"cell": "CELL-C"})
    assert store.get(OTHER_RUN, "changes", "CHG-1") is None
    assert store.query(OTHER_RUN, "changes") == []


def test_query_returns_one_doc_per_id_ordered_and_filtered(store):
    store.put(RUN, "events_normalized", "B:2", {"event_id": "B:2", "routing_role": "context"})
    store.put(RUN, "events_normalized", "A:1", {"event_id": "A:1", "routing_role": "route"})
    store.put(RUN, "events_normalized", "A:3", {"event_id": "A:3", "routing_role": "route"})
    assert [d["event_id"] for d in store.query(RUN, "events_normalized")] == ["A:1", "A:3", "B:2"]
    assert [d["event_id"] for d in store.query(RUN, "events_normalized", where={"routing_role": "route"})] == ["A:1", "A:3"]


def test_put_replaces_same_id_and_version(store):
    store.put(RUN, "incidents", "INC-1", {"n": 1})
    store.put(RUN, "incidents", "INC-1", {"n": 2})
    assert store.get(RUN, "incidents", "INC-1") == {"n": 2}
    assert len(store.query(RUN, "incidents")) == 1


def test_versions_latest_wins_and_exact_version_readable(store):
    store.put(RUN, "reports", "rep", {"v": 1}, version="1")
    store.put(RUN, "reports", "rep", {"v": 2}, version="2")
    assert store.versions(RUN, "reports", "rep") == ["1", "2"]
    assert store.get(RUN, "reports", "rep") == {"v": 2}  # latest
    assert store.get(RUN, "reports", "rep", version="1") == {"v": 1}
    assert [d["v"] for d in store.query(RUN, "reports")] == [2]  # query = latest per id


def test_doc_id_prefix_does_not_leak_between_ids(store):
    store.put(RUN, "observations", "H1", {"id": "H1"})
    store.put(RUN, "observations", "H10", {"id": "H10"})
    assert store.get(RUN, "observations", "H1") == {"id": "H1"}
    assert store.versions(RUN, "observations", "H1") == [""]


def test_delete_run_removes_only_that_run(store):
    store.put(RUN, "changes", "C1", {"a": 1})
    store.put(RUN, "kpi_windows", "K1", {"a": 1})
    store.put(OTHER_RUN, "changes", "C1", {"a": 1})
    assert store.delete_run(RUN) == 2
    assert store.query(RUN, "changes") == [] and store.query(OTHER_RUN, "changes") != []


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.put(RUN, "not_a_collection", "x", {}),
        lambda s: s.put(RUN, "changes", "", {}),
        lambda s: s.put(RUN, "changes", "a#b", {}),
        lambda s: s.put("", "changes", "x", {}),
        lambda s: s.put(RUN, "changes", "x", "not a dict"),
        lambda s: s.put(RUN, "changes", "x", {"bad": {1, 2}}),  # a set is not JSON
        lambda s: s.query(RUN, "not_a_collection"),
    ],
)
def test_bad_arguments_are_rejected(store, call):
    with pytest.raises(StoreError):
        call(store)


def test_collections_are_the_spec_ones_minus_topology():
    # BUILD SPEC v3 §5.4 lists ten; `topology` was dropped (static reference content now).
    assert set(COLLECTIONS) == {
        "events_normalized", "observations", "kpi_windows", "changes",
        "impact_records", "incidents", "unresolved_ids", "unmapped_alarms", "reports",
    }


def test_readonly_wrapper_reads_but_never_writes(store):
    store.put(RUN, "changes", "C1", {"a": 1})
    agent_view = ReadOnlyStore(store)
    assert agent_view.get(RUN, "changes", "C1") == {"a": 1}
    assert agent_view.query(RUN, "changes") == [{"a": 1}]
    with pytest.raises(StoreError, match="read-only"):
        agent_view.put(RUN, "changes", "C2", {"a": 2})
    with pytest.raises(StoreError, match="read-only"):
        agent_view.delete_run(RUN)
    assert store.get(RUN, "changes", "C2") is None


def test_open_store_factory(tmp_path, monkeypatch):
    monkeypatch.delenv("STORAGE", raising=False)
    s = open_store(path=tmp_path / "x.sqlite")
    s.put(RUN, "changes", "C1", {"a": 1})
    assert s.get(RUN, "changes", "C1") == {"a": 1}
    with pytest.raises(StoreError):
        open_store("mongodb")
    ro = open_store("sqlite", read_only=True, path=tmp_path / "x.sqlite")
    with pytest.raises(StoreError):
        ro.put(RUN, "changes", "C2", {})
