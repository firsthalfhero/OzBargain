"""
Error handling utilities for the OzBargain Deal Filter system.

This module provides comprehensive error handling, recovery mechanisms,
and graceful degradation strategies for system components.
"""

import asyncio
import functools
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .logging import get_logger


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    NETWORK = "network"
    CONFIGURATION = "configuration"
    PARSING = "parsing"
    LLM_EVALUATION = "llm_evaluation"
    MESSAGE_DELIVERY = "message_delivery"
    DATA_VALIDATION = "data_validation"
    SYSTEM = "system"
    EXTERNAL_SERVICE = "external_service"


@dataclass
class ErrorInfo:
    """Information about an error occurrence."""

    timestamp: datetime
    component: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    traceback: str
    context: Dict[str, Any]
    recovery_attempted: bool = False
    recovery_successful: bool = False


class ErrorTracker:
    """
    Tracks errors and provides statistics for monitoring.
    """

    def __init__(self, max_errors: int = 1000):
        """
        Initialize error tracker.

        Args:
            max_errors: Maximum number of errors to keep in memory
        """
        self.max_errors = max_errors
        self.errors: List[ErrorInfo] = []
        self.error_counts: Dict[str, int] = {}
        self.component_errors: Dict[str, List[ErrorInfo]] = {}
        self.logger = get_logger("error_tracker")

    def record_error(
        self,
        component: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        message: str,
        exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ErrorInfo:
        """
        Record an error occurrence.

        Args:
            component: Component where error occurred
            category: Error category
            severity: Error severity
            message: Error message
            exception: Exception object if available
            context: Additional context information

        Returns:
            ErrorInfo object
        """
        error_info = ErrorInfo(
            timestamp=datetime.now(),
            component=component,
            category=category,
            severity=severity,
            message=message,
            exception_type=type(exception).__name__ if exception else "Unknown",
            traceback=traceback.format_exc() if exception else "",
            context=context or {},
        )

        # Add to error list
        self.errors.append(error_info)
        if len(self.errors) > self.max_errors:
            self.errors.pop(0)

        # Update counts
        error_key = f"{component}.{category.value}.{severity.value}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Update component errors
        if component not in self.component_errors:
            self.component_errors[component] = []
        self.component_errors[component].append(error_info)

        # Keep only recent errors per component
        if len(self.component_errors[component]) > 100:
            self.component_errors[component].pop(0)

        # Log the error
        self.logger.error(
            f"Error recorded: {message}",
            extra={
                "component": component,
                "category": category.value,
                "severity": severity.value,
                "exception_type": error_info.exception_type,
                "context": context,
            },
            exc_info=exception is not None,
        )

        return error_info

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)

        recent_errors_hour = [e for e in self.errors if e.timestamp >= last_hour]
        recent_errors_day = [e for e in self.errors if e.timestamp >= last_day]

        return {
            "total_errors": len(self.errors),
            "errors_last_hour": len(recent_errors_hour),
            "errors_last_day": len(recent_errors_day),
            "error_counts": self.error_counts.copy(),
            "component_error_counts": {
                component: len(errors)
                for component, errors in self.component_errors.items()
            },
            "severity_breakdown": {
                severity.value: len([e for e in self.errors if e.severity == severity])
                for severity in ErrorSeverity
            },
            "category_breakdown": {
                category.value: len([e for e in self.errors if e.category == category])
                for category in ErrorCategory
            },
        }

    def get_component_errors(self, component: str, limit: int = 10) -> List[ErrorInfo]:
        """Get recent errors for a specific component."""
        component_errors = self.component_errors.get(component, [])
        return component_errors[-limit:]

    def clear_old_errors(self, older_than_days: int = 7):
        """Clear errors older than specified days."""
        cutoff = datetime.now() - timedelta(days=older_than_days)

        # Filter main error list
        self.errors = [e for e in self.errors if e.timestamp >= cutoff]

        # Filter component errors
        for component in self.component_errors:
            self.component_errors[component] = [
                e for e in self.component_errors[component] if e.timestamp >= cutoff
            ]


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff
        self.jitter = jitter


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    Prevents cascading failures by temporarily disabling calls
    to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
        self.logger = get_logger("circuit_breaker")

    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to a function."""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.logger.info("Circuit breaker moving to HALF_OPEN state")
                else:
                    raise Exception("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True

        return (
            datetime.now() - self.last_failure_time
        ).seconds >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.logger.info("Circuit breaker reset to CLOSED state")

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


# Global error tracker instance
_error_tracker: Optional[ErrorTracker] = None


def get_error_tracker() -> ErrorTracker:
    """Get global error tracker instance."""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker


def with_error_handling(
    component: str,
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    retry_config: Optional[RetryConfig] = None,
    fallback_value: Any = None,
    suppress_exceptions: bool = False,
):
    """
    Decorator for comprehensive error handling.

    Args:
        component: Component name
        category: Error category
        severity: Error severity
        retry_config: Retry configuration
        fallback_value: Value to return on failure
        suppress_exceptions: Whether to suppress exceptions
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            error_tracker = get_error_tracker()
            logger = get_logger(component)

            attempts = 1
            if retry_config:
                attempts = retry_config.max_attempts

            last_exception = None

            for attempt in range(attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    if attempt > 0:
                        logger.info(f"Function succeeded on attempt {attempt + 1}")

                    return result

                except Exception as e:
                    last_exception = e

                    # Record error
                    error_info = error_tracker.record_error(
                        component=component,
                        category=category,
                        severity=severity,
                        message=f"Error in {func.__name__}: {str(e)}",
                        exception=e,
                        context={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": attempts,
                        },
                    )

                    # If this is the last attempt or no retry config
                    if attempt == attempts - 1 or not retry_config:
                        if suppress_exceptions:
                            logger.warning(
                                f"Suppressing exception in {func.__name__}: {str(e)}"
                            )
                            return fallback_value
                        else:
                            raise e

                    # Calculate delay for retry
                    if retry_config:
                        delay = retry_config.base_delay
                        if retry_config.exponential_backoff:
                            delay = min(
                                retry_config.base_delay * (2**attempt),
                                retry_config.max_delay,
                            )

                        if retry_config.jitter:
                            import random

                            delay *= 0.5 + random.random() * 0.5

                        logger.info(
                            f"Retrying {func.__name__} in {delay:.2f} seconds (attempt {attempt + 1}/{attempts})"
                        )
                        await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if suppress_exceptions:
                return fallback_value
            else:
                raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, create a simple wrapper
            error_tracker = get_error_tracker()
            logger = get_logger(component)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_tracker.record_error(
                    component=component,
                    category=category,
                    severity=severity,
                    message=f"Error in {func.__name__}: {str(e)}",
                    exception=e,
                    context={"function": func.__name__},
                )

                if suppress_exceptions:
                    logger.warning(
                        f"Suppressing exception in {func.__name__}: {str(e)}"
                    )
                    return fallback_value
                else:
                    raise e

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = Exception,
):
    """
    Decorator to apply circuit breaker pattern.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type that triggers circuit breaker
    """
    circuit_breaker = CircuitBreaker(
        failure_threshold, recovery_timeout, expected_exception
    )
    return circuit_breaker


class GracefulDegradation:
    """
    Manages graceful degradation of system functionality.

    Allows components to continue operating with reduced functionality
    when dependencies fail.
    """

    def __init__(self):
        self.degraded_components: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger("graceful_degradation")

    def degrade_component(
        self,
        component: str,
        reason: str,
        fallback_behavior: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ):
        """
        Mark a component as degraded.

        Args:
            component: Component name
            reason: Reason for degradation
            fallback_behavior: Description of fallback behavior
            severity: Degradation severity
        """
        self.degraded_components[component] = {
            "reason": reason,
            "fallback_behavior": fallback_behavior,
            "severity": severity.value,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(
            f"Component degraded: {component}",
            extra={
                "component": component,
                "reason": reason,
                "fallback_behavior": fallback_behavior,
                "severity": severity.value,
            },
        )

    def restore_component(self, component: str):
        """Restore a component from degraded state."""
        if component in self.degraded_components:
            del self.degraded_components[component]
            self.logger.info(f"Component restored: {component}")

    def is_degraded(self, component: str) -> bool:
        """Check if a component is in degraded state."""
        return component in self.degraded_components

    def get_degradation_info(self, component: str) -> Optional[Dict[str, Any]]:
        """Get degradation information for a component."""
        return self.degraded_components.get(component)

    def get_all_degraded(self) -> Dict[str, Dict[str, Any]]:
        """Get all degraded components."""
        return self.degraded_components.copy()


# Global graceful degradation manager
_degradation_manager: Optional[GracefulDegradation] = None


def get_degradation_manager() -> GracefulDegradation:
    """Get global graceful degradation manager."""
    global _degradation_manager
    if _degradation_manager is None:
        _degradation_manager = GracefulDegradation()
    return _degradation_manager
