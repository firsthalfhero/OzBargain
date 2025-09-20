"""
Alert formatting models.
"""

from dataclasses import dataclass
from typing import Any, Dict

from .filter import UrgencyLevel


@dataclass
class FormattedAlert:
    """Formatted alert ready for delivery."""

    title: str
    message: str
    urgency: UrgencyLevel
    platform_specific_data: Dict[str, Any]

    def validate(self) -> bool:
        """Validate formatted alert data."""
        if not isinstance(self.title, str):
            raise ValueError("title must be a string")

        if not self.title.strip():
            raise ValueError("title cannot be empty")

        if len(self.title) > 200:
            raise ValueError("title too long (max 200 characters)")

        if not isinstance(self.message, str):
            raise ValueError("message must be a string")

        if not self.message.strip():
            raise ValueError("message cannot be empty")

        if len(self.message) > 4000:
            raise ValueError("message too long (max 4000 characters)")

        if not isinstance(self.urgency, UrgencyLevel):
            raise ValueError("urgency must be a UrgencyLevel enum")

        if not isinstance(self.platform_specific_data, dict):
            raise ValueError("platform_specific_data must be a dictionary")

        return True
