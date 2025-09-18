"""
LLM evaluation result models.
"""

from dataclasses import dataclass


@dataclass
class EvaluationResult:
    """Result of LLM evaluation for a deal."""

    is_relevant: bool
    confidence_score: float
    reasoning: str

    def validate(self) -> bool:
        """Validate evaluation result data."""
        if not isinstance(self.is_relevant, bool):
            raise ValueError("is_relevant must be a boolean")

        if not isinstance(self.confidence_score, (int, float)):
            raise ValueError("confidence_score must be a number")

        if not (0 <= self.confidence_score <= 1):
            raise ValueError("confidence_score must be between 0 and 1")

        if not isinstance(self.reasoning, str):
            raise ValueError("reasoning must be a string")

        if not self.reasoning.strip():
            raise ValueError("reasoning cannot be empty")

        if len(self.reasoning) > 1000:
            raise ValueError("reasoning too long (max 1000 characters)")

        return True
