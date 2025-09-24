# Development Environment Setup

This document provides a comprehensive guide for setting up the OzBargain Deal Filter development environment.

## Quick Start

For a complete automated setup, run:

```bash
# Complete development environment setup
python scripts/setup-dev.py

# Or using make
make dev-setup
```

## Manual Setup

### 1. Prerequisites

- Python 3.11 or higher
- Git
- Docker (optional, for local LLM testing)

### 2. Clone and Install

```bash
# Clone the repository
git clone <repository-url>
cd ozb-deal-filter

# Install development dependencies
pip install -e ".[dev]"
```

### 3. Setup Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Test pre-commit hooks
pre-commit run --all-files
```

### 4. Verify Setup

```bash
# Run fast tests
python scripts/run-tests.py --fast

# Run quality checks
python scripts/quality-check.py --fast

# Or use make commands
make test-fast
make quality-check
```

## Development Tools

### Testing

The project includes comprehensive testing infrastructure:

```bash
# Run all tests
make test

# Run specific test categories
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-fast          # Fast tests (exclude slow ones)
make test-slow          # Slow tests only
make test-parallel      # Run tests in parallel

# Generate test reports
make test-report        # Comprehensive test report with coverage
```

### Code Quality

Multiple code quality tools are configured:

```bash
# Run all quality checks
make quality-check

# Individual tools
make lint               # Flake8 linting
make format            # Black + isort formatting
make format-check      # Check formatting without changes
make type-check        # MyPy type checking
make security-check    # Bandit security scanning

# Auto-fix formatting issues
make quality-fix
```

### Development Scripts

Three main development scripts are available:

#### 1. Setup Script (`scripts/setup-dev.py`)

Complete development environment setup:

```bash
python scripts/setup-dev.py [--skip-tests] [--project-root PATH]
```

Features:
- Python version validation
- Virtual environment creation
- Dependency installation
- Directory structure creation
- Pre-commit hooks setup
- Git hooks configuration
- Initial test run

#### 2. Test Runner (`scripts/run-tests.py`)

Comprehensive test execution with multiple options:

```bash
# Basic usage
python scripts/run-tests.py [options]

# Test categories
--unit              # Unit tests only
--integration       # Integration tests only
--fast              # Fast tests (exclude slow)
--slow              # Slow tests only
--network           # Network-dependent tests
--docker            # Docker-dependent tests
--benchmark         # Performance benchmarks

# Execution options
--coverage          # Run with coverage reporting
--parallel          # Run tests in parallel
--workers N         # Number of parallel workers
--verbose           # Verbose output

# Utilities
--report            # Generate comprehensive report
--clean             # Clean test artifacts
--test PATH         # Run specific test
--failed            # Re-run failed tests from last run
```

#### 3. Quality Checker (`scripts/quality-check.py`)

Comprehensive code quality validation:

```bash
# Basic usage
python scripts/quality-check.py [options]

# Options
--fix               # Auto-fix formatting issues
--fast              # Skip slow checks (tests)
--project-root PATH # Specify project root
```

Quality checks include:
- Dependency consistency
- Black code formatting
- Import sorting (isort)
- Flake8 linting
- MyPy type checking
- Bandit security scanning
- Test execution with coverage

## Configuration Files

### Core Configuration

- **`pyproject.toml`**: Main project configuration
  - Build system configuration
  - Dependencies and optional dependencies
  - Tool configurations (pytest, black, mypy, etc.)
  - Coverage settings

- **`setup.cfg`**: Flake8 configuration
  - Line length and ignore rules
  - Per-file ignores
  - Complexity limits

- **`.pre-commit-config.yaml`**: Pre-commit hooks
  - Code formatting (Black, isort)
  - Linting (Flake8)
  - Type checking (MyPy)
  - Security scanning (Bandit)
  - General file checks

### Testing Configuration

- **`tests/conftest.py`**: Pytest fixtures and configuration
  - Data model fixtures
  - Mock fixtures
  - Environment fixtures
  - Temporary directory fixtures

- **`tox.ini`**: Multi-environment testing
  - Python version testing
  - Isolated environment testing
  - Quality check environments

### CI/CD Configuration

- **`.github/workflows/ci.yml`**: GitHub Actions workflow
  - Multi-platform testing (Ubuntu, Windows, macOS)
  - Multi-version testing (Python 3.11, 3.12)
  - Code quality checks
  - Security scanning
  - Docker testing
  - Performance benchmarks

## Development Workflow

### Daily Development

1. **Start development session**:
   ```bash
   # Pull latest changes
   git pull origin main

   # Run fast checks
   make dev-check
   ```

2. **Make changes**:
   - Write tests first (TDD approach)
   - Implement functionality
   - Run tests frequently: `make test-fast`

3. **Before committing**:
   ```bash
   # Auto-fix formatting
   make quality-fix

   # Run comprehensive checks
   make quality-check

   # Run relevant tests
   make test-unit
   ```

4. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat: [Task X.X] Description of changes"
   ```

   Pre-commit hooks will automatically run and validate your changes.

5. **Before pushing**:
   ```bash
   # Full CI simulation
   make ci-check

   git push origin main
   ```

### Test-Driven Development

1. **Write failing test**:
   ```python
   def test_new_feature():
       # Arrange
       component = MyComponent()

       # Act
       result = component.new_feature()

       # Assert
       assert result.is_valid
   ```

2. **Run test to confirm it fails**:
   ```bash
   python scripts/run-tests.py --test tests/test_my_component.py::test_new_feature
   ```

3. **Implement minimal code to pass**:
   ```python
   def new_feature(self):
       return ValidResult()
   ```

4. **Run test to confirm it passes**:
   ```bash
   python scripts/run-tests.py --test tests/test_my_component.py::test_new_feature
   ```

5. **Refactor and improve**:
   - Keep tests green
   - Run full test suite periodically

### Code Quality Standards

#### Python Code Style

- **PEP 8 compliance**: Enforced by Flake8
- **Black formatting**: Consistent code formatting
- **Import sorting**: Organized with isort
- **Type hints**: Comprehensive typing with MyPy
- **Docstrings**: Google-style docstrings

#### Testing Standards

- **High coverage**: Minimum 85% test coverage
- **Test categories**: Proper use of pytest markers
- **Descriptive names**: Clear test function names
- **AAA pattern**: Arrange, Act, Assert structure
- **Mock external dependencies**: Use fixtures and mocks

#### Security Standards

- **Bandit scanning**: Automated security vulnerability detection
- **Dependency checking**: Regular dependency security audits
- **Secret management**: No hardcoded secrets in code

## Troubleshooting

### Common Issues

1. **Command not found errors**:
   - Ensure development dependencies are installed: `pip install -e ".[dev]"`
   - On Windows, use Python module syntax: `python -m black` instead of `black`

2. **Import errors**:
   - Ensure project is installed in development mode: `pip install -e .`
   - Check PYTHONPATH includes project root

3. **Test failures**:
   - Run with verbose output: `python scripts/run-tests.py --verbose`
   - Check specific test: `python scripts/run-tests.py --test path/to/test`
   - Clean test artifacts: `python scripts/run-tests.py --clean`

4. **Pre-commit hook failures**:
   - Run hooks manually: `pre-commit run --all-files`
   - Fix formatting: `make quality-fix`
   - Skip hooks temporarily: `git commit --no-verify`

5. **Coverage too low**:
   - Generate HTML report: `make test-cov`
   - Open `htmlcov/index.html` to see uncovered lines
   - Add tests for uncovered code

### Getting Help

1. **Check documentation**:
   - `docs/TESTING.md` - Testing infrastructure details
   - `docs/DEVELOPMENT_SETUP.md` - This document
   - `README.md` - Project overview

2. **Run help commands**:
   ```bash
   make help                           # Available make commands
   python scripts/run-tests.py --help # Test runner options
   python scripts/quality-check.py --help # Quality checker options
   ```

3. **Check CI logs**:
   - GitHub Actions logs for CI failures
   - Local CI simulation: `make ci-check`

## Advanced Usage

### Custom Test Configurations

Create custom pytest configurations in `pytest.ini` or `pyproject.toml`:

```toml
[tool.pytest.ini_options]
# Add custom markers
markers = [
    "custom: custom test category",
]

# Add custom test paths
testpaths = ["tests", "integration_tests"]
```

### Custom Quality Checks

Extend the quality checker script for project-specific checks:

```python
# In scripts/quality-check.py
def check_custom_rules(self) -> bool:
    """Add custom quality checks."""
    return self.run_command(
        ["custom-tool", "check"],
        "Custom quality check"
    )
```

### Docker Development

For containerized development:

```bash
# Build development image
docker build -t ozb-deal-filter:dev .

# Run tests in container
docker run --rm ozb-deal-filter:dev python scripts/run-tests.py

# Run quality checks in container
docker run --rm ozb-deal-filter:dev python scripts/quality-check.py
```

## Performance Optimization

### Test Performance

- Use `--parallel` for faster test execution
- Mark slow tests with `@pytest.mark.slow`
- Use `--fast` option to skip slow tests during development
- Profile tests with `--benchmark` for performance testing

### Development Performance

- Use virtual environments to isolate dependencies
- Cache pre-commit hooks for faster execution
- Use `make dev-check` for quick validation during development
- Run full `make ci-check` only before pushing

## Maintenance

### Regular Maintenance Tasks

1. **Update dependencies**:
   ```bash
   pip list --outdated
   # Update pyproject.toml with new versions
   pip install -e ".[dev]"
   ```

2. **Update pre-commit hooks**:
   ```bash
   pre-commit autoupdate
   pre-commit run --all-files
   ```

3. **Review test coverage**:
   ```bash
   make test-cov
   # Review htmlcov/index.html
   ```

4. **Security audit**:
   ```bash
   make security-check
   pip audit  # If available
   ```

5. **Clean up artifacts**:
   ```bash
   make clean
   python scripts/run-tests.py --clean
   ```

This development setup provides a robust foundation for maintaining high code quality, comprehensive testing, and efficient development workflows.
