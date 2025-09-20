"""
Shared fixtures and utilities for integration tests.

This module provides common fixtures, mock data, and utilities
specifically for integration testing scenarios.
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

from ozb_deal_filter.models.alert import FormattedAlert
from ozb_deal_filter.models.deal import Deal, RawDeal
from ozb_deal_filter.models.delivery import DeliveryResult
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.models.filter import FilterResult, UrgencyLevel


class MockRSSServer:
    """Mock RSS server for integration testing."""

    def __init__(self):
        self.feeds: Dict[str, str] = {}
        self.request_count = 0
        self.failure_rate = 0.0
        self.response_delay = 0.0

    def add_feed(self, url: str, content: str) -> None:
        """Add a feed to the mock server."""
        self.feeds[url] = content

    def set_failure_rate(self, rate: float) -> None:
        """Set the failure rate for requests (0.0 to 1.0)."""
        self.failure_rate = rate

    def set_response_delay(self, delay: float) -> None:
        """Set response delay in seconds."""
        self.response_delay = delay

    async def get_feed(self, url: str) -> str:
        """Get feed content with simulated network behavior."""
        self.request_count += 1

        # Simulate network delay
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)

        # Simulate failures
        import random

        if random.random() < self.failure_rate:
            raise Exception("Simulated network failure")

        return self.feeds.get(url, "")


class MockLLMProvider:
    """Mock LLM provider for integration testing."""

    def __init__(self):
        self.evaluation_count = 0
        self.response_time = 0.1  # 100ms default
        self.failure_rate = 0.0
        self.responses: List[EvaluationResult] = []
        self.default_response = EvaluationResult(
            is_relevant=True,
            confidence_score=0.8,
            reasoning="Mock evaluation response",
        )

    def set_response_time(self, time_seconds: float) -> None:
        """Set simulated response time."""
        self.response_time = time_seconds

    def set_failure_rate(self, rate: float) -> None:
        """Set failure rate for evaluations."""
        self.failure_rate = rate

    def add_response(self, response: EvaluationResult) -> None:
        """Add a specific response to the queue."""
        self.responses.append(response)

    async def evaluate_deal(self, deal: Deal) -> EvaluationResult:
        """Mock deal evaluation with realistic behavior."""
        self.evaluation_count += 1

        # Simulate processing time
        await asyncio.sleep(self.response_time)

        # Simulate failures
        import random

        if random.random() < self.failure_rate:
            raise Exception("Simulated LLM failure")

        # Return queued response or default
        if self.responses:
            return self.responses.pop(0)
        return self.default_response


class MockMessagePlatform:
    """Mock messaging platform for integration testing."""

    def __init__(self):
        self.sent_messages: List[FormattedAlert] = []
        self.delivery_count = 0
        self.failure_rate = 0.0
        self.delivery_delay = 0.02  # 20ms default
        self.connection_status = True

    def set_failure_rate(self, rate: float) -> None:
        """Set failure rate for message delivery."""
        self.failure_rate = rate

    def set_delivery_delay(self, delay: float) -> None:
        """Set delivery delay in seconds."""
        self.delivery_delay = delay

    def set_connection_status(self, status: bool) -> None:
        """Set connection status."""
        self.connection_status = status

    def test_connection(self) -> bool:
        """Test platform connection."""
        return self.connection_status

    async def send_alert(self, alert: FormattedAlert) -> DeliveryResult:
        """Mock alert delivery with realistic behavior."""
        self.delivery_count += 1

        # Simulate delivery delay
        await asyncio.sleep(self.delivery_delay)

        # Simulate failures
        import random

        if random.random() < self.failure_rate:
            return DeliveryResult(
                success=False,
                delivery_time=datetime.now(timezone.utc),
                error_message="Simulated delivery failure",
            )

        # Successful delivery
        self.sent_messages.append(alert)
        return DeliveryResult(
            success=True,
            delivery_time=datetime.now(timezone.utc),
            error_message=None,
        )


class IntegrationTestData:
    """Test data generator for integration tests."""

    @staticmethod
    def create_rss_feed(deals: List[Dict[str, Any]]) -> str:
        """Create RSS feed XML from deal data."""
        items = []
        for deal in deals:
            items.append(
                f"""
                <item>
                    <title>{deal.get('title', 'Test Deal')}</title>
                    <description>{deal.get('description', 'Test description')}</description>
                    <link>{deal.get('link', 'https://example.com/deal')}</link>
                    <pubDate>{deal.get('pub_date', 'Mon, 01 Jan 2024 12:00:00 GMT')}</pubDate>
                    <category>{deal.get('category', 'Electronics')}</category>
                </item>
            """
            )

        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test RSS Feed</title>
                <description>Test feed for integration testing</description>
                {''.join(items)}
            </channel>
        </rss>"""

    @staticmethod
    def create_deal_batch(
        count: int, category: str = "Electronics"
    ) -> List[Dict[str, Any]]:
        """Create a batch of test deals."""
        deals = []
        for i in range(count):
            deals.append(
                {
                    "title": f"Test Deal {i} - {category} Special",
                    "description": f"Great {category.lower()} deal number {i}",
                    "link": f"https://www.ozbargain.com.au/node/{123456 + i}",
                    "pub_date": f"Mon, 01 Jan 2024 {12 + (i % 12):02d}:00:00 GMT",
                    "category": category,
                }
            )
        return deals

    @staticmethod
    def create_mixed_relevance_deals() -> List[Dict[str, Any]]:
        """Create deals with mixed relevance for filtering tests."""
        return [
            # Relevant deals
            {
                "title": "Gaming Laptop - 50% off MSI Katana",
                "description": "High-performance gaming laptop with RTX 4060",
                "category": "Computing",
            },
            {
                "title": "iPhone 15 Pro - 30% discount",
                "description": "Latest iPhone with titanium design",
                "category": "Electronics",
            },
            # Irrelevant deals
            {
                "title": "Free Coffee at McDonald's",
                "description": "Free small coffee with any purchase",
                "category": "Food",
            },
            {
                "title": "Car Insurance - 20% off",
                "description": "Comprehensive car insurance discount",
                "category": "Automotive",
            },
            # Edge cases
            {
                "title": "Laptop Bag - 70% off",
                "description": "Protective laptop bag, various sizes",
                "category": "Accessories",
            },
        ]

    @staticmethod
    def create_performance_test_config() -> Dict[str, Any]:
        """Create configuration optimized for performance testing."""
        return {
            "rss_feeds": [
                "https://www.ozbargain.com.au/deals/feed",
                "https://www.ozbargain.com.au/cat/computing/feed",
                "https://www.ozbargain.com.au/cat/electronics/feed",
            ],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 1000.0,
                "min_discount_percentage": 15.0,
                "categories": ["Electronics", "Computing"],
                "keywords": ["laptop", "phone", "tablet", "computer", "gaming"],
                "min_authenticity_score": 0.5,
            },
            "llm_provider": {
                "type": "local",
                "local": {"model": "llama2", "docker_image": "ollama/ollama"},
            },
            "messaging_platform": {
                "type": "telegram",
                "telegram": {"bot_token": "test_token", "chat_id": "test_chat"},
            },
            "system": {
                "polling_interval": 30,
                "max_concurrent_feeds": 10,
                "alert_timeout": 60,
                "urgent_alert_timeout": 30,
            },
        }


class PerformanceMonitor:
    """Monitor performance metrics during integration tests."""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.start_times: Dict[str, float] = {}

    def start_timer(self, metric_name: str) -> None:
        """Start timing a metric."""
        import time

        self.start_times[metric_name] = time.time()

    def end_timer(self, metric_name: str) -> float:
        """End timing and record metric."""
        import time

        if metric_name not in self.start_times:
            return 0.0

        duration = time.time() - self.start_times[metric_name]
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(duration)
        del self.start_times[metric_name]
        return duration

    def get_stats(self, metric_name: str) -> Dict[str, float]:
        """Get statistics for a metric."""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return {}

        import statistics

        values = self.metrics[metric_name]
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics."""
        return {name: self.get_stats(name) for name in self.metrics.keys()}


# Pytest fixtures
@pytest.fixture
def mock_rss_server():
    """Provide mock RSS server for tests."""
    return MockRSSServer()


@pytest.fixture
def mock_llm_provider():
    """Provide mock LLM provider for tests."""
    return MockLLMProvider()


@pytest.fixture
def mock_message_platform():
    """Provide mock messaging platform for tests."""
    return MockMessagePlatform()


@pytest.fixture
def integration_test_data():
    """Provide test data generator."""
    return IntegrationTestData()


@pytest.fixture
def performance_monitor():
    """Provide performance monitoring."""
    return PerformanceMonitor()


@pytest.fixture
def temp_config_file():
    """Create temporary config file that gets cleaned up."""
    config_files = []

    def _create_config(config_dict: Dict[str, Any]) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            config_files.append(f.name)
            return f.name

    yield _create_config

    # Cleanup
    import os

    for config_file in config_files:
        try:
            os.unlink(config_file)
        except FileNotFoundError:
            pass


@pytest.fixture
def integration_environment(
    mock_rss_server, mock_llm_provider, mock_message_platform, temp_config_file
):
    """Provide complete integration test environment."""
    # Create default test configuration
    config = IntegrationTestData.create_performance_test_config()
    config_file = temp_config_file(config)

    # Setup default test data
    test_deals = IntegrationTestData.create_mixed_relevance_deals()
    rss_content = IntegrationTestData.create_rss_feed(test_deals)
    mock_rss_server.add_feed("https://www.ozbargain.com.au/deals/feed", rss_content)

    return {
        "config_file": config_file,
        "rss_server": mock_rss_server,
        "llm_provider": mock_llm_provider,
        "message_platform": mock_message_platform,
        "test_deals": test_deals,
    }


# Async test utilities
async def wait_for_condition(
    condition_func, timeout: float = 5.0, check_interval: float = 0.1
) -> bool:
    """Wait for a condition to become true."""
    import time

    start_time = time.time()

    while time.time() - start_time < timeout:
        if condition_func():
            return True
        await asyncio.sleep(check_interval)

    return False


async def simulate_real_time_feeds(
    mock_server: MockRSSServer,
    feed_updates: List[Dict[str, Any]],
    update_interval: float = 1.0,
) -> None:
    """Simulate real-time feed updates."""
    for i, update in enumerate(feed_updates):
        # Update feed content
        rss_content = IntegrationTestData.create_rss_feed(update["deals"])
        mock_server.add_feed(update["url"], rss_content)

        # Wait before next update (except for last one)
        if i < len(feed_updates) - 1:
            await asyncio.sleep(update_interval)


# Test data constants
SAMPLE_ELECTRONICS_DEALS = [
    {
        "title": "Samsung Galaxy S24 - 25% off",
        "description": "Latest Samsung flagship with AI features",
        "category": "Electronics",
    },
    {
        "title": "Sony WH-1000XM5 Headphones - 30% discount",
        "description": "Premium noise-cancelling headphones",
        "category": "Electronics",
    },
    {
        "title": "iPad Pro 12.9 - Special pricing",
        "description": "Professional tablet with M2 chip",
        "category": "Electronics",
    },
]

SAMPLE_COMPUTING_DEALS = [
    {
        "title": "Dell XPS 13 Laptop - 40% off",
        "description": "Ultrabook with Intel Core i7",
        "category": "Computing",
    },
    {
        "title": "Mechanical Keyboard - RGB Gaming",
        "description": "Cherry MX switches, full RGB",
        "category": "Computing",
    },
    {
        "title": "4K Monitor - 27 inch IPS",
        "description": "Professional 4K display",
        "category": "Computing",
    },
]

SAMPLE_IRRELEVANT_DEALS = [
    {
        "title": "Pizza Deal - Buy 1 Get 1 Free",
        "description": "Delicious pizza offer",
        "category": "Food",
    },
    {
        "title": "Car Wash - 50% off",
        "description": "Professional car cleaning",
        "category": "Automotive",
    },
    {
        "title": "Gym Membership - 3 months free",
        "description": "Fitness center membership",
        "category": "Health",
    },
]
