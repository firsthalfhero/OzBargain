"""
Structured logging utilities for the OzBargain Deal Filter system.

This module provides comprehensive logging configuration with structured
output, appropriate log levels, and error tracking capabilities.
"""

import logging
import logging.handlers
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum


class LogLevel(Enum):
    """Log levels for different types of events."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ComponentLogger:
    """
    Structured logger for system components.
    
    Provides consistent logging format and component-specific context.
    """
    
    def __init__(self, component_name: str, extra_context: Optional[Dict[str, Any]] = None):
        """
        Initialize component logger.
        
        Args:
            component_name: Name of the component (e.g., 'rss.monitor', 'llm.evaluator')
            extra_context: Additional context to include in all log messages
        """
        self.component_name = component_name
        self.extra_context = extra_context or {}
        self.logger = logging.getLogger(f"ozb_deal_filter.{component_name}")
        
    def _format_message(self, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format log message with structured data."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "component": self.component_name,
            "message": message,
            **self.extra_context
        }
        
        if extra:
            log_data.update(extra)
            
        return log_data
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message."""
        log_data = self._format_message(message, extra)
        self.logger.debug(json.dumps(log_data))
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message."""
        log_data = self._format_message(message, extra)
        self.logger.info(json.dumps(log_data))
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message."""
        log_data = self._format_message(message, extra)
        self.logger.warning(json.dumps(log_data))
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log error message."""
        log_data = self._format_message(message, extra)
        if exc_info:
            log_data["exception"] = True
        self.logger.error(json.dumps(log_data), exc_info=exc_info)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        """Log critical message."""
        log_data = self._format_message(message, extra)
        if exc_info:
            log_data["exception"] = True
        self.logger.critical(json.dumps(log_data), exc_info=exc_info)


class LoggingManager:
    """
    Centralized logging configuration and management.
    
    Handles log file rotation, formatting, and component-specific loggers.
    """
    
    def __init__(self, log_dir: str = "logs", log_level: str = "INFO"):
        """
        Initialize logging manager.
        
        Args:
            log_dir: Directory for log files
            log_level: Default log level
        """
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())
        self.component_loggers: Dict[str, ComponentLogger] = {}
        
        # Ensure log directory exists
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup logging configuration
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration with structured output."""
        # Create formatters
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Setup root logger
        root_logger = logging.getLogger("ozb_deal_filter")
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # Main log file handler with rotation
        main_log_file = self.log_dir / "ozb_deal_filter.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Error log file handler
        error_log_file = self.log_dir / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # Component-specific log files
        self._setup_component_loggers()
    
    def _setup_component_loggers(self):
        """Setup component-specific log files."""
        components = [
            "rss.monitor",
            "deal.parser", 
            "llm.evaluator",
            "filter.engine",
            "alert.formatter",
            "message.dispatcher",
            "orchestrator"
        ]
        
        for component in components:
            component_logger = logging.getLogger(f"ozb_deal_filter.{component}")
            
            # Component-specific log file
            component_log_file = self.log_dir / f"{component.replace('.', '_')}.log"
            component_handler = logging.handlers.RotatingFileHandler(
                component_log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=2
            )
            component_handler.setLevel(self.log_level)
            component_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            ))
            
            component_logger.addHandler(component_handler)
    
    def get_component_logger(self, component_name: str, extra_context: Optional[Dict[str, Any]] = None) -> ComponentLogger:
        """
        Get or create a component logger.
        
        Args:
            component_name: Name of the component
            extra_context: Additional context for all log messages
            
        Returns:
            ComponentLogger instance
        """
        cache_key = f"{component_name}_{hash(str(extra_context))}"
        
        if cache_key not in self.component_loggers:
            self.component_loggers[cache_key] = ComponentLogger(component_name, extra_context)
        
        return self.component_loggers[cache_key]
    
    def set_log_level(self, level: str):
        """Set log level for all loggers."""
        log_level = getattr(logging, level.upper())
        
        # Update root logger
        root_logger = logging.getLogger("ozb_deal_filter")
        root_logger.setLevel(log_level)
        
        # Update all handlers
        for handler in root_logger.handlers:
            try:
                # Skip error log handler (keep it at ERROR level)
                if (hasattr(handler, 'baseFilename') and 
                    "errors.log" in str(handler.baseFilename)):
                    continue
                handler.setLevel(log_level)
            except Exception:
                # If there's any issue with handler, skip it
                continue
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        stats = {
            "log_directory": str(self.log_dir),
            "log_level": logging.getLevelName(self.log_level),
            "component_loggers": len(self.component_loggers),
            "log_files": []
        }
        
        # Get log file information
        for log_file in self.log_dir.glob("*.log"):
            try:
                file_stats = log_file.stat()
                stats["log_files"].append({
                    "name": log_file.name,
                    "size_bytes": file_stats.st_size,
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat()
                })
            except Exception:
                pass
        
        return stats


# Global logging manager instance
_logging_manager: Optional[LoggingManager] = None


def setup_logging(log_dir: str = "logs", log_level: str = "INFO") -> LoggingManager:
    """
    Setup global logging configuration.
    
    Args:
        log_dir: Directory for log files
        log_level: Default log level
        
    Returns:
        LoggingManager instance
    """
    global _logging_manager
    _logging_manager = LoggingManager(log_dir, log_level)
    return _logging_manager


def get_logger(component_name: str, extra_context: Optional[Dict[str, Any]] = None) -> ComponentLogger:
    """
    Get a component logger.
    
    Args:
        component_name: Name of the component
        extra_context: Additional context for all log messages
        
    Returns:
        ComponentLogger instance
    """
    if _logging_manager is None:
        setup_logging()
    
    return _logging_manager.get_component_logger(component_name, extra_context)


def get_logging_stats() -> Dict[str, Any]:
    """Get logging statistics."""
    if _logging_manager is None:
        return {"error": "Logging not initialized"}
    
    return _logging_manager.get_log_stats()