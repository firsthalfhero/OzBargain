"""
Unit tests for LLM evaluation components.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ozb_deal_filter.components.llm_evaluator import (
    APILLMClient,
    LLMEvaluator,
    LLMProviderType,
    LLMResponse,
    LocalLLMClient,
)
from ozb_deal_filter.models.config import LLMProviderConfig
from ozb_deal_filter.models.deal import Deal
from ozb_deal_filter.models.evaluation import EvaluationResult


@pytest.fixture
def sample_deal():
    """Sample deal for testing."""
    return Deal(
        id="test-deal-1",
        title="Gaming Laptop 50% Off",
        description="High-performance gaming laptop with RTX 4060",
        price=1200.0,
        original_price=2400.0,
        discount_percentage=50.0,
        category="Computing",
        url="https://example.com/deal",
        timestamp=datetime.now(),
        votes=25,
        comments=8,
        urgency_indicators=["limited time"],
    )


@pytest.fixture
def local_llm_config():
    """Local LLM configuration for testing."""
    return {
        "model": "llama2",
        "docker_image": "ollama/ollama",
        "base_url": "http://localhost:11434",
        "timeout": 30,
    }


@pytest.fixture
def api_llm_config():
    """API LLM configuration for testing."""
    return {
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "api_key": "test-api-key",
        "timeout": 30,
    }


@pytest.fixture
def llm_provider_config_local():
    """LLM provider configuration for local setup."""
    return LLMProviderConfig(
        type="local",
        local={
            "model": "llama2",
            "docker_image": "ollama/ollama",
            "base_url": "http://localhost:11434",
        },
    )


@pytest.fixture
def llm_provider_config_api():
    """LLM provider configuration for API setup."""
    return LLMProviderConfig(
        type="api",
        api={"provider": "openai", "model": "gpt-3.5-turbo", "api_key": "test-api-key"},
    )


class TestLocalLLMClient:
    """Test cases for LocalLLMClient."""

    def test_init(self, local_llm_config):
        """Test LocalLLMClient initialization."""
        client = LocalLLMClient(local_llm_config)

        assert client.model == "llama2"
        assert client.docker_image == "ollama/ollama"
        assert client.base_url == "http://localhost:11434"
        assert client.timeout == 30

    @pytest.mark.asyncio
    @patch("time.time")
    @patch("requests.post")
    async def test_evaluate_success(self, mock_post, mock_time, local_llm_config):
        """Test successful evaluation with local LLM."""
        # Mock time to simulate response time
        mock_time.side_effect = [1000.0, 1001.5]  # 1.5 second response time

        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "response": "RELEVANT - This is a great gaming laptop deal",
            "eval_count": 150,
        }
        mock_post.return_value = mock_response

        client = LocalLLMClient(local_llm_config)
        result = await client.evaluate("Test prompt")

        assert isinstance(result, LLMResponse)
        assert result.content == "RELEVANT - This is a great gaming laptop deal"
        assert result.provider == "local"
        assert result.model == "llama2"
        assert result.tokens_used == 150
        assert result.response_time == 1.5

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/generate"

        payload = call_args[1]["json"]
        assert payload["model"] == "llama2"
        assert payload["prompt"] == "Test prompt"
        assert payload["stream"] is False

    @pytest.mark.asyncio
    @patch("requests.post")
    async def test_evaluate_request_failure(self, mock_post, local_llm_config):
        """Test evaluation with request failure."""
        mock_post.side_effect = Exception("Connection failed")

        client = LocalLLMClient(local_llm_config)

        with pytest.raises(RuntimeError, match="Local LLM evaluation error"):
            await client.evaluate("Test prompt")

    @patch("requests.get")
    def test_test_connection_success(self, mock_get, local_llm_config):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [{"name": "llama2"}, {"name": "mistral"}]
        }
        mock_get.return_value = mock_response

        client = LocalLLMClient(local_llm_config)
        result = client.test_connection()

        assert result is True
        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)

    @patch("requests.get")
    def test_test_connection_model_not_found(self, mock_get, local_llm_config):
        """Test connection test when model is not available."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "models": [{"name": "mistral"}, {"name": "codellama"}]
        }
        mock_get.return_value = mock_response

        client = LocalLLMClient(local_llm_config)
        result = client.test_connection()

        assert result is False

    @patch("requests.get")
    def test_test_connection_failure(self, mock_get, local_llm_config):
        """Test connection test failure."""
        mock_get.side_effect = Exception("Connection failed")

        client = LocalLLMClient(local_llm_config)
        result = client.test_connection()

        assert result is False


class TestAPILLMClient:
    """Test cases for APILLMClient."""

    def test_init_openai(self, api_llm_config):
        """Test APILLMClient initialization with OpenAI."""
        with patch("openai.OpenAI") as mock_openai:
            client = APILLMClient(api_llm_config)

            assert client.provider == "openai"
            assert client.model == "gpt-3.5-turbo"
            assert client.api_key == "test-api-key"
            mock_openai.assert_called_once_with(api_key="test-api-key")

    def test_init_anthropic(self):
        """Test APILLMClient initialization with Anthropic."""
        config = {
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "api_key": "test-api-key",
            "timeout": 30,
        }

        with patch("anthropic.Anthropic") as mock_anthropic:
            client = APILLMClient(config)

            assert client.provider == "anthropic"
            assert client.model == "claude-3-sonnet-20240229"
            mock_anthropic.assert_called_once_with(api_key="test-api-key")

    def test_init_unsupported_provider(self):
        """Test initialization with unsupported provider."""
        config = {
            "provider": "unsupported",
            "model": "test-model",
            "api_key": "test-key",
        }

        with pytest.raises(ValueError, match="Unsupported API provider"):
            APILLMClient(config)

    @pytest.mark.asyncio
    @patch("time.time")
    async def test_evaluate_openai_success(self, mock_time, api_llm_config):
        """Test successful OpenAI evaluation."""
        # Mock time to simulate response time
        mock_time.side_effect = [1000.0, 1001.0]  # 1 second response time

        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "RELEVANT - Great deal"
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            client = APILLMClient(api_llm_config)
            result = await client.evaluate("Test prompt")

        assert isinstance(result, LLMResponse)
        assert result.content == "RELEVANT - Great deal"
        assert result.provider == "openai"
        assert result.model == "gpt-3.5-turbo"
        assert result.tokens_used == 100
        assert result.response_time == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_anthropic_success(self):
        """Test successful Anthropic evaluation."""
        config = {
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "api_key": "test-api-key",
            "timeout": 30,
        }

        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].text = "NOT RELEVANT - Wrong category"
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 25
        mock_client.messages.create.return_value = mock_response

        with patch("anthropic.Anthropic", return_value=mock_client):
            client = APILLMClient(config)
            result = await client.evaluate("Test prompt")

        assert isinstance(result, LLMResponse)
        assert result.content == "NOT RELEVANT - Wrong category"
        assert result.provider == "anthropic"
        assert result.model == "claude-3-sonnet-20240229"
        assert result.tokens_used == 75

    @pytest.mark.asyncio
    async def test_evaluate_failure(self, api_llm_config):
        """Test evaluation failure."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch("openai.OpenAI", return_value=mock_client):
            client = APILLMClient(api_llm_config)

            with pytest.raises(RuntimeError, match="API LLM evaluation failed"):
                await client.evaluate("Test prompt")

    def test_test_connection_openai_success(self, api_llm_config):
        """Test successful OpenAI connection test."""
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock()

        with patch("openai.OpenAI", return_value=mock_client):
            client = APILLMClient(api_llm_config)
            result = client.test_connection()

        assert result is True

    def test_test_connection_failure(self, api_llm_config):
        """Test connection test failure."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch("openai.OpenAI", return_value=mock_client):
            client = APILLMClient(api_llm_config)
            result = client.test_connection()

        assert result is False


class TestLLMEvaluator:
    """Test cases for LLMEvaluator."""

    def test_init_local_provider(self, llm_provider_config_local):
        """Test LLMEvaluator initialization with local provider."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient"
        ) as mock_local:
            evaluator = LLMEvaluator(llm_provider_config_local)

            assert evaluator.primary_provider is not None
            assert evaluator.fallback_provider is None
            mock_local.assert_called_once()

    def test_init_api_provider(self, llm_provider_config_api):
        """Test LLMEvaluator initialization with API provider."""
        with patch("ozb_deal_filter.components.llm_evaluator.APILLMClient") as mock_api:
            evaluator = LLMEvaluator(llm_provider_config_api)

            assert evaluator.primary_provider is not None
            assert evaluator.fallback_provider is None
            mock_api.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_deal_success(self, llm_provider_config_local, sample_deal):
        """Test successful deal evaluation."""
        mock_provider = AsyncMock()
        mock_response = LLMResponse(
            content='{"is_relevant": true, "confidence_score": 0.8, "reasoning": "Great gaming deal"}',
            provider="local",
            model="llama2",
            response_time=1.5,
        )
        mock_provider.evaluate.return_value = mock_response

        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient",
            return_value=mock_provider,
        ):
            evaluator = LLMEvaluator(llm_provider_config_local)
            result = await evaluator.evaluate_deal(
                sample_deal, "Evaluate this deal: {title}"
            )

        assert isinstance(result, EvaluationResult)
        assert result.is_relevant is True
        assert result.confidence_score == 0.8
        assert result.reasoning == "Great gaming deal"

    @pytest.mark.asyncio
    async def test_evaluate_deal_natural_language_response(
        self, llm_provider_config_local, sample_deal
    ):
        """Test evaluation with natural language response."""
        mock_provider = AsyncMock()
        mock_response = LLMResponse(
            content="Yes, this is definitely a relevant deal for gaming enthusiasts",
            provider="local",
            model="llama2",
            response_time=1.5,
        )
        mock_provider.evaluate.return_value = mock_response

        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient",
            return_value=mock_provider,
        ):
            evaluator = LLMEvaluator(llm_provider_config_local)
            result = await evaluator.evaluate_deal(
                sample_deal, "Evaluate this deal: {title}"
            )

        assert isinstance(result, EvaluationResult)
        assert result.is_relevant is True
        assert 0.0 <= result.confidence_score <= 1.0
        assert "Yes, this is definitely a relevant deal" in result.reasoning

    @pytest.mark.asyncio
    async def test_evaluate_deal_fallback_provider(self, sample_deal):
        """Test evaluation with fallback provider."""
        # Setup config with both providers
        config = LLMProviderConfig(
            type="local",
            local={"model": "llama2", "docker_image": "ollama/ollama"},
            api={"provider": "openai", "model": "gpt-3.5-turbo", "api_key": "test-key"},
        )

        # Primary provider fails
        mock_primary = AsyncMock()
        mock_primary.evaluate.side_effect = Exception("Primary failed")

        # Fallback provider succeeds
        mock_fallback = AsyncMock()
        mock_response = LLMResponse(
            content="RELEVANT - Good deal",
            provider="openai",
            model="gpt-3.5-turbo",
            response_time=1.0,
        )
        mock_fallback.evaluate.return_value = mock_response

        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient",
            return_value=mock_primary,
        ), patch(
            "ozb_deal_filter.components.llm_evaluator.APILLMClient",
            return_value=mock_fallback,
        ):
            evaluator = LLMEvaluator(config)
            result = await evaluator.evaluate_deal(sample_deal, "Evaluate: {title}")

        assert isinstance(result, EvaluationResult)
        assert result.is_relevant is True

    @pytest.mark.asyncio
    async def test_evaluate_deal_keyword_fallback(
        self, llm_provider_config_local, sample_deal
    ):
        """Test evaluation with keyword fallback when all providers fail."""
        mock_provider = AsyncMock()
        mock_provider.evaluate.side_effect = Exception("Provider failed")

        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient",
            return_value=mock_provider,
        ):
            evaluator = LLMEvaluator(llm_provider_config_local)
            result = await evaluator.evaluate_deal(
                sample_deal, "Look for electronics deals"
            )

        assert isinstance(result, EvaluationResult)
        assert "Fallback keyword evaluation" in result.reasoning
        assert result.confidence_score <= 0.6

    def test_format_prompt(self, llm_provider_config_local, sample_deal):
        """Test prompt formatting with deal information."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            template = "Deal: {title} - Price: {price} - Category: {category}"
            formatted = evaluator._format_prompt(sample_deal, template)

            expected = (
                "Deal: Gaming Laptop 50% Off - Price: 1200.0 - Category: Computing"
            )
            assert formatted == expected

    def test_extract_relevance_positive(self, llm_provider_config_local):
        """Test relevance extraction with positive indicators."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            content = "Yes, this is a relevant deal that matches your interests"
            result = evaluator._extract_relevance(content)

            assert result is True

    def test_extract_relevance_negative(self, llm_provider_config_local):
        """Test relevance extraction with negative indicators."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            content = "No, this deal is not relevant to your criteria"
            result = evaluator._extract_relevance(content)

            assert result is False

    def test_extract_confidence_high(self, llm_provider_config_local):
        """Test confidence extraction with high confidence indicators."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            content = "I am very confident this is a great deal"
            result = evaluator._extract_confidence(content)

            assert result == 0.9

    def test_extract_confidence_medium(self, llm_provider_config_local):
        """Test confidence extraction with medium confidence indicators."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            content = "This is likely a good deal for you"
            result = evaluator._extract_confidence(content)

            assert result == 0.7

    def test_extract_confidence_low(self, llm_provider_config_local):
        """Test confidence extraction with low confidence indicators."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            content = "Maybe this could be interesting"
            result = evaluator._extract_confidence(content)

            assert result == 0.4

    def test_keyword_fallback_evaluation(self, llm_provider_config_local, sample_deal):
        """Test keyword-based fallback evaluation."""
        with patch("ozb_deal_filter.components.llm_evaluator.LocalLLMClient"):
            evaluator = LLMEvaluator(llm_provider_config_local)

            # Template with electronics keyword
            template = "Look for electronics deals: {title}"
            result = evaluator._keyword_fallback_evaluation(sample_deal, template)

            assert isinstance(result, EvaluationResult)
            assert (
                result.is_relevant is False
            )  # "Computing" doesn't match "electronics" exactly
            assert "Fallback keyword evaluation" in result.reasoning

    def test_set_llm_provider(self, llm_provider_config_local, llm_provider_config_api):
        """Test updating LLM provider configuration."""
        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient"
        ) as mock_local, patch(
            "ozb_deal_filter.components.llm_evaluator.APILLMClient"
        ) as mock_api:
            evaluator = LLMEvaluator(llm_provider_config_local)
            mock_local.assert_called_once()

            # Update to API provider
            evaluator.set_llm_provider(llm_provider_config_api)
            mock_api.assert_called_once()

    def test_test_providers(self, llm_provider_config_local):
        """Test provider connection testing."""
        mock_provider = Mock()
        mock_provider.test_connection.return_value = True

        with patch(
            "ozb_deal_filter.components.llm_evaluator.LocalLLMClient",
            return_value=mock_provider,
        ):
            evaluator = LLMEvaluator(llm_provider_config_local)
            results = evaluator.test_providers()

            assert "primary" in results
            assert results["primary"] is True
            assert "fallback" not in results  # No fallback configured
