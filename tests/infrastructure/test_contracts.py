from pathlib import Path
from typing import Any

import hcl2

ROOT = Path(__file__).resolve().parents[2] / "infrastructure"


def config(module: str) -> dict[str, Any]:
    with (ROOT / "modules" / module / "main.tf").open() as source:
        return hcl2.load(source)


def resource(module: str, kind: str, name: str) -> dict[str, Any]:
    for item in config(module)["resource"]:
        for raw_kind, instances in item.items():
            if raw_kind.strip('"') == kind:
                for raw_name, body in instances.items():
                    if raw_name.strip('"') == name:
                        return body
    raise AssertionError(f"Missing {kind}.{name}")


def test_s3_is_private_and_versioned() -> None:
    block = resource("s3", "aws_s3_bucket_public_access_block", "this")
    assert all(
        block[key] is True
        for key in (
            "block_public_acls",
            "block_public_policy",
            "ignore_public_acls",
            "restrict_public_buckets",
        )
    )
    versioning = resource("s3", "aws_s3_bucket_versioning", "this")
    assert versioning["versioning_configuration"][0]["status"].strip('"') == "Enabled"
    assert "aws:SecureTransport" in resource("s3", "aws_s3_bucket_policy", "this")["policy"]


def test_all_application_routes_require_jwt_except_liveness() -> None:
    routes = resource("api-gateway", "aws_apigatewayv2_route", "secured")
    assert routes["authorization_type"].strip('"') == "JWT"
    assert routes["authorization_scopes"][0].strip('"') == "cloudforge-api/jobs"
    assert (
        resource("api-gateway", "aws_apigatewayv2_route", "health")["route_key"].strip('"')
        == "GET /health"
    )
    assert (
        "*"
        not in resource("api-gateway", "aws_apigatewayv2_api", "this")["cors_configuration"][0][
            "allow_origins"
        ]
    )


def test_retries_and_batch_failures_are_enabled() -> None:
    queue = resource("sqs", "aws_sqs_queue", "this")
    assert queue["sqs_managed_sse_enabled"] is True
    assert "* 6" in queue["visibility_timeout_seconds"]
    assert "maxReceiveCount" in queue["redrive_policy"]
    mapping = resource("platform", "aws_lambda_event_source_mapping", "worker")
    assert [value.strip('"') for value in mapping["function_response_types"]] == [
        "ReportBatchItemFailures"
    ]
    assert mapping["batch_size"] == 1


def test_execution_policies_have_no_service_wildcards() -> None:
    text = (ROOT / "modules/platform/main.tf").read_text()
    assert 'Action = ["*"' not in text
    for service in ("s3", "dynamodb", "sqs", "iam"):
        assert f'"{service}:*"' not in text
    assert '"s3:GetObjectVersion"' in text
    assert "module.queue.arn" in text


def test_environment_state_and_data_isolation() -> None:
    for environment in ("dev", "staging", "prod"):
        root = ROOT / "environments" / environment
        backend = (root / "backend.hcl.example").read_text()
        assert f'key = "{environment}/terraform.tfstate"' in backend
        assert "use_lockfile = true" in backend
        with (root / "main.tf").open() as source:
            parsed = hcl2.load(source)
        platform = parsed["module"][0]['"platform"']
        assert platform["environment"].strip('"') == environment
        variables = {
            key.strip('"'): value for item in parsed["variable"] for key, value in item.items()
        }
        assert variables["protect_data"]["default"] is (environment != "dev")
        workflow_inputs = {
            "region",
            "origins",
            "callback_urls",
            "logout_urls",
            "protect_data",
            "retention_days",
            "log_retention",
            "worker_memory",
            "worker_concurrency",
            "api_concurrency",
            "alert_email",
        }
        assert workflow_inputs <= variables.keys()


def test_oidc_subjects_restrict_repository_and_environment() -> None:
    plan = resource("deployment-identity", "aws_iam_role", "plan")["assume_role_policy"]
    apply = resource("deployment-identity", "aws_iam_role", "apply")["assume_role_policy"]
    assert "ref:refs/heads/main" in str(plan)
    assert "environment:" in str(apply)
    assert "sts.amazonaws.com" in str(plan) and "sts.amazonaws.com" in str(apply)
    assert "repo:*" not in str(plan) + str(apply)
