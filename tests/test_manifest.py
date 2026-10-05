"""Private run manifest: opaque UUID -> scenario mapping, written by the harness only."""

import json
import uuid

import pytest

from harness.manifest import create_manifest, manifest_path, read_manifest
from harness.new_run import new_run
from harness.scenario_inputs import InputsError, load_inputs, scenario_chain


def test_manifest_roundtrip_and_fields(inputs_file, tmp_path):
    m = create_manifest("X3", inputs_file, tmp_path)
    uuid.UUID(m.run_id)  # a real UUID, opaque
    again = read_manifest(m.run_id, tmp_path)
    assert again == m
    assert m.scenario == "X3" and m.seed == 42 and m.base_date == "2026-10-04" and m.inputs_version == "0.3"
    assert m.phases == [{"phase": 1, "run_agent_at": "10:20"}, {"phase": 2, "run_agent_at": "10:27"}]  # two-phase
    assert len(m.inputs_sha256) == 64


def test_each_run_gets_a_new_uuid_and_its_own_file(inputs_file, tmp_path):
    a, b = create_manifest("X1", inputs_file, tmp_path), create_manifest("X1", inputs_file, tmp_path)
    assert a.run_id != b.run_id
    assert manifest_path(a.run_id, tmp_path).is_file() and manifest_path(b.run_id, tmp_path).is_file()
    assert json.loads(manifest_path(a.run_id, tmp_path).read_text())["scenario"] == "X1"


def test_the_run_id_never_contains_the_scenario_key(inputs_file, tmp_path):
    """Data separation (BUILD SPEC v3 §4): run IDs are opaque UUIDs."""
    for key in ("X1", "X2", "X3"):
        assert key not in new_run(key, inputs_file, tmp_path).run_id


def test_unknown_scenario_is_refused_and_writes_nothing(inputs_file, tmp_path):
    with pytest.raises(InputsError, match="unknown scenario"):
        create_manifest("NOPE", inputs_file, tmp_path)
    assert not (tmp_path / "manifests").exists() or not list((tmp_path / "manifests").iterdir())


def test_inherits_chain_runs_root_first_and_cycles_are_refused(inputs_file):
    inputs, _, _ = load_inputs(inputs_file)
    assert scenario_chain(inputs, "X2") == ["X1", "X2"]
    with pytest.raises(InputsError, match="cycle"):
        scenario_chain(inputs, "CYC-A")


def test_run_id_must_be_a_uuid_so_paths_cannot_escape(tmp_path):
    with pytest.raises(ValueError):
        manifest_path("../../etc/passwd", tmp_path)
    with pytest.raises(InputsError, match="no manifest"):
        read_manifest(str(uuid.uuid4()), tmp_path)


def test_missing_explicit_inputs_file_gives_a_clear_error_and_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.delenv("SOP_RCA_SCENARIO_INPUTS", raising=False)
    with pytest.raises(InputsError, match="not found at"):
        create_manifest("X1", tmp_path / "does-not-exist.yaml", tmp_path)
