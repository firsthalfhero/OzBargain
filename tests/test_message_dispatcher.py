"""
Unit tests for the message dispatcher system.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from requests.exceptions import HTTPError, RequestException

from ozb_deal_filter.components.message_dispatcher import (
    BaseMessageDispatcher,
    DiscordDispatcher,
    MessageDispatcherFactory,
    SlackDispatcher,
    TelegramDispatcher,
    WhatsAppDispatcher,
)
from ozb_deal_filter.models.alert import FormattedAlert
from ozb_deal_filter.models.delivery import DeliveryResult
from ozb_deal_filter.models.filter import UrgencyLevel


class MockMessageDispatcher(BaseMessageDispatcher):
    """Test implementation of BaseMessageDispatcher."""

    def __init__(
        self,
        should_succeed: bool = True,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        super().__init__(max_retries, retry_delay)
        self.should_succeed = should_succeed
        self.send_attempts = 0

    def _send_message(self, alert: FormattedAlert) -> bool:
        self.send_attempts += 1
        if self.should_succeed:
            return True
        else:
            raise Exception("Test send failure")

    def test_connection(self) -> bool:
        return self.should_succeed


class TestBaseMessageDispatcher:
    """Test cases for BaseMessageDispatcher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_alert = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.MEDIUM,
            platform_specific_data={
                "telegram": {"text": "Telegram formatted message"},
                "discord": {"content": "Discord formatted message"},
            },
        )

    def test_send_alert_success_first_attempt(self):
        """Test successful message sending on first attempt."""
        dispatcher = MockMessageDispatcher(should_succeed=True, retry_delay=0.01)

        result = dispatcher.send_alert(self.test_alert)

        assert isinstance(result, DeliveryResult)
        assert result.success is True
        assert result.error_message is None
        assert isinstance(result.delivery_time, datetime)
        assert dispatcher.send_attempts == 1

    def test_send_alert_success_after_retries(self):
        """Test successful message sending after initial failures."""
        dispatcher = MockMessageDispatcher(
            should_succeed=False, max_retries=2, retry_delay=0.01
        )

        # Create a counter to track attempts and succeed on the third attempt
        attempt_counter = [0]

        def mock_send(alert):
            attempt_counter[0] += 1
            dispatcher.send_attempts = attempt_counter[0]
            if attempt_counter[0] < 3:
                raise Exception("Test send failure")
            else:
                return True

        dispatcher._send_message = mock_send

        result = dispatcher.send_alert(self.test_alert)

        assert result.success is True
        assert result.error_message is None
        assert dispatcher.send_attempts == 3

    def test_send_alert_failure_all_attempts(self):
        """Test message sending failure after all retry attempts."""
        dispatcher = MockMessageDispatcher(
            should_succeed=False, max_retries=2, retry_delay=0.01
        )

        result = dispatcher.send_alert(self.test_alert)

        assert result.success is False
        assert result.error_message is not None
        assert "Failed after 3 attempts" in result.error_message
        assert "Test send failure" in result.error_message
        assert dispatcher.send_attempts == 3

    def test_create_session(self):
        """Test session creation with retry configuration."""
        dispatcher = MockMessageDispatcher()
        session = dispatcher._create_session()

        assert isinstance(session, requests.Session)
        # Check that adapters are mounted
        assert "http://" in session.adapters
        assert "https://" in session.adapters


class TestTelegramDispatcher:
    """Test cases for TelegramDispatcher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.bot_token = "test_bot_token"
        self.chat_id = "test_chat_id"
        self.dispatcher = TelegramDispatcher(
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            max_retries=1,
            retry_delay=0.01,
        )

        self.test_alert = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.HIGH,
            platform_specific_data={
                "telegram": {
                    "text": "Telegram <b>formatted</b> message",
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": "View Deal", "url": "https://example.com"}]
                        ]
                    },
                }
            },
        )

    @patch("requests.Session.post")
    def test_send_message_success(self, mock_post):
        """Test successful Telegram message sending."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = self.dispatcher._send_message(self.test_alert)

        assert success is True
        mock_post.assert_called_once()

        # Check API call parameters
        call_args = mock_post.call_args
        assert f"bot{self.bot_token}/sendMessage" in call_args[0][0]

        payload = call_args[1]["json"]
        assert payload["chat_id"] == self.chat_id
        assert payload["text"] == "Telegram <b>formatted</b> message"
        assert payload["parse_mode"] == "HTML"
        assert "reply_markup" in payload

    @patch("requests.Session.post")
    def test_send_message_api_error(self, mock_post):
        """Test Telegram API error handling."""
        # Mock API error response
        mock_response = Mock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            self.dispatcher._send_message(self.test_alert)

        assert "Telegram API error: Bad Request" in str(exc_info.value)

    @patch("requests.Session.post")
    def test_send_message_http_error(self, mock_post):
        """Test HTTP error handling."""
        mock_post.side_effect = HTTPError("HTTP 500 Error")

        with pytest.raises(HTTPError):
            self.dispatcher._send_message(self.test_alert)

    @patch("requests.Session.post")
    def test_send_message_no_telegram_data(self, mock_post):
        """Test sending message without Telegram-specific data."""
        alert_without_telegram = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.LOW,
            platform_specific_data={},
        )

        with pytest.raises(ValueError) as exc_info:
            self.dispatcher._send_message(alert_without_telegram)

        assert "No Telegram-specific data found" in str(exc_info.value)

    @patch("requests.Session.get")
    def test_test_connection_success(self, mock_get):
        """Test successful connection test."""
        # Mock successful getMe response
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"username": "test_bot", "id": 123},
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.dispatcher.test_connection()

        assert result is True
        mock_get.assert_called_once()
        assert f"bot{self.bot_token}/getMe" in mock_get.call_args[0][0]

    @patch("requests.Session.get")
    def test_test_connection_failure(self, mock_get):
        """Test connection test failure."""
        mock_get.side_effect = RequestException("Connection failed")

        result = self.dispatcher.test_connection()

        assert result is False


class TestDiscordDispatcher:
    """Test cases for DiscordDispatcher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.webhook_url = "https://discord.com/api/webhooks/test"
        self.dispatcher = DiscordDispatcher(
            webhook_url=self.webhook_url, max_retries=1, retry_delay=0.01
        )

        self.test_alert = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.HIGH,
            platform_specific_data={
                "discord": {
                    "embeds": [
                        {
                            "title": "Test Deal",
                            "description": "Test description",
                            "color": 0xFF8C00,
                        }
                    ]
                }
            },
        )

    @patch("requests.Session.post")
    def test_send_message_success(self, mock_post):
        """Test successful Discord message sending."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = self.dispatcher._send_message(self.test_alert)

        assert success is True
        mock_post.assert_called_once_with(
            self.webhook_url,
            json=self.test_alert.platform_specific_data["discord"],
            timeout=30,
        )

    @patch("requests.Session.post")
    def test_send_message_fallback(self, mock_post):
        """Test Discord message sending with fallback to basic message."""
        alert_without_discord = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.LOW,
            platform_specific_data={},
        )

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = self.dispatcher._send_message(alert_without_discord)

        assert success is True

        # Check that fallback payload was used
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["content"] == "Test message content"

    @patch("requests.Session.post")
    def test_test_connection_success(self, mock_post):
        """Test successful Discord connection test."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = self.dispatcher.test_connection()

        assert result is True
        mock_post.assert_called_once()

        # Check test message payload
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert "connection test" in payload["content"].lower()


class TestSlackDispatcher:
    """Test cases for SlackDispatcher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.webhook_url = "https://hooks.slack.com/services/test"
        self.dispatcher = SlackDispatcher(
            webhook_url=self.webhook_url, max_retries=1, retry_delay=0.01
        )

        self.test_alert = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.MEDIUM,
            platform_specific_data={
                "slack": {
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "Test Deal"},
                        }
                    ]
                }
            },
        )

    @patch("requests.Session.post")
    def test_send_message_success(self, mock_post):
        """Test successful Slack message sending."""
        mock_response = Mock()
        mock_response.text = "ok"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = self.dispatcher._send_message(self.test_alert)

        assert success is True
        mock_post.assert_called_once_with(
            self.webhook_url,
            json=self.test_alert.platform_specific_data["slack"],
            timeout=30,
        )

    @patch("requests.Session.post")
    def test_send_message_slack_error(self, mock_post):
        """Test Slack webhook error handling."""
        mock_response = Mock()
        mock_response.text = "invalid_payload"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            self.dispatcher._send_message(self.test_alert)

        assert "Slack webhook error: invalid_payload" in str(exc_info.value)

    @patch("requests.Session.post")
    def test_test_connection_success(self, mock_post):
        """Test successful Slack connection test."""
        mock_response = Mock()
        mock_response.text = "ok"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = self.dispatcher.test_connection()

        assert result is True


class TestWhatsAppDispatcher:
    """Test cases for WhatsAppDispatcher."""

    def setup_method(self):
        """Set up test fixtures."""
        self.phone_number_id = "123456789"
        self.access_token = "test_access_token"
        self.recipient_number = "1234567890"
        self.dispatcher = WhatsAppDispatcher(
            phone_number_id=self.phone_number_id,
            access_token=self.access_token,
            recipient_number=self.recipient_number,
            max_retries=1,
            retry_delay=0.01,
        )

        self.test_alert = FormattedAlert(
            title="Test Alert",
            message="Test message content",
            urgency=UrgencyLevel.URGENT,
            platform_specific_data={
                "whatsapp": {"text": "WhatsApp *formatted* message"}
            },
        )

    @patch("requests.Session.post")
    def test_send_message_success(self, mock_post):
        """Test successful WhatsApp message sending."""
        mock_response = Mock()
        mock_response.json.return_value = {"messages": [{"id": "message_id_123"}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        success = self.dispatcher._send_message(self.test_alert)

        assert success is True
        mock_post.assert_called_once()

        # Check API call parameters
        call_args = mock_post.call_args
        assert f"{self.phone_number_id}/messages" in call_args[0][0]

        payload = call_args[1]["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == self.recipient_number
        assert payload["text"]["body"] == "WhatsApp *formatted* message"

    @patch("requests.Session.post")
    def test_send_message_api_error(self, mock_post):
        """Test WhatsApp API error handling."""
        mock_response = Mock()
        mock_response.json.return_value = {"error": {"message": "Invalid token"}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            self.dispatcher._send_message(self.test_alert)

        assert "WhatsApp API error" in str(exc_info.value)

    @patch("requests.Session.post")
    def test_test_connection_success(self, mock_post):
        """Test successful WhatsApp connection test."""
        mock_response = Mock()
        mock_response.json.return_value = {"messages": [{"id": "test_message_id"}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = self.dispatcher.test_connection()

        assert result is True


class TestMessageDispatcherFactory:
    """Test cases for MessageDispatcherFactory."""

    def test_create_telegram_dispatcher(self):
        """Test creating Telegram dispatcher."""
        config = {
            "bot_token": "test_token",
            "chat_id": "test_chat",
            "max_retries": 5,
            "retry_delay": 2.0,
        }

        dispatcher = MessageDispatcherFactory.create_dispatcher("telegram", config)

        assert isinstance(dispatcher, TelegramDispatcher)
        assert dispatcher.bot_token == "test_token"
        assert dispatcher.chat_id == "test_chat"
        assert dispatcher.max_retries == 5
        assert dispatcher.retry_delay == 2.0

    def test_create_discord_dispatcher(self):
        """Test creating Discord dispatcher."""
        config = {"webhook_url": "https://discord.com/api/webhooks/test"}

        dispatcher = MessageDispatcherFactory.create_dispatcher("discord", config)

        assert isinstance(dispatcher, DiscordDispatcher)
        assert dispatcher.webhook_url == config["webhook_url"]

    def test_create_slack_dispatcher(self):
        """Test creating Slack dispatcher."""
        config = {"webhook_url": "https://hooks.slack.com/services/test"}

        dispatcher = MessageDispatcherFactory.create_dispatcher("slack", config)

        assert isinstance(dispatcher, SlackDispatcher)
        assert dispatcher.webhook_url == config["webhook_url"]

    def test_create_whatsapp_dispatcher(self):
        """Test creating WhatsApp dispatcher."""
        config = {
            "phone_number_id": "123456789",
            "access_token": "test_token",
            "recipient_number": "1234567890",
        }

        dispatcher = MessageDispatcherFactory.create_dispatcher("whatsapp", config)

        assert isinstance(dispatcher, WhatsAppDispatcher)
        assert dispatcher.phone_number_id == "123456789"
        assert dispatcher.access_token == "test_token"
        assert dispatcher.recipient_number == "1234567890"

    def test_create_dispatcher_case_insensitive(self):
        """Test that platform names are case insensitive."""
        config = {"webhook_url": "https://discord.com/api/webhooks/test"}

        dispatcher1 = MessageDispatcherFactory.create_dispatcher("DISCORD", config)
        dispatcher2 = MessageDispatcherFactory.create_dispatcher("Discord", config)
        dispatcher3 = MessageDispatcherFactory.create_dispatcher("discord", config)

        assert all(
            isinstance(d, DiscordDispatcher)
            for d in [dispatcher1, dispatcher2, dispatcher3]
        )

    def test_create_dispatcher_missing_config(self):
        """Test error handling for missing configuration."""
        # Missing bot_token for Telegram
        with pytest.raises(ValueError) as exc_info:
            MessageDispatcherFactory.create_dispatcher("telegram", {"chat_id": "test"})
        assert "Missing required Telegram config: bot_token" in str(exc_info.value)

        # Missing webhook_url for Discord
        with pytest.raises(ValueError) as exc_info:
            MessageDispatcherFactory.create_dispatcher("discord", {})
        assert "Missing required Discord config: webhook_url" in str(exc_info.value)

    def test_create_dispatcher_unsupported_platform(self):
        """Test error handling for unsupported platform."""
        with pytest.raises(ValueError) as exc_info:
            MessageDispatcherFactory.create_dispatcher("unsupported", {})
        assert "Unsupported messaging platform: unsupported" in str(exc_info.value)
