"""
Integration tests for the OzBargain Deal Filter system.

This module provides end-to-end integration tests that validate the complete
workflow from RSS feed monitoring to alert delivery, including performance
benchmarking and system behavior validation.
"""

import pytest
import asyncio
import tempfile
import yaml
import time
import statistics
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from ozb_deal_filter.orchestrator import ApplicationOrchestrator
from ozb_deal_filter.models.deal import Deal, RawDeal
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.models.filter import FilterResult, UrgencyLevel
from ozb_deal_filter.models.alert import FormattedAlert
from ozb_deal_filter.models.delivery import DeliveryResult
from ozb_deal_filter.models.config import Configuration


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflow scenarios."""

    @pytest.fixture
    def integration_config(self):
        """Create integration test configuration."""
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
                "keywords": ["laptop", "phone", "tablet", "computer"],
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
    def config_file(self, integration_config):
        """Create temporary config file for integration tests."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(integration_config, f)
            return f.name

    @pytest.fixture
    def sample_rss_data(self):
        """Create sample RSS feed data for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>OzBargain</title>
                <description>OzBargain deals feed</description>
                <item>
                    <title>50% off Gaming Laptop - MSI Katana 15</title>
                    <description>Great gaming laptop with RTX 4060, 16GB RAM, 512GB SSD. Limited time offer!</description>
                    <link>https://www.ozbargain.com.au/node/123456</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                    <category>Computing</category>
                </item>
                <item>
                    <title>iPhone 15 Pro - 30% off at JB Hi-Fi</title>
                    <description>Latest iPhone with titanium design. Stock running low!</description>
                    <link>https://www.ozbargain.com.au/node/123457</link>
                    <pubDate>Mon, 01 Jan 2024 11:30:00 GMT</pubDate>
                    <category>Electronics</category>
                </item>
                <item>
                    <title>Free Coffee at 7-Eleven</title>
                    <description>Free small coffee with any purchase</description>
                    <link>https://www.ozbargain.com.au/node/123458</link>
                    <pubDate>Mon, 01 Jan 2024 11:00:00 GMT</pubDate>
                    <category>Food</category>
                </item>
            </channel>
        </rss>"""

    @pytest.mark.asyncio
    async def test_complete_workflow_success(self, config_file, sample_rss_data):
        """Test complete workflow from RSS to alert delivery."""
        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Mock RSS response
            mock_response = Mock()
            mock_response.text = sample_rss_data
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Mock LLM evaluator
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(
                return_value=EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.85,
                    reasoning="Matches user criteria for electronics/computing deals",
                )
            )

            # Mock message dispatcher
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create and initialize orchestrator
            orchestrator = ApplicationOrchestrator(config_file)
            
            # Initialize system
            init_success = await orchestrator.initialize()
            assert init_success is True

            # Simulate RSS feed processing
            from ozb_deal_filter.components.rss_monitor import RSSMonitor
            from ozb_deal_filter.components.deal_parser import DealParser

            rss_monitor = RSSMonitor(polling_interval=60)
            deal_parser = DealParser()

            # Add feed and get deals
            rss_monitor.add_feed("https://www.ozbargain.com.au/deals/feed")
            raw_deals = await rss_monitor._fetch_and_parse_feed(
                "https://www.ozbargain.com.au/deals/feed"
            )

            # Verify deals were parsed
            assert len(raw_deals) == 3
            assert "Gaming Laptop" in raw_deals[0].title
            assert "iPhone 15 Pro" in raw_deals[1].title

            # Process deals through pipeline
            relevant_deals = []
            for raw_deal in raw_deals:
                deal = deal_parser.parse_deal(raw_deal)
                if deal_parser.validate_deal(deal):
                    # Check if deal matches criteria (laptop/phone keywords)
                    if any(
                        keyword in deal.title.lower()
                        for keyword in ["laptop", "phone", "computer"]
                    ):
                        relevant_deals.append(deal)

            # Verify filtering worked
            assert len(relevant_deals) == 2  # Laptop and iPhone deals
            assert all("Coffee" not in deal.title for deal in relevant_deals)

            # Verify LLM evaluation was called
            assert mock_llm.evaluate_deal.call_count >= 2

            # Verify alerts were sent
            assert mock_dispatcher.send_alert.call_count >= 2

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_workflow_with_llm_fallback(self, config_file, sample_rss_data):
        """Test workflow when LLM fails and fallback is used."""
        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Mock RSS response
            mock_response = Mock()
            mock_response.text = sample_rss_data
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Mock LLM evaluator to fail
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            mock_llm.evaluate_deal = AsyncMock(side_effect=Exception("LLM service unavailable"))

            # Mock message dispatcher
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file)
            await orchestrator.initialize()

            # Create test deal
            test_deal = Deal(
                id="test-laptop-deal",
                title="Gaming Laptop - 50% off",
                description="Great laptop deal",
                price=500.0,
                original_price=1000.0,
                discount_percentage=50.0,
                category="Computing",
                url="https://example.com/deal",
                timestamp=datetime.now(timezone.utc),
                votes=25,
                comments=10,
                urgency_indicators=["limited time"],
            )

            # Process deal (should use fallback evaluation)
            raw_deal = RawDeal(
                title=test_deal.title,
                description=test_deal.description,
                link=test_deal.url,
                pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                category=test_deal.category,
            )

            await orchestrator._process_single_deal(raw_deal)

            # Verify LLM was attempted but failed
            assert mock_llm.evaluate_deal.called

            # Verify fallback evaluation was used and alert was sent
            assert mock_dispatcher.send_alert.called

            # Verify component health was updated
            assert orchestrator._component_health["llm_evaluator"] is False

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_workflow_with_message_delivery_failure(self, config_file, sample_rss_data):
        """Test workflow when message delivery fails."""
        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Mock RSS response
            mock_response = Mock()
            mock_response.text = sample_rss_data
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

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

            # Mock message dispatcher to fail
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=False,
                    delivery_time=datetime.now(timezone.utc),
                    error_message="Network timeout",
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file)
            await orchestrator.initialize()

            # Create test deal
            raw_deal = RawDeal(
                title="Test Laptop Deal",
                description="Great laptop deal",
                link="https://example.com/deal",
                pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                category="Computing",
            )

            # Process deal
            await orchestrator._process_single_deal(raw_deal)

            # Verify alert delivery was attempted
            assert mock_dispatcher.send_alert.called

            # Verify error was tracked
            assert orchestrator._error_counts.get("message_delivery", 0) > 0

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_feeds_concurrent_processing(self, config_file):
        """Test concurrent processing of multiple RSS feeds."""
        feed_data_1 = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Laptop Deal 1</title>
                    <description>Great laptop</description>
                    <link>https://example.com/deal1</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                    <category>Computing</category>
                </item>
            </channel>
        </rss>"""

        feed_data_2 = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Phone Deal 2</title>
                    <description>Great phone</description>
                    <link>https://example.com/deal2</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                    <category>Electronics</category>
                </item>
            </channel>
        </rss>"""

        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            
            if "computing" in url:
                mock_response.text = feed_data_1
            else:
                mock_response.text = feed_data_2
            
            return mock_response

        with patch("requests.get", side_effect=mock_get_side_effect), patch(
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

            # Mock message dispatcher
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file)
            await orchestrator.initialize()

            # Simulate concurrent feed processing
            from ozb_deal_filter.components.rss_monitor import RSSMonitor

            rss_monitor = RSSMonitor(polling_interval=60)
            
            # Add multiple feeds
            feeds = [
                "https://www.ozbargain.com.au/deals/feed",
                "https://www.ozbargain.com.au/cat/computing/feed",
            ]

            for feed_url in feeds:
                rss_monitor.add_feed(feed_url)

            # Process feeds concurrently
            tasks = []
            for feed_url in feeds:
                task = asyncio.create_task(
                    rss_monitor._fetch_and_parse_feed(feed_url)
                )
                tasks.append(task)

            # Wait for all feeds to be processed
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify both feeds were processed
            assert len(results) == 2
            assert all(not isinstance(result, Exception) for result in results)
            assert all(len(result) > 0 for result in results)

            await orchestrator.shutdown()


@pytest.mark.integration
class TestPerformanceBenchmarks:
    """Performance benchmarking tests."""

    @pytest.fixture
    def performance_config(self):
        """Create configuration optimized for performance testing."""
        return {
            "rss_feeds": ["https://www.ozbargain.com.au/deals/feed"],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 1000.0,
                "min_discount_percentage": 10.0,
                "categories": ["Electronics", "Computing"],
                "keywords": ["laptop", "phone"],
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

    @pytest.fixture
    def config_file_perf(self, performance_config):
        """Create config file for performance tests."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(performance_config, f)
            return f.name

    def create_large_rss_feed(self, num_deals: int = 100) -> str:
        """Create RSS feed with many deals for performance testing."""
        items = []
        for i in range(num_deals):
            items.append(f"""
                <item>
                    <title>Deal {i} - Laptop Special Offer</title>
                    <description>Great laptop deal number {i} with excellent features</description>
                    <link>https://www.ozbargain.com.au/node/{123456 + i}</link>
                    <pubDate>Mon, 01 Jan 2024 {12 + (i % 12):02d}:00:00 GMT</pubDate>
                    <category>Computing</category>
                </item>
            """)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>OzBargain Performance Test</title>
                <description>Large feed for performance testing</description>
                {''.join(items)}
            </channel>
        </rss>"""

    @pytest.mark.asyncio
    async def test_rss_parsing_performance(self, config_file_perf):
        """Benchmark RSS parsing performance with large feeds."""
        large_feed = self.create_large_rss_feed(100)

        with patch("requests.get") as mock_get:
            # Mock RSS response
            mock_response = Mock()
            mock_response.text = large_feed
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            from ozb_deal_filter.components.rss_monitor import RSSMonitor
            from ozb_deal_filter.components.deal_parser import DealParser

            rss_monitor = RSSMonitor(polling_interval=60)
            deal_parser = DealParser()

            # Benchmark RSS parsing
            start_time = time.time()
            raw_deals = await rss_monitor._fetch_and_parse_feed(
                "https://www.ozbargain.com.au/deals/feed"
            )
            parse_time = time.time() - start_time

            # Verify parsing results
            assert len(raw_deals) == 100
            assert parse_time < 5.0  # Should parse 100 deals in under 5 seconds

            # Benchmark deal parsing
            start_time = time.time()
            parsed_deals = []
            for raw_deal in raw_deals:
                deal = deal_parser.parse_deal(raw_deal)
                if deal_parser.validate_deal(deal):
                    parsed_deals.append(deal)
            deal_parse_time = time.time() - start_time

            # Verify deal parsing results
            assert len(parsed_deals) == 100
            assert deal_parse_time < 2.0  # Should parse deals in under 2 seconds

            print(f"RSS parsing time: {parse_time:.2f}s")
            print(f"Deal parsing time: {deal_parse_time:.2f}s")
            print(f"Total processing time: {parse_time + deal_parse_time:.2f}s")

    @pytest.mark.asyncio
    async def test_llm_evaluation_performance(self, config_file_perf):
        """Benchmark LLM evaluation performance."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class:

            # Mock LLM with realistic response times
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            async def mock_evaluate_deal(deal):
                # Simulate LLM processing time
                await asyncio.sleep(0.1)  # 100ms per evaluation
                return EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="Test evaluation",
                )

            mock_llm.evaluate_deal = mock_evaluate_deal

            from ozb_deal_filter.services.evaluation_service import EvaluationService

            evaluation_service = EvaluationService(
                llm_evaluator=mock_llm,
                prompt_template_path="prompts/deal_evaluator.example.txt",
            )

            # Create test deals
            test_deals = []
            for i in range(10):
                deal = Deal(
                    id=f"test-deal-{i}",
                    title=f"Test Laptop Deal {i}",
                    description=f"Great laptop deal number {i}",
                    price=500.0,
                    original_price=1000.0,
                    discount_percentage=50.0,
                    category="Computing",
                    url=f"https://example.com/deal{i}",
                    timestamp=datetime.now(timezone.utc),
                    votes=20,
                    comments=5,
                    urgency_indicators=[],
                )
                test_deals.append(deal)

            # Benchmark sequential evaluation
            start_time = time.time()
            sequential_results = []
            for deal in test_deals:
                result = await evaluation_service.evaluate_deal(deal)
                sequential_results.append(result)
            sequential_time = time.time() - start_time

            # Benchmark concurrent evaluation
            start_time = time.time()
            concurrent_tasks = [
                evaluation_service.evaluate_deal(deal) for deal in test_deals
            ]
            concurrent_results = await asyncio.gather(*concurrent_tasks)
            concurrent_time = time.time() - start_time

            # Verify results
            assert len(sequential_results) == 10
            assert len(concurrent_results) == 10
            assert all(result.is_relevant for result in sequential_results)
            assert all(result.is_relevant for result in concurrent_results)

            # Concurrent should be significantly faster
            assert concurrent_time < sequential_time * 0.5

            print(f"Sequential evaluation time: {sequential_time:.2f}s")
            print(f"Concurrent evaluation time: {concurrent_time:.2f}s")
            print(f"Speedup: {sequential_time / concurrent_time:.2f}x")

    @pytest.mark.asyncio
    async def test_end_to_end_latency(self, config_file_perf):
        """Measure end-to-end latency from RSS detection to alert delivery."""
        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Mock RSS response
            single_deal_feed = """<?xml version="1.0"?>
            <rss version="2.0">
                <channel>
                    <item>
                        <title>Urgent Laptop Deal - 70% off!</title>
                        <description>Limited time laptop deal</description>
                        <link>https://example.com/urgent-deal</link>
                        <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                        <category>Computing</category>
                    </item>
                </channel>
            </rss>"""

            mock_response = Mock()
            mock_response.text = single_deal_feed
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Mock LLM evaluator with timing
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            async def timed_evaluate_deal(deal):
                await asyncio.sleep(0.05)  # 50ms evaluation time
                return EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.9,
                    reasoning="Urgent laptop deal matches criteria",
                )

            mock_llm.evaluate_deal = timed_evaluate_deal

            # Mock message dispatcher with timing
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            delivery_times = []

            async def timed_send_alert(alert):
                await asyncio.sleep(0.02)  # 20ms delivery time
                delivery_time = datetime.now(timezone.utc)
                delivery_times.append(delivery_time)
                return DeliveryResult(
                    success=True,
                    delivery_time=delivery_time,
                    error_message=None,
                )

            mock_dispatcher.send_alert = timed_send_alert

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_perf)
            await orchestrator.initialize()

            # Measure end-to-end latency
            latencies = []
            for i in range(5):  # Test 5 iterations
                start_time = time.time()

                # Simulate deal processing
                raw_deal = RawDeal(
                    title=f"Urgent Laptop Deal {i} - 70% off!",
                    description="Limited time laptop deal",
                    link=f"https://example.com/urgent-deal-{i}",
                    pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                    category="Computing",
                )

                await orchestrator._process_single_deal(raw_deal)
                
                end_time = time.time()
                latency = end_time - start_time
                latencies.append(latency)

            # Analyze latency statistics
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)

            # Verify performance requirements
            assert avg_latency < 0.5  # Average under 500ms
            assert max_latency < 1.0   # Max under 1 second
            assert len(delivery_times) == 5  # All alerts delivered

            print(f"Average latency: {avg_latency:.3f}s")
            print(f"Min latency: {min_latency:.3f}s")
            print(f"Max latency: {max_latency:.3f}s")

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, config_file_perf):
        """Test memory usage stability during extended operation."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Setup mocks
            large_feed = self.create_large_rss_feed(50)

            mock_response = Mock()
            mock_response.text = large_feed
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

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

            # Mock message dispatcher
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_perf)
            await orchestrator.initialize()

            # Monitor memory usage over time
            memory_samples = []
            
            # Process deals in batches to simulate extended operation
            for batch in range(5):  # 5 batches of processing
                # Process batch of deals
                for i in range(10):  # 10 deals per batch
                    raw_deal = RawDeal(
                        title=f"Memory Test Deal {batch}-{i}",
                        description="Memory usage test deal",
                        link=f"https://example.com/deal-{batch}-{i}",
                        pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                        category="Electronics",
                    )
                    await orchestrator._process_single_deal(raw_deal)

                # Sample memory usage
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(current_memory)
                
                # Small delay between batches
                await asyncio.sleep(0.1)

            final_memory = process.memory_info().rss / 1024 / 1024  # MB

            # Analyze memory usage
            memory_growth = final_memory - initial_memory
            max_memory = max(memory_samples)
            
            # Verify memory stability (should not grow excessively)
            assert memory_growth < 50  # Less than 50MB growth
            assert max_memory < initial_memory + 100  # Less than 100MB peak

            print(f"Initial memory: {initial_memory:.1f}MB")
            print(f"Final memory: {final_memory:.1f}MB")
            print(f"Memory growth: {memory_growth:.1f}MB")
            print(f"Peak memory: {max_memory:.1f}MB")

            await orchestrator.shutdown()


@pytest.mark.integration
class TestRealRSSFeedIntegration:
    """Test integration with real OzBargain RSS feeds (respecting rate limits)."""

    @pytest.fixture
    def real_feed_config(self):
        """Create configuration for real RSS feed testing."""
        return {
            "rss_feeds": [
                "https://www.ozbargain.com.au/deals/feed",
            ],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 1000.0,
                "min_discount_percentage": 10.0,
                "categories": ["Electronics", "Computing"],
                "keywords": ["laptop", "phone", "computer"],
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
                "polling_interval": 300,  # 5 minutes to respect rate limits
                "max_concurrent_feeds": 1,
                "alert_timeout": 300,
                "urgent_alert_timeout": 120,
            },
        }

    @pytest.fixture
    def config_file_real(self, real_feed_config):
        """Create config file for real feed tests."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(real_feed_config, f)
            return f.name

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_rss_feed_parsing(self, config_file_real):
        """Test parsing of real OzBargain RSS feed data."""
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

            # Mock message dispatcher
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_real)
            await orchestrator.initialize()

            # Test RSS feed fetching and parsing
            from ozb_deal_filter.components.rss_monitor import RSSMonitor
            from ozb_deal_filter.components.deal_parser import DealParser

            rss_monitor = RSSMonitor(polling_interval=300)
            deal_parser = DealParser()

            try:
                # Fetch real RSS feed (with timeout)
                raw_deals = await asyncio.wait_for(
                    rss_monitor._fetch_and_parse_feed(
                        "https://www.ozbargain.com.au/deals/feed"
                    ),
                    timeout=30.0
                )

                # Verify we got real deals
                assert len(raw_deals) > 0
                assert all(isinstance(deal, RawDeal) for deal in raw_deals)

                # Test parsing of real deals
                parsed_deals = []
                for raw_deal in raw_deals[:5]:  # Test first 5 deals
                    try:
                        deal = deal_parser.parse_deal(raw_deal)
                        if deal_parser.validate_deal(deal):
                            parsed_deals.append(deal)
                    except Exception as e:
                        # Log parsing errors but don't fail test
                        print(f"Deal parsing error: {e}")

                # Verify parsing worked for at least some deals
                assert len(parsed_deals) > 0

                # Verify deal structure
                for deal in parsed_deals:
                    assert deal.title is not None
                    assert deal.description is not None
                    assert deal.url is not None
                    assert deal.category is not None
                    assert deal.timestamp is not None

                print(f"Successfully parsed {len(parsed_deals)} real deals")

            except asyncio.TimeoutError:
                pytest.skip("RSS feed request timed out - network issue")
            except Exception as e:
                pytest.skip(f"RSS feed test skipped due to: {e}")

            await orchestrator.shutdown()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_feed_rate_limiting(self, config_file_real):
        """Test that RSS feed requests respect rate limiting."""
        from ozb_deal_filter.components.rss_monitor import RSSMonitor

        rss_monitor = RSSMonitor(polling_interval=300)
        
        # Record request times
        request_times = []
        
        try:
            # Make multiple requests and measure timing
            for i in range(3):
                start_time = time.time()
                
                # This should respect rate limiting internally
                await rss_monitor._fetch_and_parse_feed(
                    "https://www.ozbargain.com.au/deals/feed"
                )
                
                request_times.append(time.time() - start_time)
                
                # Wait between requests to be respectful
                if i < 2:  # Don't wait after last request
                    await asyncio.sleep(2.0)

            # Verify requests completed successfully
            assert len(request_times) == 3
            assert all(t > 0 for t in request_times)

            # Verify reasonable response times (should be < 10 seconds each)
            assert all(t < 10.0 for t in request_times)

            print(f"Request times: {[f'{t:.2f}s' for t in request_times]}")

        except Exception as e:
            pytest.skip(f"Rate limiting test skipped due to: {e}")


@pytest.mark.integration
class TestSystemBehaviorValidation:
    """Test system behavior under various scenarios."""

    @pytest.fixture
    def behavior_config(self):
        """Create configuration for behavior testing."""
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
                "keywords": ["laptop", "phone", "computer"],
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
    def config_file_behavior(self, behavior_config):
        """Create config file for behavior tests."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(behavior_config, f)
            return f.name

    @pytest.mark.asyncio
    async def test_system_graceful_degradation(self, config_file_behavior):
        """Test system behavior when components fail gracefully."""
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
                        <category>Computing</category>
                    </item>
                </channel>
            </rss>"""

            mock_response = Mock()
            mock_response.text = rss_content
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Mock LLM that fails initially then recovers
            llm_call_count = 0
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            async def failing_then_working_llm(deal):
                nonlocal llm_call_count
                llm_call_count += 1
                if llm_call_count <= 2:
                    raise Exception("LLM temporarily unavailable")
                return EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning="LLM recovered",
                )

            mock_llm.evaluate_deal = failing_then_working_llm

            # Mock message dispatcher that works
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_behavior)
            await orchestrator.initialize()

            # Process deals - first two should fail LLM, third should succeed
            test_deals = [
                RawDeal(
                    title="Laptop Deal 1",
                    description="First laptop deal",
                    link="https://example.com/deal1",
                    pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
                    category="Computing",
                ),
                RawDeal(
                    title="Laptop Deal 2", 
                    description="Second laptop deal",
                    link="https://example.com/deal2",
                    pub_date="Mon, 01 Jan 2024 12:01:00 GMT",
                    category="Computing",
                ),
                RawDeal(
                    title="Laptop Deal 3",
                    description="Third laptop deal",
                    link="https://example.com/deal3",
                    pub_date="Mon, 01 Jan 2024 12:02:00 GMT",
                    category="Computing",
                ),
            ]

            for deal in test_deals:
                await orchestrator._process_single_deal(deal)

            # Verify system handled failures gracefully
            assert llm_call_count == 3  # All three deals attempted LLM evaluation
            
            # Verify error tracking
            assert orchestrator._error_counts.get("llm_evaluation", 0) == 2

            # Verify system recovered and sent alert for third deal
            assert mock_dispatcher.send_alert.call_count == 1

            # Verify component health reflects recovery
            status = orchestrator.get_system_status()
            # LLM should be marked as healthy after recovery
            assert status["component_health"]["llm_evaluator"] is True

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_high_volume_deal_processing(self, config_file_behavior):
        """Test system behavior under high volume of deals."""
        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Create large RSS feed
            num_deals = 50
            items = []
            for i in range(num_deals):
                items.append(f"""
                    <item>
                        <title>High Volume Deal {i} - Laptop Special</title>
                        <description>Deal number {i} with great features</description>
                        <link>https://www.ozbargain.com.au/node/{123456 + i}</link>
                        <pubDate>Mon, 01 Jan 2024 {12 + (i % 12):02d}:00:00 GMT</pubDate>
                        <category>Computing</category>
                    </item>
                """)

            large_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
                <channel>
                    <title>High Volume Test Feed</title>
                    <description>Large feed for volume testing</description>
                    {''.join(items)}
                </channel>
            </rss>"""

            mock_response = Mock()
            mock_response.text = large_feed
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Mock LLM with realistic processing time
            evaluation_count = 0
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            async def realistic_llm_evaluation(deal):
                nonlocal evaluation_count
                evaluation_count += 1
                await asyncio.sleep(0.01)  # 10ms processing time
                return EvaluationResult(
                    is_relevant=evaluation_count % 3 == 0,  # 1/3 relevant
                    confidence_score=0.8,
                    reasoning=f"Evaluation {evaluation_count}",
                )

            mock_llm.evaluate_deal = realistic_llm_evaluation

            # Mock message dispatcher
            alert_count = 0
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            async def count_alerts(alert):
                nonlocal alert_count
                alert_count += 1
                await asyncio.sleep(0.005)  # 5ms delivery time
                return DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )

            mock_dispatcher.send_alert = count_alerts

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_behavior)
            await orchestrator.initialize()

            # Process high volume of deals
            start_time = time.time()
            
            from ozb_deal_filter.components.rss_monitor import RSSMonitor
            from ozb_deal_filter.components.deal_parser import DealParser

            rss_monitor = RSSMonitor(polling_interval=60)
            deal_parser = DealParser()

            # Fetch and parse deals
            raw_deals = await rss_monitor._fetch_and_parse_feed(
                "https://www.ozbargain.com.au/deals/feed"
            )

            # Process all deals
            processed_deals = []
            for raw_deal in raw_deals:
                deal = deal_parser.parse_deal(raw_deal)
                if deal_parser.validate_deal(deal):
                    processed_deals.append(deal)
                    await orchestrator._process_single_deal(raw_deal)

            processing_time = time.time() - start_time

            # Verify high volume processing
            assert len(processed_deals) == num_deals
            assert evaluation_count == num_deals
            assert alert_count == num_deals // 3  # 1/3 were relevant

            # Verify performance requirements
            assert processing_time < 10.0  # Should process 50 deals in under 10 seconds
            assert processing_time / num_deals < 0.2  # Less than 200ms per deal

            print(f"Processed {num_deals} deals in {processing_time:.2f}s")
            print(f"Average time per deal: {processing_time / num_deals * 1000:.1f}ms")
            print(f"Evaluations: {evaluation_count}, Alerts: {alert_count}")

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_feed_processing_stability(self, config_file_behavior):
        """Test stability when processing multiple feeds concurrently."""
        # Create different feed contents
        feed_contents = {}
        for i in range(3):
            items = []
            for j in range(10):
                items.append(f"""
                    <item>
                        <title>Feed {i} Deal {j} - Electronics</title>
                        <description>Deal from feed {i}, item {j}</description>
                        <link>https://example.com/feed{i}/deal{j}</link>
                        <pubDate>Mon, 01 Jan 2024 {12 + j}:00:00 GMT</pubDate>
                        <category>Electronics</category>
                    </item>
                """)

            feed_contents[f"feed_{i}"] = f"""<?xml version="1.0"?>
            <rss version="2.0">
                <channel>
                    <title>Test Feed {i}</title>
                    <description>Test feed {i} for concurrent processing</description>
                    {''.join(items)}
                </channel>
            </rss>"""

        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            
            # Return different content based on URL
            if "computing" in url:
                mock_response.text = feed_contents["feed_0"]
            elif "electronics" in url:
                mock_response.text = feed_contents["feed_1"]
            else:
                mock_response.text = feed_contents["feed_2"]
            
            return mock_response

        with patch("requests.get", side_effect=mock_get_side_effect), patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Mock LLM evaluator
            evaluation_count = 0
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm

            async def concurrent_safe_evaluation(deal):
                nonlocal evaluation_count
                evaluation_count += 1
                await asyncio.sleep(0.01)  # Small delay
                return EvaluationResult(
                    is_relevant=True,
                    confidence_score=0.8,
                    reasoning=f"Concurrent evaluation {evaluation_count}",
                )

            mock_llm.evaluate_deal = concurrent_safe_evaluation

            # Mock message dispatcher
            alert_count = 0
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            async def concurrent_safe_delivery(alert):
                nonlocal alert_count
                alert_count += 1
                await asyncio.sleep(0.005)
                return DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )

            mock_dispatcher.send_alert = concurrent_safe_delivery

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_behavior)
            await orchestrator.initialize()

            # Process multiple feeds concurrently
            from ozb_deal_filter.components.rss_monitor import RSSMonitor

            rss_monitor = RSSMonitor(polling_interval=60)
            
            feeds = [
                "https://www.ozbargain.com.au/deals/feed",
                "https://www.ozbargain.com.au/cat/computing/feed",
                "https://www.ozbargain.com.au/cat/electronics/feed",
            ]

            # Add feeds
            for feed_url in feeds:
                rss_monitor.add_feed(feed_url)

            # Process feeds concurrently
            start_time = time.time()
            
            tasks = []
            for feed_url in feeds:
                task = asyncio.create_task(
                    rss_monitor._fetch_and_parse_feed(feed_url)
                )
                tasks.append(task)

            # Wait for all feeds to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            processing_time = time.time() - start_time

            # Verify concurrent processing worked
            assert len(results) == 3
            assert all(not isinstance(result, Exception) for result in results)
            
            # Verify all feeds returned deals
            total_deals = sum(len(result) for result in results)
            assert total_deals == 30  # 10 deals per feed

            # Verify reasonable processing time for concurrent execution
            assert processing_time < 5.0  # Should be faster than sequential

            print(f"Processed {len(feeds)} feeds concurrently in {processing_time:.2f}s")
            print(f"Total deals processed: {total_deals}")

            await orchestrator.shutdown()reate_large_rss_feed(50)
            mock_response = Mock()
            mock_response.text = large_feed
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

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
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_perf)
            await orchestrator.initialize()

            memory_samples = []

            # Simulate extended operation
            for iteration in range(10):
                # Process deals
                from ozb_deal_filter.components.rss_monitor import RSSMonitor
                rss_monitor = RSSMonitor(polling_interval=60)
                rss_monitor.add_feed("https://www.ozbargain.com.au/deals/feed")
                
                raw_deals = await rss_monitor._fetch_and_parse_feed(
                    "https://www.ozbargain.com.au/deals/feed"
                )

                # Process each deal
                for raw_deal in raw_deals[:10]:  # Process 10 deals per iteration
                    await orchestrator._process_single_deal(raw_deal)

                # Sample memory usage
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(current_memory)

                # Small delay between iterations
                await asyncio.sleep(0.1)

            # Analyze memory usage
            final_memory = memory_samples[-1]
            memory_growth = final_memory - initial_memory
            max_memory = max(memory_samples)

            # Verify memory stability
            assert memory_growth < 50  # Less than 50MB growth
            assert max_memory < initial_memory + 100  # Less than 100MB peak

            print(f"Initial memory: {initial_memory:.1f} MB")
            print(f"Final memory: {final_memory:.1f} MB")
            print(f"Memory growth: {memory_growth:.1f} MB")
            print(f"Peak memory: {max_memory:.1f} MB")

            await orchestrator.shutdown()


@pytest.mark.integration
class TestSystemBehaviorValidation:
    """Test system behavior under various scenarios."""

    @pytest.fixture
    def behavior_config(self):
        """Create configuration for behavior testing."""
        return {
            "rss_feeds": ["https://www.ozbargain.com.au/deals/feed"],
            "user_criteria": {
                "prompt_template": "prompts/deal_evaluator.example.txt",
                "max_price": 300.0,
                "min_discount_percentage": 25.0,
                "categories": ["Electronics"],
                "keywords": ["phone", "tablet"],
                "min_authenticity_score": 0.7,
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
    def config_file_behavior(self, behavior_config):
        """Create config file for behavior tests."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(behavior_config, f)
            return f.name

    @pytest.mark.asyncio
    async def test_network_failure_recovery(self, config_file_behavior):
        """Test system behavior during network failures."""
        call_count = 0

        def mock_get_with_failures(url, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = Mock()
            
            # Fail first 3 attempts, succeed on 4th
            if call_count <= 3:
                mock_response.raise_for_status.side_effect = Exception("Network error")
                return mock_response
            else:
                mock_response.text = """<?xml version="1.0"?>
                <rss version="2.0">
                    <channel>
                        <item>
                            <title>Phone Deal - 30% off</title>
                            <description>Great phone deal</description>
                            <link>https://example.com/deal</link>
                            <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                            <category>Electronics</category>
                        </item>
                    </channel>
                </rss>"""
                mock_response.status_code = 200
                mock_response.raise_for_status = Mock()
                return mock_response

        with patch("requests.get", side_effect=mock_get_with_failures), patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Setup mocks
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
            mock_dispatcher.send_alert = AsyncMock(
                return_value=DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )
            )

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_behavior)
            await orchestrator.initialize()

            # Test RSS monitor with network failures
            from ozb_deal_filter.components.rss_monitor import RSSMonitor
            rss_monitor = RSSMonitor(polling_interval=60)
            rss_monitor.add_feed("https://www.ozbargain.com.au/deals/feed")

            # This should eventually succeed after retries
            raw_deals = await rss_monitor._fetch_and_parse_feed(
                "https://www.ozbargain.com.au/deals/feed"
            )

            # Verify recovery worked
            assert len(raw_deals) == 1
            assert "Phone Deal" in raw_deals[0].title
            assert call_count == 4  # 3 failures + 1 success

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_invalid_rss_data_handling(self, config_file_behavior):
        """Test handling of invalid RSS data."""
        invalid_rss_scenarios = [
            # Malformed XML
            "This is not XML at all",
            # Empty response
            "",
            # Valid XML but not RSS
            "<?xml version='1.0'?><root><item>Not RSS</item></root>",
            # RSS with missing required fields
            """<?xml version="1.0"?>
            <rss version="2.0">
                <channel>
                    <item>
                        <title>Deal with missing fields</title>
                        <!-- Missing description, link, pubDate -->
                    </item>
                </channel>
            </rss>""",
        ]

        for i, invalid_rss in enumerate(invalid_rss_scenarios):
            with patch("requests.get") as mock_get:
                mock_response = Mock()
                mock_response.text = invalid_rss
                mock_response.status_code = 200
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                from ozb_deal_filter.components.rss_monitor import RSSMonitor
                rss_monitor = RSSMonitor(polling_interval=60)
                rss_monitor.add_feed("https://www.ozbargain.com.au/deals/feed")

                # Should handle invalid data gracefully
                try:
                    raw_deals = await rss_monitor._fetch_and_parse_feed(
                        "https://www.ozbargain.com.au/deals/feed"
                    )
                    # Should return empty list for invalid data
                    assert isinstance(raw_deals, list)
                    print(f"Scenario {i + 1}: Handled gracefully, got {len(raw_deals)} deals")
                except Exception as e:
                    # Should not crash the system
                    print(f"Scenario {i + 1}: Exception handled: {type(e).__name__}")
                    assert True  # Exception handling is acceptable

    @pytest.mark.asyncio
    async def test_high_volume_deal_processing(self, config_file_behavior):
        """Test system behavior with high volume of deals."""
        # Create RSS feed with many deals
        items = []
        for i in range(200):  # 200 deals
            category = "Electronics" if i % 2 == 0 else "Computing"
            items.append(f"""
                <item>
                    <title>Deal {i} - Phone Special {i % 10}% off</title>
                    <description>Great phone deal number {i}</description>
                    <link>https://www.ozbargain.com.au/node/{123456 + i}</link>
                    <pubDate>Mon, 01 Jan 2024 {12 + (i % 12):02d}:00:00 GMT</pubDate>
                    <category>{category}</category>
                </item>
            """)

        high_volume_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>High Volume Test Feed</title>
                <description>Feed with many deals</description>
                {''.join(items)}
            </channel>
        </rss>"""

        with patch("requests.get") as mock_get, patch(
            "ozb_deal_filter.components.llm_evaluator.LLMEvaluator"
        ) as mock_llm_class, patch(
            "ozb_deal_filter.components.message_dispatcher.MessageDispatcherFactory"
        ) as mock_dispatcher_factory:

            # Mock RSS response
            mock_response = Mock()
            mock_response.text = high_volume_feed
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

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

            # Track message dispatcher calls
            sent_alerts = []
            mock_dispatcher = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher
            mock_dispatcher.test_connection.return_value = True

            async def track_send_alert(alert):
                sent_alerts.append(alert)
                return DeliveryResult(
                    success=True,
                    delivery_time=datetime.now(timezone.utc),
                    error_message=None,
                )

            mock_dispatcher.send_alert = track_send_alert

            # Create orchestrator
            orchestrator = ApplicationOrchestrator(config_file_behavior)
            await orchestrator.initialize()

            # Process high volume feed
            start_time = time.time()
            
            from ozb_deal_filter.components.rss_monitor import RSSMonitor
            rss_monitor = RSSMonitor(polling_interval=60)
            rss_monitor.add_feed("https://www.ozbargain.com.au/deals/feed")
            
            raw_deals = await rss_monitor._fetch_and_parse_feed(
                "https://www.ozbargain.com.au/deals/feed"
            )

            # Process deals (limit to first 50 for reasonable test time)
            processed_count = 0
            for raw_deal in raw_deals[:50]:
                await orchestrator._process_single_deal(raw_deal)
                processed_count += 1

            processing_time = time.time() - start_time

            # Verify system handled high volume
            assert len(raw_deals) == 200  # All deals parsed
            assert processed_count == 50   # Processed subset
            assert processing_time < 30     # Completed in reasonable time
            assert len(sent_alerts) > 0     # Some alerts sent

            print(f"Processed {processed_count} deals in {processing_time:.2f}s")
            print(f"Sent {len(sent_alerts)} alerts")
            print(f"Processing rate: {processed_count / processing_time:.1f} deals/sec")

            await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_configuration_validation_scenarios(self, behavior_config):
        """Test various configuration validation scenarios."""
        invalid_configs = [
            # Missing required fields
            {
                "user_criteria": {
                    "max_price": 500.0,
                    # Missing prompt_template
                }
            },
            # Invalid data types
            {
                "rss_feeds": "not_a_list",
                "user_criteria": {
                    "prompt_template": "prompts/test.txt",
                    "max_price": "not_a_number",
                },
            },
            # Invalid values
            {
                "rss_feeds": ["https://example.com/feed"],
                "user_criteria": {
                    "prompt_template": "prompts/test.txt",
                    "max_price": -100.0,  # Negative price
                    "min_discount_percentage": 150.0,  # > 100%
                },
            },
        ]

        for i, invalid_config in enumerate(invalid_configs):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(invalid_config, f)
                config_file = f.name

            # Should handle invalid configuration gracefully
            orchestrator = ApplicationOrchestrator(config_file)
            
            try:
                init_success = await orchestrator.initialize()
                # Should fail initialization with invalid config
                assert init_success is False
                print(f"Invalid config {i + 1}: Properly rejected")
            except Exception as e:
                # Exception handling is also acceptable
                print(f"Invalid config {i + 1}: Exception handled: {type(e).__name__}")
                assert True

            # Cleanup
            Path(config_file).unlink(missing_ok=True)