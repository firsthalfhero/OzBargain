# OzBargain Deal Filter & Alert System

An intelligent monitoring solution that tracks OzBargain RSS feeds, filters deals based on user-defined criteria using LLM evaluation, and delivers real-time alerts through messaging platforms.

## Project Structure

```
ozb_deal_filter/
├── __init__.py                 # Package initialization
├── main.py                     # Application entry point
├── interfaces.py               # Protocol interfaces for all components
├── models/                     # Data models
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
├── config.example.yaml         # Example configuration

prompts/                        # LLM prompt templates
├── deal_evaluator.example.txt  # Example evaluation prompt

logs/                          # Application logs
└── .gitkeep

requirements.txt               # Python dependencies
.gitignore                    # Git ignore rules
README.md                     # This file
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy configuration template:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

3. Customize configuration with your RSS feeds, criteria, and messaging platform settings.

4. Run the application:
   ```bash
   python -m ozb_deal_filter.main
   ```

## Development

This project follows PEP 8 standards and uses type hints throughout. The architecture is based on protocol interfaces to enable dependency injection and testing.

### Key Components

- **RSS Monitor**: Polls configured feeds for new deals
- **Deal Parser**: Extracts structured data from RSS entries
- **LLM Evaluator**: Uses AI to assess deal relevance
- **Filter Engine**: Applies price, discount, authenticity, and expiration filters
- **Alert Formatter**: Creates rich notification messages
- **Message Dispatcher**: Delivers alerts via messaging platforms

### Testing

Run tests with:
```bash
pytest
```

### Code Quality

Format code with:
```bash
black ozb_deal_filter/
flake8 ozb_deal_filter/
mypy ozb_deal_filter/
```
