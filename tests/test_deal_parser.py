"""
Unit tests for deal parsing components.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ozb_deal_filter.components.deal_parser import (
    DealParser,
    DealValidator,
    PriceExtractor,
)
from ozb_deal_filter.models.deal import Deal, RawDeal


class TestPriceExtractor:
    """Test cases for PriceExtractor class."""

    def test_init(self):
        """Test PriceExtractor initialization."""
        extractor = PriceExtractor()

        assert len(extractor.price_regexes) > 0
        assert len(extractor.discount_regexes) > 0
        assert len(extractor.original_price_regexes) > 0
        assert len(extractor.urgency_regexes) > 0

    def test_extract_prices_dollar_format(self):
        """Test price extraction with dollar format."""
        extractor = PriceExtractor()

        current, original = extractor.extract_prices("Great deal for $99.99")

        assert current == 99.99
        assert original is None

    def test_extract_prices_with_commas(self):
        """Test price extraction with comma separators."""
        extractor = PriceExtractor()

        current, original = extractor.extract_prices("Expensive item $1,234.56")

        assert current == 1234.56
        assert original is None

    def test_extract_prices_with_original(self):
        """Test price extraction with original price."""
        extractor = PriceExtractor()

        current, original = extractor.extract_prices("Now $99.99 was $199.99")

        assert current == 99.99
        assert original == 199.99

    def test_extract_prices_aud_format(self):
        """Test price extraction with AUD format."""
        extractor = PriceExtractor()

        current, original = extractor.extract_prices("Price: AU$149.99")

        assert current == 149.99
        assert original is None

    def test_extract_prices_no_prices(self):
        """Test price extraction when no prices found."""
        extractor = PriceExtractor()

        current, original = extractor.extract_prices(
            "Great deal with no specific price"
        )

        assert current is None
        assert original is None

    def test_extract_discount_percentage_explicit(self):
        """Test discount percentage extraction from explicit text."""
        extractor = PriceExtractor()

        discount = extractor.extract_discount_percentage("Save 50% off today!")

        assert discount == 50.0

    def test_extract_discount_percentage_calculated(self):
        """Test discount percentage calculation from prices."""
        extractor = PriceExtractor()

        discount = extractor.extract_discount_percentage(
            "", current_price=50.0, original_price=100.0
        )

        assert discount == 50.0

    def test_extract_discount_percentage_invalid_calculation(self):
        """Test discount percentage with invalid price calculation."""
        extractor = PriceExtractor()

        # Current price higher than original (invalid)
        discount = extractor.extract_discount_percentage(
            "", current_price=150.0, original_price=100.0
        )

        assert discount is None

    def test_extract_discount_percentage_none(self):
        """Test discount percentage extraction when none found."""
        extractor = PriceExtractor()

        discount = extractor.extract_discount_percentage(
            "Great deal with no discount mentioned"
        )

        assert discount is None

    def test_extract_urgency_indicators_multiple(self):
        """Test urgency indicator extraction with multiple indicators."""
        extractor = PriceExtractor()

        indicators = extractor.extract_urgency_indicators(
            "Limited time flash sale! Hurry while stocks last!"
        )

        assert len(indicators) >= 2
        assert any("limited time" in indicator for indicator in indicators)
        assert any("flash sale" in indicator for indicator in indicators)

    def test_extract_urgency_indicators_none(self):
        """Test urgency indicator extraction when none found."""
        extractor = PriceExtractor()

        indicators = extractor.extract_urgency_indicators(
            "Regular deal with no urgency"
        )

        assert len(indicators) == 0

    def test_extract_urgency_indicators_duplicates(self):
        """Test urgency indicator extraction removes duplicates."""
        extractor = PriceExtractor()

        indicators = extractor.extract_urgency_indicators("Hurry! Hurry! Limited time!")

        # Should not have duplicate "hurry"
        hurry_count = sum(1 for indicator in indicators if "hurry" in indicator)
        assert hurry_count == 1

    def test_clean_text_html_removal(self):
        """Test text cleaning removes HTML tags."""
        extractor = PriceExtractor()

        cleaned = extractor._clean_text("<p>Price: <strong>$99.99</strong></p>")

        assert "<p>" not in cleaned
        assert "<strong>" not in cleaned
        assert "$99.99" in cleaned

    def test_clean_text_whitespace_normalization(self):
        """Test text cleaning normalizes whitespace."""
        extractor = PriceExtractor()

        cleaned = extractor._clean_text("Price:   $99.99\n\n  Great   deal")

        assert "Price: $99.99 Great deal" == cleaned


class TestDealValidator:
    """Test cases for DealValidator class."""

    def test_init(self):
        """Test DealValidator initialization."""
        validator = DealValidator()

        assert len(validator.required_fields) > 0
        assert "id" in validator.required_fields
        assert "title" in validator.required_fields

    def test_validate_deal_valid(self):
        """Test validation of valid deal."""
        validator = DealValidator()
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=99.99,
            original_price=199.99,
            discount_percentage=50.0,
            category="Electronics",
            url="https://www.ozbargain.com.au/node/123456",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=[],
        )

        result = validator.validate_deal(deal)

        assert result is True

    def test_validate_deal_invalid_price_logic(self):
        """Test validation fails with invalid price logic."""
        validator = DealValidator()
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=199.99,  # Higher than original price
            original_price=99.99,
            discount_percentage=None,
            category="Electronics",
            url="https://www.ozbargain.com.au/node/123456",
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

        with pytest.raises(
            ValueError, match="Price cannot be higher than original price"
        ):
            validator.validate_deal(deal)

    def test_validate_deal_invalid_url(self):
        """Test validation fails with invalid URL."""
        validator = DealValidator()
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=99.99,
            original_price=None,
            discount_percentage=None,
            category="Electronics",
            url="invalid-url",  # Invalid URL format
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

        with pytest.raises(ValueError, match="Invalid URL format"):
            validator.validate_deal(deal)

    def test_validate_deal_future_timestamp(self):
        """Test validation fails with future timestamp."""
        validator = DealValidator()
        future_time = datetime.now() + timedelta(days=2)  # Too far in future
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=99.99,
            original_price=None,
            discount_percentage=None,
            category="Electronics",
            url="https://www.ozbargain.com.au/node/123456",
            timestamp=future_time,
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

        with pytest.raises(ValueError, match="Deal timestamp too far in future"):
            validator.validate_deal(deal)

    def test_validate_price_logic_discount_mismatch(self):
        """Test price logic validation with discount mismatch warning."""
        validator = DealValidator()
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=50.0,
            original_price=100.0,
            discount_percentage=25.0,  # Should be 50%, significant mismatch
            category="Electronics",
            url="https://www.ozbargain.com.au/node/123456",
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

        # Should not raise exception but log warning
        with patch("ozb_deal_filter.components.deal_parser.logger") as mock_logger:
            validator._validate_price_logic(deal)
            mock_logger.warning.assert_called_once()

    def test_validate_url_format_non_ozbargain(self):
        """Test URL validation with non-OzBargain URL."""
        validator = DealValidator()
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=99.99,
            original_price=None,
            discount_percentage=None,
            category="Electronics",
            url="https://example.com/deal",  # Non-OzBargain URL
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

        with patch("ozb_deal_filter.components.deal_parser.logger") as mock_logger:
            validator._validate_url_format(deal)
            mock_logger.warning.assert_called_once()


class TestDealParser:
    """Test cases for DealParser class."""

    def test_init(self):
        """Test DealParser initialization."""
        parser = DealParser()

        assert parser.price_extractor is not None
        assert parser.validator is not None

    def test_parse_deal_basic(self):
        """Test basic deal parsing."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Great Electronics Deal - $99.99 (was $199.99)",
            description="Amazing discount on electronics with free shipping",
            link="https://www.ozbargain.com.au/node/123456",
            pub_date="2024-01-01T12:00:00Z",
            category="Electronics",
        )

        deal = parser.parse_deal(raw_deal)

        assert deal.title == "Great Electronics Deal - $99.99 (was $199.99)"
        assert deal.description == "Amazing discount on electronics with free shipping"
        assert deal.price == 99.99
        assert deal.original_price == 199.99
        assert deal.discount_percentage == 50.0
        assert deal.category == "Electronics"
        assert deal.url == raw_deal.link
        assert "node123456" in deal.id or "123456" in deal.id

    def test_parse_deal_with_urgency(self):
        """Test deal parsing with urgency indicators."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Flash Sale! Limited time offer",
            description="Hurry while stocks last! 50% off electronics",
            link="https://www.ozbargain.com.au/node/789012",
            pub_date="2024-01-01T12:00:00Z",
            category="Electronics",
        )

        deal = parser.parse_deal(raw_deal)

        assert len(deal.urgency_indicators) > 0
        assert any("flash sale" in indicator for indicator in deal.urgency_indicators)

    def test_parse_deal_no_category(self):
        """Test deal parsing without category."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Deal without category",
            description="Description",
            link="https://www.ozbargain.com.au/node/123456",
            pub_date="2024-01-01T12:00:00Z",
            category=None,
        )

        deal = parser.parse_deal(raw_deal)

        assert deal.category == "Unknown"

    def test_parse_deal_invalid_raw_deal(self):
        """Test deal parsing with invalid raw deal."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="",  # Invalid: empty title
            description="Description",
            link="https://www.ozbargain.com.au/node/123456",
            pub_date="2024-01-01T12:00:00Z",
            category="Electronics",
        )

        with pytest.raises(ValueError, match="Failed to parse deal"):
            parser.parse_deal(raw_deal)

    def test_generate_deal_id_ozbargain_node(self):
        """Test deal ID generation from OzBargain node URL."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Test Deal",
            description="Description",
            link="https://www.ozbargain.com.au/node/123456",
            pub_date="2024-01-01T12:00:00Z",
        )

        deal_id = parser._generate_deal_id(raw_deal)

        assert "node123456" in deal_id or "123456" in deal_id

    def test_generate_deal_id_ozbargain_numeric(self):
        """Test deal ID generation from OzBargain numeric URL."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Test Deal",
            description="Description",
            link="https://www.ozbargain.com.au/deals/123456",
            pub_date="2024-01-01T12:00:00Z",
        )

        deal_id = parser._generate_deal_id(raw_deal)

        assert "123456" in deal_id

    def test_generate_deal_id_fallback_hash(self):
        """Test deal ID generation fallback to hash."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Test Deal",
            description="Description",
            link="https://example.com/deal",  # Non-OzBargain URL
            pub_date="2024-01-01T12:00:00Z",
        )

        deal_id = parser._generate_deal_id(raw_deal)

        assert deal_id.startswith("deal_")
        assert len(deal_id) == 13  # "deal_" + 8 character hash

    def test_parse_timestamp_valid(self):
        """Test timestamp parsing with valid date."""
        parser = DealParser()

        timestamp = parser._parse_timestamp("2024-01-01T12:00:00Z")

        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 1
        assert timestamp.hour == 12

    def test_parse_timestamp_invalid(self):
        """Test timestamp parsing with invalid date."""
        parser = DealParser()

        with patch("ozb_deal_filter.components.deal_parser.logger") as mock_logger:
            timestamp = parser._parse_timestamp("invalid-date")

            # Should fallback to current time
            assert isinstance(timestamp, datetime)
            mock_logger.error.assert_called_once()

    def test_extract_community_data_with_votes(self):
        """Test community data extraction with votes."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Test Deal",
            description="Great deal with 25 votes and 10 comments",
            link="https://www.ozbargain.com.au/node/123456",
            pub_date="2024-01-01T12:00:00Z",
        )

        votes, comments = parser._extract_community_data(raw_deal)

        assert votes == 25
        assert comments == 10

    def test_extract_community_data_no_data(self):
        """Test community data extraction with no data."""
        parser = DealParser()
        raw_deal = RawDeal(
            title="Test Deal",
            description="Simple description without community data",
            link="https://www.ozbargain.com.au/node/123456",
            pub_date="2024-01-01T12:00:00Z",
        )

        votes, comments = parser._extract_community_data(raw_deal)

        assert votes is None
        assert comments is None

    def test_validate_deal_calls_validator(self):
        """Test that validate_deal calls the validator."""
        parser = DealParser()
        deal = Deal(
            id="test_deal_1",
            title="Test Deal",
            description="Test description",
            price=99.99,
            original_price=None,
            discount_percentage=None,
            category="Electronics",
            url="https://www.ozbargain.com.au/node/123456",
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

        with patch.object(
            parser.validator, "validate_deal", return_value=True
        ) as mock_validate:
            result = parser.validate_deal(deal)

            assert result is True
            mock_validate.assert_called_once_with(deal)


# Sample OzBargain RSS data for testing
SAMPLE_OZBARGAIN_RSS_DATA = [
    {
        "title": "50% off Gaming Laptops at TechStore - Starting from $999 (was $1999)",
        "description": "Limited time flash sale on gaming laptops! Hurry while stocks last. Free shipping included. 15 votes, 8 comments.",
        "link": "https://www.ozbargain.com.au/node/789012",
        "pub_date": "2024-01-01T10:00:00Z",
        "category": "Computing",
    },
    {
        "title": "Wireless Headphones AU$149.99 (RRP $299.99)",
        "description": "Premium wireless headphones with noise cancellation. Expires today! 32 votes, 12 comments.",
        "link": "https://www.ozbargain.com.au/node/789013",
        "pub_date": "2024-01-01T11:00:00Z",
        "category": "Electronics",
    },
    {
        "title": "Free Shipping on All Orders - No Minimum",
        "description": "Free shipping promotion for all products. Valid until end of month.",
        "link": "https://www.ozbargain.com.au/node/789014",
        "pub_date": "2024-01-01T12:00:00Z",
        "category": "General",
    },
]


class TestIntegration:
    """Integration tests for deal parsing components."""

    def test_full_parsing_workflow(self):
        """Test complete parsing workflow with real OzBargain-style data."""
        parser = DealParser()

        for sample_data in SAMPLE_OZBARGAIN_RSS_DATA:
            raw_deal = RawDeal(
                title=sample_data["title"],
                description=sample_data["description"],
                link=sample_data["link"],
                pub_date=sample_data["pub_date"],
                category=sample_data["category"],
            )

            # Should parse without errors
            deal = parser.parse_deal(raw_deal)

            # Verify basic properties
            assert deal.title == sample_data["title"]
            assert deal.description == sample_data["description"]
            assert deal.category == sample_data["category"]
            assert deal.url == sample_data["link"]
            assert isinstance(deal.timestamp, datetime)

    def test_price_extraction_integration(self):
        """Test price extraction with various formats."""
        parser = DealParser()

        # Test case 1: Gaming laptop with clear pricing
        raw_deal1 = RawDeal(
            title=SAMPLE_OZBARGAIN_RSS_DATA[0]["title"],
            description=SAMPLE_OZBARGAIN_RSS_DATA[0]["description"],
            link=SAMPLE_OZBARGAIN_RSS_DATA[0]["link"],
            pub_date=SAMPLE_OZBARGAIN_RSS_DATA[0]["pub_date"],
            category=SAMPLE_OZBARGAIN_RSS_DATA[0]["category"],
        )

        deal1 = parser.parse_deal(raw_deal1)
        assert deal1.price == 999.0
        assert deal1.original_price == 1999.0
        assert deal1.discount_percentage == 50.0

        # Test case 2: Headphones with AU$ format
        raw_deal2 = RawDeal(
            title=SAMPLE_OZBARGAIN_RSS_DATA[1]["title"],
            description=SAMPLE_OZBARGAIN_RSS_DATA[1]["description"],
            link=SAMPLE_OZBARGAIN_RSS_DATA[1]["link"],
            pub_date=SAMPLE_OZBARGAIN_RSS_DATA[1]["pub_date"],
            category=SAMPLE_OZBARGAIN_RSS_DATA[1]["category"],
        )

        deal2 = parser.parse_deal(raw_deal2)
        assert deal2.price == 149.99
        assert deal2.original_price == 299.99
        assert (
            abs(deal2.discount_percentage - 50.0) < 1.0
        )  # Allow small rounding difference

    def test_urgency_extraction_integration(self):
        """Test urgency indicator extraction with real data."""
        parser = DealParser()

        raw_deal = RawDeal(
            title=SAMPLE_OZBARGAIN_RSS_DATA[0]["title"],
            description=SAMPLE_OZBARGAIN_RSS_DATA[0]["description"],
            link=SAMPLE_OZBARGAIN_RSS_DATA[0]["link"],
            pub_date=SAMPLE_OZBARGAIN_RSS_DATA[0]["pub_date"],
            category=SAMPLE_OZBARGAIN_RSS_DATA[0]["category"],
        )

        deal = parser.parse_deal(raw_deal)

        # Should detect urgency indicators
        assert len(deal.urgency_indicators) > 0
        urgency_text = " ".join(deal.urgency_indicators)
        assert any(
            keyword in urgency_text
            for keyword in ["flash", "limited", "hurry", "stocks"]
        )

    def test_community_data_extraction_integration(self):
        """Test community data extraction with real data."""
        parser = DealParser()

        raw_deal = RawDeal(
            title=SAMPLE_OZBARGAIN_RSS_DATA[1]["title"],
            description=SAMPLE_OZBARGAIN_RSS_DATA[1]["description"],
            link=SAMPLE_OZBARGAIN_RSS_DATA[1]["link"],
            pub_date=SAMPLE_OZBARGAIN_RSS_DATA[1]["pub_date"],
            category=SAMPLE_OZBARGAIN_RSS_DATA[1]["category"],
        )

        deal = parser.parse_deal(raw_deal)

        # Should extract vote and comment counts
        assert deal.votes == 32
        assert deal.comments == 12
