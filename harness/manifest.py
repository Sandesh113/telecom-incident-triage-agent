"""Private run manifest: the ONLY place that maps a run UUID to a scenario.

Why it exists (BUILD SPEC v3 §4, §5.1): run IDs must be opaque UUIDs, and no scenario ID
may appear in anything the agent can read. The harness writes this file; the Go producer
reads `scenario` from it (flag `-scenario-run <uuid>`); nothing else may.

Where: runs/manifests/<run_id>.json  (runs/ is gitignored and never uploaded anywhere).
It is never written to the evidence store.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .scenario_inputs import InputsError, load_inputs, scenario_chain, scenario_phases

MANIFEST_VERSION = 1


def default_runs_dir() -> Path:
    return Path(os.environ.get("SOP_RCA_RUNS_DIR", "runs"))


@dataclass
class Manifest:
    run_id: str
    scenario: str  # PRIVATE: e.g. "S3". Never copy this into the store, topics or the agent's input.
    created_at: str
    inputs_path: str
    inputs_sha256: str
    inputs_version: str
    seed: int
    base_date: str
    phases: list[dict] = field(default_factory=list)  # [{phase, run_agent_at}]
    manifest_version: int = MANIFEST_VERSION


def manifest_path(run_id: str, runs_dir: str | Path | None = None) -> Path:
    uuid.UUID(run_id)  # refuses anything that is not a UUID (also blocks path tricks like ../x)
    return Path(runs_dir or default_runs_dir()) / "manifests" / f"{run_id}.json"


def create_manifest(scenario: str, inputs_path: str | Path | None = None, runs_dir: str | Path | None = None) -> Manifest:
    """New UUID + manifest for one scenario run. Validates the scenario against the inputs."""
    inputs, sha, resolved = load_inputs(inputs_path)
    scenario_chain(inputs, scenario)  # raises InputsError for an unknown scenario
    manifest = Manifest(
        run_id=str(uuid.uuid4()),
        scenario=scenario,
        created_at=datetime.now(timezone.utc).isoformat(),
        inputs_path=str(resolved),
        inputs_sha256=sha,
        inputs_version=str(inputs.get("inputs_version")),
        seed=int(inputs["seed"]),
        base_date=str(inputs["base_date"]),
        phases=scenario_phases(inputs, scenario),
    )
    path = manifest_path(manifest.run_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic: a reader never sees a half-written manifest
    return manifest


def read_manifest(run_id: str, runs_dir: str | Path | None = None) -> Manifest:
    path = manifest_path(run_id, runs_dir)
    if not path.is_file():
        raise InputsError(f"no manifest for run {run_id} at {path}")
    return Manifest(**json.loads(path.read_text(encoding="utf-8")))
