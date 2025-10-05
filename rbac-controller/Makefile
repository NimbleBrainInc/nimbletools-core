# NimbleTools RBAC Controller - Development Makefile
.PHONY: help install dev test lint type-check format clean docker-build docker-run

# Default target
help: ## Show this help message
	@echo "NimbleTools RBAC Controller Development Commands"
	@echo "==============================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development setup
install: ## Install dependencies
	uv sync --dev --frozen

dev: install ## Set up development environment
	@echo "Development environment ready!"
	@echo "Run 'make run' to start the controller"

# Code quality
lint: ## Run linting with ruff
	uv run ruff check src/ tests/

format: ## Format code with ruff
	uv run ruff format src/ tests/
	uv run ruff check src/ tests/ --fix

type-check: ## Run type checking with mypy
	uv run mypy --package nimbletools_rbac_controller

# Testing
test: ## Run tests with pytest
	uv run pytest tests/ -v

test-cov: ## Run tests with coverage report
	uv run pytest tests/ --cov=nimbletools_rbac_controller --cov-report=html --cov-report=term-missing

# Quality checks
check: lint type-check test ## Run all quality checks (basic)

# Combined verify target for CI/CD
verify: ## Run all verification steps (format, lint, type-check, test) - use COVERAGE=1 for coverage reports
	@echo "🔍 Running full verification suite..."
	@echo "================================"
	@echo "✨ Formatting code..."
	uv run ruff format src/ tests/
	uv run ruff check src/ tests/ --fix
	@echo "🔍 Running linting..."
	uv run ruff check src/ tests/
	@echo "🏷️  Running type checking..."
	uv run mypy --package nimbletools_rbac_controller
	@echo "🧪 Running tests..."
ifdef COVERAGE
	uv run pytest tests/ --cov=nimbletools_rbac_controller --cov-report=xml --cov-report=term-missing
else
	uv run pytest tests/ -v
endif
	@echo ""
	@echo "✅ All verification steps passed!"

# Development run (requires k8s cluster)
run: ## Run controller locally
	uv run python -m nimbletools_rbac_controller.main

# Docker
docker-build: ## Build Docker image
	docker build -t nimbletools-rbac-controller .

docker-run: ## Run Docker container
	docker run --rm --name nimbletools-rbac-controller nimbletools-rbac-controller

# Cleanup
clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
	rm -f coverage.xml .coverage

# Lock file management
lock: ## Update lock file
	uv lock

# Generate requirements.txt for compatibility
requirements: ## Generate requirements.txt from uv.lock
	uv pip compile pyproject.toml -o requirements.txt