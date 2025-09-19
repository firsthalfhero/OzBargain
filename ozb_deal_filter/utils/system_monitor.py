"""
System monitoring utilities for health checks and metrics collection.

This module provides utilities for monitoring system health, collecting
performance metrics, and validating system behavior.
"""

import time
import psutil
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .logging import get_logger


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Component health information."""
    name: str
    status: HealthStatus
    last_check: datetime
    error_message: Optional[str] = None
    check_count: int = 0
    failure_count: int = 0


@dataclass
class PerformanceMetric:
    """Performance metric data."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System-wide metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    uptime_seconds: float
    timestamp: datetime


class HealthChecker:
    """Component health checking utility."""

    def __init__(self):
        self.logger = get_logger("health_checker")
        self.component_health: Dict[str, ComponentHealth] = {}
        self.health_checks: Dict[str, Callable] = {}

    def register_component(
        self, 
        name: str, 
        health_check_func: Callable[[], bool]
    ) -> None:
        """Register a component for health checking."""
        self.health_checks[name] = health_check_func
        self.component_health[name] = ComponentHealth(
            name=name,
            status=HealthStatus.UNKNOWN,
            last_check=datetime.now(timezone.utc),
        )
        self.logger.info(f"Registered health check for component: {name}")

    async def check_component_health(self, component_name: str) -> HealthStatus:
        """Check health of a specific component."""
        if component_name not in self.health_checks:
            self.logger.warning(f"No health check registered for: {component_name}")
            return HealthStatus.UNKNOWN

        component = self.component_health[component_name]
        component.check_count += 1
        component.last_check = datetime.now(timezone.utc)

        try:
            # Run health check
            if asyncio.iscoroutinefunction(self.health_checks[component_name]):
                is_healthy = await self.health_checks[component_name]()
            else:
                is_healthy = self.health_checks[component_name]()

            if is_healthy:
                component.status = HealthStatus.HEALTHY
                component.error_message = None
            else:
                component.status = HealthStatus.UNHEALTHY
                component.failure_count += 1
                component.error_message = "Health check returned False"

        except Exception as e:
            component.status = HealthStatus.UNHEALTHY
            component.failure_count += 1
            component.error_message = str(e)
            self.logger.error(
                f"Health check failed for {component_name}: {e}",
                exc_info=True
            )

        return component.status

    async def check_all_components(self) -> Dict[str, HealthStatus]:
        """Check health of all registered components."""
        results = {}
        
        for component_name in self.health_checks.keys():
            results[component_name] = await self.check_component_health(component_name)

        return results

    def get_component_health(self, component_name: str) -> Optional[ComponentHealth]:
        """Get health information for a component."""
        return self.component_health.get(component_name)

    def get_all_health_info(self) -> Dict[str, ComponentHealth]:
        """Get health information for all components."""
        return self.component_health.copy()

    def get_overall_health_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.component_health:
            return HealthStatus.UNKNOWN

        statuses = [comp.status for comp in self.component_health.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN


class MetricsCollector:
    """Performance metrics collection utility."""

    def __init__(self, max_metrics: int = 1000):
        self.logger = get_logger("metrics_collector")
        self.metrics: List[PerformanceMetric] = []
        self.max_metrics = max_metrics
        self.start_time = time.time()

    def record_metric(
        self, 
        name: str, 
        value: float, 
        unit: str = "", 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(timezone.utc),
            tags=tags or {},
        )

        self.metrics.append(metric)

        # Limit metrics storage
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics:]

        self.logger.debug(f"Recorded metric: {name}={value}{unit}")

    def record_timing(self, name: str, duration_seconds: float) -> None:
        """Record a timing metric."""
        self.record_metric(name, duration_seconds, "seconds")

    def record_counter(self, name: str, count: int = 1) -> None:
        """Record a counter metric."""
        self.record_metric(name, count, "count")

    def get_metrics(
        self, 
        name_filter: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[PerformanceMetric]:
        """Get metrics with optional filtering."""
        filtered_metrics = self.metrics

        if name_filter:
            filtered_metrics = [
                m for m in filtered_metrics 
                if name_filter in m.name
            ]

        if since:
            filtered_metrics = [
                m for m in filtered_metrics 
                if m.timestamp >= since
            ]

        return filtered_metrics

    def get_metric_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a specific metric."""
        metrics = [m for m in self.metrics if m.name == name]
        
        if not metrics:
            return {}

        values = [m.value for m in metrics]
        
        import statistics
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        process = psutil.Process()
        
        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=psutil.virtual_memory().percent,
            memory_used_mb=process.memory_info().rss / 1024 / 1024,
            disk_usage_percent=psutil.disk_usage('/').percent,
            uptime_seconds=time.time() - self.start_time,
            timestamp=datetime.now(timezone.utc),
        )


class AlertDeliveryValidator:
    """Validator for alert delivery performance and reliability."""

    def __init__(self):
        self.logger = get_logger("delivery_validator")
        self.delivery_attempts: List[Dict[str, Any]] = []
        self.success_count = 0
        self.failure_count = 0

    def record_delivery_attempt(
        self,
        alert_id: str,
        platform: str,
        success: bool,
        delivery_time: datetime,
        latency_ms: float,
        error_message: Optional[str] = None
    ) -> None:
        """Record an alert delivery attempt."""
        attempt = {
            "alert_id": alert_id,
            "platform": platform,
            "success": success,
            "delivery_time": delivery_time,
            "latency_ms": latency_ms,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc),
        }

        self.delivery_attempts.append(attempt)

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        self.logger.info(
            f"Alert delivery {'succeeded' if success else 'failed'}: "
            f"platform={platform}, latency={latency_ms:.1f}ms"
        )

    def get_delivery_stats(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get delivery statistics."""
        attempts = self.delivery_attempts
        
        if since:
            attempts = [
                a for a in attempts 
                if a["timestamp"] >= since
            ]

        if not attempts:
            return {
                "total_attempts": 0,
                "success_rate": 0.0,
                "average_latency_ms": 0.0,
                "failure_count": 0,
            }

        successful_attempts = [a for a in attempts if a["success"]]
        failed_attempts = [a for a in attempts if not a["success"]]

        latencies = [a["latency_ms"] for a in successful_attempts]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "total_attempts": len(attempts),
            "successful_attempts": len(successful_attempts),
            "failed_attempts": len(failed_attempts),
            "success_rate": len(successful_attempts) / len(attempts) * 100,
            "average_latency_ms": avg_latency,
            "min_latency_ms": min(latencies) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
            "failure_reasons": [a["error_message"] for a in failed_attempts if a["error_message"]],
        }

    def validate_delivery_requirements(self) -> Dict[str, bool]:
        """Validate delivery against requirements."""
        stats = self.get_delivery_stats()
        
        return {
            "success_rate_ok": stats["success_rate"] >= 95.0,  # 95% success rate
            "latency_ok": stats["average_latency_ms"] <= 5000.0,  # 5 second average
            "has_deliveries": stats["total_attempts"] > 0,
        }


class SystemStartupValidator:
    """Validator for system startup requirements."""

    def __init__(self):
        self.logger = get_logger("startup_validator")
        self.startup_checks: List[Dict[str, Any]] = []

    def record_startup_check(
        self,
        check_name: str,
        success: bool,
        duration_ms: float,
        error_message: Optional[str] = None
    ) -> None:
        """Record a startup validation check."""
        check = {
            "check_name": check_name,
            "success": success,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc),
        }

        self.startup_checks.append(check)

        self.logger.info(
            f"Startup check {'passed' if success else 'failed'}: "
            f"{check_name} ({duration_ms:.1f}ms)"
        )

    def validate_startup_requirements(self) -> Dict[str, Any]:
        """Validate startup against requirements."""
        if not self.startup_checks:
            return {
                "all_checks_passed": False,
                "total_startup_time_ms": 0.0,
                "failed_checks": [],
                "startup_time_ok": False,
            }

        failed_checks = [c for c in self.startup_checks if not c["success"]]
        total_time = sum(c["duration_ms"] for c in self.startup_checks)

        return {
            "all_checks_passed": len(failed_checks) == 0,
            "total_checks": len(self.startup_checks),
            "passed_checks": len(self.startup_checks) - len(failed_checks),
            "failed_checks": [c["check_name"] for c in failed_checks],
            "total_startup_time_ms": total_time,
            "startup_time_ok": total_time <= 60000.0,  # 60 seconds max
            "error_messages": [c["error_message"] for c in failed_checks if c["error_message"]],
        }

    def get_startup_summary(self) -> str:
        """Get a human-readable startup summary."""
        validation = self.validate_startup_requirements()
        
        if validation["all_checks_passed"]:
            return (
                f"✅ Startup successful: {validation['passed_checks']} checks passed "
                f"in {validation['total_startup_time_ms']:.0f}ms"
            )
        else:
            return (
                f"❌ Startup issues: {len(validation['failed_checks'])} checks failed. "
                f"Failed: {', '.join(validation['failed_checks'])}"
            )


# Timing decorator for automatic metrics collection
def timed_operation(metric_name: str, collector: Optional[MetricsCollector] = None):
    """Decorator to automatically time operations and record metrics."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if collector:
                    collector.record_timing(metric_name, duration)
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if collector:
                    collector.record_timing(metric_name, duration)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Context manager for timing operations
class TimingContext:
    """Context manager for timing operations."""

    def __init__(self, metric_name: str, collector: MetricsCollector):
        self.metric_name = metric_name
        self.collector = collector
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.record_timing(self.metric_name, duration)


# Global instances (can be configured per application)
_global_health_checker = None
_global_metrics_collector = None
_global_delivery_validator = None
_global_startup_validator = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance."""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
    return _global_health_checker


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    return _global_metrics_collector


def get_delivery_validator() -> AlertDeliveryValidator:
    """Get global delivery validator instance."""
    global _global_delivery_validator
    if _global_delivery_validator is None:
        _global_delivery_validator = AlertDeliveryValidator()
    return _global_delivery_validator


def get_startup_validator() -> SystemStartupValidator:
    """Get global startup validator instance."""
    global _global_startup_validator
    if _global_startup_validator is None:
        _global_startup_validator = SystemStartupValidator()
    return _global_startup_validator