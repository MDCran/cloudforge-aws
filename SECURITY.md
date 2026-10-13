# Security

## Identity and authorization

`GET /health` is the only intentionally public application route. Cognito JWT authorization and the `cloudforge-api/jobs` scope protect job, upload, result, and monitoring routes. The API uses only the verified Cognito `sub` as the owner, scopes each list/status query to that subject, and returns `JOB_NOT_FOUND` for another owner's ID. The metrics endpoint also requires the `operators` Cognito group. The user pool permits administrator-created accounts only; an account owner deliberately assigns operators.

API and worker Lambda functions use separate roles. The API can transact/query its job table, write to its upload prefix, read result objects, and inspect the assigned queue. The worker can update/query jobs, read exact source versions, write results, and consume its queue. GitHub plan and apply identities use short-lived OIDC sessions with different trust conditions and separately reviewed policy attachments. They have access only to their environment's state and lockfile. Do not add long-lived AWS keys to repository variables or workflows.

## File handling and data storage

Job requests are size bounded and validated. Filenames reject path separators. CSV inputs must be UTF-8 with at most 256 unique columns, 100,000 records and 10 MiB. Validation errors are limited to 100 sample entries and omit raw values. Numeric values must be finite and in a JSON-safe range. The API derives a job-scoped destination key and presigns an exact size, content type, encryption header, bucket and key for five minutes. The worker validates bucket, prefix, job state, file size, and exact S3 object version before reading. Report URLs expire after five minutes.

S3 blocks all public access, enforces bucket-owner controls, uses AWS-managed encryption and versioning, denies non-TLS requests, and applies bounded lifecycles. DynamoDB encryption and SQS managed encryption are enabled. CloudWatch logs use short environment-specific retention. Logging omits tokens, signed URLs, request bodies, CSV values, and raw exception text. Errors are sanitized; correlation IDs, job IDs and stable error codes support diagnosis. Result and source buckets remain separate.

## Reliability controls

The EventBridge rule selects only object-created events for the upload bucket and prefix. Its queue policy accepts sends only from the matching rule. The queue has a five-receive dead-letter policy and 14-day DLQ retention. Lambda reports partial batch failures. Hashed idempotency records, conditional transitions, attempt-specific result keys and expiring worker leases protect duplicate messages and overlapping workers. Running jobs cannot report cancellation because the operation cannot be stopped after it begins.

## CI and operational limits

Pull request workflows receive read-only repository permissions. They do not request AWS identity. Infrastructure deployment is manually dispatched against `main`; staging and prod require protected environment reviewers. The workflow encrypts and expires the saved plan artifact and publishes only resource actions and addresses. An administrator reviews the AWS service policies attached to plan/apply roles. Checkov infrastructure exceptions and their tradeoffs are listed in [`docs/security/scanner-exceptions.md`](docs/security/scanner-exceptions.md).

The local simulator is an in-memory Moto context bound to loopback. Local credentials exist only inside that mock context; no AWS identity is used. It resets when the process stops, is not an authentication boundary, and does not demonstrate live AWS behavior. This repository has not been validated against a live AWS account or certified for a regulatory regime. Assess CloudTrail, customer-managed keys, independent S3 object access auditing, cross-region recovery, stronger identity controls, and restore procedures before using sensitive production data.
