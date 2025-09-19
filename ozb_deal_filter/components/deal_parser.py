"""
Deal parsing and extraction components for the OzBargain Deal Filter system.

This module provides functionality to convert RSS entries to Deal objects,
extract price and discount information, and validate parsed deal data.
"""

import re
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from ..models.deal import RawDeal, Deal


logger = logging.getLogger(__name__)


class PriceExtractor:
    """Extracts price and discount information from deal text."""

    # Price patterns for different formats
    PRICE_PATTERNS = [
        # Starting from $999, from $99.99 (current price indicators)
        r"(?:starting\s+from|from)\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        # AU$99.99, AUD99.99
        r"(?:AU\$|AUD)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        # $99.99, $1,234.56 (general dollar amounts)
        r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        # 99.99, 1234.56 (when preceded by price indicators)
        r"(?:price|cost|now|sale|deal)\s*:?\s*" r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
    ]

    # Discount patterns
    DISCOUNT_PATTERNS = [
        # 50% off, 25% discount
        r"(\d{1,2})%\s*(?:off|discount|save)",
        # Save 50%, 25% savings
        r"(?:save|savings?)\s*(\d{1,2})%",
        # (50% off)
        r"\((\d{1,2})%\s*off\)",
    ]

    # Original price patterns (was/originally/RRP)
    ORIGINAL_PRICE_PATTERNS = [
        r"\(was\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\)",
        r"(?:was|originally|rrp|retail)\s*:?\s*\$?" r"(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)",
        r"rrp\s*\$?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)",
    ]

    # Urgency indicators
    URGENCY_PATTERNS = [
        r"(?:limited\s*time|expires?\s*(?:today|tomorrow|soon))",
        r"(?:hurry|quick|fast|urgent)",
        r"(?:while\s*stocks?\s*last|limited\s*stock)",
        r"(?:flash\s*sale|lightning\s*deal)",
        r"(?:ends?\s*(?:in\s*)?(?:\d+\s*(?:hours?|mins?|minutes?)))",
        r"(?:only\s*\d+\s*(?:left|remaining))",
    ]

    def __init__(self):
        """Initialize price extractor."""
        # Compile regex patterns for better performance
        self.price_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.PRICE_PATTERNS
        ]
        self.discount_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.DISCOUNT_PATTERNS
        ]
        self.original_price_regexes = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.ORIGINAL_PRICE_PATTERNS
        ]
        self.urgency_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.URGENCY_PATTERNS
        ]

    def extract_prices(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract current price and original price from text.

        Args:
            text: Text to extract prices from

        Returns:
            Tuple of (current_price, original_price)
        """
        current_price = None
        original_price = None

        # Clean text for better matching
        clean_text = self._clean_text(text)

        # Extract original price first (was/originally/RRP)
        for regex in self.original_price_regexes:
            match = regex.search(clean_text)
            if match:
                try:
                    price_str = match.group(1).replace(",", "")
                    original_price = float(price_str)
                    break
                except (ValueError, IndexError):
                    continue

        # Extract current price
        for regex in self.price_regexes:
            match = regex.search(clean_text)
            if match:
                try:
                    price_str = match.group(1).replace(",", "")
                    current_price = float(price_str)
                    break
                except (ValueError, IndexError):
                    continue

        return current_price, original_price

    def extract_discount_percentage(
        self,
        text: str,
        current_price: Optional[float] = None,
        original_price: Optional[float] = None,
    ) -> Optional[float]:
        """
        Extract discount percentage from text or calculate from prices.

        Args:
            text: Text to extract discount from
            current_price: Current price for calculation
            original_price: Original price for calculation

        Returns:
            Discount percentage (0-100) or None
        """
        # First try to extract explicit discount percentage
        clean_text = self._clean_text(text)

        for regex in self.discount_regexes:
            match = regex.search(clean_text)
            if match:
                try:
                    discount = float(match.group(1))
                    if 0 <= discount <= 100:
                        return discount
                except (ValueError, IndexError):
                    continue

        # Calculate from prices if available
        if (
            current_price is not None
            and original_price is not None
            and original_price > 0
        ):
            if current_price < original_price:
                discount = ((original_price - current_price) / original_price) * 100
                return round(discount, 1)

        return None

    def extract_urgency_indicators(self, text: str) -> List[str]:
        """
        Extract urgency indicators from text.

        Args:
            text: Text to extract urgency indicators from

        Returns:
            List of urgency indicator strings
        """
        indicators = []
        clean_text = self._clean_text(text)

        for regex in self.urgency_regexes:
            matches = regex.findall(clean_text)
            for match in matches:
                if isinstance(match, str) and match.strip():
                    indicators.append(match.strip().lower())

        # Remove duplicates while preserving order
        seen = set()
        unique_indicators = []
        for indicator in indicators:
            if indicator not in seen:
                seen.add(indicator)
                unique_indicators.append(indicator)

        return unique_indicators

    def _clean_text(self, text: str) -> str:
        """
        Clean text for better pattern matching.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Only use BeautifulSoup if text actually contains HTML tags
        if "<" in text and ">" in text:
            soup = BeautifulSoup(text, "html.parser")
            clean_text = soup.get_text()
        else:
            clean_text = text

        # Normalize whitespace
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        return clean_text


class DealValidator:
    """Validates parsed deal data for completeness and accuracy."""

    def __init__(self):
        """Initialize deal validator."""
        self.required_fields = [
            "id",
            "title",
            "description",
            "category",
            "url",
            "timestamp",
        ]

    def validate_deal(self, deal: Deal) -> bool:
        """
        Validate that a deal contains required information and is logically
        consistent.

        Args:
            deal: Deal object to validate

        Returns:
            True if deal is valid

        Raises:
            ValueError: If deal validation fails
        """
        # Use the deal's built-in validation first
        deal.validate()

        # Additional business logic validation
        self._validate_price_logic(deal)
        self._validate_url_format(deal)
        self._validate_timestamp(deal)

        return True

    def _validate_price_logic(self, deal: Deal) -> None:
        """
        Validate price-related logic.

        Args:
            deal: Deal to validate

        Raises:
            ValueError: If price logic is invalid
        """
        # Check price consistency
        if deal.price is not None and deal.original_price is not None:
            if deal.price > deal.original_price:
                raise ValueError("Current price cannot be higher than original price")

        # Validate discount percentage consistency
        if (
            deal.discount_percentage is not None
            and deal.price is not None
            and deal.original_price is not None
            and deal.original_price > 0
        ):
            calculated_discount = (
                (deal.original_price - deal.price) / deal.original_price
            ) * 100

            # Allow some tolerance for rounding differences
            if abs(calculated_discount - deal.discount_percentage) > 5:
                logger.warning(
                    f"Discount percentage mismatch for deal {deal.id}: "
                    f"stated {deal.discount_percentage}%, "
                    f"calculated {calculated_discount:.1f}%"
                )

    def _validate_url_format(self, deal: Deal) -> None:
        """
        Validate URL format and domain.

        Args:
            deal: Deal to validate

        Raises:
            ValueError: If URL is invalid
        """
        parsed_url = urlparse(deal.url)

        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL format: {deal.url}")

        # Check if it's an OzBargain URL (for authenticity)
        if "ozbargain.com.au" not in parsed_url.netloc.lower():
            logger.warning(f"Non-OzBargain URL detected: {deal.url}")

    def _validate_timestamp(self, deal: Deal) -> None:
        """
        Validate timestamp is reasonable.

        Args:
            deal: Deal to validate

        Raises:
            ValueError: If timestamp is invalid
        """
        # Make both timestamps timezone-aware or timezone-naive for comparison
        now = datetime.now()
        deal_timestamp = deal.timestamp

        # If deal timestamp is timezone-aware, make now timezone-aware too
        if deal_timestamp.tzinfo is not None:
            from datetime import timezone

            now = now.replace(tzinfo=timezone.utc)
        # If deal timestamp is timezone-naive, make sure now is too
        elif now.tzinfo is not None:
            now = now.replace(tzinfo=None)

        # Check if timestamp is too far in the future (more than 1 day)
        future_limit = now.replace(hour=23, minute=59, second=59) + timedelta(days=1)
        if deal_timestamp > future_limit:
            raise ValueError(f"Deal timestamp too far in future: {deal_timestamp}")

        # Check if timestamp is too old (more than 30 days)
        past_limit = now - timedelta(days=30)
        if deal_timestamp < past_limit:
            logger.warning(f"Deal timestamp is quite old: {deal_timestamp}")


class DealParser:
    """Main deal parser that converts RSS entries to Deal objects."""

    def __init__(self):
        """Initialize deal parser."""
        self.price_extractor = PriceExtractor()
        self.validator = DealValidator()

    def parse_deal(self, raw_deal: RawDeal) -> Deal:
        """
        Parse a raw deal into a structured Deal object.

        Args:
            raw_deal: RawDeal object from RSS feed

        Returns:
            Parsed Deal object

        Raises:
            ValueError: If parsing fails or deal is invalid
        """
        try:
            # Validate raw deal first
            raw_deal.validate()

            # Generate unique ID for the deal
            deal_id = self._generate_deal_id(raw_deal)

            # Parse timestamp
            timestamp = self._parse_timestamp(raw_deal.pub_date)

            # Extract price information
            combined_text = f"{raw_deal.title} {raw_deal.description}"
            current_price, original_price = self.price_extractor.extract_prices(
                combined_text
            )
            discount_percentage = self.price_extractor.extract_discount_percentage(
                combined_text, current_price, original_price
            )

            # Extract urgency indicators
            urgency_indicators = self.price_extractor.extract_urgency_indicators(
                combined_text
            )

            # Extract vote and comment counts from URL or description
            votes, comments = self._extract_community_data(raw_deal)

            # Create Deal object
            deal = Deal(
                id=deal_id,
                title=raw_deal.title.strip(),
                description=raw_deal.description.strip(),
                price=current_price,
                original_price=original_price,
                discount_percentage=discount_percentage,
                category=raw_deal.category or "Unknown",
                url=raw_deal.link,
                timestamp=timestamp,
                votes=votes,
                comments=comments,
                urgency_indicators=urgency_indicators,
            )

            # Validate the parsed deal
            self.validator.validate_deal(deal)

            logger.debug(f"Successfully parsed deal: {deal.title}")
            return deal

        except Exception as e:
            logger.error(f"Error parsing deal '{raw_deal.title}': {e}")
            raise ValueError(f"Failed to parse deal: {e}")

    def validate_deal(self, deal: Deal) -> bool:
        """
        Validate that a deal contains required information.

        Args:
            deal: Deal object to validate

        Returns:
            True if deal is valid
        """
        return self.validator.validate_deal(deal)

    def _generate_deal_id(self, raw_deal: RawDeal) -> str:
        """
        Generate a unique ID for the deal.

        Args:
            raw_deal: RawDeal object

        Returns:
            Unique deal ID string
        """
        # Try to extract OzBargain node ID from URL
        parsed_url = urlparse(raw_deal.link)

        if "ozbargain.com.au" in parsed_url.netloc:
            # Extract node ID from OzBargain URL
            path_parts = parsed_url.path.split("/")
            for part in path_parts:
                if part.startswith("node") and len(part) > 4:
                    return part
                elif part.isdigit() and len(part) >= 5:
                    return f"node{part}"

        # Fallback: generate hash-based ID
        content = f"{raw_deal.title}{raw_deal.link}{raw_deal.pub_date}"
        hash_obj = hashlib.md5(content.encode())
        return f"deal_{hash_obj.hexdigest()[:8]}"

    def _parse_timestamp(self, pub_date: str) -> datetime:
        """
        Parse publication date string to datetime.

        Args:
            pub_date: Publication date string

        Returns:
            Parsed datetime object

        Raises:
            ValueError: If date parsing fails
        """
        try:
            # Use dateutil parser for flexible date parsing
            return date_parser.parse(pub_date)
        except Exception as e:
            logger.error(f"Error parsing date '{pub_date}': {e}")
            # Fallback to current time
            return datetime.now()

    def _extract_community_data(
        self, raw_deal: RawDeal
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Extract vote and comment counts from deal data.

        Args:
            raw_deal: RawDeal object

        Returns:
            Tuple of (votes, comments)
        """
        votes = None
        comments = None

        # Try to extract from description (OzBargain sometimes includes this)
        description = raw_deal.description.lower()

        # Look for vote patterns
        vote_patterns = [
            r"(\d+)\s*(?:votes?|ups?)",
            r"voted?\s*(\d+)",
            r"score[:\s]*(\d+)",
        ]

        for pattern in vote_patterns:
            match = re.search(pattern, description)
            if match:
                try:
                    votes = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue

        # Look for comment patterns
        comment_patterns = [
            r"(\d+)\s*comments?",
            r"(\d+)\s*replies?",
            r"discuss\s*\((\d+)\)",
        ]

        for pattern in comment_patterns:
            match = re.search(pattern, description)
            if match:
                try:
                    comments = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue

        return votes, comments
