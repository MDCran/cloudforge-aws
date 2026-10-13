import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager, suppress
from typing import Any

import boto3
from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from moto import mock_aws
from shared.config import Settings
from shared.repository import Repository

from apps.api.handler import handler as api_handler
from apps.worker.handler import handler as worker_handler
from scripts.local_resources import create_resources


async def consume() -> None:
    sqs = boto3.client("sqs", region_name="us-east-1")
    while True:
        messages = sqs.receive_message(
            QueueUrl=os.environ["QUEUE_URL"],
            MaxNumberOfMessages=1,
            MessageSystemAttributeNames=["ApproximateReceiveCount"],
        ).get("Messages", [])
        for message in messages:
            result = await asyncio.to_thread(
                worker_handler,
                {
                    "Records": [
                        {
                            "messageId": message["MessageId"],
                            "body": message["Body"],
                            "attributes": message.get("Attributes", {}),
                        }
                    ]
                },
                None,
            )
            if not result["batchItemFailures"]:
                sqs.delete_message(
                    QueueUrl=os.environ["QUEUE_URL"], ReceiptHandle=message["ReceiptHandle"]
                )
        await asyncio.sleep(0.3)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    with mock_aws():
        create_resources()
        task = asyncio.create_task(consume())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="CloudForge local simulator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.post("/local/upload/{job_id}")
async def upload(job_id: str, file: UploadFile) -> JSONResponse:
    settings = Settings.load()
    job = Repository(settings).get(job_id, "local-user")
    data = await file.read(settings.max_bytes + 1)
    if (
        len(data) > settings.max_bytes
        or len(data) != int(job["size"])
        or job["status"] != "UPLOADING"
    ):
        return JSONResponse({"error": "Upload is closed or has invalid size"}, status_code=400)
    key = f"uploads/{job_id}/input.csv"
    response = boto3.client("s3", region_name=settings.region).put_object(
        Bucket=settings.uploads, Key=key, Body=data, ContentType="text/csv"
    )
    event = {
        "id": str(uuid.uuid4()),
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {
            "bucket": {"name": settings.uploads},
            "object": {"key": key, "version-id": response["VersionId"], "etag": response["ETag"]},
        },
    }
    boto3.client("sqs", region_name=settings.region).send_message(
        QueueUrl=settings.queue_url, MessageBody=json.dumps(event)
    )
    return JSONResponse({"accepted": True}, status_code=202)


@app.get("/local/result/{job_id}")
async def result(job_id: str) -> Response:
    settings = Settings.load()
    job = Repository(settings).get(job_id, "local-user")
    if job["status"] != "COMPLETED":
        return JSONResponse({"error": "Result not ready"}, status_code=409)
    response = boto3.client("s3", region_name=settings.region).get_object(
        Bucket=settings.results, Key=job["result_key"]
    )
    return Response(
        response["Body"].read(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="report.json"'},
    )


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def dispatch(request: Request, path: str) -> JSONResponse:
    data = await request.body()
    if len(data) > 16384:
        return JSONResponse({"error": "Request too large"}, status_code=413)
    event = {
        "rawPath": f"/{path}",
        "headers": dict(request.headers),
        "queryStringParameters": dict(request.query_params),
        "body": data.decode(),
        "requestContext": {
            "http": {"method": request.method},
            "requestId": str(uuid.uuid4()),
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "local-user",
                        "token_use": "access",
                        "cognito:groups": "operators",
                    }
                }
            },
        },
    }
    response = api_handler(event, None)
    body = json.loads(response["body"])
    if path == "v1/uploads/presign" and response["statusCode"] == 200:
        body.update(url=f"{request.base_url}local/upload/{body['job_id']}", fields={})
    if path.endswith("/result") and response["statusCode"] == 200:
        job_id = path.split("/")[2]
        body["url"] = f"{request.base_url}local/result/{job_id}"
    return JSONResponse(body, status_code=response["statusCode"], headers=response["headers"])
