"""Read scenario_inputs.yaml: load it, check a scenario exists, follow `inherits`, list its phases.

Who may use this: the harness only (BUILD SPEC v3 §4). The agent, the enrichment step and
anything the agent can read must never import it, because the file holds scenario names.

Where the file lives (first match wins):
    1. the `path` argument, 2. env SOP_RCA_SCENARIO_INPUTS,
    3. knowledge/scenarios/scenario_inputs.yaml (the BUILD SPEC v3 §3 layout),
    4. ../scenario_inputs.yaml (the top "Telecom AI AGent PoC" folder, CLAUDE.md folder map).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
_CANDIDATES = (
    REPO_ROOT / "knowledge" / "scenarios" / "scenario_inputs.yaml",
    REPO_ROOT.parent / "scenario_inputs.yaml",
)


class InputsError(Exception):
    pass


def find_inputs_path(path: str | Path | None = None) -> Path:
    # An explicit path (argument or env var) must exist: a typo must not silently fall back
    # to a different file.
    for explicit in (path, os.environ.get("SOP_RCA_SCENARIO_INPUTS")):
        if explicit:
            if not Path(explicit).is_file():
                raise InputsError(f"scenario_inputs.yaml not found at {explicit}")
            return Path(explicit)
    for candidate in _CANDIDATES:
        if candidate.is_file():
            return candidate
    raise InputsError(
        "scenario_inputs.yaml not found. Pass a path or set SOP_RCA_SCENARIO_INPUTS. Looked in: "
        + ", ".join(str(c) for c in _CANDIDATES)
    )


def load_inputs(path: str | Path | None = None) -> tuple[dict, str, Path]:
    """Return (parsed inputs, sha256 of the file bytes, resolved path)."""
    resolved = find_inputs_path(path)
    raw = resolved.read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest(), resolved


def scenario_chain(inputs: dict, key: str) -> list[str]:
    """Scenario keys from the root ancestor down to `key`, following `inherits`."""
    scenarios = inputs.get("scenarios", {})
    chain: list[str] = []
    current: str | None = key
    while current is not None:
        if current not in scenarios:
            raise InputsError(f"unknown scenario {current!r}; known: {sorted(scenarios)}")
        if current in chain:
            raise InputsError(f"inherits cycle through {current!r}")
        chain.append(current)
        current = scenarios[current].get("inherits")
    return list(reversed(chain))


def scenario_phases(inputs: dict, scenario: str) -> list[dict]:
    """[{phase, run_agent_at}] from the scenario's own phase list."""
    phases = inputs["scenarios"][scenario].get("phases", [])
    return [{"phase": p["phase"], "run_agent_at": p.get("run_agent_at")} for p in phases]
