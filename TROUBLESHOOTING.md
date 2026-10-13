# Troubleshooting

| Symptom | Check and resolution |
|---|---|
| Local API is unreachable | Run `docker compose ps`, then visit `http://localhost:8000/health`. Start with `docker compose up --build -d` and inspect `docker compose logs -f api`. In-memory data resets after restart. |
| Browser reports CORS failure | Match the Vite origin to API Gateway, S3 CORS, and Cognito callback/logout settings. Use one exact HTTPS origin for a deployed host; never use `*` for authenticated origins. |
| Cognito callback fails | Check pool issuer, hosted auth domain, public client ID, `/callback` URL, logout URL and `cloudforge-api/jobs` scope. Rebuild with corrected settings. Do not configure a browser client secret. |
| Protected route returns 401 | Verify issuer, token expiry, `token_use`, client audience and API scope. Sign in again and request an access token for `cloudforge-api/jobs`. |
| Metrics returns 403 | Check Cognito `operators` group membership. Sign out and back in after an admin changes it so the access token includes the new group. |
| Job creation returns 400/422 | Check the 8–128 character idempotency key, plain `.csv` basename, file size, unique headers, and column rules. Fix the request and use a new key. The same request/key safely returns the existing job. |
| S3 rejects the presigned upload | Check five-minute expiry, required signed form fields, content type and exact file byte size. Request another link for the same `UPLOADING` job. |
| Job stays `UPLOADING` or `QUEUED` | Check S3 EventBridge notifications, bucket/prefix event rule, queue policy source ARN, event-source mapping and oldest queue age. Inspect the actual object-created event. |
| Job stays `PROCESSING` | Check lease expiry, Lambda concurrency, visibility timeout, receive count and worker logs. Allow the queue visibility window for a retry; inspect the DLQ before redriving. |
| `MISSING_COLUMNS` or `INVALID_NUMBER` | Check configured required/numeric headers and the file encoding. Correct the source and submit a new job. Sample validation errors omit raw values and cap at 100. |
| `RETRY_EXHAUSTED` | Inspect structured worker error type and queue/DLQ depth. Fix the service issue before deliberately creating a new job or redriving. |
| Terraform cannot access state | Verify account/region, bucket, key, AWS credentials and the one-key state policy, including `.tflock`. Use `terraform init -reconfigure` only when intentionally changing backend settings; never delete a lockfile manually. |
| Deployment stops before planning | Check `main`, GitHub region/state variables, plan OIDC subject, approved plan policy and `PLAN_PASSPHRASE`. Staging/prod also require reviewers and `AWS_APPLY_ROLE_ARN`. Never paste AWS credentials into workflow YAML. |
| Lambda zip is missing or incompatible | Run `uv run python scripts/package.py`; verify the checksums and Python 3.12 Linux x86_64 runtime. Do not build dependency wheels on Windows. |

Moto tests, Terraform validation and mocked-provider plans do not verify AWS quotas, live IAM, Cognito, regional pricing, or a deployed S3/EventBridge/SQS path. The opt-in smoke test writes one job, source object and result; remote use requires the explicit `--live` flag and a short-lived Cognito access token.
