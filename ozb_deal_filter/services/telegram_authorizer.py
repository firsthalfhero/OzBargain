"""
Telegram bot authorization service.

This module provides user authorization and rate limiting functionality
for Telegram bot operations.
"""

from typing import List, Set

from ..models.telegram import AuthResult
from ..utils.logging import get_logger
from ..utils.rate_limiter import MultiUserRateLimiter

logger = get_logger("telegram_authorizer")


class TelegramAuthorizer:
    """Handles authorization and rate limiting for Telegram bot users."""

    def __init__(
        self,
        authorized_users: List[str],
        global_max_commands_per_minute: int = 30,
        user_max_commands_per_minute: int = 10,
    ):
        """
        Initialize Telegram authorizer.

        Args:
            authorized_users: List of authorized user IDs
            global_max_commands_per_minute: Global command rate limit
            user_max_commands_per_minute: Per-user command rate limit
        """
        self.authorized_users: Set[str] = set(authorized_users)
        self.rate_limiter = MultiUserRateLimiter(
            global_max_requests=global_max_commands_per_minute,
            global_time_window=60.0,  # 1 minute
            user_max_requests=user_max_commands_per_minute,
            user_time_window=60.0,  # 1 minute
        )

        logger.info(
            f"Telegram authorizer initialized with {len(self.authorized_users)} authorized users"
        )

    async def is_authorized(self, user_id: str) -> AuthResult:
        """
        Check if user is authorized and rate limits allow the request.

        Args:
            user_id: Telegram user ID

        Returns:
            AuthResult with authorization status and reason
        """
        try:
            # Check if user is in authorized list
            if user_id not in self.authorized_users:
                logger.warning(f"Unauthorized access attempt from user: {user_id}")
                return AuthResult(
                    authorized=False,
                    reason="User not authorized to use this bot",
                    user_id=user_id,
                )

            # Check rate limits
            if not await self.rate_limiter.allow_request(user_id):
                logger.warning(f"Rate limit exceeded for user: {user_id}")
                return AuthResult(
                    authorized=False,
                    reason="Rate limit exceeded. Please wait before sending more commands",
                    user_id=user_id,
                )

            # All checks passed
            logger.debug(f"User authorized: {user_id}")
            return AuthResult(
                authorized=True, reason="User authorized", user_id=user_id
            )

        except Exception as e:
            logger.error(f"Error during authorization check for user {user_id}: {e}")
            return AuthResult(
                authorized=False,
                reason="Authorization check failed due to internal error",
                user_id=user_id,
            )

    def add_authorized_user(self, user_id: str) -> bool:
        """
        Add user to authorized list.

        Args:
            user_id: User ID to add

        Returns:
            True if user was added
        """
        try:
            if user_id in self.authorized_users:
                logger.info(f"User already authorized: {user_id}")
                return True

            self.authorized_users.add(user_id)
            logger.info(f"Added authorized user: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding authorized user {user_id}: {e}")
            return False

    def remove_authorized_user(self, user_id: str) -> bool:
        """
        Remove user from authorized list.

        Args:
            user_id: User ID to remove

        Returns:
            True if user was removed
        """
        try:
            if user_id not in self.authorized_users:
                logger.info(f"User not in authorized list: {user_id}")
                return True

            self.authorized_users.remove(user_id)
            logger.info(f"Removed authorized user: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing authorized user {user_id}: {e}")
            return False

    def is_user_authorized(self, user_id: str) -> bool:
        """
        Check if user is in authorized list (without rate limiting).

        Args:
            user_id: User ID to check

        Returns:
            True if user is authorized
        """
        return user_id in self.authorized_users

    def get_authorized_users(self) -> List[str]:
        """
        Get list of authorized users.

        Returns:
            List of authorized user IDs
        """
        return list(self.authorized_users)

    async def get_user_rate_limit_status(self, user_id: str) -> dict:
        """
        Get rate limit status for user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with rate limit information
        """
        try:
            status = await self.rate_limiter.get_user_status(user_id)
            status["is_authorized"] = self.is_user_authorized(user_id)
            return status

        except Exception as e:
            logger.error(f"Error getting rate limit status for user {user_id}: {e}")
            return {
                "error": "Failed to get rate limit status",
                "is_authorized": self.is_user_authorized(user_id),
            }

    def update_rate_limits(
        self, global_max_commands_per_minute: int, user_max_commands_per_minute: int
    ) -> None:
        """
        Update rate limit settings.

        Args:
            global_max_commands_per_minute: New global rate limit
            user_max_commands_per_minute: New per-user rate limit
        """
        try:
            self.rate_limiter = MultiUserRateLimiter(
                global_max_requests=global_max_commands_per_minute,
                global_time_window=60.0,
                user_max_requests=user_max_commands_per_minute,
                user_time_window=60.0,
            )

            logger.info(
                f"Updated rate limits - Global: {global_max_commands_per_minute}/min, "
                f"User: {user_max_commands_per_minute}/min"
            )

        except Exception as e:
            logger.error(f"Error updating rate limits: {e}")

    def get_stats(self) -> dict:
        """
        Get authorization and rate limiting statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "authorized_users_count": len(self.authorized_users),
            "authorized_users": list(self.authorized_users),
            "global_rate_limit": self.rate_limiter.global_limiter.max_requests,
            "user_rate_limit": self.rate_limiter.user_max_requests,
            "active_user_limiters": len(self.rate_limiter.user_limiters),
        }
