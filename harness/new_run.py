"""Start a run: new UUID and a private manifest.

    python -m harness.new_run S3

This is step 1 of the harness (BUILD SPEC v3 §9). Topology is no longer loaded here: it is
static reference-file content now (DECISIONS.md), not something written to the store.
Later phases add the producer, enrichment and agent steps in harness/run.py.
"""

from __future__ import annotations

import argparse

from .manifest import Manifest, create_manifest


def new_run(scenario: str, inputs_path=None, runs_dir=None) -> Manifest:
    """Create the run UUID and its private manifest."""
    return create_manifest(scenario, inputs_path, runs_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness.new_run")
    parser.add_argument("scenario", help="scenario key from scenario_inputs.yaml (private)")
    parser.add_argument("--inputs", default=None, help="path to scenario_inputs.yaml")
    parser.add_argument("--runs-dir", default=None)
    args = parser.parse_args(argv)

    manifest = new_run(args.scenario, args.inputs, args.runs_dir)
    # Print only what the agent side may know. The scenario key stays in the manifest file.
    print(f"run_id={manifest.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
