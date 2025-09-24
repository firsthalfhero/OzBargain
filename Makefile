# Makefile for OzBargain Deal Filter development tasks

.PHONY: help install install-dev test test-cov test-unit test-integration test-fast test-slow test-parallel lint format type-check quality-check clean pre-commit-install pre-commit-run dev-setup reports

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  dev-setup        Complete development environment setup"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-fast        Run fast tests only"
	@echo "  test-slow        Run slow tests only"
	@echo "  test-parallel    Run tests in parallel"
	@echo "  test-cov         Run tests with coverage report"
	@echo "  test-report      Generate comprehensive test report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run flake8 linting"
	@echo "  format           Format code with black and isort"
	@echo "  format-check     Check code formatting"
	@echo "  type-check       Run mypy type checking"
	@echo "  security-check   Run security checks with bandit"
	@echo "  quality-check    Run all quality checks"
	@echo "  quality-fix      Auto-fix formatting issues"
	@echo ""
	@echo "Git and Pre-commit:"
	@echo "  pre-commit-install Install pre-commit hooks"
	@echo "  pre-commit-run   Run pre-commit hooks on all files"
	@echo ""
	@echo "Utilities:"
	@echo "  clean            Clean up generated files"
	@echo "  reports          Generate all reports"

# Setup and Installation targets
dev-setup:
	python scripts/setup-dev.py

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testing targets
test:
	python scripts/run-tests.py

test-unit:
	python scripts/run-tests.py --unit

test-integration:
	python scripts/run-tests.py --integration

test-fast:
	python scripts/run-tests.py --fast

test-slow:
	python scripts/run-tests.py --slow

test-parallel:
	python scripts/run-tests.py --parallel

test-cov:
	python scripts/run-tests.py --coverage

test-report:
	python scripts/run-tests.py --report

# Code quality targets
lint:
	flake8 ozb_deal_filter/ tests/

format:
	black ozb_deal_filter/ tests/
	isort ozb_deal_filter/ tests/

format-check:
	black --check ozb_deal_filter/ tests/
	isort --check-only ozb_deal_filter/ tests/

type-check:
	mypy ozb_deal_filter/

security-check:
	bandit -r ozb_deal_filter/

quality-check:
	python scripts/quality-check.py

quality-fix:
	python scripts/quality-check.py --fix

# Pre-commit targets
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files

# Cleanup targets
clean:
	python scripts/run-tests.py --clean
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Reports and documentation
reports: test-report
	@echo "All reports generated!"

# Development workflow shortcuts
dev-check: quality-check test-fast
	@echo "Development checks passed!"

# CI/CD simulation
ci-check: quality-check test-cov
	@echo "CI checks passed!"

# Docker targets
docker-build:
	docker build -t ozb-deal-filter:latest .

docker-test:
	docker run --rm ozb-deal-filter:latest python -c "import ozb_deal_filter; print('Import successful')"
