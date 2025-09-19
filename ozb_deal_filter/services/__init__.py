"""
Service layer for the OzBargain Deal Filter system.

This module contains business logic services that orchestrate
the core functionality of RSS monitoring, deal evaluation,
filtering, and alert delivery.
"""

from .config_manager import ConfigurationManager
from .evaluation_service import EvaluationService

__all__ = [
    "ConfigurationManager",
    "EvaluationService",
]
