# Makefile for OzBargain Deal Filter development tasks

.PHONY: help install install-dev test test-cov lint format type-check quality-check clean pre-commit-install pre-commit-run

# Default target
help:
	@echo "Available commands:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo "  test             Run tests"
	@echo "  test-cov         Run tests with coverage report"
	@echo "  lint             Run flake8 linting"
	@echo "  format           Format code with black and isort"
	@echo "  type-check       Run mypy type checking"
	@echo "  quality-check    Run all quality checks (lint, format, type-check)"
	@echo "  clean            Clean up generated files"
	@echo "  pre-commit-install Install pre-commit hooks"
	@echo "  pre-commit-run   Run pre-commit hooks on all files"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Testing targets
test:
	pytest

test-cov:
	pytest --cov=ozb_deal_filter --cov-report=term-missing --cov-report=html

# Code quality targets
lint:
	flake8 ozb_deal_filter/ tests/

format:
	black ozb_deal_filter/ tests/
	isort ozb_deal_filter/ tests/

type-check:
	mypy ozb_deal_filter/

# Combined quality check
quality-check: lint type-check
	@echo "All quality checks passed!"

# Pre-commit targets
pre-commit-install:
	pre-commit install

pre-commit-run:
	pre-commit run --all-files

# Cleanup targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Development workflow
dev-setup: install-dev pre-commit-install
	@echo "Development environment setup complete!"

# CI/CD simulation
ci-check: quality-check test-cov
	@echo "CI checks passed!"