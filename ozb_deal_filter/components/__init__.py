"""
Core components for the OzBargain Deal Filter system.

This module contains the main components that handle RSS monitoring,
deal parsing, LLM evaluation, filtering, and message dispatching.
"""

from .llm_evaluator import LLMEvaluator, LocalLLMClient, APILLMClient, LLMProvider
from .prompt_manager import PromptManager
from .authenticity_assessor import AuthenticityAssessor
from .git_agent import GitAgent
from .filter_engine import FilterEngine, PriceFilter

__all__ = [
    "LLMEvaluator",
    "LocalLLMClient",
    "APILLMClient",
    "LLMProvider",
    "PromptManager",
    "AuthenticityAssessor",
    "GitAgent",
    "FilterEngine",
    "PriceFilter",
]
