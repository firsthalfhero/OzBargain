"""
URL validation service for RSS feeds.

This module provides comprehensive URL validation including format checking,
accessibility testing, and RSS feed validation.
"""

import asyncio
import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import feedparser
from aiohttp import ClientTimeout

from ..models.telegram import ValidationResult
from ..utils.logging import get_logger

logger = get_logger("url_validator")


class URLValidator:
    """Service for validating URLs and RSS feeds."""

    def __init__(self, timeout: int = 5):
        """
        Initialize URL validator.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        if self.session is None:
            timeout = ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "OzBargain-Deal-Filter/1.0 (Feed Validator)"},
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    async def validate_url(self, url: str) -> ValidationResult:
        """
        Comprehensive URL validation.

        Args:
            url: URL to validate

        Returns:
            ValidationResult with validation status and details
        """
        try:
            # 1. Format validation
            format_result = self._validate_format(url)
            if not format_result.is_valid:
                return format_result

            # 2. Security checks
            security_result = self._validate_security(url)
            if not security_result.is_valid:
                return security_result

            # 3. Accessibility check
            if not await self.is_accessible(url):
                return ValidationResult(is_valid=False, error="URL is not accessible")

            # 4. RSS feed validation
            if not await self.is_rss_feed(url):
                return ValidationResult(
                    is_valid=False, error="URL does not serve valid RSS content"
                )

            # 5. Extract feed title
            feed_title = await self.get_feed_title(url)

            return ValidationResult(is_valid=True, feed_title=feed_title)

        except Exception as e:
            logger.error(f"Error validating URL {url}: {e}")
            return ValidationResult(is_valid=False, error=f"Validation error: {str(e)}")

    def _validate_format(self, url: str) -> ValidationResult:
        """
        Validate URL format.

        Args:
            url: URL to validate

        Returns:
            ValidationResult with format validation status
        """
        try:
            # Basic length check
            if len(url) > 2048:
                return ValidationResult(
                    is_valid=False, error="URL too long (max 2048 characters)"
                )

            # Parse URL
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ["http", "https"]:
                return ValidationResult(
                    is_valid=False, error="URL must use HTTP or HTTPS scheme"
                )

            # Check netloc (domain)
            if not parsed.netloc:
                return ValidationResult(
                    is_valid=False, error="URL must include a valid domain"
                )

            # Check for invalid characters
            invalid_chars = re.search(r'[<>"\s]', url)
            if invalid_chars:
                return ValidationResult(
                    is_valid=False, error="URL contains invalid characters"
                )

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(is_valid=False, error=f"URL format error: {str(e)}")

    def _validate_security(self, url: str) -> ValidationResult:
        """
        Validate URL for security concerns.

        Args:
            url: URL to validate

        Returns:
            ValidationResult with security validation status
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname:
                return ValidationResult(
                    is_valid=False, error="URL hostname could not be determined"
                )

            # Check for localhost
            localhost_patterns = [
                "localhost",
                "127.0.0.1",
                "::1",
                "0.0.0.0",
            ]  # nosec B104

            if hostname.lower() in localhost_patterns:
                return ValidationResult(
                    is_valid=False, error="Localhost URLs are not allowed"
                )

            # Check for private IP ranges
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return ValidationResult(
                        is_valid=False,
                        error="Private/internal IP addresses are not allowed",
                    )
            except ValueError:
                # Not an IP address, hostname is fine
                pass

            # Check for suspicious domains
            suspicious_patterns = [
                r"\.local$",
                r"\.internal$",
                r"\.corp$",
                r"192\.168\.",
                r"10\.",
                r"172\.(1[6-9]|2[0-9]|3[0-1])\.",
            ]

            for pattern in suspicious_patterns:
                if re.search(pattern, hostname, re.IGNORECASE):
                    return ValidationResult(
                        is_valid=False, error="Internal/private domains are not allowed"
                    )

            return ValidationResult(is_valid=True)

        except Exception as e:
            return ValidationResult(
                is_valid=False, error=f"Security validation error: {str(e)}"
            )

    async def is_accessible(self, url: str) -> bool:
        """
        Check if URL is accessible.

        Args:
            url: URL to check

        Returns:
            True if URL is accessible
        """
        try:
            if self.session is None:
                async with self.__class__(self.timeout) as validator:
                    return await validator.is_accessible(url)

            # Perform HEAD request to check accessibility
            async with self.session.head(url, allow_redirects=True) as response:
                return 200 <= response.status < 400

        except asyncio.TimeoutError:
            logger.warning(f"Timeout checking accessibility of {url}")
            return False
        except aiohttp.ClientError as e:
            logger.warning(f"Client error checking accessibility of {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking accessibility of {url}: {e}")
            return False

    async def is_rss_feed(self, url: str) -> bool:
        """
        Verify URL serves RSS content.

        Args:
            url: URL to check

        Returns:
            True if URL serves valid RSS content
        """
        try:
            if self.session is None:
                async with self.__class__(self.timeout) as validator:
                    return await validator.is_rss_feed(url)

            # Fetch content
            async with self.session.get(url) as response:
                if not (200 <= response.status < 300):
                    return False

                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                rss_content_types = [
                    "application/rss+xml",
                    "application/xml",
                    "text/xml",
                    "application/atom+xml",
                ]

                is_rss_content_type = any(
                    ct in content_type for ct in rss_content_types
                )

                # Get first chunk of content to validate
                content = await response.text()

                # Use feedparser to validate RSS structure
                try:
                    parsed = feedparser.parse(content)

                    # Check if feed has entries and basic structure
                    has_feed_info = bool(parsed.feed)
                    has_valid_structure = not parsed.bozo or len(parsed.entries) > 0

                    # Accept if either content type indicates RSS or feedparser can parse it
                    return is_rss_content_type or (
                        has_feed_info and has_valid_structure
                    )

                except Exception as e:
                    logger.warning(f"Error parsing feed content from {url}: {e}")
                    # Fall back to content type check
                    return is_rss_content_type

        except Exception as e:
            logger.error(f"Error checking RSS feed {url}: {e}")
            return False

    async def get_feed_title(self, url: str) -> Optional[str]:
        """
        Extract feed title for naming.

        Args:
            url: URL to extract title from

        Returns:
            Feed title or None if not found
        """
        try:
            if self.session is None:
                async with self.__class__(self.timeout) as validator:
                    return await validator.get_feed_title(url)

            async with self.session.get(url) as response:
                if not (200 <= response.status < 300):
                    return None

                content = await response.text()

                # Parse feed and extract title
                parsed = feedparser.parse(content)

                if parsed.feed and hasattr(parsed.feed, "title"):
                    title = parsed.feed.title.strip()
                    return title if title else None

                return None

        except Exception as e:
            logger.error(f"Error extracting title from {url}: {e}")
            return None


# Convenience function for one-off validations
async def validate_rss_url(url: str, timeout: int = 5) -> ValidationResult:
    """
    Validate a single RSS URL.

    Args:
        url: URL to validate
        timeout: Request timeout in seconds

    Returns:
        ValidationResult with validation status and details
    """
    async with URLValidator(timeout) as validator:
        return await validator.validate_url(url)
