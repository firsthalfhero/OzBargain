"""
Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests
in the OzBargain Deal Filter test suite.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import os

from ozb_deal_filter.models.deal import Deal, RawDeal
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.models.filter import FilterResult, UrgencyLevel
from ozb_deal_filter.models.alert import FormattedAlert
from ozb_deal_filter.models.delivery import DeliveryResult
from ozb_deal_filter.models.config import Configuration, UserCriteria
from ozb_deal_filter.models.git import CommitResult, GitStatus


# Test data fixtures
@pytest.fixture
def sample_raw_deal():
    """Create a sample RawDeal for testing."""
    return RawDeal(
        title="50% off Electronics - Great Deal!",
        description="Amazing discount on electronics items",
        link="https://www.ozbargain.com.au/node/123456",
        pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
        category="Electronics",
    )


@pytest.fixture
def sample_deal():
    """Create a sample Deal for testing."""
    return Deal(
        id="deal_123456",
        title="50% off Electronics - Great Deal!",
        description="Amazing discount on electronics items",
        price=99.99,
        original_price=199.99,
        discount_percentage=50.0,
        category="Electronics",
        url="https://www.ozbargain.com.au/node/123456",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        votes=25,
        comments=5,
        urgency_indicators=["limited time", "stock running low"],
    )


@pytest.fixture
def sample_evaluation_result():
    """Create a sample EvaluationResult for testing."""
    return EvaluationResult(
        is_relevant=True,
        confidence_score=0.85,
        reasoning="Deal matches user criteria for electronics with good discount",
    )


@pytest.fixture
def sample_filter_result():
    """Create a sample FilterResult for testing."""
    return FilterResult(
        passes_filters=True,
        price_match=True,
        authenticity_score=0.8,
        urgency_level=UrgencyLevel.HIGH,
    )


@pytest.fixture
def sample_formatted_alert():
    """Create a sample FormattedAlert for testing."""
    return FormattedAlert(
        title="🔥 Hot Deal Alert!",
        message="50% off Electronics - Great Deal!\nPrice: $99.99 (was $199.99)\nSave: $100.00",
        urgency=UrgencyLevel.HIGH,
        platform_specific_data={
            "telegram": {"parse_mode": "HTML"},
            "discord": {"embed": True},
        },
    )


@pytest.fixture
def sample_delivery_result():
    """Create a sample DeliveryResult for testing."""
    return DeliveryResult(
        success=True,
        delivery_time=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        error_message=None,
    )


@pytest.fixture
def sample_user_criteria():
    """Create sample UserCriteria for testing."""
    return UserCriteria(
        prompt_template_path="prompts/deal_evaluator.example.txt",
        max_price=500.0,
        min_discount_percentage=20.0,
        categories=["Electronics", "Computing"],
        keywords=["laptop", "phone", "tablet"],
        min_authenticity_score=0.6,
    )


@pytest.fixture
def sample_configuration(sample_user_criteria):
    """Create a sample Configuration for testing."""
    return Configuration(
        rss_feeds=[
            "https://www.ozbargain.com.au/deals/feed",
            "https://www.ozbargain.com.au/cat/computing/feed",
        ],
        user_criteria=sample_user_criteria,
        llm_provider={
            "type": "local",
            "local": {"model": "llama2", "docker_image": "ollama/ollama"},
        },
        messaging_platform={
            "type": "telegram",
            "telegram": {"bot_token": "test_token", "chat_id": "test_chat_id"},
        },
        system={
            "polling_interval": 120,
            "max_concurrent_feeds": 10,
            "alert_timeout": 300,
            "urgent_alert_timeout": 120,
        },
    )


@pytest.fixture
def sample_commit_result():
    """Create a sample CommitResult for testing."""
    return CommitResult(
        success=True,
        commit_hash="abc123def456",
        message="feat: [Task 1.1] Implement basic functionality",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        files_changed=["file1.py", "file2.py"],
    )


@pytest.fixture
def sample_git_status():
    """Create a sample GitStatus for testing."""
    return GitStatus(
        has_changes=True,
        staged_files=["file1.py"],
        unstaged_files=["file2.py"],
        untracked_files=["file3.py"],
        current_branch="main",
    )


# Mock fixtures
@pytest.fixture
def mock_rss_feed():
    """Create mock RSS feed data for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>OzBargain</title>
            <description>OzBargain deals feed</description>
            <item>
                <title>50% off Electronics - Great Deal!</title>
                <description>Amazing discount on electronics items</description>
                <link>https://www.ozbargain.com.au/node/123456</link>
                <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                <category>Electronics</category>
            </item>
            <item>
                <title>30% off Books - Limited Time</title>
                <description>Great selection of books on sale</description>
                <link>https://www.ozbargain.com.au/node/123457</link>
                <pubDate>Mon, 01 Jan 2024 11:00:00 GMT</pubDate>
                <category>Books</category>
            </item>
        </channel>
    </rss>"""


@pytest.fixture
def mock_llm_evaluator():
    """Create a mock LLM evaluator for testing."""
    evaluator = Mock()
    evaluator.evaluate_deal.return_value = EvaluationResult(
        is_relevant=True,
        confidence_score=0.8,
        reasoning="Matches user criteria for electronics deals",
    )
    return evaluator


@pytest.fixture
def mock_message_dispatcher():
    """Create a mock message dispatcher for testing."""
    dispatcher = Mock()
    dispatcher.send_alert.return_value = DeliveryResult(
        success=True, delivery_time=datetime.now(timezone.utc), error_message=None
    )
    dispatcher.test_connection.return_value = True
    return dispatcher


@pytest.fixture
def mock_git_agent():
    """Create a mock git agent for testing."""
    agent = Mock()
    agent.auto_commit_task.return_value = CommitResult(
        success=True,
        commit_hash="abc123",
        message="feat: [Task 1.1] Test commit",
        timestamp=datetime.now(timezone.utc),
        files_changed=["test_file.py"],
    )
    return agent


# Temporary directory fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_git_repo(temp_dir):
    """Create a temporary git repository for testing."""
    git_dir = temp_dir / ".git"
    git_dir.mkdir()
    return temp_dir


@pytest.fixture
def temp_config_file(temp_dir, sample_configuration):
    """Create a temporary configuration file for testing."""
    config_file = temp_dir / "config.yaml"
    # This would normally write YAML, but for testing we'll just create the file
    config_file.write_text("# Test configuration file")
    return config_file


# Environment fixtures
@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "TELEGRAM_CHAT_ID": "test_chat_id",
        "OPENAI_API_KEY": "test_openai_key",
        "ANTHROPIC_API_KEY": "test_anthropic_key",
    }

    # Store original values
    original_values = {}
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value

    yield env_vars

    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# Async fixtures
@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add unit marker to all tests by default
        if not any(
            marker.name in ["integration", "slow"] for marker in item.iter_markers()
        ):
            item.add_marker(pytest.mark.unit)

        # Add slow marker to tests that might be slow
        if "llm" in item.name.lower() or "integration" in item.name.lower():
            item.add_marker(pytest.mark.slow)
