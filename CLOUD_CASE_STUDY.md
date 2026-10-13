# CloudForge AWS: asynchronous CSV processing

## Problem

Teams need a repeatable way to receive a CSV, validate records, explain data-quality issues and publish reports without making a caller wait for an HTTP request to process the entire file. CloudForge makes this an asynchronous job with clear progress and bounded processing.

## Architecture and design

The browser authenticates with Cognito, and API Gateway routes scoped access tokens to the Python API Lambda. The API writes owner-scoped jobs and signs short-lived, size-limited upload forms. S3 object-created events flow through EventBridge and SQS to a separate Python worker. The worker checks the exact object version, computes a structured report, stores a versioned result and conditionally updates job state. SQS separates request latency from work duration. Terraform models shared infrastructure modules and separate environment roots. DynamoDB on-demand indexes match listing and filtering access patterns, so common requests do not scan the table.

## Reliability and security

Conditional state changes, request idempotency and expiring worker leases handle retries and duplicate notifications. Attempt-specific report paths prevent overlapping work from replacing earlier output. Partial batch responses and a dead-letter queue isolate failures. Invalid data fails terminally; already-running work cannot be labelled cancelled. API and worker roles are separate, bucket access is prefix-scoped, and GitHub obtains AWS sessions through OIDC with a manually reviewed plan and protected apply environment.

## Cost and verification

Request-driven Lambda/API Gateway, on-demand DynamoDB and S3/SQS avoid NAT gateways, reserved databases and always-running compute in the demo setup. Retention and concurrency are bounded. An optional AWS Budget email provides a delayed alert rather than a hard spending cap.

Automated tests cover CSV summaries, API validation, access isolation, cancellation races, idempotency, retries, the local upload-to-report flow, and dashboard behavior. Terraform validation and mocked-provider tests validate selected configuration without creating AWS resources. The project does not claim a live AWS deployment, benchmark, availability measurement or certification.

## Next steps at larger scale

Before handling sensitive production workloads, test real-account recovery; assess customer-managed keys, object-access auditing, CloudTrail, cross-region recovery, federated sign-in, distributed traces, application code signing, and gradual Lambda rollouts against operating requirements and cost.
