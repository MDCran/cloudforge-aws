# Infrastructure scanner exceptions

Checkov scans the complete Terraform configuration. `.checkov.yaml` excludes the following controls globally because this portfolio intentionally uses a small serverless deployment. These exceptions are design tradeoffs, not evidence that the controls are satisfied. Reassess them before handling confidential data or deploying beyond a demonstration account.

| Control | Reason and compensating behavior |
|---|---|
| CKV_AWS_116 | The API is invoked synchronously. SQS owns worker retries and the dead-letter queue; Lambda asynchronous invocation DLQs do not apply to these event sources. |
| CKV_AWS_117 | No private VPC dependencies. A VPC would add complexity without isolating access to public AWS service endpoints; execution roles scope service access. |
| CKV_AWS_119, CKV_AWS_145, CKV_AWS_158, CKV_AWS_173 | DynamoDB, S3, logs, and Lambda use AWS-owned or AWS-managed encryption. Customer-managed KMS keys and independent rotation controls are outside this low-cost baseline. |
| CKV_AWS_144 | No cross-region replication. Region-wide recovery is not implemented. |
| CKV_AWS_18 | S3 access logging is not enabled. Application state history and API logs are available; they are not a substitute for a complete object-access audit trail. |
| CKV_AWS_272 | Lambda code signing is not configured. Packages are deterministically built, checksummed, and applied from the reviewed workflow revision. |
| CKV_AWS_28 | Point-in-time recovery is disabled in dev and enabled in staging/prod. Environment contract tests verify the defaults. |
| CKV_AWS_309 | `GET /health` is intentionally public. Contract tests require JWT and a Cognito scope for every private application route. |
| CKV_AWS_338 | Logs have 7/14/30-day retention rather than one year to bound demonstration costs. |
| CKV_AWS_50 | Distributed X-Ray tracing is not implemented. Correlation IDs, native metrics, and structured worker logs support basic diagnosis. |
| CKV2_AWS_34 | The only SSM value is a public API URL. It is not a secret and uses String. |
| CKV2_AWS_61 | Application buckets have lifecycle policies. The versioned, deletion-protected state bucket deliberately keeps state history indefinitely. |
| CKV2_AWS_62 | Only upload storage needs EventBridge notifications. Results and state buckets have no event consumers. |

Because exclusions are global, Python infrastructure contract tests and Terraform mocked-provider tests independently check private routes, bucket restrictions, retry settings, state isolation, and OIDC trust. A clean scan does not certify the architecture.
