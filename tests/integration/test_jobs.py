import json
import time
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from shared.config import Settings
from shared.models import ApiError, Status
from shared.repository import Repository

from apps.worker.handler import handler
from tests.conftest import call

CSV = b"name,amount\nAda,10\nAda,10\nBob,20\n"


def create_upload(aws: Settings, data: bytes = CSV) -> tuple[dict[str, Any], dict[str, Any]]:
    status, job = call(
        "POST",
        "/v1/jobs",
        {
            "name": "Billing report",
            "filename": "billing.csv",
            "size": len(data),
            "required_columns": ["name"],
            "numeric_columns": ["amount"],
        },
    )
    assert status == 201
    assert call("POST", "/v1/uploads/presign", {"job_id": job["job_id"]})[0] == 200
    key = f"uploads/{job['job_id']}/input.csv"
    response = boto3.client("s3", region_name=aws.region).put_object(
        Bucket=aws.uploads, Key=key, Body=data
    )
    event = {
        "id": "event-1",
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {
            "bucket": {"name": aws.uploads},
            "object": {"key": key, "version-id": response["VersionId"], "etag": response["ETag"]},
        },
    }
    return job, {
        "messageId": "message-1",
        "body": json.dumps(event),
        "attributes": {"ApproximateReceiveCount": "1"},
    }


def test_complete_lifecycle_and_duplicate_event(aws: Settings) -> None:
    job, record = create_upload(aws)
    assert handler({"Records": [record]}, None) == {"batchItemFailures": []}
    assert handler({"Records": [record]}, None) == {"batchItemFailures": []}
    status, finished = call("GET", f"/v1/jobs/{job['job_id']}")
    assert status == 200 and finished["status"] == "COMPLETED"
    assert finished["attempts"] == 1 and finished["row_count"] == 3
    assert {e["status"] for e in finished["history"]} >= {
        "CREATED",
        "UPLOADING",
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
    }
    assert call("GET", f"/v1/jobs/{job['job_id']}/result")[0] == 200
    item = Repository(aws).get(job["job_id"])
    data = (
        boto3.client("s3", region_name=aws.region)
        .get_object(Bucket=aws.results, Key=item["result_key"])["Body"]
        .read()
    )
    assert json.loads(data)["duplicate_rows"] == 1


def test_owner_isolation_and_operator_access(aws: Settings) -> None:
    job, _ = create_upload(aws)
    assert call("GET", f"/v1/jobs/{job['job_id']}", owner="bob")[0] == 404
    assert call("POST", "/v1/uploads/presign", {"job_id": job["job_id"]}, owner="bob")[0] == 404
    assert call("GET", "/v1/jobs", owner="bob")[1]["items"] == []
    assert call("GET", "/v1/jobs", owner=None)[0] == 401
    assert call("GET", "/v1/metrics/summary", groups="users")[0] == 403
    assert call("GET", "/v1/metrics/summary")[1]["sample_size"] == 1
    assert call("GET", "/health", owner=None)[0] == 200


def test_idempotency_and_conflict(aws: Settings) -> None:
    body = {"name": "Report", "filename": "file.csv", "size": 2}
    first = call("POST", "/v1/jobs", body)[1]
    assert call("POST", "/v1/jobs", body)[1]["job_id"] == first["job_id"]
    assert call("POST", "/v1/jobs", {**body, "name": "Another"})[0] == 409
    assert call("POST", "/v1/jobs", body, key="bad")[0] == 400


def test_cancellation_and_running_race(aws: Settings) -> None:
    job, record = create_upload(aws)
    assert call("POST", f"/v1/jobs/{job['job_id']}/cancel")[1]["status"] == "CANCELLED"
    assert handler({"Records": [record]}, None)["batchItemFailures"] == []
    assert Repository(aws).get(job["job_id"])["status"] == "CANCELLED"
    call(
        "POST",
        "/v1/jobs",
        {"name": "Second", "filename": "second.csv", "size": 2},
        key="second-key",
    )
    second = call("GET", "/v1/jobs")[1]["items"][0]
    repo = Repository(aws)
    pending = repo.transition(repo.get(second["job_id"]), Status.UPLOADING)
    pending = repo.transition(pending, Status.QUEUED)
    running = repo.claim(pending)
    assert running
    assert call("POST", f"/v1/jobs/{second['job_id']}/cancel")[0] == 409
    with pytest.raises(ApiError, match="worker"):
        repo.claim(running)
    with pytest.raises(ApiError, match="state changed"):
        repo.transition(pending, Status.CANCELLED)


def test_poison_messages_and_partial_batch(aws: Settings) -> None:
    job, valid = create_upload(aws)
    invalid = {"messageId": "bad", "body": "not-json"}
    assert handler({"Records": [invalid, valid]}, None)["batchItemFailures"] == [
        {"itemIdentifier": "bad"}
    ]
    assert Repository(aws).get(job["job_id"])["status"] == "COMPLETED"


def test_invalid_content_is_terminal(aws: Settings) -> None:
    job, record = create_upload(aws, b"wrong\n1\n")
    assert handler({"Records": [record]}, None)["batchItemFailures"] == []
    failed = Repository(aws).get(job["job_id"])
    assert failed["status"] == "FAILED" and failed["error_code"] == "MISSING_COLUMNS"


def test_transient_retry_and_expired_lease(aws: Settings) -> None:
    job, record = create_upload(aws)
    with patch("apps.worker.handler.process_csv", side_effect=RuntimeError("temporary")):
        assert handler({"Records": [record]}, None)["batchItemFailures"]
    repo = Repository(aws)
    assert repo.get(job["job_id"])["status"] == "QUEUED"
    running = repo.claim(repo.get(job["job_id"]))
    assert running
    repo.table.update_item(
        Key={"pk": running["pk"], "sk": "META"},
        UpdateExpression="SET lease_until=:old",
        ExpressionAttributeValues={":old": int(time.time()) - 1},
    )
    assert handler({"Records": [record]}, None)["batchItemFailures"] == []
    assert repo.get(job["job_id"])["attempts"] == 3


def test_last_retry_marks_failed_and_remains_in_dlq_path(aws: Settings) -> None:
    job, record = create_upload(aws)
    record["attributes"]["ApproximateReceiveCount"] = "5"
    with patch("apps.worker.handler.process_csv", side_effect=RuntimeError("temporary")):
        assert handler({"Records": [record]}, None)["batchItemFailures"]
    assert Repository(aws).get(job["job_id"])["error_code"] == "RETRY_EXHAUSTED"


def test_pagination_and_status_queries(aws: Settings) -> None:
    for i in range(3):
        call(
            "POST",
            "/v1/jobs",
            {"name": f"Job {i}", "filename": "file.csv", "size": 2},
            key=f"create-{i:04}",
        )
    page = call("GET", "/v1/jobs", query={"limit": "2", "status": "CREATED"})[1]
    assert len(page["items"]) == 2 and page["cursor"]
    next_page = call(
        "GET", "/v1/jobs", query={"limit": "2", "status": "CREATED", "cursor": page["cursor"]}
    )[1]
    assert len(next_page["items"]) == 1
    assert call("GET", "/v1/jobs", query={"cursor": page["cursor"]})[0] == 400
    assert call("GET", "/v1/jobs", query={"limit": "0"})[0] == 400
    assert call("GET", "/v1/jobs", query={"status": "UNKNOWN"})[0] == 400
