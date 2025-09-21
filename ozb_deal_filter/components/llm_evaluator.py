"""
LLM evaluation components for deal assessment.

This module provides LLM provider implementations for evaluating deals
against user criteria using both local Docker-hosted models and external
API services.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

import anthropic
import openai
import requests

from ..models.config import LLMProviderConfig
from ..models.deal import Deal
from ..models.evaluation import EvaluationResult

logger = logging.getLogger(__name__)


class LLMProviderType(Enum):
    """Supported LLM provider types."""

    LOCAL = "local"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


@dataclass
class LLMResponse:
    """Raw response from LLM provider."""

    content: str
    provider: str
    model: str
    response_time: float
    tokens_used: Optional[int] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.timeout = config.get("timeout", 30)

    @abstractmethod
    async def evaluate(self, prompt: str) -> LLMResponse:
        """Evaluate a prompt and return the response."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to the LLM provider."""
        pass


class LocalLLMClient(LLMProvider):
    """Client for Docker-hosted local LLM models (Ollama)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        import os

        # Use config first, then environment variable, then localhost fallback
        self.base_url = config.get("base_url") or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.model = config["model"]
        self.docker_image = config["docker_image"]
        # Use timeout from config, with a higher default for local LLM
        self.timeout = config.get("timeout", 60)

    async def evaluate(self, prompt: str) -> LLMResponse:
        """Evaluate prompt using local Ollama model."""
        start_time = time.time()

        try:
            # Prepare request payload for Ollama API
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temp for consistency
                    "top_p": 0.9,
                    "num_predict": 100,  # Shorter response for faster processing
                    "num_ctx": 2048,  # Smaller context window
                },
            }

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()
            response_time = time.time() - start_time

            return LLMResponse(
                content=result["response"],
                provider="local",
                model=self.model,
                response_time=response_time,
                tokens_used=result.get("eval_count"),
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Local LLM request failed: {e}")
            raise RuntimeError(f"Local LLM evaluation failed: {e}")
        except Exception as e:
            logger.error(f"Local LLM evaluation error: {e}")
            raise RuntimeError(f"Local LLM evaluation error: {e}")

    def test_connection(self) -> bool:
        """Test connection to local Ollama instance."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()

            # Check if our model is available
            models = response.json().get("models", [])
            model_names = [model["name"] for model in models]

            if self.model not in model_names:
                logger.warning(
                    f"Model {self.model} not found in available models: "
                    f"{model_names}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Local LLM connection test failed: {e}")
            return False


class APILLMClient(LLMProvider):
    """Client for external API-based LLM services."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = config["provider"]
        self.model = config["model"]
        self.api_key = config.get("api_key")

        # Initialize provider-specific clients
        self.client: Union[openai.OpenAI, anthropic.Anthropic]
        self.openai_client: Optional[openai.OpenAI] = None
        self.anthropic_client: Optional[anthropic.Anthropic] = None

        if self.provider == "openai":
            self.client = openai.OpenAI(api_key=self.api_key)
            self.openai_client = self.client
        elif self.provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.anthropic_client = self.client
        else:
            raise ValueError(f"Unsupported API provider: {self.provider}")

    async def evaluate(self, prompt: str) -> LLMResponse:
        """Evaluate prompt using external API service."""
        start_time = time.time()

        try:
            if self.provider == "openai":
                return await self._evaluate_openai(prompt, start_time)
            elif self.provider == "anthropic":
                return await self._evaluate_anthropic(prompt, start_time)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        except Exception as e:
            logger.error(f"API LLM evaluation failed: {e}")
            raise RuntimeError(f"API LLM evaluation failed: {e}")

    async def _evaluate_openai(self, prompt: str, start_time: float) -> LLMResponse:
        """Evaluate using OpenAI API."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")

        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that evaluates deals "
                        "based on user criteria."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
            timeout=self.timeout,
        )

        response_time = time.time() - start_time
        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return LLMResponse(
            content=content,
            provider="openai",
            model=self.model,
            response_time=response_time,
            tokens_used=tokens_used,
        )

    async def _evaluate_anthropic(self, prompt: str, start_time: float) -> LLMResponse:
        """Evaluate using Anthropic API."""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized")

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
            timeout=self.timeout,
        )

        response_time = time.time() - start_time

        return LLMResponse(
            content=response.content[0].text,
            provider="anthropic",
            model=self.model,
            response_time=response_time,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

    def test_connection(self) -> bool:
        """Test connection to API service."""
        try:
            if self.provider == "openai" and self.openai_client:
                # Test with a simple completion
                self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Test"}],
                    max_tokens=1,
                    timeout=5,
                )
            elif self.provider == "anthropic" and self.anthropic_client:
                # Test with a simple message
                self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "Test"}],
                    timeout=5,
                )

            return True

        except Exception as e:
            logger.error(f"API LLM connection test failed: {e}")
            return False


class LLMEvaluator:
    """Main LLM evaluator with provider switching and fallback mechanisms."""

    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self.primary_provider: Optional[LLMProvider] = None
        self.fallback_provider: Optional[LLMProvider] = None
        self._setup_providers()

    def _setup_providers(self) -> None:
        """Setup primary and fallback LLM providers."""
        try:
            if self.config.type == "local" and self.config.local:
                self.primary_provider = LocalLLMClient(self.config.local)
                logger.info(
                    f"Configured local LLM provider: " f"{self.config.local['model']}"
                )

                # Setup API fallback if configured
                if self.config.api:
                    self.fallback_provider = APILLMClient(self.config.api)
                    logger.info(
                        f"Configured API fallback provider: "
                        f"{self.config.api['provider']}"
                    )

            elif self.config.type == "api" and self.config.api:
                self.primary_provider = APILLMClient(self.config.api)
                logger.info(
                    f"Configured API LLM provider: " f"{self.config.api['provider']}"
                )

                # Setup local fallback if configured
                if self.config.local:
                    self.fallback_provider = LocalLLMClient(self.config.local)
                    logger.info(
                        f"Configured local fallback provider: "
                        f"{self.config.local['model']}"
                    )

        except Exception as e:
            logger.error(f"Failed to setup LLM providers: {e}")
            raise RuntimeError(f"LLM provider setup failed: {e}")
            raise RuntimeError(f"LLM provider setup failed: {e}")

    async def evaluate_deal(self, deal: Deal, prompt_template: str) -> EvaluationResult:
        """Evaluate a deal against user criteria using LLM."""
        # Format the prompt with deal information
        formatted_prompt = self._format_prompt(deal, prompt_template)

        # Try primary provider first
        try:
            if self.primary_provider:
                response = await self.primary_provider.evaluate(formatted_prompt)
                return self._parse_evaluation_response(response)
        except Exception as e:
            logger.warning(f"Primary LLM provider failed: {e}")

            # Try fallback provider
            if self.fallback_provider:
                try:
                    logger.info("Attempting fallback LLM provider")
                    response = await self.fallback_provider.evaluate(formatted_prompt)
                    return self._parse_evaluation_response(response)
                except Exception as fallback_error:
                    logger.error(f"Fallback LLM provider also failed: {fallback_error}")

            # If both providers fail, return a default evaluation
            logger.error("All LLM providers failed, using keyword-based fallback")
            return self._keyword_fallback_evaluation(deal, prompt_template)

    def _format_prompt(self, deal: Deal, template: str) -> str:
        """Format prompt template with deal information."""
        return template.format(
            title=deal.title,
            description=deal.description,
            price=deal.price or "Not specified",
            original_price=deal.original_price or "Not specified",
            discount_percentage=deal.discount_percentage or "Not specified",
            category=deal.category,
            url=deal.url,
            votes=deal.votes or 0,
            comments=deal.comments or 0,
            urgency_indicators=", ".join(deal.urgency_indicators)
            if deal.urgency_indicators
            else "None",
        )

    def _parse_evaluation_response(self, response: LLMResponse) -> EvaluationResult:
        """Parse LLM response into EvaluationResult."""
        content = response.content.strip()

        # Try to parse structured response (JSON format)
        try:
            if content.startswith("{") and content.endswith("}"):
                data = json.loads(content)
                return EvaluationResult(
                    is_relevant=bool(data.get("is_relevant", False)),
                    confidence_score=float(data.get("confidence_score", 0.5)),
                    reasoning=str(data.get("reasoning", "No reasoning provided")),
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Parse natural language response
        is_relevant = self._extract_relevance(content)
        confidence_score = self._extract_confidence(content)

        return EvaluationResult(
            is_relevant=is_relevant,
            confidence_score=confidence_score,
            reasoning=content[:1000],  # Limit reasoning length
        )

    def _extract_relevance(self, content: str) -> bool:
        """Extract relevance decision from natural language response."""
        content_lower = content.lower()

        # Look for positive indicators
        positive_indicators = [
            "yes",
            "relevant",
            "matches",
            "interested",
            "good deal",
            "recommend",
        ]
        negative_indicators = [
            "no",
            "not relevant",
            "doesn't match",
            "not interested",
            "poor deal",
            "skip",
        ]

        positive_score = sum(
            1 for indicator in positive_indicators if indicator in content_lower
        )
        negative_score = sum(
            1 for indicator in negative_indicators if indicator in content_lower
        )

        return positive_score > negative_score

    def _extract_confidence(self, content: str) -> float:
        """Extract confidence score from natural language response."""
        content_lower = content.lower()

        # Look for confidence indicators
        if any(
            word in content_lower
            for word in ["very confident", "definitely", "absolutely"]
        ):
            return 0.9
        elif any(word in content_lower for word in ["confident", "likely", "probably"]):
            return 0.7
        elif any(word in content_lower for word in ["maybe", "possibly", "uncertain"]):
            return 0.4
        else:
            return 0.5  # Default confidence

    def _keyword_fallback_evaluation(
        self, deal: Deal, prompt_template: str
    ) -> EvaluationResult:
        """Fallback evaluation using simple keyword matching."""
        # Extract keywords from prompt template (this is a simplified approach)
        keywords = []
        if "electronics" in prompt_template.lower():
            keywords.append("electronics")
        if "computing" in prompt_template.lower():
            keywords.append("computing")
        if "gaming" in prompt_template.lower():
            keywords.append("gaming")

        # Check if deal matches any keywords
        deal_text = f"{deal.title} {deal.description} {deal.category}".lower()
        matches = sum(1 for keyword in keywords if keyword in deal_text)

        is_relevant = matches > 0
        # Lower confidence for fallback
        confidence_score = min(0.6, matches * 0.2)

        return EvaluationResult(
            is_relevant=is_relevant,
            confidence_score=confidence_score,
            reasoning=f"Fallback keyword evaluation: {matches} matches found",
        )

    def set_llm_provider(self, provider_config: LLMProviderConfig) -> None:
        """Update LLM provider configuration."""
        self.config = provider_config
        self._setup_providers()
        logger.info("LLM provider configuration updated")

    def test_providers(self) -> Dict[str, bool]:
        """Test all configured providers."""
        results = {}

        if self.primary_provider:
            results["primary"] = self.primary_provider.test_connection()

        if self.fallback_provider:
            results["fallback"] = self.fallback_provider.test_connection()

        return results
