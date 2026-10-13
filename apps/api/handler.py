import json
import re
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

import boto3
from pydantic import ValidationError
from shared.config import Settings
from shared.logging import log
from shared.models import ApiError, JobInput, Status
from shared.repository import Repository


def public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in item.items()
        if k
        not in {
            "pk",
            "sk",
            "gsi1pk",
            "gsi1sk",
            "gsi2pk",
            "gsi2sk",
            "owner",
            "lease_token",
            "lease_until",
            "result_key",
            "ttl",
        }
    }


def route(event: dict[str, Any], settings: Settings) -> tuple[int, Any]:
    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "/")
    if method == "GET" and path == "/health":
        return 200, {"service": "cloudforge", "status": "ok", "version": "0.1.0"}
    claims = event["requestContext"].get("authorizer", {}).get("jwt", {}).get("claims", {})
    owner = claims.get("sub")
    if not owner or claims.get("token_use") != "access":
        raise ApiError(401, "UNAUTHORIZED", "A valid access token is required")
    repo = Repository(settings)
    query = event.get("queryStringParameters") or {}
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
    body: dict[str, Any] = {}
    if event.get("body"):
        if event.get("isBase64Encoded") or len(event["body"]) > 16384:
            raise ApiError(400, "INVALID_BODY", "Request must be a small JSON object")
        try:
            body = json.loads(event["body"])
            if not isinstance(body, dict):
                raise ValueError("Object required")
        except (ValueError, TypeError) as exc:
            raise ApiError(400, "INVALID_BODY", "Request must be a JSON object") from exc
    if method == "POST" and path == "/v1/jobs":
        request = JobInput.model_validate(body)
        if request.size > settings.max_bytes:
            raise ApiError(422, "FILE_TOO_LARGE", "File exceeds the configured size limit")
        key = headers.get("idempotency-key", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", key):
            raise ApiError(
                400, "INVALID_IDEMPOTENCY_KEY", "Supply an 8–128 character Idempotency-Key"
            )
        return 201, public(repo.create(owner, request, key))
    if method == "GET" and path == "/v1/jobs":
        status = query.get("status")
        if status and status not in Status:
            raise ApiError(400, "INVALID_STATUS", "Unknown job status")
        try:
            limit = int(query.get("limit", "25"))
            if not 1 <= limit <= 100:
                raise ValueError("Limit out of range")
        except ValueError as exc:
            raise ApiError(400, "INVALID_LIMIT", "Limit must be between 1 and 100") from exc
        result = repo.list(owner, status, limit, query.get("cursor"))
        result["items"] = [public(item) for item in result["items"]]
        return 200, result
    s3 = boto3.client("s3", region_name=settings.region)
    if method == "POST" and path == "/v1/uploads/presign":
        job = repo.get(str(body.get("job_id", "")), owner)
        key = f"uploads/{job['job_id']}/input.csv"
        if job["status"] == Status.CREATED:
            job = repo.transition(job, Status.UPLOADING)
        elif job["status"] != Status.UPLOADING:
            raise ApiError(409, "UPLOAD_CLOSED", "Job is no longer accepting uploads")
        repo.table.put_item(
            Item={
                "pk": job["pk"],
                "sk": "UPLOAD",
                "key": key,
                "size": job["size"],
                "expires_in": 300,
            }
        )
        upload = s3.generate_presigned_post(
            Bucket=settings.uploads,
            Key=key,
            Fields={"Content-Type": "text/csv", "x-amz-server-side-encryption": "AES256"},
            Conditions=[
                {"Content-Type": "text/csv"},
                {"x-amz-server-side-encryption": "AES256"},
                ["content-length-range", int(job["size"]), int(job["size"])],
            ],
            ExpiresIn=300,
        )
        return 200, {**upload, "expires_in": 300, "job_id": job["job_id"]}
    if method == "GET" and path == "/v1/metrics/summary":
        groups = claims.get("cognito:groups", "")
        if "operators" not in re.split(r"[\[\],\s]+", str(groups)):
            raise ApiError(403, "FORBIDDEN", "Operator access is required")
        recent = repo.list(owner, None, 100, None)
        queue = boto3.client("sqs", region_name=settings.region).get_queue_attributes(
            QueueUrl=settings.queue_url,
            AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
        )
        return 200, {
            "scope": "latest_100_owner_jobs",
            "counts": dict(Counter(item["status"] for item in recent["items"])),
            "sample_size": len(recent["items"]),
            "has_more": bool(recent["cursor"]),
            "queue": queue["Attributes"],
            "telemetry_source": "DynamoDB and SQS",
            "queue_scope": "environment",
        }
    match = re.fullmatch(r"/v1/jobs/([a-f0-9-]{36})(/cancel|/result)?", path)
    if match:
        job = repo.get(match[1], owner)
        if method == "GET" and not match[2]:
            return 200, {**public(job), "history": [public(e) for e in repo.history(match[1])]}
        if method == "POST" and match[2] == "/cancel":
            return 200, public(repo.transition(job, Status.CANCELLED))
        if method == "GET" and match[2] == "/result":
            if job["status"] != Status.COMPLETED:
                raise ApiError(409, "RESULT_NOT_READY", "Job has no completed result")
            url = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.results,
                    "Key": job["result_key"],
                    "ResponseContentDisposition": 'attachment; filename="report.json"',
                },
                ExpiresIn=300,
            )
            return 200, {"url": url, "expires_in": 300}
    raise ApiError(404, "ROUTE_NOT_FOUND", "Route not found")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    correlation = event.get("requestContext", {}).get("requestId", str(uuid.uuid4()))
    try:
        status, body = route(event, Settings.load())
    except ApiError as exc:
        status, body = exc.status, {"error": {"code": exc.code, "message": exc.message}}
    except ValidationError:
        status, body = 422, {"error": {"code": "INVALID_INPUT", "message": "Check the job fields"}}
    except Exception as exc:
        log("api_error", correlation_id=correlation, error_type=type(exc).__name__)
        status, body = (
            500,
            {"error": {"code": "INTERNAL_ERROR", "message": "Request could not be completed"}},
        )
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "x-correlation-id": correlation,
            "cache-control": "no-store",
        },
        "body": json.dumps(
            body,
            default=lambda v: (
                int(v)
                if isinstance(v, Decimal) and v == int(v)
                else float(v)
                if isinstance(v, Decimal)
                else str(v)
            ),
        ),
    }
