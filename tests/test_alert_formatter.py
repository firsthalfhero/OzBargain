"""
Unit tests for the alert formatting system.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from ozb_deal_filter.components.alert_formatter import AlertFormatter, UrgencyCalculator
from ozb_deal_filter.models.deal import Deal
from ozb_deal_filter.models.filter import FilterResult, UrgencyLevel
from ozb_deal_filter.models.alert import FormattedAlert


class TestUrgencyCalculator:
    """Test cases for UrgencyCalculator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = UrgencyCalculator()
        self.base_deal = Deal(
            id="test-deal-1",
            title="Test Deal",
            description="Test description",
            price=100.0,
            original_price=200.0,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=[]
        )
        self.base_filter_result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=0.8,
            urgency_level=UrgencyLevel.LOW
        )

    def test_calculate_urgency_from_indicators(self):
        """Test urgency calculation from explicit indicators."""
        # Test urgent indicators
        deal = self.base_deal
        deal.urgency_indicators = ["flash sale", "limited time"]
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.URGENT

    def test_calculate_urgency_from_title(self):
        """Test urgency calculation from title keywords."""
        deal = Deal(
            id="test-deal-2",
            title="Flash Sale - Limited Time Only!",
            description="Regular description",
            price=50.0,
            original_price=100.0,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[]
        )
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.URGENT

    def test_calculate_urgency_from_description(self):
        """Test urgency calculation from description keywords."""
        deal = Deal(
            id="test-deal-3",
            title="Regular Deal",
            description="This is a 24 hours special offer with limited quantity available",
            price=75.0,
            original_price=150.0,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=8,
            comments=3,
            urgency_indicators=[]
        )
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.HIGH

    def test_calculate_urgency_from_discount(self):
        """Test urgency calculation from high discount percentage."""
        deal = Deal(
            id="test-deal-4",
            title="Regular Deal",
            description="Regular description",
            price=30.0,
            original_price=100.0,
            discount_percentage=70.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[]
        )
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.HIGH

    def test_calculate_urgency_from_price(self):
        """Test urgency calculation from low price."""
        deal = Deal(
            id="test-deal-5",
            title="Regular Deal",
            description="Regular description",
            price=25.0,
            original_price=50.0,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[]
        )
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.MEDIUM

    def test_calculate_urgency_from_votes(self):
        """Test urgency calculation from high vote count."""
        deal = Deal(
            id="test-deal-6",
            title="Regular Deal",
            description="Regular description",
            price=100.0,
            original_price=150.0,
            discount_percentage=33.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=75,
            comments=20,
            urgency_indicators=[]
        )
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.MEDIUM

    def test_calculate_urgency_default_low(self):
        """Test default low urgency for regular deals."""
        deal = Deal(
            id="test-deal-7",
            title="Regular Deal",
            description="Regular description",
            price=100.0,
            original_price=120.0,
            discount_percentage=17.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[]
        )
        
        urgency = self.calculator.calculate_urgency(deal, self.base_filter_result)
        assert urgency == UrgencyLevel.LOW


class TestAlertFormatter:
    """Test cases for AlertFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = AlertFormatter()
        self.test_deal = Deal(
            id="test-deal-1",
            title="Amazing Electronics Deal - 50% Off!",
            description="This is an amazing deal on electronics with great features and excellent value for money.",
            price=99.99,
            original_price=199.99,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal/123",
            timestamp=datetime(2024, 1, 15, 14, 30, 0),
            votes=25,
            comments=8,
            urgency_indicators=["limited time"]
        )
        self.test_filter_result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=0.85,
            urgency_level=UrgencyLevel.HIGH
        )

    def test_format_alert_basic(self):
        """Test basic alert formatting."""
        alert = self.formatter.format_alert(self.test_deal, self.test_filter_result)
        
        assert isinstance(alert, FormattedAlert)
        # The deal has "limited time" indicator, so it should be URGENT
        assert alert.title.startswith("🚨 URGENT:")
        assert "Amazing Electronics Deal" in alert.title
        assert "$99.99" in alert.message
        assert "Electronics" in alert.message
        assert "85.0%" in alert.message
        assert "https://example.com/deal/123" in alert.message

    def test_format_alert_validation(self):
        """Test that formatted alert passes validation."""
        alert = self.formatter.format_alert(self.test_deal, self.test_filter_result)
        
        # Should not raise any validation errors
        assert alert.validate() is True

    def test_create_alert_title_urgency_levels(self):
        """Test alert title creation with different urgency levels."""
        # Test urgent
        title = self.formatter._create_alert_title(self.test_deal, UrgencyLevel.URGENT)
        assert title.startswith("🚨 URGENT:")
        
        # Test high
        title = self.formatter._create_alert_title(self.test_deal, UrgencyLevel.HIGH)
        assert title.startswith("⚡ HIGH:")
        
        # Test medium
        title = self.formatter._create_alert_title(self.test_deal, UrgencyLevel.MEDIUM)
        assert title.startswith("📢 MEDIUM:")
        
        # Test low
        title = self.formatter._create_alert_title(self.test_deal, UrgencyLevel.LOW)
        assert title.startswith("💡 DEAL:")

    def test_create_alert_title_truncation(self):
        """Test alert title truncation for long titles."""
        long_title_deal = Deal(
            id="test-deal-long",
            title="This is an extremely long deal title that should be truncated because it exceeds the maximum allowed length for alert titles in the system",
            description="Description",
            price=50.0,
            original_price=100.0,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[]
        )
        
        title = self.formatter._create_alert_title(long_title_deal, UrgencyLevel.LOW)
        assert len(title) <= 200  # Should be within reasonable limits
        # Check if truncation occurred by looking for "..." or checking if title was shortened
        original_title_in_result = "This is an extremely long deal title that should be truncated because it exceeds the maximum allowed length for alert titles in the system"
        if len(f"💡 DEAL: {original_title_in_result}") > 200:
            assert title.endswith("...")
        else:
            # If the title fits, it shouldn't be truncated
            assert original_title_in_result in title

    def test_create_alert_message_complete(self):
        """Test complete alert message creation."""
        message = self.formatter._create_alert_message(
            self.test_deal, self.test_filter_result, UrgencyLevel.HIGH
        )
        
        # Check all expected components are present
        assert "**Amazing Electronics Deal - 50% Off!**" in message
        assert "💰 **Price:** $99.99" in message
        assert "(was $199.99, 50% off)" in message
        assert "📂 **Category:** Electronics" in message
        assert "✅ **Authenticity:** 85.0%" in message
        assert "👥 **Community:** 25 votes, 8 comments" in message
        assert "⏰ **Urgency:** limited time" in message
        assert "📝 **Description:**" in message
        assert "🔗 **Link:** https://example.com/deal/123" in message
        assert "🕒 **Posted:** 2024-01-15 14:30:00" in message

    def test_create_alert_message_minimal_deal(self):
        """Test alert message creation with minimal deal data."""
        minimal_deal = Deal(
            id="minimal-deal",
            title="Simple Deal",
            description="Simple description",
            price=None,
            original_price=None,
            discount_percentage=None,
            category="General",
            url="https://example.com/simple",
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[]
        )
        
        minimal_filter = FilterResult(
            passes_filters=True,
            price_match=False,
            authenticity_score=0.0,
            urgency_level=UrgencyLevel.LOW
        )
        
        message = self.formatter._create_alert_message(
            minimal_deal, minimal_filter, UrgencyLevel.LOW
        )
        
        # Should handle missing data gracefully
        assert "**Simple Deal**" in message
        assert "📂 **Category:** General" in message
        assert "🔗 **Link:** https://example.com/simple" in message
        # Should not contain price, votes, comments, or authenticity info
        assert "💰 **Price:**" not in message
        assert "👥 **Community:**" not in message
        assert "✅ **Authenticity:**" not in message

    def test_format_telegram(self):
        """Test Telegram-specific formatting."""
        telegram_data = self.formatter._format_telegram(
            self.test_deal, self.test_filter_result, UrgencyLevel.HIGH
        )
        
        assert "text" in telegram_data
        assert "parse_mode" in telegram_data
        assert telegram_data["parse_mode"] == "HTML"
        assert "reply_markup" in telegram_data
        assert "inline_keyboard" in telegram_data["reply_markup"]
        
        # Check HTML formatting
        text = telegram_data["text"]
        assert "⚡ <b>Amazing Electronics Deal - 50% Off!</b>" in text
        assert "💰 <b>Price:</b> $99.99" in text
        assert "<i>(was $199.99, 50% off)</i>" in text
        assert "📂 <b>Category:</b> Electronics" in text
        assert "✅ <b>Authenticity:</b> 85.0%" in text

    def test_format_discord(self):
        """Test Discord-specific formatting."""
        discord_data = self.formatter._format_discord(
            self.test_deal, self.test_filter_result, UrgencyLevel.HIGH
        )
        
        assert "embeds" in discord_data
        embed = discord_data["embeds"][0]
        
        assert embed["title"] == "Amazing Electronics Deal - 50% Off!"
        assert embed["url"] == "https://example.com/deal/123"
        assert embed["color"] == 0xFF8C00  # Dark Orange for HIGH urgency
        assert "fields" in embed
        
        # Check fields
        fields = embed["fields"]
        price_field = next(f for f in fields if f["name"] == "💰 Price")
        assert "$99.99" in price_field["value"]
        assert "~~$199.99~~" in price_field["value"]
        assert "(50% off)" in price_field["value"]

    def test_format_slack(self):
        """Test Slack-specific formatting."""
        slack_data = self.formatter._format_slack(
            self.test_deal, self.test_filter_result, UrgencyLevel.HIGH
        )
        
        assert "blocks" in slack_data
        assert "color" in slack_data
        assert slack_data["color"] == "warning"  # Warning color for HIGH urgency
        
        blocks = slack_data["blocks"]
        
        # Check header block
        header_block = blocks[0]
        assert header_block["type"] == "header"
        assert "⚡ Amazing Electronics Deal - 50% Off!" in header_block["text"]["text"]
        
        # Check action block
        action_block = next(b for b in blocks if b["type"] == "actions")
        button = action_block["elements"][0]
        assert button["url"] == "https://example.com/deal/123"

    def test_format_whatsapp(self):
        """Test WhatsApp-specific formatting."""
        whatsapp_data = self.formatter._format_whatsapp(
            self.test_deal, self.test_filter_result, UrgencyLevel.HIGH
        )
        
        assert "text" in whatsapp_data
        text = whatsapp_data["text"]
        
        assert "⚡ *Amazing Electronics Deal - 50% Off!*" in text
        assert "💰 *Price:* $99.99" in text
        assert "_(was $199.99, 50% off)_" in text
        assert "📂 *Category:* Electronics" in text
        assert "✅ *Authenticity:* 85.0%" in text
        assert "https://example.com/deal/123" in text

    def test_platform_specific_data_all_platforms(self):
        """Test that platform-specific data is generated for all platforms."""
        platform_data = self.formatter._create_platform_data(
            self.test_deal, self.test_filter_result, UrgencyLevel.HIGH
        )
        
        expected_platforms = ["telegram", "discord", "slack", "whatsapp"]
        for platform in expected_platforms:
            assert platform in platform_data
            assert isinstance(platform_data[platform], dict)

    def test_format_alert_with_different_urgency_levels(self):
        """Test alert formatting with different urgency levels."""
        urgency_levels = [UrgencyLevel.URGENT, UrgencyLevel.HIGH, UrgencyLevel.MEDIUM, UrgencyLevel.LOW]
        
        for urgency in urgency_levels:
            # Mock the urgency calculator to return specific urgency
            self.formatter.urgency_calculator.calculate_urgency = Mock(return_value=urgency)
            
            alert = self.formatter.format_alert(self.test_deal, self.test_filter_result)
            
            assert alert.urgency == urgency
            # Check that title reflects the urgency
            urgency_prefixes = {
                UrgencyLevel.URGENT: "🚨 URGENT",
                UrgencyLevel.HIGH: "⚡ HIGH",
                UrgencyLevel.MEDIUM: "📢 MEDIUM",
                UrgencyLevel.LOW: "💡 DEAL"
            }
            expected_prefix = urgency_prefixes[urgency]
            assert alert.title.startswith(expected_prefix)

    def test_format_alert_description_truncation(self):
        """Test that long descriptions are properly truncated."""
        long_description_deal = Deal(
            id="long-desc-deal",
            title="Deal with Long Description",
            description="This is an extremely long description that goes on and on with lots of details about the product, its features, specifications, benefits, and other information that might be useful but is too long for a concise alert message and should be truncated appropriately.",
            price=50.0,
            original_price=100.0,
            discount_percentage=50.0,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[]
        )
        
        alert = self.formatter.format_alert(long_description_deal, self.test_filter_result)
        
        # Description should be truncated in the message
        assert "..." in alert.message
        # But should still be readable
        assert "This is an extremely long description" in alert.message

    def test_authenticity_score_display(self):
        """Test authenticity score display with different values."""
        # Test high authenticity (should show green checkmark)
        high_auth_result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=0.8,
            urgency_level=UrgencyLevel.LOW
        )
        
        alert = self.formatter.format_alert(self.test_deal, high_auth_result)
        assert "✅ **Authenticity:** 80.0%" in alert.message
        
        # Test medium authenticity (should show warning)
        medium_auth_result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=0.6,
            urgency_level=UrgencyLevel.LOW
        )
        
        alert = self.formatter.format_alert(self.test_deal, medium_auth_result)
        assert "⚠️ **Authenticity:** 60.0%" in alert.message
        
        # Test low authenticity (should show red X)
        low_auth_result = FilterResult(
            passes_filters=True,
            price_match=True,
            authenticity_score=0.3,
            urgency_level=UrgencyLevel.LOW
        )
        
        alert = self.formatter.format_alert(self.test_deal, low_auth_result)
        assert "❌ **Authenticity:** 30.0%" in alert.message