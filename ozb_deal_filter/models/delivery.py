"""
Message delivery result models.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DeliveryResult:
    """Result of message delivery attempt."""

    success: bool
    delivery_time: datetime
    error_message: Optional[str]

    def validate(self) -> bool:
        """Validate delivery result data."""
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")

        if not isinstance(self.delivery_time, datetime):
            raise ValueError("delivery_time must be a datetime object")

        if self.error_message is not None:
            if not isinstance(self.error_message, str):
                raise ValueError("error_message must be a string or None")

            if len(self.error_message) > 500:
                raise ValueError("error_message too long (max 500 characters)")

        # Logical validation: if success is False, error_message should be provided
        if not self.success and not self.error_message:
            raise ValueError("error_message should be provided when success is False")

        return True
