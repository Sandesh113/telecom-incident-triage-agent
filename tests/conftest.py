"""Shared fixtures: both store backends, and a small inline scenario-inputs file.

The inline inputs mirror the *shape* of the real scenario_inputs.yaml (a plain scenario, an
inherited scenario, a two-phase scenario) so the tests do not depend on the real file.
"""

from __future__ import annotations

import pytest
import yaml


@pytest.fixture
def inputs_file(tmp_path):
    """A scenario_inputs.yaml with: a plain scenario, a child of it, and a two-phase one."""
    inputs = {
        "inputs_version": "0.3",
        "base_date": "2026-10-04",
        "seed": 42,
        "scenarios": {
            "X1": {"phases": [{"phase": 1, "run_agent_at": "10:20"}]},
            "X2": {"inherits": "X1", "phases": [{"phase": 1, "run_agent_at": "10:30"}]},
            "X3": {
                "phases": [{"phase": 1, "run_agent_at": "10:20"}, {"phase": 2, "run_agent_at": "10:27"}],
            },
            "CYC-A": {"inherits": "CYC-B", "phases": []},
            "CYC-B": {"inherits": "CYC-A", "phases": []},
        },
    }
    path = tmp_path / "scenario_inputs.yaml"
    path.write_text(yaml.safe_dump(inputs, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture(params=["sqlite", "dynamodb"])
def store(request, tmp_path, monkeypatch):
    """Each test using `store` runs against both backends (DynamoDB via moto, never real AWS)."""
    if request.param == "sqlite":
        from store.sqlite_store import SQLiteStore

        s = SQLiteStore(tmp_path / "store.sqlite")
        yield s
        s.close()
        return

    # Make sure nothing can reach a real account: fake credentials, no profile.
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-north-1")
    monkeypatch.setenv("AWS_REGION", "eu-north-1")
    from moto import mock_aws

    with mock_aws():
        import boto3

        resource = boto3.resource("dynamodb", region_name="eu-north-1")
        # Same keys and GSI as infra/dynamodb.tf.
        resource.create_table(
            TableName="sop-rca-evidence",
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "run_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi1-run-id",
                    "KeySchema": [{"AttributeName": "run_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        from store.dynamodb_store import DynamoDBStore

        yield DynamoDBStore(resource=resource)
