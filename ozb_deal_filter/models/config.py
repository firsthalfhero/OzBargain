"""
Configuration models for the system.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


@dataclass
class LLMProviderConfig:
    """Configuration for LLM provider."""

    type: str  # "local" or "api"
    local: Optional[Dict[str, Any]] = None
    api: Optional[Dict[str, Any]] = None

    def validate(self) -> bool:
        """Validate LLM provider configuration."""
        if not self.type:
            raise ValueError("LLM provider type cannot be empty")

        if self.type not in ["local", "api"]:
            raise ValueError("LLM provider type must be 'local' or 'api'")

        if self.type == "local":
            if not self.local:
                raise ValueError(
                    "Local LLM configuration required when type is 'local'"
                )

            if "model" not in self.local:
                raise ValueError("Local LLM configuration must include 'model'")

            if "docker_image" not in self.local:
                raise ValueError("Local LLM configuration must include 'docker_image'")

        if self.type == "api":
            if not self.api:
                raise ValueError("API LLM configuration required when type is 'api'")

            if "provider" not in self.api:
                raise ValueError("API LLM configuration must include 'provider'")

            if "model" not in self.api:
                raise ValueError("API LLM configuration must include 'model'")

            valid_providers = ["openai", "anthropic", "google"]
            if self.api["provider"] not in valid_providers:
                raise ValueError(f"API provider must be one of: {valid_providers}")

            # Validate API key is present and not a placeholder
            api_key = self.api.get("api_key", "")
            if not api_key or api_key.startswith("__MISSING_ENV_VAR_"):
                missing_var = (
                    api_key.replace("__MISSING_ENV_VAR_", "").replace("__", "")
                    if api_key.startswith("__MISSING_ENV_VAR_")
                    else "API_KEY"
                )
                raise ValueError(
                    f"API key is required when using API-based LLM provider. Please set the {missing_var} environment variable."
                )

        return True


@dataclass
class MessagingPlatformConfig:
    """Configuration for messaging platform."""

    type: str  # "telegram", "whatsapp", "discord", "slack"
    telegram: Optional[Dict[str, str]] = None
    whatsapp: Optional[Dict[str, str]] = None
    discord: Optional[Dict[str, str]] = None
    slack: Optional[Dict[str, str]] = None

    def validate(self) -> bool:
        """Validate messaging platform configuration."""
        if not self.type:
            raise ValueError("Messaging platform type cannot be empty")

        valid_types = ["telegram", "whatsapp", "discord", "slack"]
        if self.type not in valid_types:
            raise ValueError(f"Messaging platform type must be one of: {valid_types}")

        # Validate platform-specific configuration
        if self.type == "telegram":
            if not self.telegram:
                raise ValueError(
                    "Telegram configuration required when type is 'telegram'"
                )

            required_keys = ["bot_token", "chat_id"]
            for key in required_keys:
                if key not in self.telegram or not self.telegram[key]:
                    raise ValueError(f"Telegram configuration must include '{key}'")

        elif self.type == "whatsapp":
            if not self.whatsapp:
                raise ValueError(
                    "WhatsApp configuration required when type is 'whatsapp'"
                )

            # WhatsApp Business API requirements would be validated here
            if "phone_number_id" not in self.whatsapp:
                raise ValueError(
                    "WhatsApp configuration must include 'phone_number_id'"
                )

        elif self.type == "discord":
            if not self.discord:
                raise ValueError(
                    "Discord configuration required when type is 'discord'"
                )

            if "webhook_url" not in self.discord or not self.discord["webhook_url"]:
                raise ValueError("Discord configuration must include 'webhook_url'")

            # Validate webhook URL format
            webhook_url = self.discord["webhook_url"]
            if not webhook_url.startswith("https://discord.com/api/webhooks/"):
                raise ValueError("Invalid Discord webhook URL format")

        elif self.type == "slack":
            if not self.slack:
                raise ValueError("Slack configuration required when type is 'slack'")

            if "webhook_url" not in self.slack or not self.slack["webhook_url"]:
                raise ValueError("Slack configuration must include 'webhook_url'")

            # Validate webhook URL format
            webhook_url = self.slack["webhook_url"]
            if not webhook_url.startswith("https://hooks.slack.com/"):
                raise ValueError("Invalid Slack webhook URL format")

        return True


@dataclass
class UserCriteria:
    """User filtering criteria."""

    prompt_template_path: str
    max_price: Optional[float]
    min_discount_percentage: Optional[float]
    categories: List[str]
    keywords: List[str]
    min_authenticity_score: float

    def validate(self) -> bool:
        """Validate user criteria configuration."""
        if not self.prompt_template_path or not self.prompt_template_path.strip():
            raise ValueError("Prompt template path cannot be empty")

        # Validate price constraints
        if self.max_price is not None and self.max_price <= 0:
            raise ValueError("Maximum price must be positive")

        if self.min_discount_percentage is not None:
            if not (0 <= self.min_discount_percentage <= 100):
                raise ValueError(
                    "Minimum discount percentage must be between 0 and 100"
                )

        # Validate authenticity score
        if not (0 <= self.min_authenticity_score <= 1):
            raise ValueError("Minimum authenticity score must be between 0 and 1")

        # Validate categories list
        if not isinstance(self.categories, list):
            raise ValueError("Categories must be a list")

        for category in self.categories:
            if not isinstance(category, str) or not category.strip():
                raise ValueError("All categories must be non-empty strings")

        # Validate keywords list
        if not isinstance(self.keywords, list):
            raise ValueError("Keywords must be a list")

        for keyword in self.keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError("All keywords must be non-empty strings")

        return True


@dataclass
class Configuration:
    """System configuration."""

    rss_feeds: List[str]
    user_criteria: UserCriteria
    llm_provider: LLMProviderConfig
    messaging_platform: MessagingPlatformConfig
    polling_interval: int
    max_concurrent_feeds: int
    max_deal_age_hours: int = 24  # Only process deals newer than this many hours

    def validate(self) -> bool:
        """Validate system configuration."""
        # Validate RSS feeds
        if not isinstance(self.rss_feeds, list):
            raise ValueError("RSS feeds must be a list")

        if not self.rss_feeds:
            raise ValueError("At least one RSS feed must be configured")

        for feed_url in self.rss_feeds:
            if not isinstance(feed_url, str) or not feed_url.strip():
                raise ValueError("All RSS feed URLs must be non-empty strings")

            # Validate URL format
            parsed_url = urlparse(feed_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError(f"Invalid RSS feed URL format: {feed_url}")

            if parsed_url.scheme not in ["http", "https"]:
                raise ValueError(f"RSS feed URL must use HTTP or HTTPS: {feed_url}")

        # Validate polling interval
        if not isinstance(self.polling_interval, int) or self.polling_interval <= 0:
            raise ValueError("Polling interval must be a positive integer")

        if self.polling_interval < 60:
            raise ValueError("Polling interval must be at least 60 seconds")

        # Validate max concurrent feeds
        if (
            not isinstance(self.max_concurrent_feeds, int)
            or self.max_concurrent_feeds <= 0
        ):
            raise ValueError("Max concurrent feeds must be a positive integer")

        if self.max_concurrent_feeds > 50:
            raise ValueError("Max concurrent feeds cannot exceed 50")

        # Validate max deal age hours
        if not isinstance(self.max_deal_age_hours, int) or self.max_deal_age_hours <= 0:
            raise ValueError("Max deal age hours must be a positive integer")

        if self.max_deal_age_hours > 168:  # 1 week
            raise ValueError("Max deal age hours cannot exceed 168 (1 week)")

        # Validate nested configurations
        self.user_criteria.validate()
        self.llm_provider.validate()
        self.messaging_platform.validate()

        return True
