ENV ?= dev
TF_ROOT = infrastructure/environments/$(ENV)
.PHONY: setup dev test lint security package terraform-fmt terraform-validate terraform-plan terraform-apply terraform-destroy smoke-test
setup:
	uv sync --locked
	cd apps/web && npm ci
dev:
	docker compose up --build -d
	cd apps/web && VITE_MODE=local npm run dev
test:
	uv run pytest
	cd apps/web && npm test
lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy apps packages scripts
	cd apps/web && npm run check
security:
	uvx --from checkov==3.2.459 checkov --config-file .checkov.yaml
	trivy fs --scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1 .
package:
	uv run python scripts/package.py
	uv run python scripts/verify_packages.py
terraform-fmt:
	terraform fmt -recursive infrastructure
terraform-validate:
	@set -e; for root in infrastructure/bootstrap infrastructure/environments/dev infrastructure/environments/staging infrastructure/environments/prod; do terraform -chdir=$$root init -backend=false -input=false; terraform -chdir=$$root validate; done
terraform-plan:
	terraform -chdir=$(TF_ROOT) init -backend-config=backend.hcl
	terraform -chdir=$(TF_ROOT) plan -out=deployment.tfplan
terraform-apply:
	@read -p "Type APPLY $(ENV) to deploy billable AWS resources: " answer; test "$$answer" = "APPLY $(ENV)"
	terraform -chdir=$(TF_ROOT) apply deployment.tfplan
terraform-destroy:
	@test "$(ENV)" = "dev" || (echo "Teardown is restricted to dev. See OPERATIONS.md."; exit 1)
	@read -p "Type DESTROY $(ENV) to delete development infrastructure: " answer; test "$$answer" = "DESTROY $(ENV)"
	terraform -chdir=$(TF_ROOT) destroy
smoke-test:
	uv run python scripts/smoke.py
