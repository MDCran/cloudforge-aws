import json
import os
import re
import time
from typing import Any

import boto3
from shared.config import Settings
from shared.logging import log, outcome
from shared.models import ApiError, Status
from shared.repository import Repository

from apps.worker.processor import ProcessingError, process_csv


def handle_record(record: dict[str, Any], settings: Settings) -> None:
    event = json.loads(record["body"])
    if event.get("source") != "aws.s3" or event.get("detail-type") != "Object Created":
        raise ValueError("Unsupported event")
    detail = event["detail"]
    key = detail["object"]["key"]
    match = re.fullmatch(r"uploads/([a-f0-9-]{36})/input\.csv", key)
    if detail["bucket"]["name"] != settings.uploads or not match:
        raise ValueError("Unexpected upload location")
    repo = Repository(settings)
    job = repo.get(match[1])
    if job["status"] in (Status.COMPLETED, Status.CANCELLED, Status.FAILED):
        return
    if job["status"] == Status.UPLOADING:
        try:
            job = repo.transition(job, Status.QUEUED)
        except ApiError as exc:
            if exc.code != "STATE_CONFLICT":
                raise
            job = repo.get(match[1])
    claimed = repo.claim(job)
    if claimed is None:
        return
    job = claimed
    lease = str(job["lease_token"])
    s3 = boto3.client("s3", region_name=settings.region)
    started = time.monotonic()
    try:
        if int(job["attempts"]) > settings.max_attempts:
            raise ProcessingError("RETRY_EXHAUSTED", "Processing attempts exhausted")
        kwargs: dict[str, Any] = {"Bucket": settings.uploads, "Key": key}
        version = detail["object"].get("version-id")
        if version:
            kwargs["VersionId"] = version
        elif detail["object"].get("etag"):
            kwargs["IfMatch"] = detail["object"]["etag"]
        response = s3.get_object(**kwargs)
        body = response["Body"]
        try:
            if response["ContentLength"] != int(job["size"]):
                raise ProcessingError("SIZE_MISMATCH", "Upload size does not match the job")
            data = body.read(settings.max_bytes + 1)
        finally:
            body.close()
        if len(data) > settings.max_bytes:
            raise ProcessingError("FILE_TOO_LARGE", "Upload exceeds the configured limit")
        report = process_csv(
            data,
            job["required_columns"],
            job["numeric_columns"],
            max_rows=settings.max_rows,
            seconds=settings.processing_seconds,
        )
        result_key = f"results/{job['job_id']}/{lease}/report.json"
        s3.put_object(
            Bucket=settings.results,
            Key=result_key,
            Body=json.dumps(report, allow_nan=False).encode(),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        repo.transition(
            job,
            Status.COMPLETED,
            {
                "result_key": result_key,
                "row_count": report["row_count"],
                "error_count": report["validation_error_count"],
                "duration_ms": int((time.monotonic() - started) * 1000),
            },
            lease=lease,
        )
        repo.table.put_item(
            Item={
                "pk": job["pk"],
                "sk": "OUTPUT",
                "key": result_key,
                "bucket": settings.results,
                "schema_version": 1,
            }
        )
        outcome(os.getenv("ENVIRONMENT", "local"), "Completed")
        log("job_completed", job_id=job["job_id"], correlation_id=event.get("id"))
    except ProcessingError as exc:
        repo.transition(job, Status.FAILED, {"error_code": exc.code}, lease=lease)
        outcome(os.getenv("ENVIRONMENT", "local"), "Failed")
        log("job_failed", job_id=job["job_id"], error_code=exc.code)
    except Exception:
        if (
            int(record.get("attributes", {}).get("ApproximateReceiveCount", "1"))
            >= settings.max_attempts
        ):
            repo.transition(job, Status.FAILED, {"error_code": "RETRY_EXHAUSTED"}, lease=lease)
        else:
            repo.transition(job, Status.QUEUED, lease=lease)
        raise


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = Settings.load()
    failed = []
    for record in event.get("Records", []):
        try:
            handle_record(record, settings)
        except Exception as exc:
            log("record_retry", message_id=record["messageId"], error_type=type(exc).__name__)
            failed.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failed}
