.PHONY: help install dev lint test unit e2e crds operator-run kind-up kind-down clean

KIND_CLUSTER ?= elpio-dev

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

dev: ## Install with dev extras
	pip install -e '.[dev]'

lint: ## Lint with ruff
	ruff check src tests

test: unit ## Alias for unit tests

unit: ## Run unit tests (no cluster needed)
	pytest -m "not e2e"

e2e: ## Run e2e tests (needs a kind cluster + Knative/KEDA)
	ELPIO_E2E=1 pytest -m e2e

crds: ## Apply the CRDs to the current kube-context
	kubectl apply -f deploy/crds

operator-run: ## Run the operator locally against the current kube-context
	kopf run -m elpio.operator.handlers

kind-up: ## Create a local kind cluster
	kind create cluster --name $(KIND_CLUSTER) --config tests/e2e/kind-config.yaml

kind-down: ## Delete the local kind cluster
	kind delete cluster --name $(KIND_CLUSTER)

clean: ## Remove build/test artefacts
	rm -rf build dist *.egg-info .pytest_cache && find . -name __pycache__ -type d -prune -exec rm -rf {} +
