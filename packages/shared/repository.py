from __future__ import annotations

import base64
import builtins
import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from shared.config import Settings
from shared.models import TRANSITIONS, ApiError, JobInput, Status


def now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, settings: Settings):
        self.table = boto3.resource("dynamodb", region_name=settings.region).Table(settings.table)
        self.settings = settings

    def get(self, job_id: str, owner: str | None = None) -> dict[str, Any]:
        item = self.table.get_item(
            Key={"pk": f"JOB#{job_id}", "sk": "META"}, ConsistentRead=True
        ).get("Item")
        if not item or (owner is not None and item["owner"] != owner):
            raise ApiError(404, "JOB_NOT_FOUND", "Job not found")
        return dict(item)

    def create(self, owner: str, request: JobInput, key: str) -> dict[str, Any]:
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        id_pk = f"IDEMP#{owner}#{hashlib.sha256(key.encode()).hexdigest()}"
        existing = self.table.get_item(Key={"pk": id_pk, "sk": "META"}, ConsistentRead=True).get(
            "Item"
        )
        if existing:
            if existing["digest"] != digest:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "Key was used for another request")
            return self.get(str(existing["job_id"]), owner)
        job_id, timestamp = str(uuid.uuid4()), now()
        item = {
            "pk": f"JOB#{job_id}",
            "sk": "META",
            "job_id": job_id,
            "owner": owner,
            "status": Status.CREATED.value,
            "created_at": timestamp,
            "updated_at": timestamp,
            "attempts": 0,
            **request.model_dump(),
            "gsi1pk": f"OWNER#{owner}",
            "gsi1sk": f"{timestamp}#{job_id}",
            "gsi2pk": f"OWNER#{owner}#STATUS#CREATED",
            "gsi2sk": f"{timestamp}#{job_id}",
        }
        idem = {
            "pk": id_pk,
            "sk": "META",
            "job_id": job_id,
            "digest": digest,
            "ttl": int(time.time()) + 86400,
        }
        serializer = TypeSerializer()
        client = boto3.client("dynamodb", region_name=self.settings.region)
        try:
            client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self.settings.table,
                            "Item": {k: serializer.serialize(v) for k, v in record.items()},
                            "ConditionExpression": "attribute_not_exists(pk)",
                        }
                    }
                    for record in (item, idem)
                ]
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "TransactionCanceledException":
                existing = self.table.get_item(
                    Key={"pk": id_pk, "sk": "META"}, ConsistentRead=True
                ).get("Item")
                if existing and existing["digest"] == digest:
                    return self.get(str(existing["job_id"]), owner)
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "Conflicting job creation") from exc
            raise
        self.event(job_id, "CREATED")
        return item

    def event(self, job_id: str, status: str, **fields: Any) -> None:
        timestamp = now()
        self.table.put_item(
            Item={
                "pk": f"JOB#{job_id}",
                "sk": f"EVENT#{timestamp}#{uuid.uuid4().hex}",
                "timestamp": timestamp,
                "status": status,
                "ttl": int(time.time()) + 90 * 86400,
                **fields,
            }
        )

    def transition(
        self,
        job: dict[str, Any],
        target: Status,
        fields: dict[str, Any] | None = None,
        lease: str | None = None,
    ) -> dict[str, Any]:
        current = Status(job["status"])
        if target not in TRANSITIONS[current]:
            raise ApiError(409, "INVALID_TRANSITION", f"Cannot change {current} to {target}")
        updates = {
            "status": target.value,
            "updated_at": now(),
            "gsi2pk": f"OWNER#{job['owner']}#STATUS#{target.value}",
            **(fields or {}),
        }
        names = {"#s": "status", **{f"#k{i}": k for i, k in enumerate(updates)}}
        values = {":old": current.value, **{f":v{i}": v for i, v in enumerate(updates.values())}}
        condition = "#s = :old"
        if lease is not None:
            condition += " AND lease_token = :lease"
            values[":lease"] = lease
        try:
            result = self.table.update_item(
                Key={"pk": job["pk"], "sk": "META"},
                UpdateExpression="SET " + ", ".join(f"#k{i} = :v{i}" for i in range(len(updates))),
                ConditionExpression=condition,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ApiError(
                    409, "STATE_CONFLICT", "Job state changed; refresh and retry"
                ) from exc
            raise
        self.event(str(job["job_id"]), target.value)
        return dict(result["Attributes"])

    def claim(self, job: dict[str, Any]) -> dict[str, Any] | None:
        epoch, token = int(time.time()), uuid.uuid4().hex
        if job["status"] == Status.PROCESSING and int(job.get("lease_until", 0)) > epoch:
            raise ApiError(409, "LEASE_BUSY", "Another worker owns this job")
        if job["status"] not in (Status.QUEUED, Status.PROCESSING):
            return None
        try:
            result = self.table.update_item(
                Key={"pk": job["pk"], "sk": "META"},
                UpdateExpression="SET #s=:processing, lease_until=:until, lease_token=:token, "
                "updated_at=:now, gsi2pk=:index ADD attempts :one",
                ConditionExpression="#s=:queued OR (#s=:processing AND lease_until < :epoch)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":processing": "PROCESSING",
                    ":queued": "QUEUED",
                    ":until": epoch + self.settings.lease_seconds,
                    ":token": token,
                    ":epoch": epoch,
                    ":now": now(),
                    ":one": 1,
                    ":index": f"OWNER#{job['owner']}#STATUS#PROCESSING",
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ApiError(409, "LEASE_BUSY", "Job was claimed or cancelled") from exc
            raise
        item: dict[str, Any] = dict(result["Attributes"])
        self.event(str(job["job_id"]), "PROCESSING", attempt=int(item["attempts"]))
        self.table.put_item(
            Item={
                "pk": job["pk"],
                "sk": f"ATTEMPT#{int(item['attempts']):05d}",
                "started_at": now(),
                "lease_token": token,
            }
        )
        return item

    def list(
        self, owner: str, status: str | None, limit: int, cursor: str | None
    ) -> dict[str, Any]:
        index = "by-status" if status else "by-owner"
        partition = f"OWNER#{owner}#STATUS#{status}" if status else f"OWNER#{owner}"
        options: dict[str, Any] = {
            "IndexName": index,
            "KeyConditionExpression": Key("gsi2pk" if status else "gsi1pk").eq(partition),
            "ScanIndexForward": False,
            "Limit": limit,
        }
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if decoded.get("gsi2pk" if status else "gsi1pk") != partition:
                    raise ValueError("Cursor belongs to a different query")
                options["ExclusiveStartKey"] = decoded
            except (ValueError, TypeError, AttributeError) as exc:
                raise ApiError(400, "INVALID_CURSOR", "Invalid pagination cursor") from exc
        response = self.table.query(**options)
        next_key = response.get("LastEvaluatedKey")
        return {
            "items": response["Items"],
            "cursor": base64.urlsafe_b64encode(json.dumps(next_key).encode()).decode()
            if next_key
            else None,
        }

    def history(self, job_id: str) -> builtins.list[dict[str, Any]]:
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(f"JOB#{job_id}") & Key("sk").begins_with("EVENT#"),
            Limit=100,
            ScanIndexForward=False,
            ConsistentRead=True,
        )
        return list(response["Items"])
