"""
Message dispatching components for the OzBargain Deal Filter system.

This module provides functionality to dispatch alert messages through
various messaging platforms with retry logic and error handling.
"""

import time
from abc import abstractmethod
from datetime import datetime
from typing import Dict, Any
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..interfaces import IMessageDispatcher
from ..models.alert import FormattedAlert
from ..models.delivery import DeliveryResult


logger = logging.getLogger(__name__)


class BaseMessageDispatcher(IMessageDispatcher):
    """Base class for message dispatchers with common retry logic."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize base dispatcher.

        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def send_alert(self, alert: FormattedAlert) -> DeliveryResult:
        """
        Send alert with retry logic.

        Args:
            alert: Formatted alert to send

        Returns:
            DeliveryResult: Result of delivery attempt
        """
        start_time = datetime.now()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    f"Attempting to send alert (attempt {attempt + 1}/{self.max_retries + 1})"
                )

                # Call platform-specific implementation
                success = self._send_message(alert)

                if success:
                    delivery_time = datetime.now()
                    logger.info(
                        f"Alert sent successfully in {(delivery_time - start_time).total_seconds():.2f}s"
                    )

                    result = DeliveryResult(
                        success=True, delivery_time=delivery_time, error_message=None
                    )
                    result.validate()
                    return result

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Send attempt {attempt + 1} failed: {last_error}")

                # Don't sleep after the last attempt
                if attempt < self.max_retries:
                    sleep_time = self.retry_delay * (
                        2**attempt
                    )  # Exponential backoff
                    logger.info(f"Retrying in {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)

        # All attempts failed
        delivery_time = datetime.now()
        error_msg = (
            f"Failed after {self.max_retries + 1} attempts. Last error: {last_error}"
        )
        logger.error(error_msg)

        result = DeliveryResult(
            success=False, delivery_time=delivery_time, error_message=error_msg
        )
        result.validate()
        return result

    @abstractmethod
    def _send_message(self, alert: FormattedAlert) -> bool:
        """
        Platform-specific message sending implementation.

        Args:
            alert: Formatted alert to send

        Returns:
            bool: True if message was sent successfully

        Raises:
            Exception: If sending fails
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to the messaging platform."""
        pass


class TelegramDispatcher(BaseMessageDispatcher):
    """Telegram Bot API message dispatcher."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Telegram dispatcher.

        Args:
            bot_token: Telegram bot token
            chat_id: Target chat ID for messages
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        super().__init__(max_retries, retry_delay)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def _send_message(self, alert: FormattedAlert) -> bool:
        """Send message via Telegram Bot API."""
        # Get Telegram-specific formatting
        telegram_data = alert.platform_specific_data.get("telegram", {})

        if not telegram_data:
            raise ValueError("No Telegram-specific data found in alert")

        # Prepare API request
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": telegram_data.get("text", alert.message),
            "parse_mode": telegram_data.get("parse_mode", "HTML"),
            "disable_web_page_preview": telegram_data.get(
                "disable_web_page_preview", False
            ),
        }

        # Add inline keyboard if present
        if "reply_markup" in telegram_data:
            payload["reply_markup"] = telegram_data["reply_markup"]

        # Send request
        response = self.session.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        if not result.get("ok"):
            raise Exception(
                f"Telegram API error: {result.get('description', 'Unknown error')}"
            )

        logger.info(f"Message sent to Telegram chat {self.chat_id}")
        return True

    def test_connection(self) -> bool:
        """Test connection to Telegram Bot API."""
        try:
            url = f"{self.base_url}/getMe"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(
                    f"Connected to Telegram bot: {bot_info.get('username', 'Unknown')}"
                )
                return True
            else:
                logger.error(
                    f"Telegram API error: {result.get('description', 'Unknown error')}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            return False


class DiscordDispatcher(BaseMessageDispatcher):
    """Discord webhook message dispatcher."""

    def __init__(
        self, webhook_url: str, max_retries: int = 3, retry_delay: float = 1.0
    ):
        """
        Initialize Discord dispatcher.

        Args:
            webhook_url: Discord webhook URL
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        super().__init__(max_retries, retry_delay)
        self.webhook_url = webhook_url

    def _send_message(self, alert: FormattedAlert) -> bool:
        """Send message via Discord webhook."""
        # Get Discord-specific formatting
        discord_data = alert.platform_specific_data.get("discord", {})

        if not discord_data:
            # Fallback to basic message
            payload = {"content": alert.message}
        else:
            payload = discord_data

        # Send request
        response = self.session.post(self.webhook_url, json=payload, timeout=30)
        response.raise_for_status()

        logger.info("Message sent to Discord webhook")
        return True

    def test_connection(self) -> bool:
        """Test connection to Discord webhook."""
        try:
            # Send a test message
            test_payload = {"content": "🔧 OzBargain Deal Filter connection test"}

            response = self.session.post(
                self.webhook_url, json=test_payload, timeout=10
            )
            response.raise_for_status()

            logger.info("Discord webhook connection test successful")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Discord webhook: {e}")
            return False


class SlackDispatcher(BaseMessageDispatcher):
    """Slack webhook message dispatcher."""

    def __init__(
        self, webhook_url: str, max_retries: int = 3, retry_delay: float = 1.0
    ):
        """
        Initialize Slack dispatcher.

        Args:
            webhook_url: Slack webhook URL
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        super().__init__(max_retries, retry_delay)
        self.webhook_url = webhook_url

    def _send_message(self, alert: FormattedAlert) -> bool:
        """Send message via Slack webhook."""
        # Get Slack-specific formatting
        slack_data = alert.platform_specific_data.get("slack", {})

        if not slack_data:
            # Fallback to basic message
            payload = {"text": alert.message}
        else:
            payload = slack_data

        # Send request
        response = self.session.post(self.webhook_url, json=payload, timeout=30)
        response.raise_for_status()

        # Slack returns "ok" for successful webhook calls
        if response.text.strip() != "ok":
            raise Exception(f"Slack webhook error: {response.text}")

        logger.info("Message sent to Slack webhook")
        return True

    def test_connection(self) -> bool:
        """Test connection to Slack webhook."""
        try:
            # Send a test message
            test_payload = {"text": "🔧 OzBargain Deal Filter connection test"}

            response = self.session.post(
                self.webhook_url, json=test_payload, timeout=10
            )
            response.raise_for_status()

            if response.text.strip() == "ok":
                logger.info("Slack webhook connection test successful")
                return True
            else:
                logger.error(f"Slack webhook test failed: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Slack webhook: {e}")
            return False


class WhatsAppDispatcher(BaseMessageDispatcher):
    """WhatsApp Business API message dispatcher."""

    def __init__(
        self,
        phone_number_id: str,
        access_token: str,
        recipient_number: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize WhatsApp dispatcher.

        Args:
            phone_number_id: WhatsApp Business phone number ID
            access_token: WhatsApp Business API access token
            recipient_number: Recipient phone number
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        super().__init__(max_retries, retry_delay)
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.recipient_number = recipient_number
        self.base_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"

        # Add authorization header
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )

    def _send_message(self, alert: FormattedAlert) -> bool:
        """Send message via WhatsApp Business API."""
        # Get WhatsApp-specific formatting
        whatsapp_data = alert.platform_specific_data.get("whatsapp", {})

        message_text = whatsapp_data.get("text", alert.message)

        # Prepare API request
        payload = {
            "messaging_product": "whatsapp",
            "to": self.recipient_number,
            "type": "text",
            "text": {"body": message_text},
        }

        # Send request
        response = self.session.post(self.base_url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        if "messages" not in result:
            raise Exception(f"WhatsApp API error: {result}")

        logger.info(f"Message sent to WhatsApp number {self.recipient_number}")
        return True

    def test_connection(self) -> bool:
        """Test connection to WhatsApp Business API."""
        try:
            # Test by sending a simple test message
            test_payload = {
                "messaging_product": "whatsapp",
                "to": self.recipient_number,
                "type": "text",
                "text": {"body": "🔧 OzBargain Deal Filter connection test"},
            }

            response = self.session.post(self.base_url, json=test_payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if "messages" in result:
                logger.info("WhatsApp Business API connection test successful")
                return True
            else:
                logger.error(f"WhatsApp API test failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to WhatsApp Business API: {e}")
            return False


class MessageDispatcherFactory:
    """Factory for creating message dispatchers."""

    @staticmethod
    def create_dispatcher(platform: str, config: Dict[str, Any]) -> IMessageDispatcher:
        """
        Create a message dispatcher for the specified platform.

        Args:
            platform: Platform name (telegram, discord, slack, whatsapp)
            config: Platform-specific configuration

        Returns:
            IMessageDispatcher: Configured message dispatcher

        Raises:
            ValueError: If platform is not supported or config is invalid
        """
        platform = platform.lower()

        if platform == "telegram":
            required_keys = ["bot_token", "chat_id"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required Telegram config: {key}")

            return TelegramDispatcher(
                bot_token=config["bot_token"],
                chat_id=config["chat_id"],
                max_retries=config.get("max_retries", 3),
                retry_delay=config.get("retry_delay", 1.0),
            )

        elif platform == "discord":
            if "webhook_url" not in config:
                raise ValueError("Missing required Discord config: webhook_url")

            return DiscordDispatcher(
                webhook_url=config["webhook_url"],
                max_retries=config.get("max_retries", 3),
                retry_delay=config.get("retry_delay", 1.0),
            )

        elif platform == "slack":
            if "webhook_url" not in config:
                raise ValueError("Missing required Slack config: webhook_url")

            return SlackDispatcher(
                webhook_url=config["webhook_url"],
                max_retries=config.get("max_retries", 3),
                retry_delay=config.get("retry_delay", 1.0),
            )

        elif platform == "whatsapp":
            required_keys = ["phone_number_id", "access_token", "recipient_number"]
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required WhatsApp config: {key}")

            return WhatsAppDispatcher(
                phone_number_id=config["phone_number_id"],
                access_token=config["access_token"],
                recipient_number=config["recipient_number"],
                max_retries=config.get("max_retries", 3),
                retry_delay=config.get("retry_delay", 1.0),
            )

        else:
            raise ValueError(f"Unsupported messaging platform: {platform}")
