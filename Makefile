SHELL := /bin/bash
PYTHON := .venv/bin/python
PROJECT_ID ?= pairpilot-agentic-ecb84a

.PHONY: bootstrap dev lint typecheck test test-live seed reset deploy deploy-candidate verify submission-check

bootstrap:
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) infra/bootstrap_gcp.sh

dev:
	@set -euo pipefail; \
	PAIRPILOT_PEER_ID_TOKEN="$$(gcloud auth print-identity-token)" \
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) GOOGLE_CLOUD_LOCATION=global \
	PAIRPILOT_MODEL_ID=gemini-3.7-flash \
	PAIRPILOT_PEER_BASE_URL=https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app \
	PAIRPILOT_WEB_DIST="$$(pwd)/web/dist" \
	PYTHONPATH=.:packages/schemas:services/orchestrator:services/peer_agents \
	.venv/bin/uvicorn pairpilot_orchestrator.web:app --host 127.0.0.1 --port 8080 & \
	API_PID=$$!; trap 'kill $$API_PID 2>/dev/null || true' EXIT; \
	npm --prefix web run dev

lint:
	.venv/bin/ruff check .
	npm --prefix web run lint

typecheck:
	.venv/bin/mypy --strict packages/schemas services/orchestrator services/peer_agents
	npm --prefix web run typecheck

test:
	.venv/bin/pytest tests/unit -q
	npm --prefix web test

test-live:
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) .venv/bin/pytest tests/integration -q

seed:
	$(PYTHON) infra/seed_demo.py --project $(PROJECT_ID)

reset:
	$(PYTHON) infra/reset_demo.py --project $(PROJECT_ID) --reset-workflow --confirm-project $(PROJECT_ID)

deploy:
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) infra/deploy.sh

deploy-candidate:
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
	PAIRPILOT_DEPLOY_CANDIDATE=DEPLOY_ISOLATED_V2_CANDIDATE \
	bash infra/deploy_startup_v2_candidate.sh

verify:
	GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) infra/verify_deployment.sh

submission-check: lint typecheck test
	npm --prefix web run build
	git diff --check
	@! git grep -n -E '(RXPT-[A-Z0-9-]+|BEGIN (RSA |EC )?PRIVATE KEY|AIza[0-9A-Za-z_-]{30,})'
