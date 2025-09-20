"""
Main entry point for the OzBargain Deal Filter system.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from .orchestrator import ApplicationOrchestrator
from .utils.logging import get_logger, setup_logging


async def async_main(config_path: Optional[str] = None):
    """Async main application entry point."""
    # Setup structured logging
    setup_logging(log_level="INFO")
    logger = get_logger("main")

    logger.info(
        "Starting OzBargain Deal Filter system", extra={"config_path": config_path}
    )

    try:
        # Create and run the application orchestrator
        orchestrator = ApplicationOrchestrator(config_path)
        await orchestrator.run()

    except Exception as e:
        logger.error("Application failed", extra={"error": str(e)}, exc_info=True)
        sys.exit(1)


def main():
    """Main application entry point."""
    config_path = None

    # Check for config path argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    # Run the async application
    try:
        asyncio.run(async_main(config_path))
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
