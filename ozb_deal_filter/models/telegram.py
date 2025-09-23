"""
Telegram-specific data models for the OzBargain Deal Filter system.

This module defines data structures for Telegram bot operations,
including messages, commands, and feed configurations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class TelegramUser:
    """Represents a Telegram user."""

    id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    def validate(self) -> bool:
        """Validate user data."""
        return bool(self.id and self.id.strip())


@dataclass
class TelegramChat:
    """Represents a Telegram chat."""

    id: str
    type: str  # "private", "group", "supergroup", "channel"
    title: Optional[str] = None

    def validate(self) -> bool:
        """Validate chat data."""
        return bool(self.id and self.id.strip() and self.type)


@dataclass
class TelegramMessage:
    """Represents a Telegram message."""

    message_id: int
    from_user: TelegramUser
    chat: TelegramChat
    text: Optional[str]
    date: datetime

    def validate(self) -> bool:
        """Validate message structure."""
        return (
            self.message_id > 0
            and self.from_user is not None
            and self.from_user.validate()
            and self.chat is not None
            and self.chat.validate()
            and self.date is not None
        )


@dataclass
class BotCommand:
    """Represents a parsed bot command."""

    command: str
    args: List[str]
    user_id: str
    chat_id: str
    raw_text: str

    def validate(self) -> bool:
        """Validate command structure."""
        valid_commands = [
            "add_feed",
            "remove_feed",
            "list_feeds",
            "feed_status",
            "help",
        ]
        return (
            self.command in valid_commands
            and isinstance(self.args, list)
            and bool(self.user_id and self.user_id.strip())
            and bool(self.chat_id and self.chat_id.strip())
            and bool(self.raw_text and self.raw_text.strip())
        )


@dataclass
class FeedConfig:
    """Configuration for a dynamically managed RSS feed."""

    url: str
    name: Optional[str]
    added_by: str
    added_at: datetime
    enabled: bool = True

    def validate(self) -> bool:
        """Validate feed configuration."""
        # Validate URL format
        try:
            parsed_url = urlparse(self.url)
            url_valid = (
                self.url.startswith(("http://", "https://"))
                and len(self.url) <= 2048
                and parsed_url.scheme in ["http", "https"]
                and parsed_url.netloc
            )
        except Exception:
            url_valid = False

        return (
            url_valid
            and bool(self.added_by and self.added_by.strip())
            and self.added_at is not None
            and isinstance(self.enabled, bool)
        )


@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool
    message: str
    data: Optional[dict] = None

    def validate(self) -> bool:
        """Validate command result."""
        return (
            isinstance(self.success, bool)
            and isinstance(self.message, str)
            and bool(self.message.strip())
        )


@dataclass
class AuthResult:
    """Result of an authorization check."""

    authorized: bool
    reason: str
    user_id: Optional[str] = None

    def validate(self) -> bool:
        """Validate authorization result."""
        return (
            isinstance(self.authorized, bool)
            and isinstance(self.reason, str)
            and bool(self.reason.strip())
        )


@dataclass
class ValidationResult:
    """Result of URL validation."""

    is_valid: bool
    error: Optional[str] = None
    feed_title: Optional[str] = None

    def validate(self) -> bool:
        """Validate validation result."""
        return isinstance(self.is_valid, bool)
