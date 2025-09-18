"""
Data models for the OzBargain Deal Filter system.

This module contains all data classes and type definitions used throughout
the application for representing deals, configuration, and system state.
"""

from .deal import Deal, RawDeal
from .evaluation import EvaluationResult
from .filter import FilterResult, UrgencyLevel
from .alert import FormattedAlert
from .delivery import DeliveryResult
from .config import Configuration, UserCriteria, LLMProviderConfig, MessagingPlatformConfig

__all__ = [
    'Deal',
    'RawDeal',
    'EvaluationResult',
    'FilterResult',
    'UrgencyLevel',
    'FormattedAlert',
    'DeliveryResult',
    'Configuration',
    'UserCriteria',
    'LLMProviderConfig',
    'MessagingPlatformConfig',
]