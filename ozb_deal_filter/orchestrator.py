"""
Main application orchestrator for the OzBargain Deal Filter system.

This module provides the central coordination point for all system components,
managing their lifecycle, error handling, and graceful shutdown.
"""

import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .components.alert_formatter import AlertFormatter
from .components.deal_parser import DealParser
from .components.llm_evaluator import LLMEvaluator
from .components.message_dispatcher import MessageDispatcherFactory
from .components.rss_monitor import RSSMonitor
from .interfaces import (
    IAlertFormatter,
    IConfigurationManager,
    IDealParser,
    IFilterEngine,
    ILLMEvaluator,
    IMessageDispatcher,
    IRSSMonitor,
)
from .models.alert import FormattedAlert
from .models.config import Configuration
from .models.deal import Deal, RawDeal
from .models.delivery import DeliveryResult
from .models.evaluation import EvaluationResult
from .models.filter import FilterResult

# Import concrete implementations
from .services.config_manager import ConfigurationManager
from .services.evaluation_service import EvaluationService
from .utils.error_handling import (
    ErrorCategory,
    ErrorSeverity,
    RetryConfig,
    get_degradation_manager,
    get_error_tracker,
    with_circuit_breaker,
    with_error_handling,
)

# Import error handling and logging utilities
from .utils.logging import get_logger, setup_logging


class ApplicationOrchestrator:
    """
    Main application orchestrator that coordinates all system components.

    This class manages the lifecycle of all components, handles system startup
    and shutdown, and provides error recovery mechanisms.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the application orchestrator.

        Args:
            config_path: Path to configuration file. If None, uses default paths.
        """
        # Setup logging first
        setup_logging()
        self.logger = get_logger("orchestrator")

        self.config_path = config_path
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Error handling and monitoring
        self.error_tracker = get_error_tracker()
        self.degradation_manager = get_degradation_manager()

        # Component instances
        self._config_manager: Optional[IConfigurationManager] = None
        self._rss_monitor: Optional[IRSSMonitor] = None
        self._deal_parser: Optional[IDealParser] = None
        self._llm_evaluator: Optional[ILLMEvaluator] = None
        self._filter_engine: Optional[IFilterEngine] = None
        self._alert_formatter: Optional[IAlertFormatter] = None
        self._message_dispatcher: Optional[IMessageDispatcher] = None
        self._evaluation_service: Optional[EvaluationService] = None

        # System state
        self._config: Optional[Configuration] = None
        self._startup_time: Optional[datetime] = None
        self._component_health: Dict[str, bool] = {}
        self._error_counts: Dict[str, int] = {}

        # Setup signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        if sys.platform != "win32":
            # Unix-style signal handling
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        else:
            # Windows signal handling
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGBREAK, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        self.logger.info(
            "Received shutdown signal, initiating graceful shutdown",
            extra={"signal": signum},
        )
        asyncio.create_task(self.shutdown())

    @with_error_handling(
        component="orchestrator",
        category=ErrorCategory.SYSTEM,
        severity=ErrorSeverity.CRITICAL,
        fallback_value=False,
        suppress_exceptions=True,
    )
    async def initialize(self) -> bool:
        """
        Initialize all system components.

        Returns:
            True if initialization successful, False otherwise.
        """
        self.logger.info("Initializing OzBargain Deal Filter system...")

        # Initialize configuration manager
        if not await self._initialize_config_manager():
            return False

        # Load configuration
        if not await self._load_configuration():
            return False

        # Initialize components in dependency order
        if not await self._initialize_components():
            return False

        # Validate component connectivity
        if not await self._validate_components():
            return False

        self._startup_time = datetime.now()
        self.logger.info("System initialization completed successfully")
        return True

    @with_error_handling(
        component="orchestrator",
        category=ErrorCategory.CONFIGURATION,
        severity=ErrorSeverity.CRITICAL,
        fallback_value=False,
        suppress_exceptions=True,
    )
    async def _initialize_config_manager(self) -> bool:
        """Initialize the configuration manager."""
        self._config_manager = ConfigurationManager(self.config_path)
        self._component_health["config_manager"] = True
        self.logger.info("Configuration manager initialized")
        return True

    @with_error_handling(
        component="orchestrator",
        category=ErrorCategory.CONFIGURATION,
        severity=ErrorSeverity.CRITICAL,
        fallback_value=False,
        suppress_exceptions=True,
    )
    async def _load_configuration(self) -> bool:
        """Load and validate system configuration."""
        self._config = self._config_manager.load_configuration(
            self.config_path or "config/config.yaml"
        )
        self.logger.info("Configuration loaded and validated successfully")
        return True

    async def _initialize_components(self) -> bool:
        """Initialize all system components."""
        try:
            # Initialize RSS monitor with callback
            self._rss_monitor = RSSMonitor(
                polling_interval=self._config.polling_interval,
                max_concurrent_feeds=self._config.max_concurrent_feeds,
                max_deal_age_hours=self._config.max_deal_age_hours,
                deal_callback=self._handle_new_deals,
            )

            # Add feeds to monitor
            for feed_url in self._config.rss_feeds:
                self._rss_monitor.add_feed(feed_url)

            self._component_health["rss_monitor"] = True
            self.logger.info("RSS monitor initialized")

            # Initialize deal parser
            self._deal_parser = DealParser()
            self._component_health["deal_parser"] = True
            self.logger.info("Deal parser initialized")

            # Initialize LLM evaluator
            self._llm_evaluator = LLMEvaluator(self._config.llm_provider)
            self._component_health["llm_evaluator"] = True
            self.logger.info("LLM evaluator initialized")

            # Initialize evaluation service
            self._evaluation_service = EvaluationService(
                llm_config=self._config.llm_provider,
                user_criteria=self._config.user_criteria,
                prompts_directory="prompts",
                evaluation_timeout=30,
            )
            self._component_health["evaluation_service"] = True
            self.logger.info("Evaluation service initialized")

            # Initialize filter engine
            from .components.filter_engine import FilterEngine

            self._filter_engine = FilterEngine(self._config.user_criteria)
            self._component_health["filter_engine"] = True
            self.logger.info("Filter engine initialized")

            # Initialize alert formatter
            self._alert_formatter = AlertFormatter()
            self._component_health["alert_formatter"] = True
            self.logger.info("Alert formatter initialized")

            # Initialize message dispatcher
            platform_config = {}
            if self._config.messaging_platform.type == "telegram":
                platform_config = self._config.messaging_platform.telegram
            elif self._config.messaging_platform.type == "discord":
                platform_config = self._config.messaging_platform.discord
            elif self._config.messaging_platform.type == "slack":
                platform_config = self._config.messaging_platform.slack
            elif self._config.messaging_platform.type == "whatsapp":
                platform_config = self._config.messaging_platform.whatsapp

            self._message_dispatcher = MessageDispatcherFactory.create_dispatcher(
                self._config.messaging_platform.type, platform_config
            )
            self._component_health["message_dispatcher"] = True
            self.logger.info("Message dispatcher initialized")

            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}", exc_info=True)
            return False

    async def _validate_components(self) -> bool:
        """Validate that all components are working correctly."""
        try:
            # Test message dispatcher connection
            if not self._message_dispatcher.test_connection():
                self.logger.warning("Message dispatcher connection test failed")
                self._component_health["message_dispatcher"] = False

            # Test LLM evaluator (if available)
            try:
                test_deal = Deal(
                    id="test",
                    title="Test Deal",
                    description="Test description",
                    price=100.0,
                    original_price=200.0,
                    discount_percentage=50.0,
                    category="Test",
                    url="https://example.com",
                    timestamp=datetime.now(),
                    votes=10,
                    comments=5,
                    urgency_indicators=[],
                )

                result = await self._evaluation_service.evaluate_deal(test_deal)
                if result is None:
                    self.logger.warning("LLM evaluation test failed")
                    self._component_health["llm_evaluator"] = False

            except Exception as e:
                self.logger.warning(f"LLM evaluation test failed: {e}")
                self._component_health["llm_evaluator"] = False

            # Log component health status
            healthy_components = sum(
                1 for health in self._component_health.values() if health
            )
            total_components = len(self._component_health)

            self.logger.info(
                f"Component health check: {healthy_components}/{total_components} "
                f"components healthy"
            )

            # System can operate with some components degraded
            critical_components = ["config_manager", "rss_monitor", "deal_parser"]
            for component in critical_components:
                if not self._component_health.get(component, False):
                    self.logger.error(
                        f"Critical component '{component}' is not healthy"
                    )
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Component validation failed: {e}", exc_info=True)
            return False

    async def start(self) -> None:
        """Start the main application loop."""
        if self._running:
            self.logger.warning("System is already running")
            return

        try:
            self._running = True
            self.logger.info("Starting main application loop...")

            # Start RSS monitoring
            await self._rss_monitor.start_monitoring()

            # Main processing loop
            while self._running and not self._shutdown_event.is_set():
                try:
                    # Check for configuration changes
                    await self._check_config_reload()

                    # Health check
                    await self._health_check()

                    # Wait before next iteration
                    await asyncio.sleep(30)  # Check every 30 seconds

                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}", exc_info=True)
                    await self._handle_main_loop_error(e)

        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self._running = False

    async def _check_config_reload(self) -> None:
        """Check if configuration needs to be reloaded."""
        try:
            if self._config_manager.reload_if_changed():
                self.logger.info("Configuration reloaded")
                # Update components with new configuration if needed
                await self._update_components_config()
        except Exception as e:
            self.logger.error(f"Error checking config reload: {e}")

    async def _update_components_config(self) -> None:
        """Update components with new configuration."""
        try:
            new_config = self._config_manager.get_config()

            # Update RSS monitor feeds if changed
            if new_config.rss_feeds != self._config.rss_feeds:
                # Remove old feeds
                for feed_url in self._config.rss_feeds:
                    if feed_url not in new_config.rss_feeds:
                        self._rss_monitor.remove_feed(feed_url)

                # Add new feeds
                for feed_url in new_config.rss_feeds:
                    if feed_url not in self._config.rss_feeds:
                        self._rss_monitor.add_feed(feed_url)

                self.logger.info("RSS feeds updated")

            # Update LLM provider if changed
            if new_config.llm_provider != self._config.llm_provider:
                try:
                    self._llm_evaluator = LLMEvaluator(new_config.llm_provider)
                    self._component_health["llm_evaluator"] = True
                    self.logger.info("LLM provider updated")
                except Exception as e:
                    self.logger.error(f"Failed to update LLM provider: {e}")
                    self._component_health["llm_evaluator"] = False

            # Update messaging platform if changed
            if new_config.messaging_platform != self._config.messaging_platform:
                # Recreate message dispatcher with new config
                try:
                    platform_config = {}
                    if new_config.messaging_platform.type == "telegram":
                        platform_config = new_config.messaging_platform.telegram
                    elif new_config.messaging_platform.type == "discord":
                        platform_config = new_config.messaging_platform.discord
                    elif new_config.messaging_platform.type == "slack":
                        platform_config = new_config.messaging_platform.slack
                    elif new_config.messaging_platform.type == "whatsapp":
                        platform_config = new_config.messaging_platform.whatsapp

                    self._message_dispatcher = (
                        MessageDispatcherFactory.create_dispatcher(
                            new_config.messaging_platform.type, platform_config
                        )
                    )
                    self._component_health["message_dispatcher"] = True
                    self.logger.info("Messaging platform updated")
                except Exception as e:
                    self.logger.error(f"Failed to update messaging platform: {e}")
                    self._component_health["message_dispatcher"] = False

            self._config = new_config

        except Exception as e:
            self.logger.error(f"Error updating components config: {e}")

    async def _handle_new_deals(self, new_deals: List[RawDeal]) -> None:
        """
        Handle new deals from RSS monitor (callback method).

        This method is called by the RSS monitor when new deals are detected.
        """
        if not new_deals:
            return

        self.logger.info(
            f"Received {len(new_deals)} new deals from RSS monitor",
            extra={"deal_count": len(new_deals)},
        )

        # Process deals asynchronously
        await self._process_deals_async(new_deals)

    async def _process_deals_async(self, new_deals: List[RawDeal]) -> None:
        """Process new deals asynchronously."""
        for raw_deal in new_deals:
            try:
                await self._process_single_deal(raw_deal)
            except Exception as e:
                self.logger.error(
                    f"Error processing deal: {e}",
                    extra={"deal_title": raw_deal.title},
                    exc_info=True,
                )
                self._increment_error_count("deal_processing")

    @with_error_handling(
        component="orchestrator",
        category=ErrorCategory.DATA_VALIDATION,
        severity=ErrorSeverity.MEDIUM,
        retry_config=RetryConfig(max_attempts=2, base_delay=1.0),
    )
    async def _process_single_deal(self, raw_deal: RawDeal) -> None:
        """Process a single deal through the entire pipeline."""
        # Parse the deal
        deal = self._deal_parser.parse_deal(raw_deal)
        if not self._deal_parser.validate_deal(deal):
            self.logger.warning(
                "Deal validation failed", extra={"deal_title": deal.title}
            )
            return

        # Evaluate with LLM
        evaluation_result = None
        if self._component_health.get("llm_evaluator", False):
            try:
                evaluation_result = await self._evaluation_service.evaluate_deal(deal)
            except Exception as e:
                self.logger.warning(
                    "LLM evaluation failed, falling back to keyword matching",
                    extra={"deal_title": deal.title, "error": str(e)},
                )
                self._component_health["llm_evaluator"] = False
                self.degradation_manager.degrade_component(
                    "llm_evaluator",
                    f"LLM evaluation failed: {str(e)}",
                    "Using keyword-based fallback evaluation",
                    ErrorSeverity.MEDIUM,
                )

        # If LLM evaluation failed, use basic keyword matching
        if evaluation_result is None:
            evaluation_result = self._fallback_evaluation(deal)

        # Skip if not relevant
        if not evaluation_result.is_relevant:
            self.logger.debug(
                "Deal not relevant",
                extra={
                    "deal_title": deal.title,
                    "reasoning": evaluation_result.reasoning,
                },
            )
            return

        # Apply filters (price, discount, authenticity)
        filter_result = await self._apply_filters(deal, evaluation_result)
        if not filter_result.passes_filters:
            self.logger.debug(
                "Deal filtered out",
                extra={
                    "deal_title": deal.title,
                    "price_match": filter_result.price_match,
                    "authenticity_score": filter_result.authenticity_score,
                },
            )
            return

        # Format alert
        formatted_alert = self._alert_formatter.format_alert(deal, filter_result)

        # Send alert
        if self._component_health.get("message_dispatcher", False):
            delivery_result = self._message_dispatcher.send_alert(formatted_alert)
            if delivery_result.success:
                self.logger.info(
                    "Alert sent successfully",
                    extra={
                        "deal_title": deal.title,
                        "urgency": filter_result.urgency_level.value,
                        "delivery_time": delivery_result.delivery_time.isoformat(),
                    },
                )
            else:
                self.logger.error(
                    "Failed to send alert",
                    extra={
                        "deal_title": deal.title,
                        "error": delivery_result.error_message,
                    },
                )
                self._increment_error_count("message_delivery")
        else:
            self.logger.warning(
                "Message dispatcher unavailable, skipping alert",
                extra={"deal_title": deal.title},
            )

    def _fallback_evaluation(self, deal: Deal) -> EvaluationResult:
        """Provide fallback evaluation when LLM is unavailable."""
        # Simple keyword-based evaluation
        keywords = self._config.user_criteria.keywords
        categories = self._config.user_criteria.categories

        # Check if deal matches any keywords
        title_lower = deal.title.lower()
        desc_lower = deal.description.lower()

        keyword_match = any(
            keyword.lower() in title_lower or keyword.lower() in desc_lower
            for keyword in keywords
        )

        # Check if deal matches any categories
        category_match = deal.category in categories if categories else True

        is_relevant = keyword_match and category_match
        confidence = 0.6 if is_relevant else 0.3

        return EvaluationResult(
            is_relevant=is_relevant,
            confidence_score=confidence,
            reasoning="Fallback keyword/category matching (LLM unavailable)",
        )

    async def _apply_filters(
        self, deal: Deal, evaluation: EvaluationResult
    ) -> FilterResult:
        """Apply price, discount, and authenticity filters using FilterEngine."""
        if self._filter_engine:
            return self._filter_engine.apply_filters(deal, evaluation)
        else:
            # Fallback to basic filtering if FilterEngine is not available
            from .models.filter import FilterResult, UrgencyLevel

            passes_price = True
            if (
                self._config.user_criteria.max_price is not None
                and deal.price is not None
            ):
                passes_price = deal.price <= self._config.user_criteria.max_price

            passes_discount = True
            if (
                self._config.user_criteria.min_discount_percentage is not None
                and deal.discount_percentage is not None
            ):
                passes_discount = (
                    deal.discount_percentage
                    >= self._config.user_criteria.min_discount_percentage
                )

            # Basic authenticity score
            authenticity_score = 0.7
            if deal.votes is not None and deal.comments is not None:
                authenticity_score = min(1.0, (deal.votes + deal.comments) / 20.0)

            passes_authenticity = (
                authenticity_score >= self._config.user_criteria.min_authenticity_score
            )

            # Determine urgency
            urgency = UrgencyLevel.LOW
            if deal.discount_percentage and deal.discount_percentage > 50:
                urgency = UrgencyLevel.HIGH
            elif (
                "limited time" in deal.title.lower()
                or "expires" in deal.description.lower()
            ):
                urgency = UrgencyLevel.URGENT

            return FilterResult(
                passes_filters=passes_price and passes_discount and passes_authenticity,
                price_match=passes_price,
                authenticity_score=authenticity_score,
                urgency_level=urgency,
            )

    async def _health_check(self) -> None:
        """Perform periodic health checks on components."""
        try:
            # Check RSS monitor health
            self._component_health["rss_monitor"] = self._rss_monitor.is_monitoring

            # Check message dispatcher health
            if self._component_health.get("message_dispatcher", False):
                try:
                    if not self._message_dispatcher.test_connection():
                        self._component_health["message_dispatcher"] = False
                        self.logger.warning("Message dispatcher health check failed")
                except Exception:
                    self._component_health["message_dispatcher"] = False

            # Log health status periodically
            unhealthy_components = [
                name for name, health in self._component_health.items() if not health
            ]

            if unhealthy_components:
                self.logger.warning(f"Unhealthy components: {unhealthy_components}")

        except Exception as e:
            self.logger.error(f"Error in health check: {e}")

    def _increment_error_count(self, error_type: str) -> None:
        """Increment error count for a specific error type."""
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

        # Log if error count is getting high
        if self._error_counts[error_type] % 10 == 0:
            self.logger.warning(
                f"High error count for {error_type}: {self._error_counts[error_type]}"
            )

    async def _handle_main_loop_error(self, error: Exception) -> None:
        """Handle errors in the main loop."""
        self._increment_error_count("main_loop")

        # If too many errors, consider shutting down
        if self._error_counts.get("main_loop", 0) > 50:
            self.logger.critical("Too many main loop errors, initiating shutdown")
            await self.shutdown()
        else:
            # Wait before retrying
            await asyncio.sleep(30)

    async def shutdown(self) -> None:
        """Gracefully shutdown the system."""
        if not self._running:
            return

        self.logger.info("Initiating graceful shutdown...")
        self._running = False
        self._shutdown_event.set()

        try:
            # Stop RSS monitoring
            if self._rss_monitor:
                await self._rss_monitor.stop_monitoring()
                self.logger.info("RSS monitor stopped")

            # Components don't need explicit closing
            self.logger.info("All components stopped")

            # Log final statistics
            uptime = datetime.now() - self._startup_time if self._startup_time else None
            self.logger.info(f"System shutdown complete. Uptime: {uptime}")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status information."""
        return {
            "running": self._running,
            "startup_time": self._startup_time.isoformat()
            if self._startup_time
            else None,
            "uptime": str(datetime.now() - self._startup_time)
            if self._startup_time
            else None,
            "component_health": self._component_health.copy(),
            "error_counts": self._error_counts.copy(),
            "config_loaded": self._config is not None,
        }

    async def run(self) -> None:
        """Run the complete application lifecycle."""
        try:
            # Initialize system
            if not await self.initialize():
                self.logger.error("System initialization failed")
                return

            # Start main loop
            await self.start()

        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Unexpected error in application: {e}", exc_info=True)
        finally:
            await self.shutdown()
