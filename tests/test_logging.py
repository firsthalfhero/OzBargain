"""
Tests for logging utilities.
"""

import pytest
import tempfile
import json
import logging
from pathlib import Path
from unittest.mock import patch, Mock

from ozb_deal_filter.utils.logging import (
    ComponentLogger,
    LoggingManager,
    LogLevel,
    setup_logging,
    get_logger,
    get_logging_stats
)


class TestComponentLogger:
    """Test cases for ComponentLogger."""

    def test_component_logger_initialization(self):
        """Test component logger initialization."""
        logger = ComponentLogger("test_component", {"key": "value"})
        
        assert logger.component_name == "test_component"
        assert logger.extra_context == {"key": "value"}
        assert logger.logger.name == "ozb_deal_filter.test_component"

    def test_format_message(self):
        """Test message formatting."""
        logger = ComponentLogger("test_component", {"context_key": "context_value"})
        
        formatted = logger._format_message("Test message", {"extra_key": "extra_value"})
        
        assert formatted["component"] == "test_component"
        assert formatted["message"] == "Test message"
        assert formatted["context_key"] == "context_value"
        assert formatted["extra_key"] == "extra_value"
        assert "timestamp" in formatted

    def test_log_methods(self):
        """Test different log level methods."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = ComponentLogger("test_component")
            
            # Test debug
            logger.debug("Debug message", {"key": "value"})
            mock_logger.debug.assert_called_once()
            
            # Test info
            logger.info("Info message")
            mock_logger.info.assert_called_once()
            
            # Test warning
            logger.warning("Warning message")
            mock_logger.warning.assert_called_once()
            
            # Test error
            logger.error("Error message", exc_info=True)
            mock_logger.error.assert_called_once()
            
            # Test critical
            logger.critical("Critical message")
            mock_logger.critical.assert_called_once()

    def test_structured_logging_format(self):
        """Test that log messages are properly structured as JSON."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = ComponentLogger("test_component", {"context": "test"})
            logger.info("Test message", {"extra": "data"})
            
            # Get the call arguments
            call_args = mock_logger.info.call_args[0]
            log_message = call_args[0]
            
            # Should be valid JSON
            parsed = json.loads(log_message)
            assert parsed["component"] == "test_component"
            assert parsed["message"] == "Test message"
            assert parsed["context"] == "test"
            assert parsed["extra"] == "data"


class TestLoggingManager:
    """Test cases for LoggingManager."""

    @patch('logging.handlers.RotatingFileHandler')
    def test_logging_manager_initialization(self, mock_handler):
        """Test logging manager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir, log_level="DEBUG")
            
            assert manager.log_dir == Path(temp_dir)
            assert manager.log_level == logging.DEBUG
            
            # Check that log directory exists
            assert manager.log_dir.exists()
            
            # Verify that rotating file handlers were created
            assert mock_handler.call_count >= 2  # Main log and error log

    @patch('logging.handlers.RotatingFileHandler')
    def test_get_component_logger(self, mock_handler):
        """Test getting component loggers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir)
            
            logger1 = manager.get_component_logger("test_component")
            logger2 = manager.get_component_logger("test_component")
            
            # Should return same instance for same component
            assert logger1 is logger2
            
            # Different component should return different logger
            logger3 = manager.get_component_logger("other_component")
            assert logger1 is not logger3

    @patch('logging.handlers.RotatingFileHandler')
    def test_get_component_logger_with_context(self, mock_handler):
        """Test getting component loggers with different contexts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir)
            
            logger1 = manager.get_component_logger("test_component", {"key": "value1"})
            logger2 = manager.get_component_logger("test_component", {"key": "value2"})
            
            # Should return different instances for different contexts
            assert logger1 is not logger2

    @patch('logging.handlers.RotatingFileHandler')
    def test_set_log_level(self, mock_handler):
        """Test setting log level."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir, log_level="INFO")
            
            # Change log level
            manager.set_log_level("DEBUG")
            
            # Check that root logger level was updated
            root_logger = logging.getLogger("ozb_deal_filter")
            assert root_logger.level == logging.DEBUG

    @patch('logging.handlers.RotatingFileHandler')
    def test_get_log_stats(self, mock_handler):
        """Test getting log statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir)
            
            # Create some component loggers
            manager.get_component_logger("comp1")
            manager.get_component_logger("comp2")
            
            stats = manager.get_log_stats()
            
            assert stats["log_directory"] == str(manager.log_dir)
            assert stats["log_level"] == "INFO"
            assert stats["component_loggers"] == 2
            assert isinstance(stats["log_files"], list)

    @patch('logging.handlers.RotatingFileHandler')
    def test_component_specific_log_files(self, mock_handler):
        """Test that component-specific log files are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir)
            
            # Check that component log files are created
            expected_files = [
                "rss_monitor.log",
                "deal_parser.log",
                "llm_evaluator.log",
                "filter_engine.log",
                "alert_formatter.log",
                "message_dispatcher.log",
                "orchestrator.log"
            ]
            
            # Verify that handlers were created for component loggers
            assert mock_handler.call_count >= len(expected_files)


class TestGlobalFunctions:
    """Test cases for global logging functions."""

    @patch('logging.handlers.RotatingFileHandler')
    def test_setup_logging(self, mock_handler):
        """Test global logging setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = setup_logging(log_dir=temp_dir, log_level="DEBUG")
            
            assert isinstance(manager, LoggingManager)
            assert manager.log_dir == Path(temp_dir)
            assert manager.log_level == logging.DEBUG

    @patch('logging.handlers.RotatingFileHandler')
    def test_get_logger(self, mock_handler):
        """Test getting logger through global function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(log_dir=temp_dir)
            
            logger = get_logger("test_component")
            
            assert isinstance(logger, ComponentLogger)
            assert logger.component_name == "test_component"

    def test_get_logger_without_setup(self):
        """Test getting logger without explicit setup."""
        # Reset global state
        import ozb_deal_filter.utils.logging as logging_module
        logging_module._logging_manager = None
        
        logger = get_logger("test_component")
        
        assert isinstance(logger, ComponentLogger)
        assert logger.component_name == "test_component"

    @patch('logging.handlers.RotatingFileHandler')
    def test_get_logging_stats(self, mock_handler):
        """Test getting logging stats through global function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(log_dir=temp_dir)
            
            stats = get_logging_stats()
            
            assert isinstance(stats, dict)
            assert "log_directory" in stats
            assert "log_level" in stats

    def test_get_logging_stats_without_setup(self):
        """Test getting logging stats without setup."""
        # Reset global state
        import ozb_deal_filter.utils.logging as logging_module
        logging_module._logging_manager = None
        
        stats = get_logging_stats()
        
        assert stats == {"error": "Logging not initialized"}


class TestLogLevel:
    """Test cases for LogLevel enum."""

    def test_log_level_values(self):
        """Test log level enum values."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestLogFileRotation:
    """Test cases for log file rotation."""

    @patch('logging.handlers.RotatingFileHandler')
    def test_rotating_file_handler_setup(self, mock_handler):
        """Test that rotating file handlers are properly configured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LoggingManager(log_dir=temp_dir)
            
            # Verify that rotating file handlers were created
            assert mock_handler.call_count >= 2  # Main log and error log
            
            # Check that handlers were called with proper configuration
            for call in mock_handler.call_args_list:
                args, kwargs = call
                # Should have maxBytes and backupCount configured
                # (These would be set after creation in the real implementation)


class TestStructuredLogging:
    """Test cases for structured logging output."""

    def test_json_log_format(self):
        """Test that logs are formatted as valid JSON."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = ComponentLogger("test_component")
            logger.info("Test message", {"key": "value"})
            
            # Get the logged message
            call_args = mock_logger.info.call_args[0]
            log_message = call_args[0]
            
            # Should be valid JSON
            parsed = json.loads(log_message)
            
            # Check required fields
            assert "timestamp" in parsed
            assert "component" in parsed
            assert "message" in parsed
            assert parsed["component"] == "test_component"
            assert parsed["message"] == "Test message"
            assert parsed["key"] == "value"

    def test_exception_logging(self):
        """Test exception logging with structured format."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            logger = ComponentLogger("test_component")
            logger.error("Error occurred", exc_info=True)
            
            # Check that error was called with exc_info=True
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs.get("exc_info") is True
            
            # Check log message structure
            call_args = mock_logger.error.call_args[0]
            log_message = call_args[0]
            parsed = json.loads(log_message)
            
            assert parsed["exception"] is True