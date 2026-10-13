# Contributing

Use Python 3.12, Node 22, `uv`, and Terraform 1.13.5. Create a focused branch and describe the changed behavior, checks, operational impact and limitations in each pull request.

Run `uv sync --locked`, `uv run ruff check .`, `uv run mypy apps packages scripts`, and `uv run pytest` before backend/infrastructure changes. Run `npm ci`, `npm run check`, `npm test`, and `npm run test:e2e` in `apps/web` for dashboard changes. Run Terraform formatting, validation, mocked-provider tests, Checkov and Trivy. Describe Moto/mock-provider results as simulated rather than live AWS verification.

Use short imperative commit subjects such as `Handle duplicate upload notifications safely`. Keep comments for non-obvious constraints. Never commit credentials, Terraform state/plans, customer data, generated Lambda archives, or private test files. Edit all Terraform roots from compatible modules and preserve explicit per-environment state keys.
