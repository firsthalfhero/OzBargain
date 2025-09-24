# Development Guide

This guide covers the development setup, code quality standards, and testing procedures for the OzBargain Deal Filter project.

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ozb-deal-filter
   ```

2. **Set up development environment**
   ```bash
   python scripts/setup-dev.py
   ```

3. **Run tests**
   ```bash
   make test
   ```

4. **Run quality checks**
   ```bash
   make quality-check
   ```

## Development Environment Setup

### Prerequisites

- Python 3.11 or 3.12
- Git
- pip

### Manual Setup

If you prefer to set up the environment manually:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run initial quality checks
python scripts/quality-check.py
```

## Code Quality Standards

This project follows strict code quality standards enforced by automated tools:

### Code Formatting

- **Black**: Automatic code formatting
- **isort**: Import statement sorting
- Line length: 88 characters (Black default)

```bash
# Format code
black ozb_deal_filter/ tests/
isort ozb_deal_filter/ tests/

# Check formatting
black --check ozb_deal_filter/ tests/
isort --check-only ozb_deal_filter/ tests/
```

### Linting

- **Flake8**: Code linting and style checking
- **Bandit**: Security vulnerability scanning

```bash
# Run linting
flake8 ozb_deal_filter/ tests/

# Run security checks
bandit -r ozb_deal_filter/
```

### Type Checking

- **MyPy**: Static type checking
- All code must include type hints
- Strict mode enabled

```bash
# Run type checking
mypy ozb_deal_filter/
```

## Testing

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_models.py           # Data model tests
├── test_components/         # Component tests
├── test_services/           # Service tests
└── test_integration/        # Integration tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_git_agent.py

# Run with coverage (requires pytest-cov)
pytest --cov=ozb_deal_filter --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Test Categories

Tests are categorized using pytest markers:

- `@pytest.mark.unit`: Fast unit tests (default)
- `@pytest.mark.integration`: Integration tests with external dependencies
- `@pytest.mark.slow`: Slow-running tests

### Writing Tests

1. **Use descriptive test names**
   ```python
   def test_git_agent_generates_meaningful_commit_messages():
       """Test that GitAgent generates meaningful commit messages."""
   ```

2. **Use fixtures from conftest.py**
   ```python
   def test_deal_validation(sample_deal):
       """Test deal validation with sample data."""
       sample_deal.validate()  # Should not raise
   ```

3. **Mock external dependencies**
   ```python
   @patch('subprocess.run')
   def test_git_command_execution(mock_run):
       """Test git command execution with mocked subprocess."""
   ```

## Pre-commit Hooks

Pre-commit hooks run automatically before each commit to ensure code quality:

- **trailing-whitespace**: Remove trailing whitespace
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml**: Validate YAML files
- **black**: Format Python code
- **isort**: Sort imports
- **flake8**: Lint code
- **mypy**: Type checking
- **bandit**: Security scanning

### Manual Pre-commit Run

```bash
# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Skip hooks for emergency commits
git commit --no-verify -m "Emergency fix"
```

## Make Commands

The project includes a Makefile with convenient development commands:

```bash
# Development setup
make dev-setup              # Complete development environment setup
make install-dev            # Install development dependencies
make pre-commit-install     # Install pre-commit hooks

# Code quality
make format                 # Format code with black and isort
make lint                   # Run flake8 linting
make type-check            # Run mypy type checking
make quality-check         # Run all quality checks

# Testing
make test                  # Run tests
make test-cov             # Run tests with coverage

# Cleanup
make clean                # Clean up generated files

# CI simulation
make ci-check             # Run all CI checks locally
```

## Continuous Integration

The project uses GitHub Actions for CI/CD with the following checks:

1. **Code Quality**: Black, isort, flake8, mypy
2. **Security**: Bandit security scanning
3. **Testing**: pytest across Python 3.11 and 3.12
4. **Coverage**: Code coverage reporting

### Local CI Simulation

```bash
# Run the same checks as CI
make ci-check
```

## Git Workflow

### Commit Message Format

Follow conventional commit format:

```
type: [Task X.X] Brief description

Detailed description of changes
- Specific changes made
- Requirements addressed

Task: X.X Task Name from tasks.md
Requirements: Req 1.1, 2.3
```

### Automated Commits

The GitAgent component can automatically generate commits:

```python
from ozb_deal_filter.components import GitAgent

agent = GitAgent()
result = agent.auto_commit_task("1.1 Implement basic functionality")
```

## IDE Configuration

### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- isort
- GitLens

Settings (`.vscode/settings.json`):
```json
{
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "editor.formatOnSave": true,
    "python.sortImports.args": ["--profile", "black"]
}
```

### PyCharm

1. Configure Black as external tool
2. Enable flake8 inspection
3. Configure mypy as external tool
4. Set line length to 88

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure package is installed in development mode
   ```bash
   pip install -e .
   ```

2. **Pre-commit hook failures**: Run hooks manually to see detailed errors
   ```bash
   pre-commit run --all-files
   ```

3. **Type checking errors**: Ensure all imports have type stubs
   ```bash
   pip install types-requests types-PyYAML types-python-dateutil
   ```

4. **Test failures**: Check if test dependencies are installed
   ```bash
   pip install -e ".[dev]"
   ```

### Getting Help

1. Check the error messages carefully
2. Run individual quality checks to isolate issues
3. Use `make clean` to remove generated files
4. Reinstall development dependencies if needed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the code quality standards
4. Run quality checks and tests
5. Commit with meaningful messages
6. Submit a pull request

All contributions must pass the automated quality checks and tests.
