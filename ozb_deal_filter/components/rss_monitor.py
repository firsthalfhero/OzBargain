"""
RSS monitoring components for the OzBargain Deal Filter system.

This module provides RSS feed monitoring functionality with error handling
for network timeouts and invalid feeds.
"""

import asyncio
import logging
from typing import List, Dict, Set, Optional, Callable, Union, Awaitable
from datetime import datetime
import hashlib

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models.deal import RawDeal


logger = logging.getLogger(__name__)


class FeedPoller:
    """Individual RSS feed polling and management."""

    def __init__(
        self,
        feed_url: str,
        polling_interval: int = 120,
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

    def __init__(self):
        """Initialize deal detector."""
        self.seen_deal_ids: Set[str] = set()

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

            for entry in parsed_feed.entries:
                try:
                    # Create unique ID for deal (using link as identifier)
                    deal_id = entry.get("link", "")

                    if not deal_id or deal_id in self.seen_deal_ids:
                        continue

                    # Extract deal information
                    raw_deal = RawDeal(
                        title=entry.get("title", "").strip(),
                        description=entry.get("description", "").strip(),
                        link=deal_id,
                        pub_date=entry.get("published", ""),
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


class RSSMonitor:
    """Main RSS monitoring orchestrator."""

    def __init__(
        self,
        polling_interval: int = 120,
        max_concurrent_feeds: int = 10,
        deal_callback: Optional[Union[Callable[[List[RawDeal]], None], Callable[[List[RawDeal]], Awaitable[None]]]] = None,
    ):
        """
        Initialize RSS monitor.

        Args:
            polling_interval: Default polling interval in seconds
            max_concurrent_feeds: Maximum number of feeds to monitor
            deal_callback: Callback function for new deals
        """
        self.polling_interval = polling_interval
        self.max_concurrent_feeds = max_concurrent_feeds
        self.deal_callback = deal_callback

        self.feed_pollers: Dict[str, FeedPoller] = {}
        self.deal_detector = DealDetector()
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
            feed_content = await asyncio.get_running_loop().run_in_executor(None, poller.fetch_feed)

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
                    await loop.run_in_executor(None, self.deal_callback, new_deals)

        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")
