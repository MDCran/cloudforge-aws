# Deployment

The local Docker simulator and mocked Terraform tests need no AWS account. AWS deployment is a separate, manually dispatched workflow after its account, backend, GitHub OIDC roles, deployment permissions, and protected environments have been set up. Pull request workflows never assume AWS identity.

## Requirements

- Terraform 1.13.5, AWS CLI v2, Docker, `uv`, Node 22, and npm.
- A personal AWS account and globally unique S3 state bucket name. Review current regional pricing before deploying.
- A GitHub administrator who can set variables and a repository secret, create protected staging/prod environments with required reviewers, and inspect the policies attached to GitHub OIDC roles.

## Bootstrap remote state

1. Copy `infrastructure/bootstrap/terraform.tfvars.example` to `terraform.tfvars`. Replace the sample bucket and repository values.
2. Create reviewed customer-managed IAM policies for plan reads and deployment writes, and provide the ARNs as `plan_policy_arns` and `apply_policy_arns`. Bootstrap deliberately creates trust, not administrator access. An AWS owner must review every permission.
3. From the repository root, run `terraform -chdir=infrastructure/bootstrap init`, review `terraform -chdir=infrastructure/bootstrap plan`, then manually run `terraform -chdir=infrastructure/bootstrap apply`. This creates only the deletion-protected, TLS-only, versioned, encrypted state bucket, optional budget alert, OIDC provider/trust, and six plan/apply identities. Applying in AWS can incur charges. Review and approve it yourself.
4. Record the plan/apply role ARNs from Terraform output. Keep bootstrap variables, state, and plans private; never commit them.

The S3 backend uses native state lockfiles and versioned snapshots. Local work uses your regular AWS CLI profile. CI assumes short-lived GitHub OIDC credentials.

## IAM trust and policy scope

The plan role receives only its attached reviewed metadata-read policy plus access to one environment's state and `.tflock`. The apply role receives only its separately reviewed deployment policy and the same state restriction. Bootstrap attaches neither policy automatically.

| Environment | Plan OIDC `sub` | Apply OIDC `sub` | Resource prefix |
|---|---|---|---|
| dev | `repo:MDCran/cloudforge-aws:ref:refs/heads/main` | `repo:MDCran/cloudforge-aws:environment:dev` | `cloudforge-dev-` |
| staging | `repo:MDCran/cloudforge-aws:ref:refs/heads/main` | `repo:MDCran/cloudforge-aws:environment:staging` | `cloudforge-staging-` |
| prod | `repo:MDCran/cloudforge-aws:ref:refs/heads/main` | `repo:MDCran/cloudforge-aws:environment:prod` | `cloudforge-prod-` |

`ReadOnlyAccess` is not attached by default because it also exposes unrelated account data. Build environment-scoped policies from a Terraform plan reviewed in a non-production account. Allow only the required `Describe`, `Get`, and tag/list calls against CloudForge resources for planning, plus the exact service create/read/update/delete and constrained `iam:PassRole` calls needed by your reviewed resource set. Restrict role and policy manipulation to CloudForge execution-role prefixes. Set each plan trust to the repository's exact protected `main` ref. Set each apply trust to its environment subject. Do not broaden trust to arbitrary branches or repositories.

## GitHub settings

Protect `main` by requiring a pull request and passing `Backend checks`, `Dashboard checks`, `Terraform checks`, and `Dependency and secret scan`. Disallow force pushes and branch deletion. Set an approval requirement that fits the number of maintainers; the required checks still apply when a solo maintainer opens a pull request.

Set these repository variables:

| Variable | Value |
|---|---|
| `AWS_REGION` | One deployment region, such as `us-east-1`. |
| `TF_STATE_BUCKET` | The bootstrap bucket name. |
| `AWS_PLAN_ROLE_dev`, `AWS_PLAN_ROLE_staging`, `AWS_PLAN_ROLE_prod` | The corresponding plan-role ARNs. |
| `TF_CONFIG_dev`, `TF_CONFIG_staging`, `TF_CONFIG_prod` | JSON objects with `region` (matching `AWS_REGION`), explicit `origins`, Cognito `callback_urls` and `logout_urls`, `protect_data`, `retention_days`, `log_retention`, `worker_memory`, `worker_concurrency`, `api_concurrency`, and optional `alert_email`. Use the exact hosted HTTPS origin for a real dashboard; keep dev restricted to loopback origins. Do not put credentials or private data in these values. |

Set the repository secret `PLAN_PASSPHRASE` to a strong random value. Create environments named `dev`, `staging`, and `prod`, each with its own `AWS_APPLY_ROLE_ARN` variable. Set required reviewers for staging and prod; the plan job checks this before AWS authentication and apply waits for review. The workflow encrypts the saved Terraform plan, expires it after one day, verifies the checked-out revision, and shows resource addresses and actions without resource values. Manually dispatch **Deploy infrastructure** on `main` after reviewing the plan and the billable resources it creates.

After deployment, save Terraform outputs `api_url`, `user_pool_id`, `client_id`, `auth_url`, and `dashboard_name` into local configuration. An administrator can invite a Cognito user and add it to `operators`; this repository never invents an account or sends invitations.

## Dashboard and Cognito

Configure `apps/web/.env.example` with `VITE_MODE=aws`, the API URL, Cognito issuer, hosted domain, public client ID, callback URI, region, and environment. Use one HTTPS browser origin in API CORS, Cognito callbacks/logout URLs, and web hosting. The frontend uses authorization code with PKCE; never put a Cognito client secret in the browser.

Build with `npm ci && npm run build` from `apps/web`. Host the result through a separate HTTPS static host configured to serve `index.html` for `/callback`. CDN/static hosting is deliberately separate from baseline Terraform to keep demo resource cost optional. The user pool requires administrator-created accounts. A user needs membership in `operators` to see the operator metrics summary.

## Manual plan

```powershell
uv run python scripts/package.py
Copy-Item infrastructure/environments/dev/backend.hcl.example infrastructure/environments/dev/backend.hcl
# Edit backend.hcl with your state bucket before continuing.
terraform -chdir=infrastructure/environments/dev init -backend-config=backend.hcl
terraform -chdir=infrastructure/environments/dev plan
```

Inspect the complete local plan before any AWS apply. Do not commit the local variables, state, backend configuration, or plan. Review expected charges, permissions, region, and account before applying. Production and staging require their protected GitHub environments.
