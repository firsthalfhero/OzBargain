"""
Deal evaluation service that integrates LLM evaluation with prompt management.

This service provides the main evaluation logic with timeout handling,
error recovery, and comprehensive deal assessment capabilities.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from ..components.llm_evaluator import LLMEvaluator
from ..components.prompt_manager import PromptManager
from ..models.deal import Deal
from ..models.evaluation import EvaluationResult
from ..models.config import LLMProviderConfig, UserCriteria


logger = logging.getLogger(__name__)


class EvaluationService:
    """
    Main service for evaluating deals using LLM and prompt templates.

    This service coordinates between the LLM evaluator and prompt manager
    to provide comprehensive deal evaluation with timeout handling and
    error recovery mechanisms.
    """

    def __init__(
        self,
        llm_config: LLMProviderConfig,
        user_criteria: UserCriteria,
        prompts_directory: str = "prompts",
        evaluation_timeout: int = 30,
    ):
        self.llm_config = llm_config
        self.user_criteria = user_criteria
        self.evaluation_timeout = evaluation_timeout

        # Initialize components
        self.llm_evaluator = LLMEvaluator(llm_config)
        self.prompt_manager = PromptManager(prompts_directory)

        # Load and cache the prompt template
        self._prompt_template: Optional[str] = None
        self._load_prompt_template()

        # Evaluation statistics
        self.stats = {
            "total_evaluations": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "timeout_evaluations": 0,
            "fallback_evaluations": 0,
            "average_response_time": 0.0,
        }

    def _load_prompt_template(self) -> None:
        """Load the prompt template from configuration."""
        try:
            self._prompt_template = self.prompt_manager.load_template(
                self.user_criteria.prompt_template_path
            )
            logger.info(
                f"Loaded prompt template: {self.user_criteria.prompt_template_path}"
            )
        except Exception as e:
            logger.error(f"Failed to load prompt template: {e}")
            # Create a default template if loading fails
            try:
                self._prompt_template = self.prompt_manager.create_default_template(
                    self.user_criteria.prompt_template_path
                )
                logger.info("Created default prompt template")
            except Exception as create_error:
                logger.error(f"Failed to create default template: {create_error}")
                raise RuntimeError(
                    f"Cannot initialize evaluation service: {create_error}"
                )

    async def evaluate_deal(self, deal: Deal) -> EvaluationResult:
        """
        Evaluate a deal using LLM with timeout and error handling.

        Args:
            deal: The deal to evaluate

        Returns:
            EvaluationResult with relevance assessment

        Raises:
            RuntimeError: If evaluation fails completely
        """
        start_time = datetime.now()
        self.stats["total_evaluations"] += 1

        try:
            # Validate inputs
            if not self._prompt_template:
                raise RuntimeError("No prompt template available")

            deal.validate()

            # Perform evaluation with timeout
            result = await asyncio.wait_for(
                self._perform_evaluation(deal), timeout=self.evaluation_timeout
            )

            # Update statistics
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_stats(response_time, success=True)

            logger.info(
                f"Deal evaluation completed: {deal.title[:50]}... -> "
                f"{'RELEVANT' if result.is_relevant else 'NOT RELEVANT'} "
                f"(confidence: {result.confidence_score:.2f})"
            )

            return result

        except asyncio.TimeoutError:
            logger.warning(
                f"Deal evaluation timed out after {self.evaluation_timeout}s: "
                f"{deal.title[:50]}..."
            )
            self.stats["timeout_evaluations"] += 1
            self.stats["failed_evaluations"] += 1

            # Return a timeout result
            return EvaluationResult(
                is_relevant=False,
                confidence_score=0.0,
                reasoning=f"Evaluation timed out after {self.evaluation_timeout}s",
            )

        except Exception as e:
            logger.error(f"Deal evaluation failed: {e}")
            self.stats["failed_evaluations"] += 1

            # Try fallback evaluation
            try:
                result = self._fallback_evaluation(deal)
                self.stats["fallback_evaluations"] += 1
                return result
            except Exception as fallback_error:
                logger.error(f"Fallback evaluation also failed: {fallback_error}")

                # Return a failed evaluation result
                return EvaluationResult(
                    is_relevant=False,
                    confidence_score=0.0,
                    reasoning=f"Evaluation failed: {str(e)[:200]}",
                )

    async def _perform_evaluation(self, deal: Deal) -> EvaluationResult:
        """Perform the actual LLM evaluation."""
        if not self._prompt_template:
            raise RuntimeError("No prompt template available")

        return await self.llm_evaluator.evaluate_deal(deal, self._prompt_template)

    def _fallback_evaluation(self, deal: Deal) -> EvaluationResult:
        """
        Perform fallback evaluation using simple keyword matching.

        This is used when LLM evaluation fails completely.
        """
        logger.info(f"Performing fallback evaluation for: {deal.title[:50]}...")

        # Extract keywords from user criteria
        keywords = self.user_criteria.keywords.copy()
        categories = [cat.lower() for cat in self.user_criteria.categories]

        # Add category-based keywords
        if "computing" in categories:
            keywords.extend(["laptop", "computer", "pc", "cpu", "gpu"])
        if "electronics" in categories:
            keywords.extend(["phone", "tablet", "camera", "headphones"])
        if "gaming" in categories:
            keywords.extend(["game", "console", "xbox", "playstation", "nintendo"])

        # Check deal content for keywords
        deal_text = f"{deal.title} {deal.description} {deal.category}".lower()
        matches = sum(1 for keyword in keywords if keyword.lower() in deal_text)

        # Simple relevance logic
        is_relevant = matches > 0
        confidence_score = min(0.6, matches * 0.15)  # Lower confidence for fallback

        reasoning = (
            f"Fallback keyword evaluation: {matches} keyword matches found. "
            f"Keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}"
        )

        return EvaluationResult(
            is_relevant=is_relevant,
            confidence_score=confidence_score,
            reasoning=reasoning,
        )

    def _update_stats(self, response_time: float, success: bool) -> None:
        """Update evaluation statistics."""
        if success:
            self.stats["successful_evaluations"] += 1

        # Update average response time
        total_successful = self.stats["successful_evaluations"]
        if total_successful > 0:
            current_avg = self.stats["average_response_time"]
            self.stats["average_response_time"] = (
                current_avg * (total_successful - 1) + response_time
            ) / total_successful

    def reload_prompt_template(self) -> bool:
        """
        Reload the prompt template from file.

        Returns:
            True if reload was successful, False otherwise
        """
        try:
            self._prompt_template = self.prompt_manager.reload_template(
                self.user_criteria.prompt_template_path
            )
            logger.info("Prompt template reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload prompt template: {e}")
            return False

    def update_llm_config(self, new_config: LLMProviderConfig) -> bool:
        """
        Update LLM provider configuration.

        Args:
            new_config: New LLM provider configuration

        Returns:
            True if update was successful, False otherwise
        """
        try:
            self.llm_config = new_config
            self.llm_evaluator.set_llm_provider(new_config)
            logger.info("LLM configuration updated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to update LLM configuration: {e}")
            return False

    def test_evaluation_pipeline(self) -> Dict[str, Any]:
        """
        Test the complete evaluation pipeline.

        Returns:
            Dictionary with test results and status information
        """
        results = {
            "prompt_template_loaded": self._prompt_template is not None,
            "prompt_template_valid": False,
            "llm_providers_status": {},
            "overall_status": "unknown",
        }

        # Test prompt template
        if self._prompt_template:
            try:
                self.prompt_manager._validate_template(self._prompt_template)
                results["prompt_template_valid"] = True
            except Exception as e:
                results["prompt_template_error"] = str(e)

        # Test LLM providers
        try:
            provider_results = self.llm_evaluator.test_providers()
            results["llm_providers_status"] = provider_results
        except Exception as e:
            results["llm_providers_error"] = str(e)

        # Determine overall status
        if (
            results["prompt_template_loaded"]
            and results["prompt_template_valid"]
            and any(results["llm_providers_status"].values())
        ):
            results["overall_status"] = "healthy"
        elif results["prompt_template_loaded"]:
            results["overall_status"] = "degraded"
        else:
            results["overall_status"] = "failed"

        return results

    def get_evaluation_stats(self) -> Dict[str, Any]:
        """Get current evaluation statistics."""
        stats = self.stats.copy()

        # Calculate success rate
        total = stats["total_evaluations"]
        if total > 0:
            stats["success_rate"] = stats["successful_evaluations"] / total
            stats["failure_rate"] = stats["failed_evaluations"] / total
            stats["timeout_rate"] = stats["timeout_evaluations"] / total
            stats["fallback_rate"] = stats["fallback_evaluations"] / total
        else:
            stats["success_rate"] = 0.0
            stats["failure_rate"] = 0.0
            stats["timeout_rate"] = 0.0
            stats["fallback_rate"] = 0.0

        return stats

    def reset_stats(self) -> None:
        """Reset evaluation statistics."""
        self.stats = {
            "total_evaluations": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "timeout_evaluations": 0,
            "fallback_evaluations": 0,
            "average_response_time": 0.0,
        }
        logger.info("Evaluation statistics reset")
