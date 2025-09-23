"""
Integration tests for Telegram functionality.

This module contains tests to verify the Telegram bot integration works correctly.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ozb_deal_filter.components.feed_command_processor import FeedCommandProcessor
from ozb_deal_filter.components.telegram_bot_handler import TelegramBotHandler
from ozb_deal_filter.models.telegram import BotCommand, FeedConfig, ValidationResult
from ozb_deal_filter.services.dynamic_feed_manager import DynamicFeedManager
from ozb_deal_filter.services.telegram_authorizer import TelegramAuthorizer
from ozb_deal_filter.utils.url_validator import URLValidator


class TestTelegramIntegration:
    """Test Telegram integration functionality."""

    @pytest.fixture
    def mock_rss_monitor(self):
        """Mock RSS monitor for testing."""
        mock_monitor = MagicMock()
        mock_monitor.add_feed.return_value = True
        mock_monitor.remove_feed.return_value = True
        mock_monitor.add_feed_dynamic.return_value = True
        mock_monitor.remove_feed_dynamic.return_value = True
        mock_monitor.get_feed_status.return_value = {
            "total_feeds": 1,
            "active_feeds": 1,
            "monitor_running": True,
        }
        return mock_monitor

    @pytest.fixture
    def mock_feed_manager(self):
        """Mock dynamic feed manager for testing."""
        mock_manager = MagicMock()
        mock_manager.add_feed_config = AsyncMock(return_value=True)
        mock_manager.remove_feed_config = AsyncMock(return_value=True)
        mock_manager.list_feed_configs.return_value = [
            FeedConfig(
                url="https://example.com/feed.xml",
                name="Example Feed",
                added_by="user123",
                added_at=datetime.now(),
                enabled=True,
            )
        ]
        return mock_manager

    @pytest.fixture
    def command_processor(self, mock_rss_monitor, mock_feed_manager):
        """Create command processor with mocked dependencies."""
        return FeedCommandProcessor(
            rss_monitor=mock_rss_monitor, feed_manager=mock_feed_manager
        )

    @pytest.mark.asyncio
    async def test_add_feed_command(self, command_processor):
        """Test adding a feed via command processor."""
        # Mock URL validation
        with patch(
            "ozb_deal_filter.components.feed_command_processor.URLValidator"
        ) as mock_validator_class:
            mock_validator = AsyncMock()
            mock_validator.__aenter__ = AsyncMock(return_value=mock_validator)
            mock_validator.__aexit__ = AsyncMock(return_value=None)
            mock_validator.validate_url = AsyncMock(
                return_value=ValidationResult(is_valid=True, feed_title="Test Feed")
            )
            mock_validator_class.return_value = mock_validator

            # Create command
            command = BotCommand(
                command="add_feed",
                args=["https://example.com/feed.xml", "My", "Test", "Feed"],
                user_id="user123",
                chat_id="chat123",
                raw_text="/add_feed https://example.com/feed.xml My Test Feed",
            )

            # Process command
            result = await command_processor.add_feed(command)

            # Verify result
            assert result.success
            assert "Feed added successfully" in result.message
            assert "My Test Feed" in result.message

    @pytest.mark.asyncio
    async def test_list_feeds_command(self, command_processor):
        """Test listing feeds via command processor."""
        command = BotCommand(
            command="list_feeds",
            args=[],
            user_id="user123",
            chat_id="chat123",
            raw_text="/list_feeds",
        )

        result = await command_processor.list_feeds(command)

        assert result.success
        assert "Active RSS Feeds" in result.message
        assert "Example Feed" in result.message

    @pytest.mark.asyncio
    async def test_feed_status_command(self, command_processor):
        """Test getting feed status via command processor."""
        command = BotCommand(
            command="feed_status",
            args=[],
            user_id="user123",
            chat_id="chat123",
            raw_text="/feed_status",
        )

        result = await command_processor.feed_status(command)

        assert result.success
        assert "RSS Monitor Status" in result.message
        assert "Total Feeds: 1" in result.message

    @pytest.mark.asyncio
    async def test_help_command(self, command_processor):
        """Test help command."""
        command = BotCommand(
            command="help",
            args=[],
            user_id="user123",
            chat_id="chat123",
            raw_text="/help",
        )

        result = await command_processor.help_command(command)

        assert result.success
        assert "OzBargain Deal Filter Bot" in result.message
        assert "/add_feed" in result.message

    def test_telegram_authorizer(self):
        """Test Telegram authorization functionality."""
        authorizer = TelegramAuthorizer(
            authorized_users=["user123", "user456"],
            global_max_commands_per_minute=30,
            user_max_commands_per_minute=10,
        )

        # Test authorized user
        assert authorizer.is_user_authorized("user123")

        # Test unauthorized user
        assert not authorizer.is_user_authorized("user789")

        # Test adding user
        assert authorizer.add_authorized_user("user789")
        assert authorizer.is_user_authorized("user789")

        # Test removing user
        assert authorizer.remove_authorized_user("user789")
        assert not authorizer.is_user_authorized("user789")

    @pytest.mark.asyncio
    async def test_url_validator(self):
        """Test URL validation functionality."""
        validator = URLValidator()

        # Test format validation
        result = validator._validate_format("https://example.com/feed.xml")
        assert result.is_valid

        # Test invalid format
        result = validator._validate_format("not-a-url")
        assert not result.is_valid

        # Test security validation
        result = validator._validate_security("https://example.com/feed.xml")
        assert result.is_valid

        # Test localhost rejection
        result = validator._validate_security("http://localhost/feed.xml")
        assert not result.is_valid

    def test_feed_config_validation(self):
        """Test FeedConfig validation."""
        # Valid config
        config = FeedConfig(
            url="https://example.com/feed.xml",
            name="Test Feed",
            added_by="user123",
            added_at=datetime.now(),
            enabled=True,
        )
        assert config.validate()

        # Invalid URL
        config_invalid = FeedConfig(
            url="not-a-url",
            name="Test Feed",
            added_by="user123",
            added_at=datetime.now(),
            enabled=True,
        )
        assert not config_invalid.validate()

    def test_bot_command_validation(self):
        """Test BotCommand validation."""
        # Valid command
        command = BotCommand(
            command="add_feed",
            args=["https://example.com/feed.xml"],
            user_id="user123",
            chat_id="chat123",
            raw_text="/add_feed https://example.com/feed.xml",
        )
        assert command.validate()

        # Invalid command
        command_invalid = BotCommand(
            command="invalid_command",
            args=[],
            user_id="user123",
            chat_id="chat123",
            raw_text="/invalid_command",
        )
        assert not command_invalid.validate()


@pytest.mark.asyncio
async def test_telegram_bot_integration():
    """Integration test for Telegram bot functionality."""
    # This test would require actual Telegram API access
    # For now, we'll just test the component initialization

    # Mock the bot initialization
    with patch("ozb_deal_filter.components.telegram_bot_handler.Bot") as mock_bot:
        with patch(
            "ozb_deal_filter.components.telegram_bot_handler.Application"
        ) as mock_app:
            mock_bot.return_value = MagicMock()
            mock_app.builder.return_value.token.return_value.build.return_value = (
                MagicMock()
            )

            bot_handler = TelegramBotHandler(
                bot_token="test:token", authorized_users=["user123"]
            )

            # Test bot info
            info = bot_handler.get_bot_info()
            assert not info["is_polling"]  # Should not be polling yet
            assert info["authorized_users_count"] == 1


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
