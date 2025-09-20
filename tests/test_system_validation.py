"""
System validation and monitoring tests.

This module provides tests for health check endpoints, metrics collection,
alert delivery validation, and system startup validation.
"""

import asyncio
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml

from ozb_deal_filter.models.alert import FormattedAlert
from ozb_deal_filter.models.deal import Deal, RawDeal
from ozb_deal_filter.models.delivery import DeliveryResult
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.models.filter import FilterResult, UrgencyLevel
from ozb_deal_filter.orchestrator import ApplicationOrchestrator


@pytest.mark.integration
class TestHealthCheckEndpoints:
    """Test system health check functionality."""

    @pytest.fixture
    def health_check_config(self):
        """Create configuration for health check testing."""
        return {
            "rss_feeds": ["https://www.ozbargain.com.au/deals/feed"],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 500.0,
                "min_discount_percentage": 20.0,
                "categories": ["Electronics"],
                "keywords": ["laptop", "phone"],
                "min_authenticity_score": 0.6,
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
                "polling_interval": 60,
                "max_concurrent_feeds": 5,
                "alert_timeout": 300,
                "urgent_alert_timeout": 120,
            },
        }

    @pytest.fixture
    def config_file_health(self, health_check_config):
        """Create config file for health check tests."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(health_check_config, f)
            return f.name

    @pytest.mark.asyncio
    async def test_system_health_check_all_healthy(self, config_file_health):
        """Test health check when all components are healthy."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock healthy components
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            # Create and initialize orchestrator
            orchestrator = ApplicationOrchestrator(config_file_health)
            await orchestrator.initialize()

            # Perform health check
            await orchestrator._health_check()

            # Get system status
            status = orchestrator.get_system_status()

            # Verify health status
            assert status["running"] is False  # Not started yet
            assert status["config_loaded"] is True
            assert status["component_health"]["config_manager"] is True
            assert status["component_health"]["rss_monitor"] is True
            assert status["component_health"]["deal_parser"] is True
            assert status["component_health"]["llm_evaluator"] is True
            assert status["component_health"]["message_dispatcher"] is True

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_system_health_check_with_failures(self, config_file_health):
        """Test health check when some components are unhealthy."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock LLM failure
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(side_effect=Exception("LLM unavailable"))

            # Mock message dispatcher failure
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = False

            # Create and initialize orchestrator
            orchestrator = ApplicationOrchestrator(config_file_health)
            await orchestrator.initialize()

            # Simulate component failures
            orchestrator._component_health["llm_evaluator"] = False
            orchestrator._component_health["message_dispatcher"] = False

            # Perform health check
            await orchestrator._health_check()

            # Get system status
            status = orchestrator.get_system_status()

            # Verify health status reflects failures
            assert status["component_health"]["llm_evaluator"] is False
            assert status["component_health"]["message_dispatcher"] is False

            # Critical components should still be healthy
            assert status["component_health"]["config_manager"] is True
            assert status["component_health"]["rss_monitor"] is True
            assert status["component_health"]["deal_parser"] is True

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_recovery(self, config_file_health):
        """Test health check recovery after component failure."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock dispatcher that initially fails then recovers
            connection_attempts = 0

            def mock_test_connection():
                nonlocal connection_attempts
                connection_attempts += 1
                return connection_attempts > 2  # Fail first 2 attempts

            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection = mock_test_connection

            # Create and initialize orchestrator
            orchestrator = ApplicationOrchestrator(config_file_health)
            await orchestrator.initialize()

            # First health check - should fail
            await orchestrator._health_check()
            status1 = orchestrator.get_system_status()
            assert status1["component_health"]["message_dispatcher"] is False

            # Second health check - should still fail
            await orchestrator._health_check()
            status2 = orchestrator.get_system_status()
            assert status2["component_health"]["message_dispatcher"] is False

            # Third health check - should recover
            await orchestrator._health_check()
            status3 = orchestrator.get_system_status()
            assert status3["component_health"]["message_dispatcher"] is True

            await orchestrator.shutdown()

    def test_system_status_reporting(self, config_file_health):
        """Test comprehensive system status reporting."""
        with patch("ozb_deal_filter.components.llm_evaluator.LLMEvaluator"), patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ):
            orchestrator = ApplicationOrchestrator(config_file_health)

            # Set up test state
            orchestrator._running = True
            orchestrator._startup_time = datetime.now() - timedelta(hours=2)
            orchestrator._component_health = {
                "config_manager": True,
                "rss_monitor": True,
                "deal_parser": True,
                "llm_evaluator": False,
                "message_dispatcher": True,
            }
            orchestrator._error_counts = {
                "llm_evaluation": 5,
                "message_delivery": 2,
                "main_loop": 1,
            }
            orchestrator._config = Mock()

            # Get system status
            status = orchestrator.get_system_status()

            # Verify status structure
            assert "running" in status
            assert "startup_time" in status
            assert "uptime" in status
            assert "component_health" in status
            assert "error_counts" in status
            assert "config_loaded" in status

            # Verify status values
            assert status["running"] is True
            assert status["startup_time"] is not None
            assert status["uptime"] is not None
            assert status["config_loaded"] is True

            # Verify component health
            assert len(status["component_health"]) == 5
            assert status["component_health"]["llm_evaluator"] is False
            assert status["component_health"]["message_dispatcher"] is True

            # Verify error counts
            assert status["error_counts"]["llm_evaluation"] == 5
            assert status["error_counts"]["message_delivery"] == 2


@pytest.mark.integration
class TestMetricsCollection:
    """Test performance metrics collection and tracking."""

    @pytest.fixture
    def metrics_config(self):
        """Create configuration for metrics testing."""
        return {
            "rss_feeds": ["https://www.ozbargain.com.au/deals/feed"],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 500.0,
                "min_discount_percentage": 20.0,
                "categories": ["Electronics"],
                "keywords": ["laptop"],
                "min_authenticity_score": 0.6,
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
                "polling_interval": 60,
                "max_concurrent_feeds": 5,
                "alert_timeout": 300,
                "urgent_alert_timeout": 120,
            },
        }

    @pytest.fixture
    def config_file_metrics(self, metrics_config):
        """Create config file for metrics tests."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(metrics_config, f)
            return f.name

    def test_error_count_tracking(self, config_file_metrics):
        """Test error count tracking functionality."""
        with patch("ozb_deal_filter.components.llm_evaluator.LLMEvaluator"), patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ):
            orchestrator = ApplicationOrchestrator(config_file_metrics)

            # Test error count increment
            orchestrator._increment_error_count("test_error")
            assert orchestrator._error_counts["test_error"] == 1

            orchestrator._increment_error_count("test_error")
            assert orchestrator._error_counts["test_error"] == 2

            # Test multiple error types
            orchestrator._increment_error_count("another_error")
            assert orchestrator._error_counts["another_error"] == 1
            assert orchestrator._error_counts["test_error"] == 2

            # Test high error count warning (should log warning at multiples of 10)
            for i in range(8):  # Bring total to 10
                orchestrator._increment_error_count("test_error")

            assert orchestrator._error_counts["test_error"] == 10

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, config_file_metrics):
        """Test collection of performance metrics during operation."""
        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock RSS response
            rss_content = """<?xml version="1.0"?>
            <rss version="2.0">
                <channel>
                    <item>
                        <title>Test Laptop Deal</title>
                        <description>Great laptop deal</description>
                        <link>https://example.com/deal</link>
                        <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                        <category>Electronics</category>
                    </item>
                </channel>
            </rss>"""

            mock_response = Mock()
            mock_response.text = rss_content
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Mock LLM with timing
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            evaluation_times = []

            async def timed_evaluate_deal(deal):
                start_time = time.time()
                await asyncio.sleep(0.05)  # 50ms processing
                end_time = time.time()
                evaluation_times.append(end_time - start_time)
                return EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )

            mock_llm.evaluate_deal = timed_evaluate_deal

            # Mock message dispatcher with timing
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            delivery_times = []

            async def timed_send_alert(alert):
                start_time = time.time()
                await asyncio.sleep(0.02)  # 20ms delivery
                end_time = time.time()
                delivery_times.append(end_time - start_time)
                return DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )

            mock_dispatcher.send_alert = timed_send_alert

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_metrics)
            await orchestrator.initialize()

            # Process multiple deals to collect metrics
            for i in range(5):
                raw_deal = RawDeal(
                    title=f"Test Laptop Deal {i}",
                    description="Great laptop deal",
                    link=f"https://example.com/deal{i}",
                    pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                    category="Electronics",
                )

                await orchestrator._process_single_deal(raw_deal)

            # Verify metrics were collected
            assert len(evaluation_times) == 5
            assert len(delivery_times) == 5

            # Verify timing ranges
            assert all(0.04 < t < 0.06 for t in evaluation_times)  # ~50ms
            assert all(0.01 < t < 0.03 for t in delivery_times)  # ~20ms

            # Calculate performance statistics
            import statistics

            avg_eval_time = statistics.mean(evaluation_times)
            avg_delivery_time = statistics.mean(delivery_times)

            print(f"Average evaluation time: {avg_eval_time:.3f}s")
            print(f"Average delivery time: {avg_delivery_time:.3f}s")

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_uptime_tracking(self, config_file_metrics):
        """Test system uptime tracking."""
        with patch("ozb_deal_filter.components.llm_evaluator.LLMEvaluator"), patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ):
            orchestrator = ApplicationOrchestrator(config_file_metrics)

            # Set startup time
            start_time = datetime.now() - timedelta(minutes=30)
            orchestrator._startup_time = start_time

            # Get status and check uptime
            status = orchestrator.get_system_status()

            assert status["startup_time"] == start_time.isoformat()
            assert status["uptime"] is not None

            # Parse uptime string and verify it's approximately 30 minutes
            uptime_str = status["uptime"]
            assert (
                "0:30:" in uptime_str or "0:29:" in uptime_str
            )  # Allow for small timing differences


@pytest.mark.integration
class TestAlertDeliveryValidation:
    """Test alert delivery validation and tracking."""

    @pytest.fixture
    def delivery_config(self):
        """Create configuration for delivery testing."""
        return {
            "rss_feeds": ["https://www.ozbargain.com.au/deals/feed"],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 500.0,
                "min_discount_percentage": 20.0,
                "categories": ["Electronics"],
                "keywords": ["laptop"],
                "min_authenticity_score": 0.6,
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
                "polling_interval": 60,
                "max_concurrent_feeds": 5,
                "alert_timeout": 300,
                "urgent_alert_timeout": 120,
            },
        }

    @pytest.fixture
    def config_file_delivery(self, delivery_config):
        """Create config file for delivery tests."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(delivery_config, f)
            return f.name

    @pytest.mark.asyncio
    async def test_successful_alert_delivery_tracking(self, config_file_delivery):
        """Test tracking of successful alert deliveries."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock LLM evaluator
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            # Track delivery results
            delivery_results = []
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            async def track_delivery(alert):
                result = DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
                delivery_results.append(result)
                return result

            mock_dispatcher.send_alert = track_delivery

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_delivery)
            await orchestrator.initialize()

            # Process test deals
            test_deals = [
                RawDeal(
                    title="Laptop Deal 1",
                    description="Great laptop",
                    link="https://example.com/deal1",
                    pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                    category="Electronics",
                ),
                RawDeal(
                    title="Laptop Deal 2",
                    description="Another laptop",
                    link="https://example.com/deal2",
                    pub_date="Mon, 01 Jan 2024 12:01:00 GMT",
                    category="Electronics",
                ),
            ]

            for deal in test_deals:
                await orchestrator._process_single_deal(deal)

            # Verify deliveries were tracked
            assert len(delivery_results) == 2
            assert all(result.success for result in delivery_results)
            assert all(result.error_message is None for result in delivery_results)
            assert all(result.delivery_time is not None for result in delivery_results)

            # Verify no delivery errors were counted
            assert orchestrator._error_counts.get("message_delivery", 0) == 0

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_failed_alert_delivery_tracking(self, config_file_delivery):
        """Test tracking of failed alert deliveries."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock LLM evaluator
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            # Mock failing message dispatcher
            delivery_attempts = []
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            async def failing_delivery(alert):
                result = DeliveryResult(
                    success=False,
                    delivery_time=datetime.now(timezone.utc),
                    error_message="Network timeout",
                )
                delivery_attempts.append(result)
                return result

            mock_dispatcher.send_alert = failing_delivery

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_delivery)
            await orchestrator.initialize()

            # Process test deal
            test_deal = RawDeal(
                title="Laptop Deal",
                description="Great laptop",
                link="https://example.com/deal",
                pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                category="Electronics",
            )

            await orchestrator._process_single_deal(test_deal)

            # Verify failure was tracked
            assert len(delivery_attempts) == 1
            assert not delivery_attempts[0].success
            assert delivery_attempts[0].error_message == "Network timeout"

            # Verify error count was incremented
            assert orchestrator._error_counts.get("message_delivery", 0) == 1

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_delivery_timeout_validation(self, config_file_delivery):
        """Test validation of delivery timeouts."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock LLM evaluator
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            # Mock slow message dispatcher
            delivery_times = []
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            async def slow_delivery(alert):
                start_time = time.time()
                await asyncio.sleep(0.1)  # 100ms delay
                end_time = time.time()

                result = DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
                delivery_times.append(end_time - start_time)
                return result

            mock_dispatcher.send_alert = slow_delivery

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_delivery)
            await orchestrator.initialize()

            # Process urgent deal
            urgent_deal = RawDeal(
                title="URGENT: Laptop Deal - Limited Time!",
                description="Stock running low!",
                link="https://example.com/urgent-deal",
                pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                category="Electronics",
            )

            start_time = time.time()
            await orchestrator._process_single_deal(urgent_deal)
            total_time = time.time() - start_time

            # Verify delivery timing
            assert len(delivery_times) == 1
            assert delivery_times[0] >= 0.1  # At least 100ms as expected

            # For urgent deals, total processing should be reasonable
            assert total_time < 1.0  # Less than 1 second total

            await orchestrator.shutdown()


@pytest.mark.integration
class TestSystemStartupValidation:
    """Test system startup validation and initialization checks."""

    @pytest.fixture
    def startup_config(self):
        """Create configuration for startup testing."""
        return {
            "rss_feeds": [
                "https://www.ozbargain.com.au/deals/feed",
                "https://www.ozbargain.com.au/cat/computing/feed",
            ],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 500.0,
                "min_discount_percentage": 20.0,
                "categories": ["Electronics", "Computing"],
                "keywords": ["laptop", "phone"],
                "min_authenticity_score": 0.6,
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
                "polling_interval": 60,
                "max_concurrent_feeds": 5,
                "alert_timeout": 300,
                "urgent_alert_timeout": 120,
            },
        }

    @pytest.fixture
    def config_file_startup(self, startup_config):
        """Create config file for startup tests."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(startup_config, f)
            return f.name

    @pytest.mark.asyncio
    async def test_successful_system_startup(self, config_file_startup):
        """Test successful system startup and initialization."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock successful components
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_startup)

            # Test initialization
            start_time = time.time()
            init_success = await orchestrator.initialize()
            init_time = time.time() - start_time

            # Verify successful initialization
            assert init_success is True
            assert init_time < 5.0  # Should initialize within 5 seconds
            assert orchestrator._startup_time is not None

            # Verify all components are healthy
            status = orchestrator.get_system_status()
            assert status["config_loaded"] is True
            assert all(health for health in status["component_health"].values())

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_startup_with_component_failures(self, config_file_startup):
        """Test startup behavior when some components fail."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock LLM failure
            mock_llm_class.side_effect = Exception("LLM initialization failed")

            # Mock successful message dispatcher
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_startup)

            # Test initialization (should still succeed with degraded functionality)
            init_success = await orchestrator.initialize()

            # System should still initialize (non-critical component failure)
            assert init_success is True

            # Verify component health reflects the failure
            status = orchestrator.get_system_status()
            assert status["component_health"]["llm_evaluator"] is False
            assert status["component_health"]["message_dispatcher"] is True

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_startup_with_critical_component_failure(self, config_file_startup):
        """Test startup behavior when critical components fail."""
        with patch(
            "ozb_deal_filter.services.config_manager.ConfigurationManager"
        ) as mock_config_mgr:
            # Mock critical component failure (config manager)
            mock_config_mgr.side_effect = Exception("Configuration loading failed")

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_startup)

            # Test initialization (should fail)
            init_success = await orchestrator.initialize()

            # System should fail to initialize
            assert init_success is False
            assert orchestrator._startup_time is None

    @pytest.mark.asyncio
    async def test_startup_validation_checks(self, config_file_startup):
        """Test comprehensive startup validation checks."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock components
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )
            )

            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_startup)

            # Initialize system
            await orchestrator.initialize()

            # Validate startup state
            status = orchestrator.get_system_status()

            # Check required status fields
            required_fields = [
                "running",
                "startup_time",
                "uptime",
                "component_health",
                "error_counts",
                "config_loaded",
            ]

            for field in required_fields:
                assert field in status, f"Missing required status field: {field}"

            # Check component health structure
            expected_components = [
                "config_manager",
                "rss_monitor",
                "deal_parser",
                "llm_evaluator",
                "evaluation_service",
                "alert_formatter",
                "message_dispatcher",
            ]

            for component in expected_components:
                assert (
                    component in status["component_health"]
                ), f"Missing component health: {component}"

            # Verify configuration was loaded
            assert orchestrator._config is not None
            assert len(orchestrator._config.rss_feeds) == 2
            assert orchestrator._config.user_criteria.max_price == 500.0

            await orchestrator.shutdown()

    def test_startup_timing_requirements(self, config_file_startup):
        """Test that startup meets timing requirements."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:
            # Mock fast components
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_startup)

            # Measure initialization time
            start_time = time.time()

            # Run initialization synchronously for timing
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                init_success = loop.run_until_complete(orchestrator.initialize())
                init_time = time.time() - start_time

                # Verify timing requirements
                assert init_success is True
                assert init_time < 10.0  # Should initialize within 10 seconds

                print(f"System initialization time: {init_time:.2f}s")

                # Cleanup
                loop.run_until_complete(orchestrator.shutdown())
            finally:
                loop.close()
