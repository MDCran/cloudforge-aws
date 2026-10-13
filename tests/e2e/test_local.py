from fastapi.testclient import TestClient

from scripts.local import app


def test_local_http_workflow() -> None:
    import time

    with TestClient(app) as client:
        data = b"name,amount\nAda,10\nBob,20\n"
        job = client.post(
            "/v1/jobs",
            json={"name": "Local flow", "filename": "data.csv", "size": len(data)},
            headers={"Idempotency-Key": "local-test-123"},
        ).json()
        upload = client.post("/v1/uploads/presign", json={"job_id": job["job_id"]}).json()
        assert (
            client.post(upload["url"], files={"file": ("data.csv", data, "text/csv")}).status_code
            == 202
        )
        for _ in range(30):
            finished = client.get(f"/v1/jobs/{job['job_id']}").json()
            if finished["status"] == "COMPLETED":
                break
            time.sleep(0.1)
        assert finished["status"] == "COMPLETED"
        result = client.get(f"/v1/jobs/{job['job_id']}/result").json()
        assert client.get(result["url"]).json()["row_count"] == 2
