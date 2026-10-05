import importlib.util
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import boto3


def test_shim_waits_for_long_agent_run_without_sdk_retries(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:example:runtime")
    stream = BytesIO(b'{"status":"validated"}')
    client = Mock()
    client.invoke_agent_runtime.return_value = {"statusCode": 200, "response": stream}
    factory = Mock(return_value=client)
    monkeypatch.setattr(boto3, "client", factory)
    path = Path(__file__).resolve().parents[1] / "infra/lambda_shim/handler.py"
    spec = importlib.util.spec_from_file_location("shim_test", path)
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    config = factory.call_args.kwargs["config"]
    assert config.read_timeout == 870
    assert config.retries["total_max_attempts"] == 1
    result = shim.lambda_handler({"id": "event-id", "detail": {"incident_id": "INC-1", "run_id": "run-1"}}, None)
    assert result["status"] == "ok"
    assert stream.closed
    assert json.loads(client.invoke_agent_runtime.call_args.kwargs["payload"])["run_id"] == "run-1"
