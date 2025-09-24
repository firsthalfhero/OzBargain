# Testing Infrastructure

This document describes the comprehensive testing infrastructure for the OzBargain Deal Filter project.

## Overview

The project uses a multi-layered testing approach with:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: Tests for component interactions
- **Performance Benchmarks**: Performance and load testing
- **Security Tests**: Security vulnerability scanning
- **Code Quality Checks**: Linting, formatting, and type checking

## Test Categories

### Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit`: Fast unit tests (default)
- `@pytest.mark.integration`: Integration tests requiring external services
- `@pytest.mark.slow`: Slow-running tests (LLM calls, network requests)
- `@pytest.mark.benchmark`: Performance benchmark tests
- `@pytest.mark.network`: Tests requiring network access
- `@pytest.mark.docker`: Tests requiring Docker

### Running Tests

#### Using Scripts

```bash
# Run all tests
python scripts/run-tests.py

# Run specific test categories
python scripts/run-tests.py --unit
python scripts/run-tests.py --integration
python scripts/run-tests.py --fast
python scripts/run-tests.py --slow

# Run with coverage
python scripts/run-tests.py --coverage

# Run in parallel
python scripts/run-tests.py --parallel

# Generate comprehensive report
python scripts/run-tests.py --report
```

#### Using Make Commands

```bash
# Run all tests
make test

# Run specific categories
make test-unit
make test-integration
make test-fast
make test-slow
make test-parallel

# Run with coverage
make test-cov

# Generate reports
make test-report
```

#### Using Pytest Directly

```bash
# Run all tests
pytest

# Run specific markers
pytest -m unit
pytest -m "not slow"
pytest -m integration

# Run with coverage
pytest --cov=ozb_deal_filter --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run specific test function
pytest tests/test_models.py::test_deal_validation
```

## Code Quality Checks

### Quality Check Script

The `scripts/quality-check.py` script runs comprehensive code quality checks:

```bash
# Run all quality checks
python scripts/quality-check.py

# Auto-fix formatting issues
python scripts/quality-check.py --fix

# Run fast checks only (skip slow tests)
python scripts/quality-check.py --fast
```

### Individual Quality Tools

```bash
# Code formatting
black ozb_deal_filter/ tests/
isort ozb_deal_filter/ tests/

# Linting
flake8 ozb_deal_filter/ tests/

# Type checking
mypy ozb_deal_filter/

# Security scanning
bandit -r ozb_deal_filter/
```

## Test Configuration

### Pytest Configuration

Configuration is defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=ozb_deal_filter",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=85",
]
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "benchmark: marks tests as performance benchmarks",
    "network: marks tests that require network access",
    "docker: marks tests that require Docker",
]
```

### Coverage Configuration

Coverage settings are also in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["ozb_deal_filter"]
omit = [
    "*/tests/*",
    "*/test_*.py",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

## Test Fixtures

Comprehensive test fixtures are available in `tests/conftest.py`:

### Data Fixtures

- `sample_raw_deal`: Raw RSS deal data
- `sample_deal`: Parsed deal object
- `sample_evaluation_result`: LLM evaluation result
- `sample_filter_result`: Filter engine result
- `sample_formatted_alert`: Formatted alert message
- `sample_configuration`: Complete system configuration

### Mock Fixtures

- `mock_rss_feed`: Mock RSS feed XML data
- `mock_llm_evaluator`: Mock LLM evaluator
- `mock_message_dispatcher`: Mock message dispatcher
- `mock_git_agent`: Mock git operations

### Environment Fixtures

- `temp_dir`: Temporary directory for tests
- `temp_git_repo`: Temporary git repository
- `mock_env_vars`: Mock environment variables

## Continuous Integration

### GitHub Actions

The project includes a comprehensive CI/CD pipeline (`.github/workflows/ci.yml`):

- **Multi-platform testing**: Ubuntu, Windows, macOS
- **Multi-version testing**: Python 3.11, 3.12
- **Code quality checks**: All quality tools
- **Security scanning**: Bandit and Safety
- **Docker testing**: Container build and test
- **Performance benchmarks**: Automated performance testing

### Pre-commit Hooks

Pre-commit hooks are configured in `.pre-commit-config.yaml`:

- Code formatting (Black, isort)
- Linting (Flake8)
- Type checking (MyPy)
- Security scanning (Bandit)
- General file checks

Install pre-commit hooks:

```bash
pre-commit install
```

Run pre-commit hooks manually:

```bash
pre-commit run --all-files
```

## Development Workflow

### Initial Setup

```bash
# Complete development environment setup
make dev-setup
# or
python scripts/setup-dev.py
```

### Daily Development

```bash
# Before committing
make dev-check  # Fast quality checks and tests

# Before pushing
make ci-check   # Full CI simulation
```

### Test-Driven Development

1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green
4. Run quality checks before committing

## Performance Testing

### Benchmark Tests

Performance benchmarks use `pytest-benchmark`:

```python
@pytest.mark.benchmark
def test_deal_parsing_performance(benchmark, sample_raw_deal):
    parser = DealParser()
    result = benchmark(parser.parse_deal, sample_raw_deal)
    assert result.title == sample_raw_deal.title
```

Run benchmarks:

```bash
pytest -m benchmark --benchmark-only
```

### Load Testing

For load testing RSS monitoring and LLM evaluation:

```python
@pytest.mark.slow
@pytest.mark.benchmark
def test_concurrent_deal_processing(benchmark):
    # Test concurrent processing of multiple deals
    pass
```

## Debugging Tests

### Verbose Output

```bash
pytest -v  # Verbose test names
pytest -s  # Don't capture output (show prints)
pytest -vv # Extra verbose
```

### Debugging Specific Tests

```bash
# Run specific test with debugging
pytest tests/test_models.py::test_deal_validation -v -s

# Run last failed tests
pytest --lf

# Run tests that failed in last run, then all
pytest --ff
```

### Test Coverage Analysis

```bash
# Generate HTML coverage report
pytest --cov=ozb_deal_filter --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html # Windows
```

## Best Practices

### Writing Tests

1. **Use descriptive test names**: `test_deal_validation_fails_with_negative_price`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Use appropriate markers**: Mark slow tests, integration tests, etc.
4. **Mock external dependencies**: Use fixtures for consistent test data
5. **Test edge cases**: Empty inputs, boundary values, error conditions

### Test Organization

1. **One test file per module**: `test_deal_parser.py` for `deal_parser.py`
2. **Group related tests**: Use test classes for related functionality
3. **Use fixtures**: Avoid code duplication with shared fixtures
4. **Separate unit and integration tests**: Clear separation of concerns

### Performance Considerations

1. **Mark slow tests**: Use `@pytest.mark.slow` for tests > 1 second
2. **Use parallel execution**: Run tests with `-n auto` for speed
3. **Mock expensive operations**: Don't make real API calls in unit tests
4. **Profile test performance**: Use `--benchmark` for performance tests

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure project is installed in development mode (`pip install -e .`)
2. **Missing dependencies**: Run `pip install -e ".[dev]"` to install dev dependencies
3. **Permission errors**: On Windows, run scripts with `python scripts/script-name.py`
4. **Coverage too low**: Check `htmlcov/index.html` for uncovered lines

### Getting Help

1. Check test output for specific error messages
2. Run tests with `-v` for verbose output
3. Use `pytest --collect-only` to see available tests
4. Check GitHub Actions for CI failures
