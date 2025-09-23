"""
Dynamic feed management service.

This module provides functionality for managing RSS feeds that can be
added/removed at runtime via Telegram bot commands.
"""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from ..models.config import Configuration
from ..models.telegram import FeedConfig
from ..utils.logging import get_logger

logger = get_logger("dynamic_feed_manager")


class DynamicFeedManager:
    """Manages dynamic RSS feed configurations."""

    def __init__(self, config_path: str):
        """
        Initialize dynamic feed manager.

        Args:
            config_path: Path to the main configuration file
        """
        self.config_path = Path(config_path)
        self.dynamic_feeds_file = self.config_path.parent / "dynamic_feeds.yaml"
        self.backup_dir = self.config_path.parent / "backups"
        self._lock = asyncio.Lock()

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialize dynamic feeds file if it doesn't exist
        if not self.dynamic_feeds_file.exists():
            self._create_dynamic_feeds_file()

        logger.info(f"Dynamic feed manager initialized with config: {self.config_path}")

    def _create_dynamic_feeds_file(self):
        """Create initial dynamic feeds file."""
        try:
            initial_data = {"dynamic_feeds": []}
            with open(self.dynamic_feeds_file, "w", encoding="utf-8") as f:
                yaml.dump(initial_data, f, default_flow_style=False)
            logger.info(f"Created dynamic feeds file: {self.dynamic_feeds_file}")
        except Exception as e:
            logger.error(f"Error creating dynamic feeds file: {e}")

    async def add_feed_config(self, feed_config: FeedConfig) -> bool:
        """
        Add new feed configuration in a thread-safe manner.

        Args:
            feed_config: Feed configuration to add

        Returns:
            True if feed was added successfully
        """
        async with self._lock:
            try:
                # Validate feed config
                if not feed_config.validate():
                    logger.error("Invalid feed configuration provided")
                    return False

                # Load current dynamic feeds
                dynamic_feeds = self._load_dynamic_feeds()

                # Load main configuration for duplicate checking
                current_config = self._load_configuration()
                if not current_config:
                    logger.error("Failed to load current configuration")
                    return False

                # Check for duplicates in dynamic feeds
                if feed_config.url in dynamic_feeds:
                    logger.warning(
                        f"Feed URL already exists in dynamic feeds: {feed_config.url}"
                    )
                    return False

                # Also check static feeds for duplicates
                if feed_config.url in current_config.rss_feeds:
                    logger.warning(
                        f"Feed URL exists in static feeds: {feed_config.url}"
                    )
                    return False

                # Create backup before modification
                backup_path = self._backup_dynamic_feeds()
                logger.info(f"Dynamic feeds backed up to: {backup_path}")

                # Add feed to dynamic feeds
                dynamic_feeds.append(feed_config.url)

                # Save updated dynamic feeds
                if self._save_dynamic_feeds(dynamic_feeds):
                    logger.info(f"Successfully added dynamic feed: {feed_config.url}")
                    return True
                else:
                    # Restore backup on failure
                    self._restore_dynamic_feeds_backup(backup_path)
                    logger.error("Failed to save dynamic feeds, restored backup")
                    return False

            except Exception as e:
                logger.error(f"Error adding feed configuration: {e}")
                return False

    async def remove_feed_config(self, identifier: str) -> bool:
        """
        Remove feed configuration by URL or name.

        Args:
            identifier: Feed URL or name to remove

        Returns:
            True if feed was removed successfully
        """
        async with self._lock:
            try:
                # Load current dynamic feeds
                dynamic_feeds = self._load_dynamic_feeds()

                # Find feed to remove
                feeds_to_remove = []
                for feed_url in dynamic_feeds:
                    if feed_url == identifier:
                        feeds_to_remove.append(feed_url)

                if not feeds_to_remove:
                    logger.warning(f"Feed not found for removal: {identifier}")
                    return False

                # Create backup before modification
                backup_path = self._backup_dynamic_feeds()
                logger.info(f"Dynamic feeds backed up to: {backup_path}")

                # Remove feeds
                for feed_url in feeds_to_remove:
                    dynamic_feeds.remove(feed_url)

                # Save updated dynamic feeds
                if self._save_dynamic_feeds(dynamic_feeds):
                    logger.info(
                        f"Successfully removed dynamic feed(s): {feeds_to_remove}"
                    )
                    return True
                else:
                    # Restore backup on failure
                    self._restore_dynamic_feeds_backup(backup_path)
                    logger.error("Failed to save dynamic feeds, restored backup")
                    return False

            except Exception as e:
                logger.error(f"Error removing feed configuration: {e}")
                return False

    def list_feed_configs(self) -> List[FeedConfig]:
        """
        List all dynamic feed configurations.

        Returns:
            List of FeedConfig objects for dynamic feeds
        """
        try:
            # Load only dynamic feeds for user management
            dynamic_feeds = self._load_dynamic_feeds()

            # Create FeedConfig objects for dynamic feeds only
            feed_configs = []
            for feed_url in dynamic_feeds:
                feed_config = FeedConfig(
                    url=feed_url,
                    name=self._extract_feed_name(feed_url),
                    added_by="user",  # Dynamic feeds are user-added
                    added_at=datetime.now(),  # Approximate
                    enabled=True,
                )
                feed_configs.append(feed_config)

            return feed_configs

        except Exception as e:
            logger.error(f"Error listing feed configurations: {e}")
            return []

    def backup_configuration(self) -> str:
        """
        Create timestamped backup of current configuration.

        Returns:
            Path to backup file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"config_backup_{timestamp}.yaml"
            backup_path = self.backup_dir / backup_filename

            # Copy current config to backup
            shutil.copy2(self.config_path, backup_path)

            logger.info(f"Configuration backed up to: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Error creating configuration backup: {e}")
            raise

    async def reload_configuration(self) -> bool:
        """
        Reload configuration from file.

        Returns:
            True if configuration was reloaded successfully
        """
        try:
            config = self._load_configuration()
            if not config:
                return False

            # Validate the loaded configuration
            config.validate()
            logger.info("Configuration reloaded and validated successfully")
            return True

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False

    def _load_configuration(self) -> Optional[Configuration]:
        """
        Load configuration from file.

        Returns:
            Configuration object or None if failed
        """
        try:
            if not self.config_path.exists():
                logger.error(f"Configuration file not found: {self.config_path}")
                return None

            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # Convert to Configuration object
            # This is a simplified conversion - in practice you'd use the ConfigurationManager
            from ..services.config_manager import ConfigurationManager

            config_manager = ConfigurationManager()
            return config_manager._parse_config(config_data)

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return None

    def _save_configuration(self, config: Configuration) -> bool:
        """
        Save configuration to file.

        Args:
            config: Configuration object to save

        Returns:
            True if configuration was saved successfully
        """
        try:
            # Convert Configuration object to dict for YAML serialization
            config_dict = self._config_to_dict(config)

            # Write to file
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

            # Validate saved configuration
            saved_config = self._load_configuration()
            if saved_config and saved_config.validate():
                logger.info("Configuration saved and validated successfully")
                return True
            else:
                logger.error("Saved configuration failed validation")
                return False

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def _config_to_dict(self, config: Configuration) -> dict:
        """
        Convert Configuration object to dictionary for YAML serialization.

        Args:
            config: Configuration object

        Returns:
            Dictionary representation of configuration
        """
        config_dict = {
            "rss_feeds": config.rss_feeds,
            "polling_interval": config.polling_interval,
            "max_concurrent_feeds": config.max_concurrent_feeds,
            "max_deal_age_hours": config.max_deal_age_hours,
            "user_criteria": {
                "prompt_template_path": config.user_criteria.prompt_template_path,
                "max_price": config.user_criteria.max_price,
                "min_discount_percentage": config.user_criteria.min_discount_percentage,
                "categories": config.user_criteria.categories,
                "keywords": config.user_criteria.keywords,
                "min_authenticity_score": config.user_criteria.min_authenticity_score,
            },
            "llm_provider": {
                "type": config.llm_provider.type,
                "local": config.llm_provider.local,
                "api": config.llm_provider.api,
            },
            "messaging_platform": {
                "type": config.messaging_platform.type,
                "telegram": config.messaging_platform.telegram,
                "whatsapp": config.messaging_platform.whatsapp,
                "discord": config.messaging_platform.discord,
                "slack": config.messaging_platform.slack,
            },
        }

        # Add dynamic feeds if present
        if config.dynamic_feeds is not None:
            config_dict["dynamic_feeds"] = config.dynamic_feeds

        # Add telegram bot config if present
        if config.telegram_bot is not None:
            config_dict["telegram_bot"] = {
                "enabled": config.telegram_bot.enabled,
                "bot_token": config.telegram_bot.bot_token,
                "authorized_users": config.telegram_bot.authorized_users,
                "max_commands_per_minute": config.telegram_bot.max_commands_per_minute,
                "max_commands_per_user_per_minute": config.telegram_bot.max_commands_per_user_per_minute,
            }

        return config_dict

    def _restore_backup(self, backup_path: str) -> bool:
        """
        Restore configuration from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup was restored successfully
        """
        try:
            shutil.copy2(backup_path, self.config_path)
            logger.info(f"Configuration restored from backup: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False

    def _extract_feed_name(self, feed_url: str) -> Optional[str]:
        """
        Extract a readable name from feed URL.

        Args:
            feed_url: Feed URL

        Returns:
            Extracted name or None
        """
        try:
            from urllib.parse import urlparse

            parsed = urlparse(feed_url)
            domain = parsed.netloc

            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]

            return domain

        except Exception:
            return None

    def _load_dynamic_feeds(self) -> List[str]:
        """Load dynamic feeds from separate file."""
        try:
            if not self.dynamic_feeds_file.exists():
                return []

            with open(self.dynamic_feeds_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            return data.get("dynamic_feeds", [])
        except Exception as e:
            logger.error(f"Error loading dynamic feeds: {e}")
            return []

    def _save_dynamic_feeds(self, feeds: List[str]) -> bool:
        """Save dynamic feeds to separate file."""
        try:
            data = {"dynamic_feeds": feeds}
            with open(self.dynamic_feeds_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False)

            logger.info("Dynamic feeds saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving dynamic feeds: {e}")
            return False

    def _backup_dynamic_feeds(self) -> str:
        """Create backup of dynamic feeds file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"dynamic_feeds_backup_{timestamp}.yaml"
            backup_path = self.backup_dir / backup_filename

            if self.dynamic_feeds_file.exists():
                shutil.copy2(self.dynamic_feeds_file, backup_path)

            logger.info(f"Dynamic feeds backed up to: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"Error creating dynamic feeds backup: {e}")
            raise

    def _restore_dynamic_feeds_backup(self, backup_path: str) -> bool:
        """Restore dynamic feeds from backup."""
        try:
            shutil.copy2(backup_path, self.dynamic_feeds_file)
            logger.info(f"Dynamic feeds restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error restoring dynamic feeds backup: {e}")
            return False


# Utility function for migration
def migrate_static_to_dynamic_feeds(config_path: str, backup: bool = True) -> bool:
    """
    Migrate static RSS feeds to dynamic feeds structure.

    Args:
        config_path: Path to configuration file
        backup: Whether to create backup before migration

    Returns:
        True if migration was successful
    """
    try:
        manager = DynamicFeedManager(config_path)

        if backup:
            manager.backup_configuration()

        config = manager._load_configuration()
        if not config:
            return False

        # Move RSS feeds to dynamic feeds if not already done
        if config.dynamic_feeds is None and config.rss_feeds:
            config.dynamic_feeds = config.rss_feeds.copy()

            if manager._save_configuration(config):
                logger.info("Successfully migrated static feeds to dynamic feeds")
                return True

        return True

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return False
