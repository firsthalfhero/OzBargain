# Technology Stack

## Core Technologies

- **Python 3.12+**: Primary development language
- **Type Hints**: Comprehensive typing throughout codebase using `typing` module
- **Dataclasses**: For data model definitions
- **Protocol Interfaces**: For dependency injection and testability
- **Asyncio**: For concurrent RSS feed processing

## Key Dependencies

### Data Processing
- `feedparser==6.0.10`: RSS feed parsing
- `requests==2.31.0`: HTTP requests
- `pyyaml==6.0.1`: YAML configuration parsing
- `python-dateutil==2.8.2`: Date/time handling
- `pydantic==2.5.0`: Data validation
- `beautifulsoup4==4.12.2`: HTML parsing

### LLM Integration
- `openai==1.3.0`: OpenAI API integration
- `anthropic==0.7.0`: Anthropic API integration

### Messaging Platforms
- `python-telegram-bot==20.7`: Telegram bot integration
- `discord-webhook==1.3.0`: Discord webhook support

### Infrastructure
- `docker==6.1.3`: Docker container management for local LLM
- `GitPython==3.1.40`: Git automation
- `structlog==23.2.0`: Structured logging

### Development Tools
- `pytest==7.4.3`: Testing framework
- `pytest-asyncio==0.21.1`: Async testing support
- `pytest-mock==3.12.0`: Mocking utilities
- `black==23.11.0`: Code formatting
- `flake8==6.1.0`: Linting
- `mypy==1.7.1`: Static type checking

## Common Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy configuration template
cp config/config.example.yaml config/config.yaml
```

### Running the Application
```bash
# Run main application
python -m ozb_deal_filter.main
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=ozb_deal_filter

# Run specific test file
pytest tests/test_models.py
```

### Code Quality
```bash
# Format code
black ozb_deal_filter/

# Lint code
flake8 ozb_deal_filter/

# Type checking
mypy ozb_deal_filter/

# Run all quality checks
black ozb_deal_filter/ && flake8 ozb_deal_filter/ && mypy ozb_deal_filter/
```

## Configuration

- **YAML-based**: Main configuration in `config/config.yaml`
- **Environment Variables**: Support for `${VAR_NAME}` substitution
- **Validation**: Comprehensive validation using dataclass methods
- **Hot Reload**: Configuration can be reloaded without restart