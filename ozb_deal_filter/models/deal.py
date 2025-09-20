"""
Deal data models for the OzBargain Deal Filter system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class RawDeal:
    """Raw deal data from RSS feed."""

    title: str
    description: str
    link: str
    pub_date: str
    category: Optional[str] = None

    def validate(self) -> bool:
        """Validate the raw deal data."""
        if not self.title or not self.title.strip():
            raise ValueError("Deal title cannot be empty")

        if not self.description or not self.description.strip():
            raise ValueError("Deal description cannot be empty")

        if not self.link or not self.link.strip():
            raise ValueError("Deal link cannot be empty")

        # Validate URL format
        parsed_url = urlparse(self.link)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL format: {self.link}")

        if not self.pub_date or not self.pub_date.strip():
            raise ValueError("Publication date cannot be empty")

        # Validate title length (reasonable limits)
        if len(self.title) > 500:
            raise ValueError("Deal title too long (max 500 characters)")

        # Validate description length
        if len(self.description) > 5000:
            raise ValueError("Deal description too long (max 5000 characters)")

        return True


@dataclass
class Deal:
    """Parsed and structured deal data."""

    id: str
    title: str
    description: str
    price: Optional[float]
    original_price: Optional[float]
    discount_percentage: Optional[float]
    category: str
    url: str
    timestamp: datetime
    votes: Optional[int]
    comments: Optional[int]
    urgency_indicators: List[str]

    def validate(self) -> bool:
        """Validate the deal data."""
        if not self.id or not self.id.strip():
            raise ValueError("Deal ID cannot be empty")

        if not self.title or not self.title.strip():
            raise ValueError("Deal title cannot be empty")

        if not self.description or not self.description.strip():
            raise ValueError("Deal description cannot be empty")

        if not self.category or not self.category.strip():
            raise ValueError("Deal category cannot be empty")

        if not self.url or not self.url.strip():
            raise ValueError("Deal URL cannot be empty")

        # Validate URL format
        parsed_url = urlparse(self.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL format: {self.url}")

        # Validate price values
        if self.price is not None and self.price < 0:
            raise ValueError("Price cannot be negative")

        if self.original_price is not None and self.original_price < 0:
            raise ValueError("Original price cannot be negative")

        if self.discount_percentage is not None:
            if not (0 <= self.discount_percentage <= 100):
                raise ValueError("Discount percentage must be between 0 and 100")

        # Validate price consistency
        if (
            self.price is not None
            and self.original_price is not None
            and self.price > self.original_price
        ):
            raise ValueError("Price cannot be higher than original price")

        # Validate vote and comment counts
        if self.votes is not None and self.votes < 0:
            raise ValueError("Vote count cannot be negative")

        if self.comments is not None and self.comments < 0:
            raise ValueError("Comment count cannot be negative")

        # Validate urgency indicators
        if not isinstance(self.urgency_indicators, list):
            raise ValueError("Urgency indicators must be a list")

        # Validate string lengths
        if len(self.title) > 500:
            raise ValueError("Deal title too long (max 500 characters)")

        if len(self.description) > 5000:
            raise ValueError("Deal description too long (max 5000 characters)")

        if len(self.category) > 100:
            raise ValueError("Category name too long (max 100 characters)")

        return True
