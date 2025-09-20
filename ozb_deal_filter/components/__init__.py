"""
Core components for the OzBargain Deal Filter system.

This module contains the main components that handle RSS monitoring,
deal parsing, LLM evaluation, filtering, and message dispatching.
"""

from .authenticity_assessor import AuthenticityAssessor
from .filter_engine import FilterEngine, PriceFilter
from .git_agent import GitAgent
from .llm_evaluator import APILLMClient, LLMEvaluator, LLMProvider, LocalLLMClient
from .prompt_manager import PromptManager

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
