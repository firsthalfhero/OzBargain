"""
LLM client implementations for different providers.

This module provides concrete implementations for various LLM providers
including local Docker-hosted models and external API services.
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Union

import docker
import requests
from docker.errors import DockerException

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
class LLMRequest:
    """Request data for LLM evaluation."""

    prompt: str
    deal: Deal
    max_tokens: int = 500
    temperature: float = 0.1
    timeout: int = 30


@dataclass
class LLMResponse:
    """Response from LLM evaluation."""

    content: str
    provider: str
    model: str
    tokens_used: Optional[int] = None
    response_time: Optional[float] = None


class BaseLLMClient(ABC):
    """Base class for all LLM clients."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass

    @abstractmethod
    async def evaluate(self, request: LLMRequest) -> LLMResponse:
        """Evaluate a deal using the LLM provider."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to the LLM provider."""
        pass

    def parse_evaluation_response(self, response_content: str) -> EvaluationResult:
        """Parse LLM response into structured evaluation result."""
        try:
            # Try to parse as JSON first
            if response_content.strip().startswith("{"):
                data = json.loads(response_content)
                return EvaluationResult(
                    is_relevant=bool(data.get("is_relevant", False)),
                    confidence_score=float(data.get("confidence_score", 0.0)),
                    reasoning=str(data.get("reasoning", "No reasoning provided")),
                )

            # Fallback to text parsing
            lines = response_content.strip().split("\n")
            is_relevant = False
            confidence_score = 0.0
            reasoning = response_content

            for line in lines:
                line = line.strip().lower()
                if "relevant: true" in line or "is_relevant: true" in line:
                    is_relevant = True
                elif "relevant: false" in line or "is_relevant: false" in line:
                    is_relevant = False
                elif "confidence:" in line or "confidence_score:" in line:
                    try:
                        score_str = line.split(":")[1].strip()
                        confidence_score = float(score_str)
                    except (IndexError, ValueError):
                        pass

            return EvaluationResult(
                is_relevant=is_relevant,
                confidence_score=max(0.0, min(1.0, confidence_score)),
                reasoning=reasoning[:1000],  # Limit reasoning length
            )

        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            # Return conservative fallback
            return EvaluationResult(
                is_relevant=False,
                confidence_score=0.0,
                reasoning=f"Failed to parse response: {str(e)}",
            )


class LocalLLMClient(BaseLLMClient):
    """Client for local Docker-hosted LLM models (Ollama)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.docker_client = None
        self.container = None
        import os
        # Use config first, then environment variable, then localhost fallback
        self.base_url = config.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = config["model"]
        self.docker_image = config["docker_image"]

    def _validate_config(self) -> None:
        """Validate local LLM configuration."""
        required_keys = ["model", "docker_image"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Local LLM config missing required key: {key}")

    def _ensure_docker_container(self) -> bool:
        """Ensure Docker container is running."""
        try:
            if not self.docker_client:
                self.docker_client = docker.from_env()

            # Check if container is already running
            try:
                containers = self.docker_client.containers.list(
                    filters={"ancestor": self.docker_image}
                )
                if containers:
                    self.container = containers[0]
                    if self.container.status == "running":
                        return True
            except DockerException:
                pass

            # Start new container
            logger.info(f"Starting Docker container for {self.docker_image}")
            self.container = self.docker_client.containers.run(
                self.docker_image,
                ports={"11434/tcp": 11434},
                detach=True,
                remove=True,
                name=f"ollama-{int(time.time())}",
            )

            # Wait for container to be ready
            for _ in range(30):  # Wait up to 30 seconds
                if self.test_connection():
                    return True
                time.sleep(1)

            logger.error("Docker container failed to start properly")
            return False

        except DockerException as e:
            logger.error(f"Docker error: {e}")
            return False

    async def evaluate(self, request: LLMRequest) -> LLMResponse:
        """Evaluate using local Ollama model."""
        if not self._ensure_docker_container():
            raise RuntimeError("Failed to start local LLM container")

        start_time = time.time()

        try:
            # Prepare Ollama API request
            payload = {
                "model": self.model,
                "prompt": request.prompt,
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            }

            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=request.timeout
            )
            response.raise_for_status()

            result = response.json()
            response_time = time.time() - start_time

            return LLMResponse(
                content=result.get("response", ""),
                provider="local",
                model=self.model,
                response_time=response_time,
            )

        except requests.RequestException as e:
            logger.error(f"Local LLM request failed: {e}")
            raise RuntimeError(f"Local LLM evaluation failed: {e}")

    def test_connection(self) -> bool:
        """Test connection to local Ollama instance."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI API services."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.model = config["model"]
        self.base_url = config.get("base_url", "https://api.openai.com/v1")

    def _validate_config(self) -> None:
        """Validate OpenAI configuration."""
        required_keys = ["api_key", "model"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"OpenAI config missing required key: {key}")

    async def evaluate(self, request: LLMRequest) -> LLMResponse:
        """Evaluate using OpenAI API."""
        start_time = time.time()

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": request.prompt}],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=request.timeout,
            )
            response.raise_for_status()

            result = response.json()
            response_time = time.time() - start_time

            content = result["choices"][0]["message"]["content"]
            tokens_used = result.get("usage", {}).get("total_tokens")

            return LLMResponse(
                content=content,
                provider="openai",
                model=self.model,
                tokens_used=tokens_used,
                response_time=response_time,
            )

        except requests.RequestException as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise RuntimeError(f"OpenAI evaluation failed: {e}")

    def test_connection(self) -> bool:
        """Test connection to OpenAI API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.base_url}/models", headers=headers, timeout=10
            )
            return response.status_code == 200
        except requests.RequestException:
            return False


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.model = config["model"]
        self.base_url = config.get("base_url", "https://api.anthropic.com/v1")

    def _validate_config(self) -> None:
        """Validate Anthropic configuration."""
        required_keys = ["api_key", "model"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Anthropic config missing required key: {key}")

    async def evaluate(self, request: LLMRequest) -> LLMResponse:
        """Evaluate using Anthropic Claude API."""
        start_time = time.time()

        try:
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            payload = {
                "model": self.model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            }

            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=request.timeout,
            )
            response.raise_for_status()

            result = response.json()
            response_time = time.time() - start_time

            content = result["content"][0]["text"]
            tokens_used = result.get("usage", {}).get("input_tokens", 0) + result.get(
                "usage", {}
            ).get("output_tokens", 0)

            return LLMResponse(
                content=content,
                provider="anthropic",
                model=self.model,
                tokens_used=tokens_used,
                response_time=response_time,
            )

        except requests.RequestException as e:
            logger.error(f"Anthropic API request failed: {e}")
            raise RuntimeError(f"Anthropic evaluation failed: {e}")

    def test_connection(self) -> bool:
        """Test connection to Anthropic API."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            # Use a minimal request to test connection
            payload = {
                "model": self.model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "Hi"}],
            }

            response = requests.post(
                f"{self.base_url}/messages", headers=headers, json=payload, timeout=10
            )
            return response.status_code == 200
        except requests.RequestException:
            return False


class LLMClientFactory:
    """Factory for creating LLM clients based on configuration."""

    @staticmethod
    def create_client(provider_config: LLMProviderConfig) -> BaseLLMClient:
        """Create appropriate LLM client based on configuration."""
        if provider_config.type == "local":
            return LocalLLMClient(provider_config.local)
        elif provider_config.type == "api":
            api_config = provider_config.api
            provider = api_config["provider"]

            if provider == "openai":
                return OpenAIClient(api_config)
            elif provider == "anthropic":
                return AnthropicClient(api_config)
            else:
                raise ValueError(f"Unsupported API provider: {provider}")
        else:
            raise ValueError(f"Unsupported LLM provider type: {provider_config.type}")
