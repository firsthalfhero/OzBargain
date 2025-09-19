"""
Tests for error handling utilities.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from ozb_deal_filter.utils.error_handling import (
    ErrorTracker,
    ErrorCategory,
    ErrorSeverity,
    ErrorInfo,
    RetryConfig,
    CircuitBreaker,
    CircuitBreakerState,
    GracefulDegradation,
    with_error_handling,
    with_circuit_breaker,
    get_error_tracker,
    get_degradation_manager,
)


class TestErrorTracker:
    """Test cases for ErrorTracker."""

    def test_record_error(self):
        """Test error recording."""
        tracker = ErrorTracker()

        error_info = tracker.record_error(
            component="test_component",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            message="Test error message",
            context={"key": "value"},
        )

        assert isinstance(error_info, ErrorInfo)
        assert error_info.component == "test_component"
        assert error_info.category == ErrorCategory.NETWORK
        assert error_info.severity == ErrorSeverity.HIGH
        assert error_info.message == "Test error message"
        assert error_info.context == {"key": "value"}

        assert len(tracker.errors) == 1
        assert tracker.errors[0] == error_info

    def test_record_error_with_exception(self):
        """Test error recording with exception."""
        tracker = ErrorTracker()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            error_info = tracker.record_error(
                component="test_component",
                category=ErrorCategory.DATA_VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                message="Validation failed",
                exception=e,
            )

        assert error_info.exception_type == "ValueError"
        assert "Test exception" in error_info.traceback

    def test_error_counts(self):
        """Test error count tracking."""
        tracker = ErrorTracker()

        # Record multiple errors
        for i in range(3):
            tracker.record_error(
                component="test_component",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.LOW,
                message=f"Error {i}",
            )

        # Record different type of error
        tracker.record_error(
            component="test_component",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.HIGH,
            message="Parse error",
        )

        error_key_network = "test_component.network.low"
        error_key_parsing = "test_component.parsing.high"

        assert tracker.error_counts[error_key_network] == 3
        assert tracker.error_counts[error_key_parsing] == 1

    def test_get_error_stats(self):
        """Test error statistics."""
        tracker = ErrorTracker()

        # Record some errors
        tracker.record_error(
            component="comp1",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            message="Error 1",
        )

        tracker.record_error(
            component="comp2",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.LOW,
            message="Error 2",
        )

        stats = tracker.get_error_stats()

        assert stats["total_errors"] == 2
        assert stats["severity_breakdown"]["high"] == 1
        assert stats["severity_breakdown"]["low"] == 1
        assert stats["category_breakdown"]["network"] == 1
        assert stats["category_breakdown"]["parsing"] == 1

    def test_component_errors(self):
        """Test component-specific error tracking."""
        tracker = ErrorTracker()

        # Record errors for different components
        tracker.record_error(
            component="comp1",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            message="Comp1 error",
        )

        tracker.record_error(
            component="comp2",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.LOW,
            message="Comp2 error",
        )

        comp1_errors = tracker.get_component_errors("comp1")
        comp2_errors = tracker.get_component_errors("comp2")

        assert len(comp1_errors) == 1
        assert len(comp2_errors) == 1
        assert comp1_errors[0].message == "Comp1 error"
        assert comp2_errors[0].message == "Comp2 error"

    def test_clear_old_errors(self):
        """Test clearing old errors."""
        tracker = ErrorTracker()

        # Create an old error by manually setting timestamp
        old_error = ErrorInfo(
            timestamp=datetime.now() - timedelta(days=10),
            component="test",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            message="Old error",
            exception_type="Exception",
            traceback="",
            context={},
        )

        # Create a recent error
        recent_error = tracker.record_error(
            component="test",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            message="Recent error",
        )

        # Manually add old error
        tracker.errors.insert(0, old_error)
        tracker.component_errors["test"].insert(0, old_error)

        assert len(tracker.errors) == 2

        # Clear old errors
        tracker.clear_old_errors(older_than_days=7)

        assert len(tracker.errors) == 1
        assert tracker.errors[0].message == "Recent error"


class TestRetryConfig:
    """Test cases for RetryConfig."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_backoff is True
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_backoff=False,
            jitter=False,
        )

        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_backoff is False
        assert config.jitter is False


class TestCircuitBreaker:
    """Test cases for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        circuit_breaker = CircuitBreaker(failure_threshold=2)

        @circuit_breaker
        async def test_function():
            return "success"

        result = await test_function()
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        circuit_breaker = CircuitBreaker(failure_threshold=2)

        @circuit_breaker
        async def failing_function():
            raise Exception("Test failure")

        # First failure
        with pytest.raises(Exception):
            await failing_function()
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # Second failure - should open circuit
        with pytest.raises(Exception):
            await failing_function()
        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # Third call should fail immediately due to open circuit
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await failing_function()

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        call_count = 0

        @circuit_breaker
        async def sometimes_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First failure")
            return "success"

        # First call fails, opens circuit
        with pytest.raises(Exception):
            await sometimes_failing_function()
        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout (0 seconds in test)
        await asyncio.sleep(0.1)

        # Next call should succeed and close circuit
        result = await sometimes_failing_function()
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED


class TestWithErrorHandling:
    """Test cases for with_error_handling decorator."""

    @pytest.mark.asyncio
    async def test_successful_async_function(self):
        """Test error handling decorator with successful async function."""

        @with_error_handling(
            component="test", category=ErrorCategory.NETWORK, severity=ErrorSeverity.LOW
        )
        async def test_function():
            return "success"

        result = await test_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_failing_async_function_with_suppression(self):
        """Test error handling decorator with failing async function and suppression."""

        @with_error_handling(
            component="test",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            fallback_value="fallback",
            suppress_exceptions=True,
        )
        async def failing_function():
            raise Exception("Test failure")

        result = await failing_function()
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_failing_async_function_without_suppression(self):
        """Test error handling decorator with failing async function without suppression."""

        @with_error_handling(
            component="test", category=ErrorCategory.NETWORK, severity=ErrorSeverity.LOW
        )
        async def failing_function():
            raise ValueError("Test failure")

        with pytest.raises(ValueError):
            await failing_function()

    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test retry mechanism in error handling decorator."""
        call_count = 0

        @with_error_handling(
            component="test",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            retry_config=RetryConfig(max_attempts=3, base_delay=0.1),
            fallback_value="fallback",
            suppress_exceptions=True,
        )
        async def sometimes_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Failure {call_count}")
            return "success"

        result = await sometimes_failing_function()
        assert result == "success"
        assert call_count == 3

    def test_sync_function_error_handling(self):
        """Test error handling decorator with synchronous function."""

        @with_error_handling(
            component="test",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.MEDIUM,
            fallback_value="fallback",
            suppress_exceptions=True,
        )
        def failing_sync_function():
            raise Exception("Sync failure")

        result = failing_sync_function()
        assert result == "fallback"


class TestGracefulDegradation:
    """Test cases for GracefulDegradation."""

    def test_degrade_component(self):
        """Test component degradation."""
        degradation = GracefulDegradation()

        degradation.degrade_component(
            component="test_component",
            reason="Service unavailable",
            fallback_behavior="Using cached data",
            severity=ErrorSeverity.MEDIUM,
        )

        assert degradation.is_degraded("test_component")

        info = degradation.get_degradation_info("test_component")
        assert info["reason"] == "Service unavailable"
        assert info["fallback_behavior"] == "Using cached data"
        assert info["severity"] == "medium"

    def test_restore_component(self):
        """Test component restoration."""
        degradation = GracefulDegradation()

        # Degrade component
        degradation.degrade_component(
            component="test_component", reason="Test", fallback_behavior="Test fallback"
        )

        assert degradation.is_degraded("test_component")

        # Restore component
        degradation.restore_component("test_component")

        assert not degradation.is_degraded("test_component")
        assert degradation.get_degradation_info("test_component") is None

    def test_get_all_degraded(self):
        """Test getting all degraded components."""
        degradation = GracefulDegradation()

        degradation.degrade_component("comp1", "reason1", "fallback1")
        degradation.degrade_component("comp2", "reason2", "fallback2")

        all_degraded = degradation.get_all_degraded()

        assert len(all_degraded) == 2
        assert "comp1" in all_degraded
        assert "comp2" in all_degraded
        assert all_degraded["comp1"]["reason"] == "reason1"
        assert all_degraded["comp2"]["reason"] == "reason2"


class TestGlobalInstances:
    """Test cases for global instance management."""

    def test_get_error_tracker(self):
        """Test global error tracker instance."""
        tracker1 = get_error_tracker()
        tracker2 = get_error_tracker()

        assert tracker1 is tracker2  # Should be same instance

    def test_get_degradation_manager(self):
        """Test global degradation manager instance."""
        manager1 = get_degradation_manager()
        manager2 = get_degradation_manager()

        assert manager1 is manager2  # Should be same instance
