# Operations

## Observability

Use the Terraform-named CloudWatch dashboard for the right account, region, and environment. Inspect HTTP request/errors and latency; API and worker Lambda errors, invocations and duration; queue age and visible messages; dead-letter depth; DynamoDB throttling; and custom completed/failed job outcomes. Alarms use native service metrics in five-minute periods and notify the SNS topic. Email recipients must confirm their subscription. Missing data is treated as non-breaching; verify alarm behavior in the deployed account before relying on it.

Application logs are structured JSON. Search by correlation ID, job ID, SQS message ID, stable error code and environment. The API and worker do not log upload data, tokens, signed URLs, request bodies, or exception payloads.

## Queue and job recovery

1. Identify the job from event history and its structured worker log record.
2. For an old visible message, inspect the exact S3 object version, expected byte size, job state, worker errors, Lambda throttles and queue age. Keep SQS visibility timeout at least six times the worker timeout.
3. For transiently `FAILED`/`RETRY_EXHAUSTED`, resolve the service problem, then create a new job after checking for an existing report. Every attempt uses its own report key.
4. For a permanent validation error, correct the input and create a new job. Invalid files fail terminally.
5. For a dead-letter message, determine whether it is malformed event data, a missing job, a stale object version, an unsupported event or an exhausted service failure. Fix the cause before a deliberate redrive and verify that the message cannot loop.
6. Cancellation only works for `CREATED`, `UPLOADING`, and `QUEUED`. Upload links cannot be revoked once issued; later events for a cancelled job are acknowledged without processing. Running work finishes or fails through its lease.

## Deploy and recover

The CI workflow validates every change. Manually dispatch deployment for the selected environment, review its resource-action summary and account/region, then approve through the protected staging/prod environment. Apply the reviewed plan once; if it expires, generate a new plan. Terraform owns these resources: inspect the plan before reconciling any console edit.

Terraform can restore an earlier infrastructure definition from a commit; it does not restore application data. S3 versioning keeps prior file/report versions and the protected bootstrap bucket keeps prior Terraform states. Staging/prod DynamoDB point-in-time recovery is enabled, but a live restore has not been tested. Save an isolated state snapshot and rehearse object-version and table recovery before processing production data. Never force-delete a bucket to make `terraform destroy` succeed.

## Drift

After setting up the optional dev plan-role variables, the weekly read-only workflow runs `terraform plan -refresh-only`. Exit code 2 identifies a difference for human investigation; the workflow does not apply or reconcile it. Check for console edits, wrong account/region, expired OIDC access and manual state changes. The plan role still needs reviewed metadata read permissions.

## Tear down dev

Export results that need to be kept, review all object versions, and verify account, region and environment before any destruction. Both the PowerShell helper and Make target restrict automatic teardown to dev and require typing `DESTROY dev`; inspect the Terraform plan yourself. Nonempty versioned buckets block deletion. The separate protected bootstrap bucket and its state remain. Staging/prod require a separately reviewed manual change and recovery plan.
