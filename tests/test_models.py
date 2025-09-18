"""
Unit tests for data model validation.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from ozb_deal_filter.models import (
    Deal, RawDeal, Configuration, UserCriteria, 
    LLMProviderConfig, MessagingPlatformConfig,
    EvaluationResult, FilterResult, UrgencyLevel,
    FormattedAlert, DeliveryResult
)


class TestRawDeal:
    """Test RawDeal validation."""
    
    def test_valid_raw_deal(self):
        """Test validation of valid raw deal."""
        raw_deal = RawDeal(
            title="Test Deal",
            description="A great test deal",
            link="https://example.com/deal",
            pub_date="Mon, 01 Jan 2024 12:00:00 GMT",
            category="Electronics"
        )
        assert raw_deal.validate() is True
    
    def test_empty_title_raises_error(self):
        """Test that empty title raises ValueError."""
        raw_deal = RawDeal(
            title="",
            description="A great test deal",
            link="https://example.com/deal",
            pub_date="Mon, 01 Jan 2024 12:00:00 GMT"
        )
        with pytest.raises(ValueError, match="Deal title cannot be empty"):
            raw_deal.validate()
    
    def test_empty_description_raises_error(self):
        """Test that empty description raises ValueError."""
        raw_deal = RawDeal(
            title="Test Deal",
            description="",
            link="https://example.com/deal",
            pub_date="Mon, 01 Jan 2024 12:00:00 GMT"
        )
        with pytest.raises(ValueError, match="Deal description cannot be empty"):
            raw_deal.validate()
    
    def test_invalid_url_raises_error(self):
        """Test that invalid URL raises ValueError."""
        raw_deal = RawDeal(
            title="Test Deal",
            description="A great test deal",
            link="not-a-url",
            pub_date="Mon, 01 Jan 2024 12:00:00 GMT"
        )
        with pytest.raises(ValueError, match="Invalid URL format"):
            raw_deal.validate()
    
    def test_title_too_long_raises_error(self):
        """Test that overly long title raises ValueError."""
        raw_deal = RawDeal(
            title="x" * 501,  # 501 characters
            description="A great test deal",
            link="https://example.com/deal",
            pub_date="Mon, 01 Jan 2024 12:00:00 GMT"
        )
        with pytest.raises(ValueError, match="Deal title too long"):
            raw_deal.validate()


class TestDeal:
    """Test Deal validation."""
    
    def test_valid_deal(self):
        """Test validation of valid deal."""
        deal = Deal(
            id="deal-123",
            title="Test Deal",
            description="A great test deal",
            price=99.99,
            original_price=199.99,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=["limited time"]
        )
        assert deal.validate() is True
    
    def test_negative_price_raises_error(self):
        """Test that negative price raises ValueError."""
        deal = Deal(
            id="deal-123",
            title="Test Deal",
            description="A great test deal",
            price=-10.0,
            original_price=199.99,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=[]
        )
        with pytest.raises(ValueError, match="Price cannot be negative"):
            deal.validate()
    
    def test_invalid_discount_percentage_raises_error(self):
        """Test that invalid discount percentage raises ValueError."""
        deal = Deal(
            id="deal-123",
            title="Test Deal",
            description="A great test deal",
            price=99.99,
            original_price=199.99,
            discount_percentage=150.0,  # Invalid: > 100
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=[]
        )
        with pytest.raises(ValueError, match="Discount percentage must be between 0 and 100"):
            deal.validate()
    
    def test_price_higher_than_original_raises_error(self):
        """Test that price higher than original price raises ValueError."""
        deal = Deal(
            id="deal-123",
            title="Test Deal",
            description="A great test deal",
            price=299.99,
            original_price=199.99,  # Original price lower than current price
            discount_percentage=None,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=[]
        )
        with pytest.raises(ValueError, match="Price cannot be higher than original price"):
            deal.validate()


class TestUserCriteria:
    """Test UserCriteria validation."""
    
    def test_valid_user_criteria(self):
        """Test validation of valid user criteria."""
        criteria = UserCriteria(
            prompt_template_path="prompts/deal_evaluator.txt",
            max_price=500.0,
            min_discount_percentage=20.0,
            categories=["Electronics", "Computing"],
            keywords=["laptop", "phone"],
            min_authenticity_score=0.6
        )
        assert criteria.validate() is True
    
    def test_invalid_authenticity_score_raises_error(self):
        """Test that invalid authenticity score raises ValueError."""
        criteria = UserCriteria(
            prompt_template_path="prompts/deal_evaluator.txt",
            max_price=500.0,
            min_discount_percentage=20.0,
            categories=["Electronics"],
            keywords=["laptop"],
            min_authenticity_score=1.5  # Invalid: > 1
        )
        with pytest.raises(ValueError, match="Minimum authenticity score must be between 0 and 1"):
            criteria.validate()
    
    def test_negative_max_price_raises_error(self):
        """Test that negative max price raises ValueError."""
        criteria = UserCriteria(
            prompt_template_path="prompts/deal_evaluator.txt",
            max_price=-100.0,  # Invalid: negative
            min_discount_percentage=20.0,
            categories=["Electronics"],
            keywords=["laptop"],
            min_authenticity_score=0.6
        )
        with pytest.raises(ValueError, match="Maximum price must be positive"):
            criteria.validate()


class TestLLMProviderConfig:
    """Test LLMProviderConfig validation."""
    
    def test_valid_local_config(self):
        """Test validation of valid local LLM config."""
        config = LLMProviderConfig(
            type="local",
            local={"model": "llama2", "docker_image": "ollama/ollama"}
        )
        assert config.validate() is True
    
    def test_valid_api_config(self):
        """Test validation of valid API LLM config."""
        config = LLMProviderConfig(
            type="api",
            api={"provider": "openai", "model": "gpt-3.5-turbo", "api_key": "test-key"}
        )
        assert config.validate() is True
    
    def test_invalid_type_raises_error(self):
        """Test that invalid type raises ValueError."""
        config = LLMProviderConfig(type="invalid")
        with pytest.raises(ValueError, match="LLM provider type must be 'local' or 'api'"):
            config.validate()
    
    def test_missing_local_config_raises_error(self):
        """Test that missing local config raises ValueError."""
        config = LLMProviderConfig(type="local")
        with pytest.raises(ValueError, match="Local LLM configuration required"):
            config.validate()


class TestMessagingPlatformConfig:
    """Test MessagingPlatformConfig validation."""
    
    def test_valid_telegram_config(self):
        """Test validation of valid Telegram config."""
        config = MessagingPlatformConfig(
            type="telegram",
            telegram={"bot_token": "test-token", "chat_id": "test-chat"}
        )
        assert config.validate() is True
    
    def test_valid_discord_config(self):
        """Test validation of valid Discord config."""
        config = MessagingPlatformConfig(
            type="discord",
            discord={"webhook_url": "https://discord.com/api/webhooks/123/abc"}
        )
        assert config.validate() is True
    
    def test_invalid_discord_webhook_raises_error(self):
        """Test that invalid Discord webhook URL raises ValueError."""
        config = MessagingPlatformConfig(
            type="discord",
            discord={"webhook_url": "https://invalid.com/webhook"}
        )
        with pytest.raises(ValueError, match="Invalid Discord webhook URL format"):
            config.validate()


class TestConfiguration:
    """Test Configuration validation."""
    
    def test_valid_configuration(self):
        """Test validation of valid configuration."""
        config = Configuration(
            rss_feeds=["https://example.com/feed.xml"],
            user_criteria=UserCriteria(
                prompt_template_path="prompts/deal_evaluator.txt",
                max_price=500.0,
                min_discount_percentage=20.0,
                categories=["Electronics"],
                keywords=["laptop"],
                min_authenticity_score=0.6
            ),
            llm_provider=LLMProviderConfig(
                type="local",
                local={"model": "llama2", "docker_image": "ollama/ollama"}
            ),
            messaging_platform=MessagingPlatformConfig(
                type="telegram",
                telegram={"bot_token": "test-token", "chat_id": "test-chat"}
            ),
            polling_interval=120,
            max_concurrent_feeds=5
        )
        assert config.validate() is True
    
    def test_empty_rss_feeds_raises_error(self):
        """Test that empty RSS feeds list raises ValueError."""
        config = Configuration(
            rss_feeds=[],  # Empty list
            user_criteria=UserCriteria(
                prompt_template_path="prompts/deal_evaluator.txt",
                max_price=500.0,
                min_discount_percentage=20.0,
                categories=["Electronics"],
                keywords=["laptop"],
                min_authenticity_score=0.6
            ),
            llm_provider=LLMProviderConfig(
                type="local",
                local={"model": "llama2", "docker_image": "ollama/ollama"}
            ),
            messaging_platform=MessagingPlatformConfig(
                type="telegram",
                telegram={"bot_token": "test-token", "chat_id": "test-chat"}
            ),
            polling_interval=120,
            max_concurrent_feeds=5
        )
        with pytest.raises(ValueError, match="At least one RSS feed must be configured"):
            config.validate()
    
    def test_short_polling_interval_raises_error(self):
        """Test that too short polling interval raises ValueError."""
        config = Configuration(
            rss_feeds=["https://example.com/feed.xml"],
            user_criteria=UserCriteria(
                prompt_template_path="prompts/deal_evaluator.txt",
                max_price=500.0,
                min_discount_percentage=20.0,
                categories=["Electronics"],
                keywords=["laptop"],
                min_authenticity_score=0.6
            ),
            llm_provider=LLMProviderConfig(
                type="local",
                local={"model": "llama2", "docker_image": "ollama/ollama"}
            ),
            messaging_platform=MessagingPlatformConfig(
                type="telegram",
                telegram={"bot_token": "test-token", "chat_id": "test-chat"}
            ),
            polling_interval=30,  # Too short
            max_concurrent_feeds=5
        )
        with pytest.raises(ValueError, match="Polling interval must be at least 60 seconds"):
            config.validate()


class TestEvaluationResult:
    """Test EvaluationResult validation."""
    
    def test_valid_evaluation_result(self):
        """Test validation of valid evaluation result."""
        result = EvaluationResult(
            is_relevant=True,
            confidence_score=0.8,
            reasoning="This deal matches the user's criteria for electronics."
        )
        assert result.validate() is True
    
    def test_invalid_confidence_score_raises_error(self):
        """Test that invalid confidence score raises ValueError."""
        result = EvaluationResult(
            is_relevant=True,
            confidence_score=1.5,  # Invalid: > 1
            reasoning="This deal matches the user's criteria."
        )
        with pytest.raises(ValueError, match="confidence_score must be between 0 and 1"):
            result.validate()


class TestFilterResult:
    """Test FilterResult validation."""
    
    def test_valid_filter_result(self):
        """Test validation of valid filter result."""
        result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=0.7,
            urgency_level=UrgencyLevel.MEDIUM
        )
        assert result.validate() is True
    
    def test_invalid_authenticity_score_raises_error(self):
        """Test that invalid authenticity score raises ValueError."""
        result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=2.0,  # Invalid: > 1
            urgency_level=UrgencyLevel.MEDIUM
        )
        with pytest.raises(ValueError, match="authenticity_score must be between 0 and 1"):
            result.validate()


class TestFormattedAlert:
    """Test FormattedAlert validation."""
    
    def test_valid_formatted_alert(self):
        """Test validation of valid formatted alert."""
        alert = FormattedAlert(
            title="Great Deal Alert!",
            message="Check out this amazing deal on electronics.",
            urgency=UrgencyLevel.HIGH,
            platform_specific_data={"parse_mode": "HTML"}
        )
        assert alert.validate() is True
    
    def test_empty_title_raises_error(self):
        """Test that empty title raises ValueError."""
        alert = FormattedAlert(
            title="",  # Empty title
            message="Check out this amazing deal on electronics.",
            urgency=UrgencyLevel.HIGH,
            platform_specific_data={}
        )
        with pytest.raises(ValueError, match="title cannot be empty"):
            alert.validate()


class TestDeliveryResult:
    """Test DeliveryResult validation."""
    
    def test_valid_successful_delivery(self):
        """Test validation of valid successful delivery."""
        result = DeliveryResult(
            success=True,
            delivery_time=datetime.now(),
            error_message=None
        )
        assert result.validate() is True
    
    def test_valid_failed_delivery(self):
        """Test validation of valid failed delivery."""
        result = DeliveryResult(
            success=False,
            delivery_time=datetime.now(),
            error_message="Network timeout"
        )
        assert result.validate() is True
    
    def test_failed_delivery_without_error_message_raises_error(self):
        """Test that failed delivery without error message raises ValueError."""
        result = DeliveryResult(
            success=False,
            delivery_time=datetime.now(),
            error_message=None  # Should have error message when success=False
        )
        with pytest.raises(ValueError, match="error_message should be provided when success is False"):
            result.validate()