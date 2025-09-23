"""
Telegram bot handler for RSS feed management.

This module provides the core Telegram bot functionality for handling
user messages and managing RSS feed subscriptions.
"""

import asyncio
import re
from datetime import datetime
from typing import List, Optional

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..models.telegram import (
    AuthResult,
    BotCommand,
    TelegramChat,
    TelegramMessage,
    TelegramUser,
)
from ..services.telegram_authorizer import TelegramAuthorizer
from ..utils.logging import get_logger

logger = get_logger("telegram_bot_handler")


class TelegramBotHandler:
    """Handles Telegram bot operations including message polling and command processing."""

    def __init__(
        self, bot_token: str, authorized_users: List[str], command_processor=None
    ):
        """
        Initialize Telegram bot handler.

        Args:
            bot_token: Telegram bot token
            authorized_users: List of authorized user IDs
            command_processor: Command processor instance
        """
        self.bot_token = bot_token
        self.authorized_users = authorized_users
        self.command_processor = command_processor

        # Initialize bot and application
        self.bot = Bot(token=bot_token)
        self.application = Application.builder().token(bot_token).build()

        # Initialize authorization
        self.authorizer = TelegramAuthorizer(
            authorized_users=authorized_users,
            global_max_commands_per_minute=30,
            user_max_commands_per_minute=10,
        )

        # Polling state
        self.is_polling = False
        self._polling_task: Optional[asyncio.Task] = None

        # Setup handlers
        self._setup_handlers()

        logger.info("Telegram bot handler initialized")

    def _setup_handlers(self) -> None:
        """Setup message and command handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("add_feed", self._handle_add_feed))
        self.application.add_handler(
            CommandHandler("remove_feed", self._handle_remove_feed)
        )
        self.application.add_handler(
            CommandHandler("list_feeds", self._handle_list_feeds)
        )
        self.application.add_handler(
            CommandHandler("feed_status", self._handle_feed_status)
        )
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("start", self._handle_start))

        # Message handler for non-command messages
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        logger.info("Telegram bot handlers configured")

    async def start_polling(self) -> None:
        """Start polling for messages from Telegram."""
        if self.is_polling:
            logger.warning("Bot is already polling")
            return

        try:
            self.is_polling = True
            logger.info("Starting Telegram bot polling...")

            # Initialize and start the application
            await self.application.initialize()
            await self.application.start()

            # Start polling
            await self.application.updater.start_polling()

            logger.info("Telegram bot polling started successfully")

        except Exception as e:
            logger.error(f"Error starting bot polling: {e}")
            self.is_polling = False
            raise

    async def stop_polling(self) -> None:
        """Stop polling for messages."""
        if not self.is_polling:
            return

        try:
            self.is_polling = False
            logger.info("Stopping Telegram bot polling...")

            # Stop polling and application
            if self.application.updater:
                await self.application.updater.stop()

            await self.application.stop()
            await self.application.shutdown()

            logger.info("Telegram bot polling stopped")

        except Exception as e:
            logger.error(f"Error stopping bot polling: {e}")

    async def _handle_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command."""
        await self._handle_help(update, context)

    async def _handle_add_feed(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /add_feed command."""
        await self._process_command(update, "add_feed", context.args or [])

    async def _handle_remove_feed(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /remove_feed command."""
        await self._process_command(update, "remove_feed", context.args or [])

    async def _handle_list_feeds(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /list_feeds command."""
        await self._process_command(update, "list_feeds", context.args or [])

    async def _handle_feed_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /feed_status command."""
        await self._process_command(update, "feed_status", context.args or [])

    async def _handle_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command."""
        await self._process_command(update, "help", context.args or [])

    async def _handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle non-command messages."""
        if not update.message or not update.message.text:
            return

        user_id = str(update.effective_user.id)

        # Check authorization
        auth_result = await self.authorizer.is_authorized(user_id)
        if not auth_result.authorized:
            await self.send_response(
                str(update.effective_chat.id), f"❌ {auth_result.reason}"
            )
            return

        # Send help for unrecognized messages
        help_text = """
🤖 **OzBargain Deal Filter Bot**

Available commands:
• `/add_feed <url> [name]` - Add a new RSS feed
• `/remove_feed <url>` - Remove an RSS feed
• `/list_feeds` - Show all active feeds
• `/feed_status` - Get feed monitoring status
• `/help` - Show this help message

Example:
`/add_feed https://www.ozbargain.com.au/deals/feed My Deals`
        """

        await self.send_response(str(update.effective_chat.id), help_text)

    async def _process_command(
        self, update: Update, command: str, args: List[str]
    ) -> None:
        """Process a command through the command processor."""
        try:
            if not update.effective_user or not update.effective_chat:
                logger.warning("Received update without user or chat information")
                return

            user_id = str(update.effective_user.id)
            chat_id = str(update.effective_chat.id)

            # Check authorization
            auth_result = await self.authorizer.is_authorized(user_id)
            if not auth_result.authorized:
                await self.send_response(chat_id, f"❌ {auth_result.reason}")
                return

            # Create bot command
            bot_command = BotCommand(
                command=command,
                args=args,
                user_id=user_id,
                chat_id=chat_id,
                raw_text=update.message.text if update.message else "",
            )

            # Process command
            if self.command_processor:
                result = await self.command_processor.process_command(bot_command)
                await self.send_response(chat_id, result.message)
            else:
                await self.send_response(chat_id, "❌ Command processor not available")

        except Exception as e:
            logger.error(f"Error processing command {command}: {e}")
            chat_id = (
                str(update.effective_chat.id) if update.effective_chat else "unknown"
            )
            await self.send_response(
                chat_id, "❌ An error occurred processing your command"
            )

    async def handle_message(self, message: TelegramMessage) -> None:
        """Process incoming Telegram message (for interface compliance)."""
        # This method is for interface compliance
        # Actual message handling is done through the application handlers
        pass

    async def send_response(self, chat_id: str, text: str) -> bool:
        """
        Send response message to chat.

        Args:
            chat_id: Chat ID to send message to
            text: Message text

        Returns:
            True if message was sent successfully
        """
        try:
            # Format text for better readability
            formatted_text = self._format_message(text)

            await self.bot.send_message(
                chat_id=int(chat_id), text=formatted_text, parse_mode="Markdown"
            )

            logger.debug(f"Sent response to chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending response to chat {chat_id}: {e}")

            # Try sending without markdown if formatting fails
            try:
                await self.bot.send_message(chat_id=int(chat_id), text=text)
                return True
            except Exception as e2:
                logger.error(f"Error sending fallback response: {e2}")
                return False

    def _format_message(self, text: str) -> str:
        """
        Format message text for better readability.

        Args:
            text: Raw message text

        Returns:
            Formatted message text
        """
        # Escape markdown special characters if needed
        # but preserve our intentional formatting
        return text

    async def test_connection(self) -> bool:
        """
        Test connection to Telegram Bot API.

        Returns:
            True if connection test successful
        """
        try:
            # Get bot info to test connection
            bot_info = await self.bot.get_me()
            logger.info(f"Bot connection test successful. Bot: @{bot_info.username}")
            return True

        except Exception as e:
            logger.error(f"Bot connection test failed: {e}")
            return False

    def parse_command(self, text: str) -> Optional[BotCommand]:
        """
        Parse text into command structure.

        Args:
            text: Message text

        Returns:
            BotCommand object or None if not a valid command
        """
        if not text.startswith("/"):
            return None

        # Remove leading slash and split
        parts = text[1:].split()
        if not parts:
            return None

        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # Map command aliases
        command_map = {
            "start": "help",
            "h": "help",
            "add": "add_feed",
            "remove": "remove_feed",
            "rm": "remove_feed",
            "list": "list_feeds",
            "ls": "list_feeds",
            "status": "feed_status",
        }

        command = command_map.get(command, command)

        return BotCommand(
            command=command,
            args=args,
            user_id="",  # Will be filled by caller
            chat_id="",  # Will be filled by caller
            raw_text=text,
        )

    def get_bot_info(self) -> dict:
        """
        Get bot information and status.

        Returns:
            Dictionary with bot information
        """
        return {
            "is_polling": self.is_polling,
            "authorized_users_count": len(self.authorized_users),
            "bot_token_valid": bool(self.bot_token and len(self.bot_token) > 10),
        }


# Utility functions for message formatting
def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown formatting."""
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def format_feed_list(feeds: List[str]) -> str:
    """Format feed list for display."""
    if not feeds:
        return "📭 No feeds configured"

    formatted_feeds = []
    for i, feed in enumerate(feeds, 1):
        # Try to extract domain name for readability
        try:
            from urllib.parse import urlparse

            domain = urlparse(feed).netloc
            if domain.startswith("www."):
                domain = domain[4:]
            formatted_feeds.append(f"{i}. {domain}\n   `{feed}`")
        except Exception:
            formatted_feeds.append(f"{i}. `{feed}`")

    return "📋 **Active RSS Feeds:**\n\n" + "\n\n".join(formatted_feeds)


def format_status_info(status: dict) -> str:
    """Format status information for display."""
    if "error" in status:
        return f"❌ Error: {status['error']}"

    total_feeds = status.get("total_feeds", 0)
    active_feeds = status.get("active_feeds", 0)

    status_text = f"""
📊 **Feed Status**

Total Feeds: {total_feeds}
Active Feeds: {active_feeds}
Status: {"✅ All feeds active" if total_feeds == active_feeds else "⚠️ Some feeds inactive"}
    """

    return status_text.strip()
