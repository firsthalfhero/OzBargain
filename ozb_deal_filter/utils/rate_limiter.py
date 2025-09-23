"""
Rate limiting utilities for controlling request frequency.

This module provides token bucket-based rate limiting for controlling
the frequency of operations like Telegram bot commands.
"""

import asyncio
import time
from typing import Dict, Optional

from ..utils.logging import get_logger

logger = get_logger("rate_limiter")


class TokenBucket:
    """Token bucket rate limiter implementation."""

    def __init__(
        self, capacity: int, refill_rate: float, initial_tokens: Optional[int] = None
    ):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens in bucket
            refill_rate: Tokens added per second
            initial_tokens: Initial token count (defaults to capacity)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        async with self._lock:
            await self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        if elapsed > 0:
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now

    async def get_tokens(self) -> float:
        """Get current token count."""
        async with self._lock:
            await self._refill()
            return self.tokens

    async def wait_for_tokens(
        self, tokens: int = 1, timeout: Optional[float] = None
    ) -> bool:
        """
        Wait for sufficient tokens to become available.

        Args:
            tokens: Number of tokens needed
            timeout: Maximum time to wait in seconds

        Returns:
            True if tokens became available, False if timeout
        """
        start_time = time.time()

        while True:
            if await self.consume(tokens):
                return True

            if timeout and (time.time() - start_time) >= timeout:
                return False

            # Calculate wait time until next token
            wait_time = min(1.0, tokens / self.refill_rate)
            await asyncio.sleep(wait_time)


class RateLimiter:
    """Simple rate limiter for tracking request frequency."""

    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.bucket = TokenBucket(max_requests, max_requests / time_window)

    async def allow_request(self) -> bool:
        """
        Check if request is allowed.

        Returns:
            True if request is allowed
        """
        return await self.bucket.consume(1)

    async def wait_for_slot(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for a request slot to become available.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if slot became available
        """
        return await self.bucket.wait_for_tokens(1, timeout)


class MultiUserRateLimiter:
    """Rate limiter that tracks limits per user."""

    def __init__(
        self,
        global_max_requests: int,
        global_time_window: float,
        user_max_requests: int,
        user_time_window: float,
    ):
        """
        Initialize multi-user rate limiter.

        Args:
            global_max_requests: Global maximum requests
            global_time_window: Global time window in seconds
            user_max_requests: Per-user maximum requests
            user_time_window: Per-user time window in seconds
        """
        self.global_limiter = RateLimiter(global_max_requests, global_time_window)
        self.user_limiters: Dict[str, RateLimiter] = {}
        self.user_max_requests = user_max_requests
        self.user_time_window = user_time_window
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    async def allow_request(self, user_id: str) -> bool:
        """
        Check if request is allowed for user.

        Args:
            user_id: User identifier

        Returns:
            True if request is allowed
        """
        # Check global rate limit first
        if not await self.global_limiter.allow_request():
            logger.warning("Global rate limit exceeded")
            return False

        # Check user-specific rate limit
        user_limiter = self._get_user_limiter(user_id)
        if not await user_limiter.allow_request():
            logger.warning(f"User rate limit exceeded for {user_id}")
            return False

        # Periodic cleanup of old user limiters
        await self._cleanup_if_needed()

        return True

    def _get_user_limiter(self, user_id: str) -> RateLimiter:
        """Get or create rate limiter for user."""
        if user_id not in self.user_limiters:
            self.user_limiters[user_id] = RateLimiter(
                self.user_max_requests, self.user_time_window
            )
        return self.user_limiters[user_id]

    async def _cleanup_if_needed(self) -> None:
        """Clean up old user limiters periodically."""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            # Remove limiters that haven't been used recently
            # For simplicity, we'll just clear all and let them recreate
            # In production, you'd track last access times
            if len(self.user_limiters) > 100:  # Prevent memory bloat
                old_count = len(self.user_limiters)
                self.user_limiters.clear()
                logger.info(f"Cleaned up {old_count} user rate limiters")

            self._last_cleanup = now

    async def get_user_status(self, user_id: str) -> Dict[str, float]:
        """
        Get rate limit status for user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with rate limit status
        """
        global_tokens = await self.global_limiter.bucket.get_tokens()

        user_limiter = self._get_user_limiter(user_id)
        user_tokens = await user_limiter.bucket.get_tokens()

        return {
            "global_tokens_available": global_tokens,
            "global_capacity": self.global_limiter.max_requests,
            "user_tokens_available": user_tokens,
            "user_capacity": self.user_max_requests,
        }
