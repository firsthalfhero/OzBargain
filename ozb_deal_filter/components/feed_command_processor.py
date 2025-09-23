"""
Feed command processor for Telegram bot commands.

This module processes feed management commands received via Telegram bot,
including adding, removing, listing feeds, and getting status information.
"""

from datetime import datetime
from typing import Optional

from ..interfaces import IDynamicFeedManager, IRSSMonitor
from ..models.telegram import BotCommand, CommandResult, FeedConfig
from ..utils.logging import get_logger
from ..utils.url_validator import URLValidator

logger = get_logger("feed_command_processor")


class FeedCommandProcessor:
    """Processes feed management commands from Telegram bot."""

    def __init__(self, rss_monitor: IRSSMonitor, feed_manager: IDynamicFeedManager):
        """
        Initialize feed command processor.

        Args:
            rss_monitor: RSS monitor instance
            feed_manager: Dynamic feed manager instance
        """
        self.rss_monitor = rss_monitor
        self.feed_manager = feed_manager
        self.url_validator = URLValidator()

        logger.info("Feed command processor initialized")

    async def process_command(self, command: BotCommand) -> CommandResult:
        """
        Route command to appropriate handler.

        Args:
            command: Bot command to process

        Returns:
            CommandResult with execution status and message
        """
        try:
            if not command.validate():
                return CommandResult(success=False, message="❌ Invalid command format")

            # Route to specific command handlers
            handlers = {
                "add_feed": self.add_feed,
                "remove_feed": self.remove_feed,
                "list_feeds": self.list_feeds,
                "feed_status": self.feed_status,
                "help": self.help_command,
            }

            handler = handlers.get(command.command)
            if not handler:
                return CommandResult(
                    success=False, message=f"❌ Unknown command: `{command.command}`"
                )

            # Execute command
            result = await handler(command)

            # Log command execution
            logger.info(
                f"Command executed: {command.command} by user {command.user_id}, "
                f"success: {result.success}"
            )

            return result

        except Exception as e:
            logger.error(f"Error processing command {command.command}: {e}")
            return CommandResult(
                success=False, message="❌ Internal error processing command"
            )

    async def add_feed(self, command: BotCommand) -> CommandResult:
        """
        Add new RSS feed.

        Args:
            command: Bot command with feed URL and optional name

        Returns:
            CommandResult with operation status
        """
        try:
            # Check arguments
            if len(command.args) < 1:
                return CommandResult(
                    success=False,
                    message="❌ **Usage:** `/add_feed <url> [name]`\n\n"
                    "**Example:** `/add_feed https://www.ozbargain.com.au/deals/feed My Deals`",
                )

            url = command.args[0].strip()
            name = " ".join(command.args[1:]).strip() if len(command.args) > 1 else None

            # Validate URL
            async with self.url_validator as validator:
                validation_result = await validator.validate_url(url)

            if not validation_result.is_valid:
                return CommandResult(
                    success=False,
                    message=f"❌ **Invalid URL:** {validation_result.error}\n\n"
                    "Please ensure the URL is a valid RSS feed.",
                )

            # Use extracted title if no name provided
            if not name:
                name = validation_result.feed_title or self._extract_domain_name(url)

            # Check for duplicates
            existing_feeds = self.feed_manager.list_feed_configs()
            for existing_feed in existing_feeds:
                if existing_feed.url == url:
                    return CommandResult(
                        success=False,
                        message=f"❌ **Feed already exists:** {existing_feed.name or url}",
                    )

            # Create feed config
            feed_config = FeedConfig(
                url=url,
                name=name,
                added_by=command.user_id,
                added_at=datetime.now(),
                enabled=True,
            )

            # Add to configuration
            if await self.feed_manager.add_feed_config(feed_config):
                # Add to RSS monitor with metadata
                if hasattr(self.rss_monitor, "add_feed_dynamic"):
                    monitor_success = self.rss_monitor.add_feed_dynamic(feed_config)
                else:
                    monitor_success = self.rss_monitor.add_feed(url)

                if monitor_success:
                    return CommandResult(
                        success=True,
                        message=f"✅ **Feed added successfully!**\n\n"
                        f"**Name:** {name}\n"
                        f"**URL:** `{url}`\n\n"
                        f"The feed is now being monitored for new deals.",
                    )
                else:
                    # Rollback configuration change
                    await self.feed_manager.remove_feed_config(url)
                    return CommandResult(
                        success=False,
                        message="❌ **Failed to start monitoring feed.** "
                        "The feed configuration was not saved.",
                    )
            else:
                return CommandResult(
                    success=False,
                    message="❌ **Failed to save feed configuration.** "
                    "Please try again or contact an administrator.",
                )

        except Exception as e:
            logger.error(f"Error adding feed: {e}")
            return CommandResult(
                success=False,
                message="❌ **Error adding feed.** Please try again later.",
            )

    async def remove_feed(self, command: BotCommand) -> CommandResult:
        """
        Remove RSS feed.

        Args:
            command: Bot command with feed URL or identifier

        Returns:
            CommandResult with operation status
        """
        try:
            # Check arguments
            if len(command.args) < 1:
                return CommandResult(
                    success=False,
                    message="❌ **Usage:** `/remove_feed <url>`\n\n"
                    "**Example:** `/remove_feed https://www.ozbargain.com.au/deals/feed`",
                )

            identifier = command.args[0].strip()

            # Find feed to remove
            existing_feeds = self.feed_manager.list_feed_configs()
            feed_to_remove = None

            for feed in existing_feeds:
                if feed.url == identifier or feed.name == identifier:
                    feed_to_remove = feed
                    break

            if not feed_to_remove:
                return CommandResult(
                    success=False,
                    message=f"❌ **Feed not found:** `{identifier}`\n\n"
                    "Use `/list_feeds` to see all active feeds.",
                )

            # Remove from RSS monitor first
            if hasattr(self.rss_monitor, "remove_feed_dynamic"):
                monitor_removed = self.rss_monitor.remove_feed_dynamic(identifier)
            else:
                monitor_removed = self.rss_monitor.remove_feed(feed_to_remove.url)

            # Remove from configuration
            config_removed = await self.feed_manager.remove_feed_config(identifier)

            if config_removed:
                status_msg = "✅ **Feed removed successfully!**\n\n"
                status_msg += f"**Name:** {feed_to_remove.name}\n"
                status_msg += f"**URL:** `{feed_to_remove.url}`\n\n"

                if not monitor_removed:
                    status_msg += "⚠️ *Note: Feed was removed from configuration but may still be monitored until next restart.*"

                return CommandResult(success=True, message=status_msg)
            else:
                return CommandResult(
                    success=False,
                    message="❌ **Failed to remove feed configuration.** "
                    "Please try again or contact an administrator.",
                )

        except Exception as e:
            logger.error(f"Error removing feed: {e}")
            return CommandResult(
                success=False,
                message="❌ **Error removing feed.** Please try again later.",
            )

    async def list_feeds(self, command: BotCommand) -> CommandResult:
        """
        List all active feeds.

        Args:
            command: Bot command

        Returns:
            CommandResult with feed list
        """
        try:
            feeds = self.feed_manager.list_feed_configs()

            if not feeds:
                return CommandResult(
                    success=True,
                    message="📭 **No feeds configured**\n\n"
                    "Use `/add_feed <url>` to add your first RSS feed.",
                )

            # Format feed list
            message = "📋 **Active RSS Feeds:**\n\n"

            for i, feed in enumerate(feeds, 1):
                feed_name = feed.name or self._extract_domain_name(feed.url)
                status_emoji = "✅" if feed.enabled else "❌"

                message += f"{i}. {status_emoji} **{feed_name}**\n"
                message += f"   `{feed.url}`\n"

                if feed.added_by != "unknown":
                    message += f"   *Added by user {feed.added_by}*\n"

                message += "\n"

            message += f"**Total:** {len(feeds)} feed(s)"

            return CommandResult(success=True, message=message)

        except Exception as e:
            logger.error(f"Error listing feeds: {e}")
            return CommandResult(
                success=False,
                message="❌ **Error retrieving feed list.** Please try again later.",
            )

    async def feed_status(self, command: BotCommand) -> CommandResult:
        """
        Get feed status information.

        Args:
            command: Bot command

        Returns:
            CommandResult with status information
        """
        try:
            # Get feed list
            feeds = self.feed_manager.list_feed_configs()
            total_feeds = len(feeds)

            # Get RSS monitor status if available
            try:
                if hasattr(self.rss_monitor, "get_feed_status"):
                    # Use enhanced status method if available
                    monitor_status = self.rss_monitor.get_feed_status()
                    monitor_active = monitor_status.get("monitor_running", False)
                    active_feeds = monitor_status.get("active_feeds", 0)
                else:
                    monitor_active = (
                        hasattr(self.rss_monitor, "is_monitoring")
                        and self.rss_monitor.is_monitoring
                    )
                    active_feeds = len([f for f in feeds if f.enabled]) if feeds else 0
            except Exception:
                monitor_active = False
                active_feeds = 0

            # Format status message
            status_emoji = "✅" if monitor_active and total_feeds > 0 else "⚠️"

            message = f"{status_emoji} **RSS Monitor Status**\n\n"
            message += f"**Total Feeds:** {total_feeds}\n"
            message += f"**Active Feeds:** {active_feeds}\n"
            message += (
                f"**Monitor Status:** {'Running' if monitor_active else 'Stopped'}\n\n"
            )

            if total_feeds == 0:
                message += "📭 No feeds configured. Use `/add_feed` to add feeds.\n"
            elif not monitor_active:
                message += (
                    "⚠️ RSS monitor is not running. Feeds are not being monitored.\n"
                )
            elif active_feeds == total_feeds:
                message += "✅ All feeds are active and being monitored.\n"
            else:
                message += f"⚠️ {total_feeds - active_feeds} feed(s) are inactive.\n"

            # Add specific feed info if requested
            if command.args and command.args[0].strip():
                identifier = command.args[0].strip()
                specific_feed = None

                for feed in feeds:
                    if feed.url == identifier or feed.name == identifier:
                        specific_feed = feed
                        break

                if specific_feed:
                    message += "\n**Feed Details:**\n"
                    message += f"**Name:** {specific_feed.name}\n"
                    message += f"**URL:** `{specific_feed.url}`\n"
                    message += f"**Status:** {'Active' if specific_feed.enabled else 'Inactive'}\n"
                    message += f"**Added:** {specific_feed.added_at.strftime('%Y-%m-%d %H:%M')}\n"
                else:
                    message += f"\n❌ Feed not found: `{identifier}`"

            return CommandResult(success=True, message=message)

        except Exception as e:
            logger.error(f"Error getting feed status: {e}")
            return CommandResult(
                success=False,
                message="❌ **Error retrieving feed status.** Please try again later.",
            )

    async def help_command(self, command: BotCommand) -> CommandResult:
        """
        Show help information.

        Args:
            command: Bot command

        Returns:
            CommandResult with help message
        """
        help_text = """
🤖 **OzBargain Deal Filter Bot**

**Available Commands:**

📥 `/add_feed <url> [name]`
   Add a new RSS feed to monitor
   *Example:* `/add_feed https://www.ozbargain.com.au/deals/feed OzBargain`

🗑️ `/remove_feed <url>`
   Remove an RSS feed from monitoring
   *Example:* `/remove_feed https://www.ozbargain.com.au/deals/feed`

📋 `/list_feeds`
   Show all active RSS feeds

📊 `/feed_status [url]`
   Get monitoring status for all feeds or a specific feed

❓ `/help`
   Show this help message

**Notes:**
• Only authorized users can manage feeds
• RSS feeds must be publicly accessible
• Feed changes are applied immediately
• Use valid RSS/XML feed URLs
        """

        return CommandResult(success=True, message=help_text.strip())

    def _extract_domain_name(self, url: str) -> str:
        """
        Extract a readable domain name from URL.

        Args:
            url: URL to extract domain from

        Returns:
            Domain name or fallback
        """
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc

            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain or url

        except Exception:
            return url
