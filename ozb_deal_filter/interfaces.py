"""
Protocol interfaces for the OzBargain Deal Filter system.

This module defines all the protocol interfaces that establish
system boundaries and enable dependency injection throughout
the application.
"""

# Forward declarations for type hints
from typing import TYPE_CHECKING, List, Optional, Protocol

from .models.alert import FormattedAlert
from .models.deal import Deal, RawDeal
from .models.delivery import DeliveryResult
from .models.evaluation import EvaluationResult
from .models.filter import FilterResult

if TYPE_CHECKING:
    from .models.config import Configuration, LLMProviderConfig
    from .models.telegram import (
        AuthResult,
        BotCommand,
        CommandResult,
        FeedConfig,
        TelegramMessage,
        ValidationResult,
    )


class IRSSMonitor(Protocol):
    """Protocol for RSS feed monitoring components."""

    def start_monitoring(self) -> None:
        """Start monitoring configured RSS feeds."""
        ...

    def stop_monitoring(self) -> None:
        """Stop monitoring RSS feeds."""
        ...

    def add_feed(self, feed_url: str) -> bool:
        """Add a new RSS feed to monitor."""
        ...

    def remove_feed(self, feed_url: str) -> bool:
        """Remove an RSS feed from monitoring."""
        ...


class IDealDetector(Protocol):
    """Protocol for detecting new deals from RSS feed data."""

    def detect_new_deals(self, feed_data: str) -> List[RawDeal]:
        """Detect new deals from RSS feed data."""
        ...


class IDealParser(Protocol):
    """Protocol for parsing raw deals into structured data."""

    def parse_deal(self, raw_deal: RawDeal) -> Deal:
        """Parse a raw deal into a structured Deal object."""
        ...

    def validate_deal(self, deal: Deal) -> bool:
        """Validate that a deal contains required information."""
        ...


class ILLMEvaluator(Protocol):
    """Protocol for LLM-based deal evaluation."""

    def evaluate_deal(self, deal: Deal, prompt_template: str) -> EvaluationResult:
        """Evaluate a deal against user criteria using LLM."""
        ...

    def set_llm_provider(self, provider_config: "LLMProviderConfig") -> None:
        """Set the LLM provider for evaluations."""
        ...


class IFilterEngine(Protocol):
    """Protocol for applying filters to deals."""

    def apply_filters(self, deal: Deal, evaluation: EvaluationResult) -> FilterResult:
        """Apply price, discount, and authenticity filters to a deal."""
        ...


class IAlertFormatter(Protocol):
    """Protocol for formatting deal alerts."""

    def format_alert(self, deal: Deal, filter_result: FilterResult) -> FormattedAlert:
        """Format a deal into an alert message."""
        ...


class IMessageDispatcher(Protocol):
    """Protocol for dispatching alert messages."""

    def send_alert(self, alert: FormattedAlert) -> DeliveryResult:
        """Send an alert through the configured messaging platform."""
        ...

    def test_connection(self) -> bool:
        """Test connection to the messaging platform."""
        ...


class IConfigurationManager(Protocol):
    """Protocol for managing system configuration."""

    def load_configuration(self, config_path: str) -> "Configuration":
        """Load configuration from file."""
        ...

    def validate_configuration(self, config: "Configuration") -> bool:
        """Validate configuration data."""
        ...

    def reload_configuration(self) -> None:
        """Reload configuration without restart."""
        ...


class IGitAgent(Protocol):
    """Protocol for automated git operations."""

    def commit_changes(self, message: str) -> bool:
        """Commit current changes with the specified message."""
        ...

    def generate_commit_message(self, task_description: str) -> str:
        """Generate a meaningful commit message for a task."""
        ...


class ITelegramBotHandler(Protocol):
    """Protocol for Telegram bot message handling."""

    async def start_polling(self) -> None:
        """Start polling for messages from Telegram."""
        ...

    async def stop_polling(self) -> None:
        """Stop polling for messages."""
        ...

    async def handle_message(self, message: "TelegramMessage") -> None:
        """Process incoming Telegram message."""
        ...

    async def send_response(self, chat_id: str, text: str) -> bool:
        """Send response message to chat."""
        ...

    async def test_connection(self) -> bool:
        """Test connection to Telegram Bot API."""
        ...


class IFeedCommandProcessor(Protocol):
    """Protocol for processing feed management commands."""

    async def process_command(self, command: "BotCommand") -> "CommandResult":
        """Process a bot command and return result."""
        ...

    async def add_feed(self, command: "BotCommand") -> "CommandResult":
        """Add new RSS feed."""
        ...

    async def remove_feed(self, command: "BotCommand") -> "CommandResult":
        """Remove RSS feed."""
        ...

    async def list_feeds(self, command: "BotCommand") -> "CommandResult":
        """List all feeds."""
        ...

    async def feed_status(self, command: "BotCommand") -> "CommandResult":
        """Get feed status information."""
        ...

    async def help_command(self, command: "BotCommand") -> "CommandResult":
        """Show help information."""
        ...


class IDynamicFeedManager(Protocol):
    """Protocol for managing dynamic feed configurations."""

    async def add_feed_config(self, feed_config: "FeedConfig") -> bool:
        """Add new feed configuration."""
        ...

    async def remove_feed_config(self, identifier: str) -> bool:
        """Remove feed configuration by URL or name."""
        ...

    def list_feed_configs(self) -> List["FeedConfig"]:
        """List all dynamic feed configurations."""
        ...

    def backup_configuration(self) -> str:
        """Create timestamped backup of configuration."""
        ...

    async def reload_configuration(self) -> bool:
        """Reload configuration from file."""
        ...


class IURLValidator(Protocol):
    """Protocol for URL validation services."""

    async def validate_url(self, url: str) -> "ValidationResult":
        """Validate URL and check if it's a valid RSS feed."""
        ...

    async def is_accessible(self, url: str) -> bool:
        """Check if URL is accessible."""
        ...

    async def is_rss_feed(self, url: str) -> bool:
        """Verify URL serves RSS content."""
        ...

    async def get_feed_title(self, url: str) -> Optional[str]:
        """Extract feed title for naming."""
        ...


class ITelegramAuthorizer(Protocol):
    """Protocol for Telegram bot authorization."""

    def is_authorized(self, user_id: str) -> "AuthResult":
        """Check if user is authorized to use the bot."""
        ...

    def add_authorized_user(self, user_id: str) -> bool:
        """Add user to authorized list."""
        ...

    def remove_authorized_user(self, user_id: str) -> bool:
        """Remove user from authorized list."""
        ...
