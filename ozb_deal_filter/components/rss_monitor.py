"""
RSS monitoring components for the OzBargain Deal Filter system.

This module provides RSS feed monitoring functionality with error handling
for network timeouts and invalid feeds.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Set, Union

import feedparser
import requests
from dateutil import parser as date_parser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models.deal import RawDeal

logger = logging.getLogger(__name__)


class FeedPoller:
    """Individual RSS feed polling and management."""

    def __init__(
        self,
        feed_url: str,
        polling_interval: int,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize feed poller.

        Args:
            feed_url: RSS feed URL to monitor
            polling_interval: Seconds between polls
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.feed_url = feed_url
        self.polling_interval = polling_interval
        self.timeout = timeout
        self.max_retries = max_retries

        # Track last successful poll and feed state
        self.last_poll_time: Optional[datetime] = None
        self.last_feed_hash: Optional[str] = None
        self.consecutive_failures = 0
        self.is_active = False

        # Setup HTTP session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set user agent to be respectful
        self.session.headers.update(
            {"User-Agent": "OzBargain-Deal-Filter/1.0 (RSS Monitor)"}
        )

    def fetch_feed(self) -> Optional[str]:
        """
        Fetch RSS feed content with error handling.

        Returns:
            Feed content as string, or None if failed
        """
        try:
            logger.debug(f"Fetching RSS feed: {self.feed_url}")

            response = self.session.get(self.feed_url, timeout=self.timeout)
            response.raise_for_status()

            # Reset failure counter on success
            self.consecutive_failures = 0
            self.last_poll_time = datetime.now()

            return response.text

        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            logger.warning(
                f"Timeout fetching feed {self.feed_url} "
                f"(failure #{self.consecutive_failures})"
            )
            return None

        except requests.exceptions.ConnectionError:
            self.consecutive_failures += 1
            logger.warning(
                f"Connection error for feed {self.feed_url} "
                f"(failure #{self.consecutive_failures})"
            )
            return None

        except requests.exceptions.HTTPError as e:
            self.consecutive_failures += 1
            logger.error(
                f"HTTP error {e.response.status_code} for feed "
                f"{self.feed_url} (failure #{self.consecutive_failures})"
            )
            return None

        except Exception as e:
            self.consecutive_failures += 1
            logger.error(
                f"Unexpected error fetching feed {self.feed_url}: {e} "
                f"(failure #{self.consecutive_failures})"
            )
            return None

    def has_feed_changed(self, feed_content: str) -> bool:
        """
        Check if feed content has changed since last poll.

        Args:
            feed_content: Current feed content

        Returns:
            True if feed has changed or is first poll
        """
        current_hash = hashlib.md5(feed_content.encode()).hexdigest()

        if self.last_feed_hash is None:
            self.last_feed_hash = current_hash
            return True

        if current_hash != self.last_feed_hash:
            self.last_feed_hash = current_hash
            return True

        return False

    def should_poll(self) -> bool:
        """
        Check if it's time to poll the feed.

        Returns:
            True if feed should be polled now
        """
        if self.last_poll_time is None:
            return True

        time_since_poll = datetime.now() - self.last_poll_time
        return time_since_poll.total_seconds() >= self.polling_interval

    def is_healthy(self) -> bool:
        """
        Check if feed poller is healthy (not too many consecutive failures).

        Returns:
            True if poller is healthy
        """
        return self.consecutive_failures < self.max_retries * 2


class DealDetector:
    """Detects new deals from RSS feed data."""

    def __init__(
        self, state_file: str = "logs/seen_deals.json", max_age_hours: int = 24
    ):
        """Initialize deal detector with persistent state.

        Args:
            state_file: Path to file for storing seen deal IDs
            max_age_hours: Maximum age in hours for deals to be considered new
        """
        self.state_file = Path(state_file)
        self.max_age_hours = max_age_hours
        self.seen_deal_ids: Set[str] = set()
        self.last_cleanup = datetime.now()

        # Load existing state
        self._load_state()

        logger.info(
            f"DealDetector initialized with {len(self.seen_deal_ids)} known deals"
        )

    def detect_new_deals(self, feed_data: str) -> List[RawDeal]:
        """
        Detect new deals from RSS feed data.

        Args:
            feed_data: RSS feed content as string

        Returns:
            List of new RawDeal objects
        """
        try:
            # Parse RSS feed
            parsed_feed = feedparser.parse(feed_data)

            if parsed_feed.bozo:
                logger.warning(
                    f"RSS feed parsing warning: " f"{parsed_feed.bozo_exception}"
                )

            new_deals = []
            cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)

            for entry in parsed_feed.entries:
                try:
                    # Create unique ID for deal (using link as identifier)
                    deal_id = entry.get("link", "")

                    if not deal_id:
                        continue

                    # Check if we've already seen this deal
                    if deal_id in self.seen_deal_ids:
                        continue

                    # Parse publication date to check if deal is recent enough
                    pub_date_str = entry.get("published", "")
                    if pub_date_str:
                        try:
                            pub_date = date_parser.parse(pub_date_str)
                            # Make timezone-naive for comparison
                            if pub_date.tzinfo is not None:
                                pub_date = pub_date.replace(tzinfo=None)

                            # Skip deals older than max_age_hours
                            if pub_date < cutoff_time:
                                logger.debug(
                                    f"Skipping old deal: {entry.get('title', 'Unknown')} ({pub_date})"
                                )
                                continue
                        except Exception as e:
                            logger.warning(
                                f"Could not parse date '{pub_date_str}': {e}"
                            )
                            # If we can't parse the date, let it through (better safe than sorry)

                    # Extract deal information
                    raw_deal = RawDeal(
                        title=entry.get("title", "").strip(),
                        description=entry.get("description", "").strip(),
                        link=deal_id,
                        pub_date=pub_date_str,
                        category=self._extract_category(entry),
                    )

                    # Validate raw deal
                    if raw_deal.validate():
                        new_deals.append(raw_deal)
                        self.seen_deal_ids.add(deal_id)
                        logger.debug(f"New deal detected: {raw_deal.title}")

                except Exception as e:
                    logger.error(f"Error processing RSS entry: {e}")
                    continue

            # Save state after processing
            self._save_state()

            # Periodic cleanup of old entries
            if datetime.now() - self.last_cleanup > timedelta(hours=1):
                self._cleanup_old_entries()

            logger.info(f"Detected {len(new_deals)} new deals from RSS feed")
            return new_deals

        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
            return []

    def _extract_category(self, entry: dict) -> Optional[str]:
        """
        Extract category from RSS entry.

        Args:
            entry: RSS entry dictionary

        Returns:
            Category string or None
        """
        # Try different possible category fields
        category_fields = ["category", "tags", "categories"]

        for field in category_fields:
            if field in entry:
                category_data = entry[field]

                # Handle different category formats
                if isinstance(category_data, list) and category_data:
                    # Take first category if multiple
                    if hasattr(category_data[0], "term"):
                        return category_data[0].term
                    elif isinstance(category_data[0], str):
                        return category_data[0]
                elif isinstance(category_data, str):
                    return category_data

        return None

    def _load_state(self) -> None:
        """Load seen deal IDs from persistent storage."""
        try:
            if self.state_file.exists():
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.seen_deal_ids = set(data.get("seen_deals", []))
                    logger.debug(
                        f"Loaded {len(self.seen_deal_ids)} seen deals from {self.state_file}"
                    )
        except Exception as e:
            logger.warning(f"Could not load state from {self.state_file}: {e}")
            self.seen_deal_ids = set()

    def _save_state(self) -> None:
        """Save seen deal IDs to persistent storage."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "seen_deals": list(self.seen_deal_ids),
                "last_updated": datetime.now().isoformat(),
            }

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(
                f"Saved {len(self.seen_deal_ids)} seen deals to {self.state_file}"
            )
        except Exception as e:
            logger.error(f"Could not save state to {self.state_file}: {e}")

    def _cleanup_old_entries(self) -> None:
        """Clean up old entries from seen deals to prevent memory bloat."""
        # For now, we'll keep all entries since we don't have timestamps for when they were added
        # In a production system, you'd want to store timestamps and clean up old entries
        self.last_cleanup = datetime.now()
        logger.debug(
            "Cleanup completed (no action taken - keeping all entries for safety)"
        )


class RSSMonitor:
    """Main RSS monitoring orchestrator."""

    def __init__(
        self,
        polling_interval: int,
        max_concurrent_feeds: int,
        max_deal_age_hours: int = 24,
        deal_callback: Optional[
            Union[
                Callable[[List[RawDeal]], None],
                Callable[[List[RawDeal]], Awaitable[None]],
            ]
        ] = None,
    ):
        """
        Initialize RSS monitor.

        Args:
            polling_interval: Default polling interval in seconds
            max_concurrent_feeds: Maximum number of feeds to monitor
            max_deal_age_hours: Maximum age in hours for deals to be considered new
            deal_callback: Callback function for new deals
        """
        self.polling_interval = polling_interval
        self.max_concurrent_feeds = max_concurrent_feeds
        self.max_deal_age_hours = max_deal_age_hours
        self.deal_callback = deal_callback

        self.feed_pollers: Dict[str, FeedPoller] = {}
        self.deal_detector = DealDetector(max_age_hours=max_deal_age_hours)
        self.is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

    def add_feed(self, feed_url: str) -> bool:
        """
        Add a new RSS feed to monitor.

        Args:
            feed_url: RSS feed URL

        Returns:
            True if feed was added successfully
        """
        if len(self.feed_pollers) >= self.max_concurrent_feeds:
            logger.error(
                f"Cannot add feed: maximum of "
                f"{self.max_concurrent_feeds} feeds allowed"
            )
            return False

        if feed_url in self.feed_pollers:
            logger.warning(f"Feed already being monitored: {feed_url}")
            return True

        try:
            poller = FeedPoller(feed_url, self.polling_interval)
            self.feed_pollers[feed_url] = poller
            logger.info(f"Added RSS feed for monitoring: {feed_url}")
            return True

        except Exception as e:
            logger.error(f"Error adding RSS feed {feed_url}: {e}")
            return False

    def remove_feed(self, feed_url: str) -> bool:
        """
        Remove an RSS feed from monitoring.

        Args:
            feed_url: RSS feed URL

        Returns:
            True if feed was removed successfully
        """
        if feed_url not in self.feed_pollers:
            logger.warning(f"Feed not found for removal: {feed_url}")
            return False

        try:
            del self.feed_pollers[feed_url]
            logger.info(f"Removed RSS feed from monitoring: {feed_url}")
            return True

        except Exception as e:
            logger.error(f"Error removing RSS feed {feed_url}: {e}")
            return False

    async def start_monitoring(self) -> None:
        """Start monitoring configured RSS feeds."""
        if self.is_monitoring:
            logger.warning("RSS monitoring is already running")
            return

        self.is_monitoring = True
        logger.info(f"Starting RSS monitoring for {len(self.feed_pollers)} feeds")

        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop monitoring RSS feeds."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        logger.info("Stopping RSS monitoring")

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Check each feed poller
                for feed_url, poller in list(self.feed_pollers.items()):
                    if not poller.should_poll():
                        continue

                    if not poller.is_healthy():
                        logger.error(f"Feed poller unhealthy, removing: {feed_url}")
                        self.remove_feed(feed_url)
                        continue

                    # Fetch and process feed
                    await self._process_feed(feed_url, poller)

                # Wait before next monitoring cycle
                await asyncio.sleep(
                    10
                )  # Check every 10 seconds for feeds ready to poll

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait longer on error

    async def _process_feed(self, feed_url: str, poller: FeedPoller) -> None:
        """
        Process a single RSS feed.

        Args:
            feed_url: RSS feed URL
            poller: FeedPoller instance
        """
        try:
            # Fetch feed content (run in thread pool to avoid blocking)
            feed_content = await asyncio.get_running_loop().run_in_executor(
                None, poller.fetch_feed
            )

            if feed_content is None:
                return

            # Check if feed has changed
            if not poller.has_feed_changed(feed_content):
                logger.debug(f"No changes in feed: {feed_url}")
                return

            # Detect new deals
            new_deals = self.deal_detector.detect_new_deals(feed_content)

            if new_deals and self.deal_callback:
                # Call callback with new deals
                # Check if callback is async or sync
                if asyncio.iscoroutinefunction(self.deal_callback):
                    await self.deal_callback(new_deals)
                else:
                    await asyncio.get_running_loop().run_in_executor(
                        None, self.deal_callback, new_deals
                    )

        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")

    def add_feed_dynamic(self, feed_config) -> bool:
        """
        Add feed with enhanced metadata for dynamic management.

        Args:
            feed_config: FeedConfig object with metadata

        Returns:
            True if feed was added successfully
        """
        if len(self.feed_pollers) >= self.max_concurrent_feeds:
            logger.error(
                f"Cannot add feed: maximum of {self.max_concurrent_feeds} feeds allowed"
            )
            return False

        if feed_config.url in self.feed_pollers:
            logger.warning(f"Feed already being monitored: {feed_config.url}")
            return True

        try:
            poller = FeedPoller(feed_config.url, self.polling_interval)

            # Add metadata for dynamic feeds
            poller.metadata = {
                "name": feed_config.name,
                "added_by": feed_config.added_by,
                "added_at": feed_config.added_at,
                "enabled": feed_config.enabled,
                "is_dynamic": True,
            }

            self.feed_pollers[feed_config.url] = poller
            logger.info(
                f"Added dynamic RSS feed: {feed_config.name or feed_config.url}"
            )
            return True

        except Exception as e:
            logger.error(f"Error adding dynamic RSS feed {feed_config.url}: {e}")
            return False

    def remove_feed_dynamic(self, identifier: str) -> bool:
        """
        Remove feed by URL or name with validation.

        Args:
            identifier: Feed URL or name

        Returns:
            True if feed was removed successfully
        """
        feed_url_to_remove = None

        # Find feed by URL or name
        for url, poller in self.feed_pollers.items():
            if url == identifier:
                feed_url_to_remove = url
                break

            # Check metadata for name match
            if hasattr(poller, "metadata") and poller.metadata:
                if poller.metadata.get("name") == identifier:
                    feed_url_to_remove = url
                    break

        if not feed_url_to_remove:
            logger.warning(f"Feed not found for removal: {identifier}")
            return False

        return self.remove_feed(feed_url_to_remove)

    def get_feed_status(self, identifier: str = None) -> dict:
        """
        Get detailed feed status information.

        Args:
            identifier: Optional feed URL or name for specific feed status

        Returns:
            Dictionary with feed status information
        """
        try:
            if identifier:
                # Return status for specific feed
                feed_info = self._find_feed_by_identifier(identifier)
                if not feed_info:
                    return {"error": "Feed not found"}

                url, poller = feed_info
                return self._get_single_feed_status(url, poller)
            else:
                # Return status for all feeds
                active_feeds = sum(
                    1 for poller in self.feed_pollers.values() if poller.is_active
                )

                feeds_status = []
                for url, poller in self.feed_pollers.items():
                    feeds_status.append(self._get_single_feed_status(url, poller))

                return {
                    "total_feeds": len(self.feed_pollers),
                    "active_feeds": active_feeds,
                    "monitor_running": self.is_monitoring,
                    "feeds": feeds_status,
                }

        except Exception as e:
            logger.error(f"Error getting feed status: {e}")
            return {"error": f"Status check failed: {str(e)}"}

    def _find_feed_by_identifier(self, identifier: str):
        """Find feed by URL or name."""
        for url, poller in self.feed_pollers.items():
            if url == identifier:
                return (url, poller)

            # Check metadata for name match
            if hasattr(poller, "metadata") and poller.metadata:
                if poller.metadata.get("name") == identifier:
                    return (url, poller)

        return None

    def _get_single_feed_status(self, url: str, poller: FeedPoller) -> dict:
        """Get status information for a single feed."""
        metadata = getattr(poller, "metadata", {})

        return {
            "url": url,
            "name": metadata.get("name", self._extract_domain(url)),
            "is_active": poller.is_active,
            "is_healthy": poller.is_healthy(),
            "consecutive_failures": poller.consecutive_failures,
            "last_poll_time": poller.last_poll_time.isoformat()
            if poller.last_poll_time
            else None,
            "added_by": metadata.get("added_by", "unknown"),
            "added_at": metadata.get("added_at").isoformat()
            if metadata.get("added_at")
            else None,
            "enabled": metadata.get("enabled", True),
            "is_dynamic": metadata.get("is_dynamic", False),
        }

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL for display."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return url

    def reload_feeds(self, feed_urls: list) -> bool:
        """
        Reload feeds with new configuration.

        Args:
            feed_urls: List of feed URLs to monitor

        Returns:
            True if reload was successful
        """
        try:
            logger.info("Reloading RSS feeds...")

            # Get current feed URLs
            current_urls = set(self.feed_pollers.keys())
            new_urls = set(feed_urls)

            # Remove feeds that are no longer in the list
            for url in current_urls - new_urls:
                self.remove_feed(url)

            # Add new feeds
            for url in new_urls - current_urls:
                self.add_feed(url)

            logger.info(
                f"Feed reload completed. Now monitoring {len(self.feed_pollers)} feeds"
            )
            return True

        except Exception as e:
            logger.error(f"Error reloading feeds: {e}")
            return False
