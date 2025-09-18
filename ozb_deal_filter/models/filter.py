"""
Filter result models.
"""

from dataclasses import dataclass
from enum import Enum


class UrgencyLevel(Enum):
    """Urgency levels for deals."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class FilterResult:
    """Result of applying filters to a deal."""

    passes_filters: bool
    price_match: bool
    authenticity_score: float
    urgency_level: UrgencyLevel

    def validate(self) -> bool:
        """Validate filter result data."""
        if not isinstance(self.passes_filters, bool):
            raise ValueError("passes_filters must be a boolean")

        if not isinstance(self.price_match, bool):
            raise ValueError("price_match must be a boolean")

        if not isinstance(self.authenticity_score, (int, float)):
            raise ValueError("authenticity_score must be a number")

        if not (0 <= self.authenticity_score <= 1):
            raise ValueError("authenticity_score must be between 0 and 1")

        if not isinstance(self.urgency_level, UrgencyLevel):
            raise ValueError("urgency_level must be a UrgencyLevel enum")

        return True
