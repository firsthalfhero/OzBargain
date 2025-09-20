"""
Data models for the OzBargain Deal Filter system.

This module contains all data classes and type definitions used throughout
the application for representing deals, configuration, and system state.
"""

from .alert import FormattedAlert
from .config import (
    Configuration,
    LLMProviderConfig,
    MessagingPlatformConfig,
    UserCriteria,
)
from .deal import Deal, RawDeal
from .delivery import DeliveryResult
from .evaluation import EvaluationResult
from .filter import FilterResult, UrgencyLevel
from .git import CommitResult, GitStatus

__all__ = [
    "Deal",
    "RawDeal",
    "EvaluationResult",
    "FilterResult",
    "UrgencyLevel",
    "FormattedAlert",
    "DeliveryResult",
    "Configuration",
    "UserCriteria",
    "LLMProviderConfig",
    "MessagingPlatformConfig",
    "CommitResult",
    "GitStatus",
]
