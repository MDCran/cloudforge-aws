import argparse
import json
import os
import time
import uuid
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one bounded job against a selected API")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--live", action="store_true", help="Explicitly authorize one live AWS job")
    args = parser.parse_args()
    if not args.url.startswith(("http://localhost:", "http://127.0.0.1:")) and not args.live:
        parser.error("Remote smoke tests require --live; they create a job and upload a file")
    token = os.getenv("CLOUDFORGE_ACCESS_TOKEN", "")
    if args.live and not token:
        parser.error("Set CLOUDFORGE_ACCESS_TOKEN to a short-lived Cognito access token")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(timeout=15) as client:
        data = (Path(__file__).resolve().parents[1] / "examples/orders.csv").read_bytes()
        response = client.post(
            f"{args.url}/v1/jobs",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            json={
                "name": "Smoke test",
                "filename": "orders.csv",
                "size": len(data),
                "required_columns": ["customer"],
                "numeric_columns": ["amount"],
            },
        )
        response.raise_for_status()
        job = response.json()
        upload_response = client.post(
            f"{args.url}/v1/uploads/presign", headers=headers, json={"job_id": job["job_id"]}
        )
        upload_response.raise_for_status()
        upload = upload_response.json()
        response = client.post(
            upload["url"], data=upload["fields"], files={"file": ("orders.csv", data, "text/csv")}
        )
        response.raise_for_status()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            response = client.get(f"{args.url}/v1/jobs/{job['job_id']}", headers=headers)
            response.raise_for_status()
            state = response.json()
            if state["status"] == "FAILED":
                raise RuntimeError(f"Job failed: {state.get('error_code')}")
            if state["status"] == "COMPLETED":
                result = client.get(f"{args.url}/v1/jobs/{job['job_id']}/result", headers=headers)
                result.raise_for_status()
                report_response = client.get(result.json()["url"])
                report_response.raise_for_status()
                report = report_response.json()
                assert report["row_count"] == 6 and report["duplicate_rows"] == 1
                assert report["validation_error_count"] == 2
                print(
                    json.dumps(
                        {
                            "job_id": job["job_id"],
                            "status": "COMPLETED",
                            "row_count": report["row_count"],
                            "live": args.live,
                        }
                    )
                )
                return
            time.sleep(1)
        raise TimeoutError("Job did not finish within 90 seconds")


if __name__ == "__main__":
    main()
