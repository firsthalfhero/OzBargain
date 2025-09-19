"""
Tests for the application orchestrator.
"""

import pytest
import asyncio
import tempfile
import yaml
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from ozb_deal_filter.orchestrator import ApplicationOrchestrator
from ozb_deal_filter.models.config import Configuration, UserCriteria, LLMProviderConfig, MessagingPlatformConfig
from ozb_deal_filter.models.deal import Deal, RawDeal
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.models.filter import FilterResult, UrgencyLevel


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return {
        "rss_feeds": [
            "https://www.ozbargain.com.au/deals/feed"
        ],
        "user_criteria": {
            "prompt_template": "prompts/deal_evaluator.txt",
            "max_price": 500.0,
            "min_discount_percentage": 20.0,
            "categories": ["Electronics"],
            "keywords": ["laptop"],
            "min_authenticity_score": 0.6
        },
        "llm_provider": {
            "type": "local",
            "local": {
                "model": "llama2",
                "docker_image": "ollama/ollama"
            }
        },
        "messaging_platform": {
            "type": "telegram",
            "telegram": {
                "bot_token": "test_token",
                "chat_id": "test_chat"
            }
        },
        "system": {
            "polling_interval": 120,
            "max_concurrent_feeds": 10
        }
    }


@pytest.fixture
def config_file(sample_config):
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        return f.name


@pytest.fixture
def sample_deal():
    """Create a sample deal for testing."""
    return Deal(
        id="test-deal-1",
        title="Test Laptop Deal - 50% Off",
        description="Great laptop deal with 50% discount",
        price=250.0,
        original_price=500.0,
        discount_percentage=50.0,
        category="Electronics",
        url="https://example.com/deal",
        timestamp=datetime.now(),
        votes=15,
        comments=8,
        urgency_indicators=["limited time"]
    )


@pytest.fixture
def sample_raw_deal():
    """Create a sample raw deal for testing."""
    return RawDeal(
        title="Test Laptop Deal - 50% Off",
        description="Great laptop deal with 50% discount",
        link="https://example.com/deal",
        pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
        category="Electronics"
    )


class TestApplicationOrchestrator:
    """Test cases for ApplicationOrchestrator."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, config_file):
        """Test successful system initialization."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager') as mock_config_mgr, \
             patch('ozb_deal_filter.orchestrator.RSSMonitor') as mock_rss, \
             patch('ozb_deal_filter.orchestrator.DealParser') as mock_parser, \
             patch('ozb_deal_filter.orchestrator.LLMEvaluator') as mock_llm, \
             patch('ozb_deal_filter.orchestrator.AlertFormatter') as mock_formatter, \
             patch('ozb_deal_filter.orchestrator.MessageDispatcherFactory') as mock_dispatcher_factory, \
             patch('ozb_deal_filter.orchestrator.EvaluationService') as mock_eval_service:
            
            # Setup mocks
            mock_config_instance = Mock()
            mock_config_mgr.return_value = mock_config_instance
            mock_config_instance.load_configuration.return_value = Mock()
            
            mock_llm_instance = Mock()
            mock_llm.return_value = mock_llm_instance
            mock_llm_instance.initialize = AsyncMock()
            
            mock_dispatcher_instance = Mock()
            mock_dispatcher_factory.create_dispatcher.return_value = mock_dispatcher_instance
            mock_dispatcher_instance.test_connection.return_value = True
            
            mock_eval_service_instance = Mock()
            mock_eval_service.return_value = mock_eval_service_instance
            mock_eval_service_instance.evaluate_deal = AsyncMock(return_value=EvaluationResult(
                is_relevant=True,
                confidence_score=0.8,
                reasoning="Test evaluation"
            ))
            
            # Test initialization
            orchestrator = ApplicationOrchestrator(config_file)
            result = await orchestrator.initialize()
            
            assert result is True
            assert orchestrator._startup_time is not None
            assert orchestrator._component_health["config_manager"] is True

    @pytest.mark.asyncio
    async def test_initialization_config_failure(self, config_file):
        """Test initialization failure due to config issues."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager') as mock_config_mgr:
            mock_config_mgr.side_effect = Exception("Config error")
            
            orchestrator = ApplicationOrchestrator(config_file)
            result = await orchestrator.initialize()
            
            assert result is False
            assert orchestrator._component_health.get("config_manager", False) is False

    @pytest.mark.asyncio
    async def test_process_single_deal_success(self, config_file, sample_raw_deal, sample_deal):
        """Test successful processing of a single deal."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager') as mock_config_mgr, \
             patch('ozb_deal_filter.orchestrator.DealParser') as mock_parser, \
             patch('ozb_deal_filter.orchestrator.EvaluationService') as mock_eval_service, \
             patch('ozb_deal_filter.orchestrator.AlertFormatter') as mock_formatter, \
             patch('ozb_deal_filter.orchestrator.MessageDispatcher') as mock_dispatcher:
            
            # Setup mocks
            mock_config_instance = Mock()
            mock_config_mgr.return_value = mock_config_instance
            
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse_deal.return_value = sample_deal
            mock_parser_instance.validate_deal.return_value = True
            
            mock_eval_service_instance = Mock()
            mock_eval_service.return_value = mock_eval_service_instance
            mock_eval_service_instance.evaluate_deal = AsyncMock(return_value=EvaluationResult(
                is_relevant=True,
                confidence_score=0.8,
                reasoning="Matches user criteria"
            ))
            
            mock_formatter_instance = Mock()
            mock_formatter.return_value = mock_formatter_instance
            mock_formatter_instance.format_alert.return_value = Mock()
            
            mock_dispatcher_instance = Mock()
            mock_dispatcher.return_value = mock_dispatcher_instance
            mock_dispatcher_instance.send_alert = AsyncMock(return_value=Mock(success=True))
            
            # Setup orchestrator
            orchestrator = ApplicationOrchestrator(config_file)
            orchestrator._deal_parser = mock_parser_instance
            orchestrator._evaluation_service = mock_eval_service_instance
            orchestrator._alert_formatter = mock_formatter_instance
            orchestrator._message_dispatcher = mock_dispatcher_instance
            orchestrator._component_health = {
                "llm_evaluator": True,
                "message_dispatcher": True
            }
            orchestrator._config = Mock()
            orchestrator._config.user_criteria = Mock()
            orchestrator._config.user_criteria.max_price = 1000.0
            orchestrator._config.user_criteria.min_discount_percentage = 10.0
            orchestrator._config.user_criteria.min_authenticity_score = 0.5
            
            # Test processing
            await orchestrator._process_single_deal(sample_raw_deal)
            
            # Verify calls
            mock_parser_instance.parse_deal.assert_called_once_with(sample_raw_deal)
            mock_eval_service_instance.evaluate_deal.assert_called_once()
            mock_dispatcher_instance.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_deal_llm_fallback(self, config_file, sample_raw_deal, sample_deal):
        """Test deal processing with LLM fallback."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager') as mock_config_mgr, \
             patch('ozb_deal_filter.orchestrator.DealParser') as mock_parser, \
             patch('ozb_deal_filter.orchestrator.EvaluationService') as mock_eval_service, \
             patch('ozb_deal_filter.orchestrator.AlertFormatter') as mock_formatter, \
             patch('ozb_deal_filter.orchestrator.MessageDispatcher') as mock_dispatcher:
            
            # Setup mocks
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse_deal.return_value = sample_deal
            mock_parser_instance.validate_deal.return_value = True
            
            mock_eval_service_instance = Mock()
            mock_eval_service.return_value = mock_eval_service_instance
            mock_eval_service_instance.evaluate_deal = AsyncMock(side_effect=Exception("LLM error"))
            
            mock_formatter_instance = Mock()
            mock_formatter.return_value = mock_formatter_instance
            mock_formatter_instance.format_alert.return_value = Mock()
            
            mock_dispatcher_instance = Mock()
            mock_dispatcher.return_value = mock_dispatcher_instance
            mock_dispatcher_instance.send_alert = AsyncMock(return_value=Mock(success=True))
            
            # Setup orchestrator
            orchestrator = ApplicationOrchestrator(config_file)
            orchestrator._deal_parser = mock_parser_instance
            orchestrator._evaluation_service = mock_eval_service_instance
            orchestrator._alert_formatter = mock_formatter_instance
            orchestrator._message_dispatcher = mock_dispatcher_instance
            orchestrator._component_health = {
                "llm_evaluator": True,
                "message_dispatcher": True
            }
            orchestrator._config = Mock()
            orchestrator._config.user_criteria = Mock()
            orchestrator._config.user_criteria.max_price = 1000.0
            orchestrator._config.user_criteria.min_discount_percentage = 10.0
            orchestrator._config.user_criteria.min_authenticity_score = 0.5
            orchestrator._config.user_criteria.keywords = ["laptop"]
            orchestrator._config.user_criteria.categories = ["Electronics"]
            
            # Test processing
            await orchestrator._process_single_deal(sample_raw_deal)
            
            # Verify fallback was used
            assert orchestrator._component_health["llm_evaluator"] is False
            mock_dispatcher_instance.send_alert.assert_called_once()

    def test_fallback_evaluation_keyword_match(self, config_file, sample_deal):
        """Test fallback evaluation with keyword matching."""
        orchestrator = ApplicationOrchestrator(config_file)
        orchestrator._config = Mock()
        orchestrator._config.user_criteria = Mock()
        orchestrator._config.user_criteria.keywords = ["laptop", "computer"]
        orchestrator._config.user_criteria.categories = ["Electronics"]
        
        result = orchestrator._fallback_evaluation(sample_deal)
        
        assert result.is_relevant is True
        assert result.confidence_score == 0.6
        assert "Fallback" in result.reasoning

    def test_fallback_evaluation_no_match(self, config_file, sample_deal):
        """Test fallback evaluation with no keyword match."""
        orchestrator = ApplicationOrchestrator(config_file)
        orchestrator._config = Mock()
        orchestrator._config.user_criteria = Mock()
        orchestrator._config.user_criteria.keywords = ["phone", "tablet"]
        orchestrator._config.user_criteria.categories = ["Electronics"]
        
        result = orchestrator._fallback_evaluation(sample_deal)
        
        assert result.is_relevant is False
        assert result.confidence_score == 0.3

    @pytest.mark.asyncio
    async def test_apply_filters_pass(self, config_file, sample_deal):
        """Test filter application with passing deal."""
        orchestrator = ApplicationOrchestrator(config_file)
        orchestrator._config = Mock()
        orchestrator._config.user_criteria = Mock()
        orchestrator._config.user_criteria.max_price = 1000.0
        orchestrator._config.user_criteria.min_discount_percentage = 20.0
        orchestrator._config.user_criteria.min_authenticity_score = 0.5
        
        evaluation = EvaluationResult(
            is_relevant=True,
            confidence_score=0.8,
            reasoning="Test"
        )
        
        result = await orchestrator._apply_filters(sample_deal, evaluation)
        
        assert result.passes_filters is True
        assert result.price_match is True
        assert result.authenticity_score > 0.5

    @pytest.mark.asyncio
    async def test_apply_filters_fail_price(self, config_file, sample_deal):
        """Test filter application with price failure."""
        orchestrator = ApplicationOrchestrator(config_file)
        orchestrator._config = Mock()
        orchestrator._config.user_criteria = Mock()
        orchestrator._config.user_criteria.max_price = 100.0  # Lower than deal price
        orchestrator._config.user_criteria.min_discount_percentage = 20.0
        orchestrator._config.user_criteria.min_authenticity_score = 0.5
        
        evaluation = EvaluationResult(
            is_relevant=True,
            confidence_score=0.8,
            reasoning="Test"
        )
        
        result = await orchestrator._apply_filters(sample_deal, evaluation)
        
        assert result.passes_filters is False
        assert result.price_match is False

    @pytest.mark.asyncio
    async def test_health_check(self, config_file):
        """Test system health check."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager'):
            orchestrator = ApplicationOrchestrator(config_file)
            
            # Setup mock components
            mock_rss_monitor = Mock()
            mock_rss_monitor.is_healthy.return_value = True
            orchestrator._rss_monitor = mock_rss_monitor
            
            mock_dispatcher = Mock()
            mock_dispatcher.test_connection.return_value = True
            orchestrator._message_dispatcher = mock_dispatcher
            
            orchestrator._component_health = {
                "rss_monitor": True,
                "message_dispatcher": True
            }
            
            await orchestrator._health_check()
            
            assert orchestrator._component_health["rss_monitor"] is True

    def test_get_system_status(self, config_file):
        """Test system status reporting."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager'):
            orchestrator = ApplicationOrchestrator(config_file)
            orchestrator._running = True
            orchestrator._startup_time = datetime.now()
            orchestrator._component_health = {"test": True}
            orchestrator._error_counts = {"test_error": 5}
            orchestrator._config = Mock()
            
            status = orchestrator.get_system_status()
            
            assert status["running"] is True
            assert status["startup_time"] is not None
            assert status["uptime"] is not None
            assert status["component_health"]["test"] is True
            assert status["error_counts"]["test_error"] == 5
            assert status["config_loaded"] is True

    @pytest.mark.asyncio
    async def test_shutdown(self, config_file):
        """Test graceful shutdown."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager'):
            orchestrator = ApplicationOrchestrator(config_file)
            orchestrator._running = True
            orchestrator._startup_time = datetime.now()
            
            # Setup mock components
            mock_rss_monitor = Mock()
            mock_rss_monitor.stop_monitoring = AsyncMock()
            orchestrator._rss_monitor = mock_rss_monitor
            
            mock_llm_evaluator = Mock()
            mock_llm_evaluator.close = AsyncMock()
            orchestrator._llm_evaluator = mock_llm_evaluator
            
            mock_dispatcher = Mock()
            mock_dispatcher.close = AsyncMock()
            orchestrator._message_dispatcher = mock_dispatcher
            
            await orchestrator.shutdown()
            
            assert orchestrator._running is False
            assert orchestrator._shutdown_event.is_set()
            mock_rss_monitor.stop_monitoring.assert_called_once()

    def test_increment_error_count(self, config_file):
        """Test error count tracking."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager'):
            orchestrator = ApplicationOrchestrator(config_file)
            
            orchestrator._increment_error_count("test_error")
            assert orchestrator._error_counts["test_error"] == 1
            
            orchestrator._increment_error_count("test_error")
            assert orchestrator._error_counts["test_error"] == 2

    @pytest.mark.asyncio
    async def test_config_reload(self, config_file):
        """Test configuration reloading."""
        with patch('ozb_deal_filter.orchestrator.ConfigurationManager') as mock_config_mgr:
            mock_config_instance = Mock()
            mock_config_mgr.return_value = mock_config_instance
            mock_config_instance.reload_if_changed.return_value = True
            mock_config_instance.get_config.return_value = Mock()
            
            orchestrator = ApplicationOrchestrator(config_file)
            orchestrator._config_manager = mock_config_instance
            orchestrator._config = Mock()
            orchestrator._config.rss_feeds = ["old_feed"]
            
            # Setup mock components for update
            mock_rss_monitor = Mock()
            mock_rss_monitor.update_feeds = AsyncMock()
            orchestrator._rss_monitor = mock_rss_monitor
            
            mock_llm_evaluator = Mock()
            mock_llm_evaluator.update_provider = AsyncMock()
            orchestrator._llm_evaluator = mock_llm_evaluator
            
            mock_dispatcher = Mock()
            mock_dispatcher.update_platform = AsyncMock()
            orchestrator._message_dispatcher = mock_dispatcher
            
            # Mock new config with different feeds
            new_config = Mock()
            new_config.rss_feeds = ["new_feed"]
            new_config.llm_provider = Mock()
            new_config.messaging_platform = Mock()
            mock_config_instance.get_config.return_value = new_config
            
            await orchestrator._check_config_reload()
            
            mock_config_instance.reload_if_changed.assert_called_once()