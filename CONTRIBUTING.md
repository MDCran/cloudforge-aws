# Contributing

Use Python 3.12, Node 22, uv, and Terraform 1.13.5. Work on a focused branch and describe the behavior changed and the checks run in each pull request.

Run `uv sync --locked`, `uv run ruff check .`, `uv run mypy apps packages`, and `uv run pytest` before submitting backend changes. Run `npm ci`, `npm run check`, and `npm test` in `apps/web` for dashboard changes. Validate all Terraform roots before changing infrastructure.

Use short, imperative commit subjects, such as `Handle duplicate upload notifications safely`. Keep comments focused on non-obvious constraints. Never commit credentials, Terraform state, plans, customer files, or private test data.
