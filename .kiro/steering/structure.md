# Project Structure & Architecture

## Directory Organization

```
ozb_deal_filter/                # Main package
├── __init__.py                 # Package initialization
├── main.py                     # Application entry point
├── interfaces.py               # Protocol interfaces for all components
├── models/                     # Data models and validation
│   ├── __init__.py
│   ├── deal.py                # Deal and RawDeal models
│   ├── evaluation.py          # LLM evaluation results
│   ├── filter.py              # Filter results and urgency levels
│   ├── alert.py               # Alert formatting models
│   ├── delivery.py            # Message delivery results
│   └── config.py              # Configuration models
├── services/                   # Business logic services
│   └── __init__.py
└── components/                 # Core system components
    └── __init__.py

config/                         # Configuration files
├── config.example.yaml         # Example configuration template

prompts/                        # LLM prompt templates
├── deal_evaluator.example.txt  # Example evaluation prompt

tests/                          # Test suite
├── __init__.py
├── test_models.py             # Model validation tests
└── test_config_manager.py     # Configuration tests

logs/                          # Application logs
└── .gitkeep                   # Keep directory in git
```

## Architecture Patterns

### Protocol-Based Design
- All components implement protocol interfaces defined in `interfaces.py`
- Enables dependency injection and easy testing
- Clear separation of concerns between components

### Data Model Hierarchy
- **RawDeal**: Unprocessed RSS feed data
- **Deal**: Parsed and structured deal information
- **EvaluationResult**: LLM assessment output
- **FilterResult**: Applied filter outcomes
- **FormattedAlert**: Platform-ready notifications
- **DeliveryResult**: Message dispatch status

### Component Responsibilities
- **RSS Monitor**: Feed polling and change detection
- **Deal Parser**: Raw data to structured conversion
- **LLM Evaluator**: AI-based relevance assessment
- **Filter Engine**: Price/discount/authenticity filtering
- **Alert Formatter**: Platform-specific message creation
- **Message Dispatcher**: Multi-platform delivery

## Code Conventions

### File Naming
- Snake_case for all Python files and directories
- Descriptive names reflecting component purpose
- Test files prefixed with `test_`

### Class Structure
- Dataclasses for data models with validation methods
- Protocol interfaces for component contracts
- Comprehensive type hints throughout

### Validation Pattern
- All models implement `validate()` method
- Raises `ValueError` with descriptive messages
- Validates data types, ranges, and business rules
- Consistent error handling across components

### Import Organization
- Standard library imports first
- Third-party imports second
- Local imports last
- Absolute imports preferred over relative

### Configuration Management
- YAML-based configuration files
- Environment variable substitution support
- Nested dataclass structure for type safety
- Comprehensive validation at startup

## Testing Structure
- Unit tests for all data models
- Validation testing for edge cases
- Mock-based testing for external dependencies
- Async testing support for concurrent operations