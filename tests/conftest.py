import json
from collections.abc import Iterator
from typing import Any

import pytest
from moto import mock_aws
from shared.config import Settings

from apps.api.handler import handler
from scripts.local_resources import create_resources


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        create_resources()
        yield Settings.load()


def call(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    owner: str | None = "alice",
    groups: str = "operators",
    key: str = "test-key-123",
    query: dict[str, str] | None = None,
) -> tuple[int, Any]:
    claims = {"sub": owner, "token_use": "access", "cognito:groups": groups} if owner else {}
    event = {
        "rawPath": path,
        "body": json.dumps(body) if body is not None else None,
        "headers": {"Idempotency-Key": key},
        "queryStringParameters": query,
        "requestContext": {
            "http": {"method": method},
            "requestId": "test-correlation",
            "authorizer": {"jwt": {"claims": claims}},
        },
    }
    response = handler(event, None)
    return response["statusCode"], json.loads(response["body"])
