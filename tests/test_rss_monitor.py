"""
Unit tests for RSS monitoring components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
from datetime import datetime, timedelta
import requests

from ozb_deal_filter.components.rss_monitor import FeedPoller, DealDetector, RSSMonitor
from ozb_deal_filter.models.deal import RawDeal


class TestFeedPoller:
    """Test cases for FeedPoller class."""

    def test_init(self):
        """Test FeedPoller initialization."""
        poller = FeedPoller("https://example.com/feed.xml")

        assert poller.feed_url == "https://example.com/feed.xml"
        assert poller.polling_interval == 120
        assert poller.timeout == 30
        assert poller.max_retries == 3
        assert poller.last_poll_time is None
        assert poller.last_feed_hash is None
        assert poller.consecutive_failures == 0
        assert not poller.is_active

    def test_init_with_custom_params(self):
        """Test FeedPoller initialization with custom parameters."""
        poller = FeedPoller(
            "https://example.com/feed.xml",
            polling_interval=60,
            timeout=15,
            max_retries=5,
        )

        assert poller.polling_interval == 60
        assert poller.timeout == 15
        assert poller.max_retries == 5

    @patch("requests.Session.get")
    def test_fetch_feed_success(self, mock_get):
        """Test successful feed fetching."""
        mock_response = Mock()
        mock_response.text = "<rss>test content</rss>"
        mock_get.return_value = mock_response

        poller = FeedPoller("https://example.com/feed.xml")
        result = poller.fetch_feed()

        assert result == "<rss>test content</rss>"
        assert poller.consecutive_failures == 0
        assert poller.last_poll_time is not None
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_fetch_feed_timeout(self, mock_get):
        """Test feed fetching with timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()

        poller = FeedPoller("https://example.com/feed.xml")
        result = poller.fetch_feed()

        assert result is None
        assert poller.consecutive_failures == 1

    @patch("requests.Session.get")
    def test_fetch_feed_connection_error(self, mock_get):
        """Test feed fetching with connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        poller = FeedPoller("https://example.com/feed.xml")
        result = poller.fetch_feed()

        assert result is None
        assert poller.consecutive_failures == 1

    @patch("requests.Session.get")
    def test_fetch_feed_http_error(self, mock_get):
        """Test feed fetching with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )

        poller = FeedPoller("https://example.com/feed.xml")
        result = poller.fetch_feed()

        assert result is None
        assert poller.consecutive_failures == 1

    def test_has_feed_changed_first_time(self):
        """Test feed change detection on first poll."""
        poller = FeedPoller("https://example.com/feed.xml")

        result = poller.has_feed_changed("test content")

        assert result is True
        assert poller.last_feed_hash is not None

    def test_has_feed_changed_same_content(self):
        """Test feed change detection with same content."""
        poller = FeedPoller("https://example.com/feed.xml")

        # First call
        poller.has_feed_changed("test content")

        # Second call with same content
        result = poller.has_feed_changed("test content")

        assert result is False

    def test_has_feed_changed_different_content(self):
        """Test feed change detection with different content."""
        poller = FeedPoller("https://example.com/feed.xml")

        # First call
        poller.has_feed_changed("test content")

        # Second call with different content
        result = poller.has_feed_changed("different content")

        assert result is True

    def test_should_poll_first_time(self):
        """Test polling decision on first poll."""
        poller = FeedPoller("https://example.com/feed.xml")

        assert poller.should_poll() is True

    def test_should_poll_too_soon(self):
        """Test polling decision when too soon."""
        poller = FeedPoller("https://example.com/feed.xml", polling_interval=120)
        poller.last_poll_time = datetime.now()

        assert poller.should_poll() is False

    def test_should_poll_time_elapsed(self):
        """Test polling decision when enough time has elapsed."""
        poller = FeedPoller("https://example.com/feed.xml", polling_interval=120)
        poller.last_poll_time = datetime.now() - timedelta(seconds=130)

        assert poller.should_poll() is True

    def test_is_healthy_no_failures(self):
        """Test health check with no failures."""
        poller = FeedPoller("https://example.com/feed.xml", max_retries=3)

        assert poller.is_healthy() is True

    def test_is_healthy_some_failures(self):
        """Test health check with some failures."""
        poller = FeedPoller("https://example.com/feed.xml", max_retries=3)
        poller.consecutive_failures = 3

        assert poller.is_healthy() is True

    def test_is_healthy_too_many_failures(self):
        """Test health check with too many failures."""
        poller = FeedPoller("https://example.com/feed.xml", max_retries=3)
        poller.consecutive_failures = 7  # More than max_retries * 2

        assert poller.is_healthy() is False


class TestDealDetector:
    """Test cases for DealDetector class."""

    def test_init(self):
        """Test DealDetector initialization."""
        detector = DealDetector()

        assert len(detector.seen_deal_ids) == 0

    @patch("feedparser.parse")
    def test_detect_new_deals_valid_feed(self, mock_parse):
        """Test detecting new deals from valid RSS feed."""
        # Mock feedparser response
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {
                "title": "Great Deal on Electronics",
                "description": "Amazing discount on electronics",
                "link": "https://example.com/deal1",
                "published": "2024-01-01T12:00:00Z",
                "category": "Electronics",
            },
            {
                "title": "Another Deal",
                "description": "Another great deal",
                "link": "https://example.com/deal2",
                "published": "2024-01-01T13:00:00Z",
            },
        ]
        mock_parse.return_value = mock_feed

        detector = DealDetector()
        deals = detector.detect_new_deals("<rss>test feed</rss>")

        assert len(deals) == 2
        assert deals[0].title == "Great Deal on Electronics"
        assert deals[0].link == "https://example.com/deal1"
        assert deals[1].title == "Another Deal"
        assert len(detector.seen_deal_ids) == 2

    @patch("feedparser.parse")
    def test_detect_new_deals_duplicate_deals(self, mock_parse):
        """Test detecting deals with duplicates."""
        # Mock feedparser response
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {
                "title": "Great Deal",
                "description": "Amazing discount",
                "link": "https://example.com/deal1",
                "published": "2024-01-01T12:00:00Z",
            }
        ]
        mock_parse.return_value = mock_feed

        detector = DealDetector()

        # First detection
        deals1 = detector.detect_new_deals("<rss>test feed</rss>")
        assert len(deals1) == 1

        # Second detection with same deal
        deals2 = detector.detect_new_deals("<rss>test feed</rss>")
        assert len(deals2) == 0  # Should be filtered out as duplicate

    @patch("feedparser.parse")
    def test_detect_new_deals_invalid_entry(self, mock_parse):
        """Test detecting deals with invalid entry."""
        # Mock feedparser response with invalid entry
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {
                "title": "",  # Invalid: empty title
                "description": "Amazing discount",
                "link": "https://example.com/deal1",
                "published": "2024-01-01T12:00:00Z",
            },
            {
                "title": "Valid Deal",
                "description": "Valid description",
                "link": "https://example.com/deal2",
                "published": "2024-01-01T13:00:00Z",
            },
        ]
        mock_parse.return_value = mock_feed

        detector = DealDetector()
        deals = detector.detect_new_deals("<rss>test feed</rss>")

        # Should only get the valid deal
        assert len(deals) == 1
        assert deals[0].title == "Valid Deal"

    @patch("feedparser.parse")
    def test_detect_new_deals_bozo_feed(self, mock_parse):
        """Test detecting deals from malformed RSS feed."""
        # Mock feedparser response with bozo flag
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = "Invalid XML"
        mock_feed.entries = [
            {
                "title": "Deal from Bozo Feed",
                "description": "Description",
                "link": "https://example.com/deal1",
                "published": "2024-01-01T12:00:00Z",
            }
        ]
        mock_parse.return_value = mock_feed

        detector = DealDetector()
        deals = detector.detect_new_deals("<rss>malformed feed</rss>")

        # Should still process deals despite bozo flag
        assert len(deals) == 1
        assert deals[0].title == "Deal from Bozo Feed"

    @patch("feedparser.parse")
    def test_detect_new_deals_parse_error(self, mock_parse):
        """Test detecting deals with parsing error."""
        mock_parse.side_effect = Exception("Parse error")

        detector = DealDetector()
        deals = detector.detect_new_deals("<rss>invalid feed</rss>")

        assert len(deals) == 0

    def test_extract_category_string(self):
        """Test category extraction from string."""
        detector = DealDetector()
        entry = {"category": "Electronics"}

        category = detector._extract_category(entry)

        assert category == "Electronics"

    def test_extract_category_list_with_term(self):
        """Test category extraction from list with term attribute."""
        detector = DealDetector()
        mock_category = Mock()
        mock_category.term = "Computing"
        entry = {"category": [mock_category]}

        category = detector._extract_category(entry)

        assert category == "Computing"

    def test_extract_category_list_with_string(self):
        """Test category extraction from list with strings."""
        detector = DealDetector()
        entry = {"category": ["Gaming"]}

        category = detector._extract_category(entry)

        assert category == "Gaming"

    def test_extract_category_none(self):
        """Test category extraction when no category present."""
        detector = DealDetector()
        entry = {"title": "Deal without category"}

        category = detector._extract_category(entry)

        assert category is None


class TestRSSMonitor:
    """Test cases for RSSMonitor class."""

    def test_init(self):
        """Test RSSMonitor initialization."""
        monitor = RSSMonitor()

        assert monitor.polling_interval == 120
        assert monitor.max_concurrent_feeds == 10
        assert monitor.deal_callback is None
        assert len(monitor.feed_pollers) == 0
        assert not monitor.is_monitoring

    def test_init_with_callback(self):
        """Test RSSMonitor initialization with callback."""
        callback = Mock()
        monitor = RSSMonitor(deal_callback=callback)

        assert monitor.deal_callback == callback

    def test_add_feed_success(self):
        """Test adding RSS feed successfully."""
        monitor = RSSMonitor()

        result = monitor.add_feed("https://example.com/feed.xml")

        assert result is True
        assert len(monitor.feed_pollers) == 1
        assert "https://example.com/feed.xml" in monitor.feed_pollers

    def test_add_feed_duplicate(self):
        """Test adding duplicate RSS feed."""
        monitor = RSSMonitor()

        # Add first time
        result1 = monitor.add_feed("https://example.com/feed.xml")
        assert result1 is True

        # Add duplicate
        result2 = monitor.add_feed("https://example.com/feed.xml")
        assert result2 is True  # Should still return True but not add duplicate
        assert len(monitor.feed_pollers) == 1

    def test_add_feed_max_limit(self):
        """Test adding RSS feed when at maximum limit."""
        monitor = RSSMonitor(max_concurrent_feeds=2)

        # Add feeds up to limit
        monitor.add_feed("https://example.com/feed1.xml")
        monitor.add_feed("https://example.com/feed2.xml")

        # Try to add one more
        result = monitor.add_feed("https://example.com/feed3.xml")

        assert result is False
        assert len(monitor.feed_pollers) == 2

    def test_remove_feed_success(self):
        """Test removing RSS feed successfully."""
        monitor = RSSMonitor()
        monitor.add_feed("https://example.com/feed.xml")

        result = monitor.remove_feed("https://example.com/feed.xml")

        assert result is True
        assert len(monitor.feed_pollers) == 0

    def test_remove_feed_not_found(self):
        """Test removing RSS feed that doesn't exist."""
        monitor = RSSMonitor()

        result = monitor.remove_feed("https://example.com/nonexistent.xml")

        assert result is False

    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        """Test starting RSS monitoring."""
        monitor = RSSMonitor()

        # Start monitoring
        await monitor.start_monitoring()

        assert monitor.is_monitoring is True
        assert monitor._monitor_task is not None

        # Clean up
        await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self):
        """Test starting RSS monitoring when already running."""
        monitor = RSSMonitor()

        # Start monitoring first time
        await monitor.start_monitoring()
        assert monitor.is_monitoring is True

        # Try to start again
        await monitor.start_monitoring()
        assert monitor.is_monitoring is True  # Should still be running

        # Clean up
        await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self):
        """Test stopping RSS monitoring."""
        monitor = RSSMonitor()

        # Start then stop monitoring
        await monitor.start_monitoring()
        await monitor.stop_monitoring()

        assert monitor.is_monitoring is False

    @pytest.mark.asyncio
    async def test_stop_monitoring_not_running(self):
        """Test stopping RSS monitoring when not running."""
        monitor = RSSMonitor()

        # Stop monitoring when not running
        await monitor.stop_monitoring()

        assert monitor.is_monitoring is False

    @pytest.mark.asyncio
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.fetch_feed")
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.should_poll")
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.is_healthy")
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.has_feed_changed")
    async def test_process_feed_success(
        self, mock_changed, mock_healthy, mock_should_poll, mock_fetch
    ):
        """Test processing a single RSS feed successfully."""
        # Setup mocks
        mock_should_poll.return_value = True
        mock_healthy.return_value = True
        mock_fetch.return_value = "<rss>test content</rss>"
        mock_changed.return_value = True

        # Mock deal callback
        callback = Mock()
        monitor = RSSMonitor(deal_callback=callback)
        monitor.add_feed("https://example.com/feed.xml")

        # Mock deal detector to return deals
        with patch.object(monitor.deal_detector, "detect_new_deals") as mock_detect:
            mock_deals = [
                RawDeal(
                    title="Test Deal",
                    description="Test Description",
                    link="https://example.com/deal1",
                    pub_date="2024-01-01T12:00:00Z",
                )
            ]
            mock_detect.return_value = mock_deals

            # Process feed
            poller = monitor.feed_pollers["https://example.com/feed.xml"]
            await monitor._process_feed("https://example.com/feed.xml", poller)

            # Verify callback was called
            callback.assert_called_once_with(mock_deals)

    @pytest.mark.asyncio
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.fetch_feed")
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.should_poll")
    @patch("ozb_deal_filter.components.rss_monitor.FeedPoller.is_healthy")
    async def test_process_feed_fetch_failure(
        self, mock_healthy, mock_should_poll, mock_fetch
    ):
        """Test processing feed when fetch fails."""
        # Setup mocks
        mock_should_poll.return_value = True
        mock_healthy.return_value = True
        mock_fetch.return_value = None  # Simulate fetch failure

        callback = Mock()
        monitor = RSSMonitor(deal_callback=callback)
        monitor.add_feed("https://example.com/feed.xml")

        # Process feed
        poller = monitor.feed_pollers["https://example.com/feed.xml"]
        await monitor._process_feed("https://example.com/feed.xml", poller)

        # Verify callback was not called
        callback.assert_not_called()


# Sample RSS feed data for testing
SAMPLE_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>OzBargain</title>
        <description>OzBargain Deals</description>
        <item>
            <title>50% off Electronics at TechStore</title>
            <description>Great deal on electronics with free shipping</description>
            <link>https://www.ozbargain.com.au/node/123456</link>
            <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
            <category>Electronics</category>
        </item>
        <item>
            <title>Gaming Laptop $999 (was $1999)</title>
            <description>High-performance gaming laptop at half price</description>
            <link>https://www.ozbargain.com.au/node/123457</link>
            <pubDate>Mon, 01 Jan 2024 13:00:00 GMT</pubDate>
            <category>Computing</category>
        </item>
    </channel>
</rss>"""


@pytest.fixture
def sample_rss_feed():
    """Fixture providing sample RSS feed data."""
    return SAMPLE_RSS_FEED


class TestIntegration:
    """Integration tests for RSS monitoring components."""

    @patch("requests.Session.get")
    def test_full_workflow_integration(self, mock_get, sample_rss_feed):
        """Test full workflow from RSS fetch to deal detection."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = sample_rss_feed
        mock_get.return_value = mock_response

        # Create components
        poller = FeedPoller("https://example.com/feed.xml")
        detector = DealDetector()

        # Fetch feed
        feed_content = poller.fetch_feed()
        assert feed_content is not None

        # Check if changed (first time should be True)
        changed = poller.has_feed_changed(feed_content)
        assert changed is True

        # Detect deals
        deals = detector.detect_new_deals(feed_content)
        assert len(deals) == 2
        assert deals[0].title == "50% off Electronics at TechStore"
        assert deals[1].title == "Gaming Laptop $999 (was $1999)"

        # Second fetch should show no changes
        feed_content2 = poller.fetch_feed()
        changed2 = poller.has_feed_changed(feed_content2)
        assert changed2 is False

        # Should detect no new deals
        deals2 = detector.detect_new_deals(feed_content2)
        assert len(deals2) == 0  # All deals already seen
