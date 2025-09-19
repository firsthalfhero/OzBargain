"""
Protocol interfaces for the OzBargain Deal Filter system.

This module defines all the protocol interfaces that establish
system boundaries and enable dependency injection throughout
the application.
"""

from abc import ABC, abstractmethod
from typing import Protocol, List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from .models.deal import Deal, RawDeal
from .models.evaluation import EvaluationResult
from .models.filter import FilterResult
from .models.alert import FormattedAlert
from .models.delivery import DeliveryResult


class IRSSMonitor(Protocol):
    """Protocol for RSS feed monitoring components."""

    def start_monitoring(self) -> None:
        """Start monitoring configured RSS feeds."""
        ...

    def stop_monitoring(self) -> None:
        """Stop monitoring RSS feeds."""
        ...

    def add_feed(self, feed_url: str) -> bool:
        """Add a new RSS feed to monitor."""
        ...

    def remove_feed(self, feed_url: str) -> bool:
        """Remove an RSS feed from monitoring."""
        ...


class IDealDetector(Protocol):
    """Protocol for detecting new deals from RSS feed data."""

    def detect_new_deals(self, feed_data: str) -> List[RawDeal]:
        """Detect new deals from RSS feed data."""
        ...


class IDealParser(Protocol):
    """Protocol for parsing raw deals into structured data."""

    def parse_deal(self, raw_deal: RawDeal) -> Deal:
        """Parse a raw deal into a structured Deal object."""
        ...

    def validate_deal(self, deal: Deal) -> bool:
        """Validate that a deal contains required information."""
        ...


class ILLMEvaluator(Protocol):
    """Protocol for LLM-based deal evaluation."""

    def evaluate_deal(self, deal: Deal, prompt_template: str) -> EvaluationResult:
        """Evaluate a deal against user criteria using LLM."""
        ...

    def set_llm_provider(self, provider_config: "LLMProviderConfig") -> None:
        """Set the LLM provider for evaluations."""
        ...


class IFilterEngine(Protocol):
    """Protocol for applying filters to deals."""

    def apply_filters(self, deal: Deal, evaluation: EvaluationResult) -> FilterResult:
        """Apply price, discount, and authenticity filters to a deal."""
        ...


class IAlertFormatter(Protocol):
    """Protocol for formatting deal alerts."""

    def format_alert(self, deal: Deal, filter_result: FilterResult) -> FormattedAlert:
        """Format a deal into an alert message."""
        ...


class IMessageDispatcher(Protocol):
    """Protocol for dispatching alert messages."""

    def send_alert(self, alert: FormattedAlert) -> DeliveryResult:
        """Send an alert through the configured messaging platform."""
        ...

    def test_connection(self) -> bool:
        """Test connection to the messaging platform."""
        ...


class IConfigurationManager(Protocol):
    """Protocol for managing system configuration."""

    def load_configuration(self, config_path: str) -> "Configuration":
        """Load configuration from file."""
        ...

    def validate_configuration(self, config: "Configuration") -> bool:
        """Validate configuration data."""
        ...

    def reload_configuration(self) -> None:
        """Reload configuration without restart."""
        ...


class IGitAgent(Protocol):
    """Protocol for automated git operations."""

    def commit_changes(self, message: str) -> bool:
        """Commit current changes with the specified message."""
        ...

    def generate_commit_message(self, task_description: str) -> str:
        """Generate a meaningful commit message for a task."""
        ...
