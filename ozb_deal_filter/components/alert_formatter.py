"""
Alert formatting component for the OzBargain Deal Filter system.

This module provides functionality to format deals into rich alert messages
with platform-specific formatting and urgency level determination.
"""

from typing import Any, Dict, List

from ..interfaces import IAlertFormatter
from ..models.alert import FormattedAlert
from ..models.deal import Deal
from ..models.filter import FilterResult, UrgencyLevel


class UrgencyCalculator:
    """Calculates urgency level for deals based on various factors."""

    def __init__(self):
        """Initialize the urgency calculator."""
        self.urgency_keywords = {
            UrgencyLevel.URGENT: [
                "flash sale",
                "limited time",
                "expires today",
                "ends today",
                "last chance",
                "final hours",
                "while stocks last",
                "limited stock",
                "clearance",
                "closing down",
                "going out of business",
            ],
            UrgencyLevel.HIGH: [
                "24 hours",
                "tomorrow",
                "weekend only",
                "today only",
                "limited quantity",
                "few left",
                "almost sold out",
                "expires soon",
                "ends soon",
                "hurry",
            ],
            UrgencyLevel.MEDIUM: [
                "this week",
                "weekly special",
                "limited offer",
                "special price",
                "bonus offer",
                "extra discount",
            ],
        }

    def calculate_urgency(
        self, deal: Deal, filter_result: FilterResult
    ) -> UrgencyLevel:
        """
        Calculate urgency level based on deal content and filter results.

        Args:
            deal: The deal to assess
            filter_result: Filter results containing authenticity and price

        Returns:
            UrgencyLevel: Calculated urgency level
        """
        # Check for explicit urgency indicators from deal parsing
        if deal.urgency_indicators:
            for indicator in deal.urgency_indicators:
                indicator_lower = indicator.lower()
                for level, keywords in self.urgency_keywords.items():
                    if any(keyword in indicator_lower for keyword in keywords):
                        return level

        # Check title and description for urgency keywords
        combined_text = f"{deal.title} {deal.description}".lower()

        for level, keywords in self.urgency_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                return level

        # Calculate based on discount percentage
        if deal.discount_percentage:
            if deal.discount_percentage >= 70:
                return UrgencyLevel.HIGH
            elif deal.discount_percentage >= 50:
                return UrgencyLevel.MEDIUM

        # Calculate based on price threshold
        if deal.price and deal.price <= 50:
            # Very cheap deals might be urgent
            return UrgencyLevel.MEDIUM

        # Calculate based on community engagement
        if deal.votes and deal.votes >= 50:
            # Highly voted deals
            return UrgencyLevel.MEDIUM

        # Default to low urgency
        return UrgencyLevel.LOW


class AlertFormatter(IAlertFormatter):
    """Formats deals into rich alert messages for various platforms."""

    def __init__(self):
        """Initialize the alert formatter."""
        self.urgency_calculator = UrgencyCalculator()
        self.platform_formatters = {
            "telegram": self._format_telegram,
            "discord": self._format_discord,
            "slack": self._format_slack,
            "whatsapp": self._format_whatsapp,
        }

    def format_alert(self, deal: Deal, filter_result: FilterResult) -> FormattedAlert:
        """
        Format a deal into an alert message.

        Args:
            deal: The deal to format
            filter_result: Filter results for the deal

        Returns:
            FormattedAlert: Formatted alert ready for delivery
        """
        # Calculate urgency level
        urgency = self.urgency_calculator.calculate_urgency(deal, filter_result)

        # Create base alert title
        title = self._create_alert_title(deal, urgency)

        # Create base alert message
        message = self._create_alert_message(deal, filter_result, urgency)

        # Create platform-specific data
        platform_data = self._create_platform_data(deal, filter_result, urgency)

        alert = FormattedAlert(
            title=title,
            message=message,
            urgency=urgency,
            platform_specific_data=platform_data,
        )

        alert.validate()
        return alert

    def _create_alert_title(self, deal: Deal, urgency: UrgencyLevel) -> str:
        """Create alert title with urgency indicator."""
        urgency_prefix = {
            UrgencyLevel.URGENT: "🚨 URGENT",
            UrgencyLevel.HIGH: "⚡ HIGH",
            UrgencyLevel.MEDIUM: "📢 MEDIUM",
            UrgencyLevel.LOW: "💡 DEAL",
        }

        prefix = urgency_prefix.get(urgency, "💡 DEAL")

        # Calculate available space for title after prefix
        prefix_with_separator = f"{prefix}: "
        max_total_length = 200
        max_title_length = max_total_length - len(prefix_with_separator)

        title = deal.title
        if len(title) > max_title_length:
            title = title[: max_title_length - 3] + "..."

        return f"{prefix}: {title}"

    def _create_alert_message(
        self, deal: Deal, filter_result: FilterResult, urgency: UrgencyLevel
    ) -> str:
        """Create detailed alert message."""
        lines = []

        # Deal title
        lines.append(f"**{deal.title}**")
        lines.append("")

        # Price information
        if deal.price is not None:
            price_line = f"💰 **Price:** ${deal.price:.2f}"

            if deal.original_price and deal.discount_percentage:
                price_line += (
                    f" (was ${deal.original_price:.2f}, "
                    f"{deal.discount_percentage:.0f}% off)"
                )

            lines.append(price_line)

        # Category
        if deal.category:
            lines.append(f"📂 **Category:** {deal.category}")

        # Feed source
        if deal.feed_source:
            lines.append(f"📡 **Feed:** {deal.feed_source}")

        # Authenticity score
        if filter_result.authenticity_score > 0:
            score_emoji = (
                "✅"
                if filter_result.authenticity_score >= 0.7
                else "⚠️"
                if filter_result.authenticity_score >= 0.5
                else "❌"
            )
            lines.append(
                f"{score_emoji} **Authenticity:** "
                f"{filter_result.authenticity_score:.1%}"
            )

        # Community engagement
        if deal.votes is not None or deal.comments is not None:
            engagement_parts = []
            if deal.votes is not None:
                engagement_parts.append(f"{deal.votes} votes")
            if deal.comments is not None:
                engagement_parts.append(f"{deal.comments} comments")

            lines.append(f"👥 **Community:** {', '.join(engagement_parts)}")

        # Urgency indicators
        if deal.urgency_indicators:
            lines.append(f"⏰ **Urgency:** {', '.join(deal.urgency_indicators)}")

        # Description (truncated)
        if deal.description:
            description = deal.description.strip()
            if len(description) > 200:
                description = description[:200] + "..."
            lines.append("")
            lines.append(f"📝 **Description:** {description}")

        # Link
        lines.append("")
        lines.append(f"🔗 **Link:** {deal.url}")

        # Timestamp
        time_str = deal.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"🕒 **Posted:** {time_str}")

        return "\n".join(lines)

    def _create_platform_data(
        self, deal: Deal, filter_result: FilterResult, urgency: UrgencyLevel
    ) -> Dict[str, Any]:
        """Create platform-specific formatting data."""
        platform_data = {}

        # Generate formatted messages for each platform
        for platform, formatter in self.platform_formatters.items():
            platform_data[platform] = formatter(deal, filter_result, urgency)

        return platform_data

    def _format_telegram(
        self, deal: Deal, filter_result: FilterResult, urgency: UrgencyLevel
    ) -> Dict[str, Any]:
        """Format alert for Telegram."""
        # Telegram supports HTML and Markdown formatting
        message_lines = []

        # Title with urgency emoji
        urgency_emoji = {
            UrgencyLevel.URGENT: "🚨",
            UrgencyLevel.HIGH: "⚡",
            UrgencyLevel.MEDIUM: "📢",
            UrgencyLevel.LOW: "💡",
        }

        emoji = urgency_emoji.get(urgency, "💡")
        message_lines.append(f"{emoji} <b>{deal.title}</b>")
        message_lines.append("")

        # Price with formatting
        if deal.price is not None:
            price_text = f"💰 <b>Price:</b> ${deal.price:.2f}"
            if deal.original_price and deal.discount_percentage:
                price_text += (
                    f" <i>(was ${deal.original_price:.2f}, "
                    f"{deal.discount_percentage:.0f}% off)</i>"
                )
            message_lines.append(price_text)

        # Category
        message_lines.append(f"📂 <b>Category:</b> {deal.category}")

        # Feed source
        if deal.feed_source:
            message_lines.append(f"📡 <b>Feed:</b> {deal.feed_source}")

        # Authenticity
        if filter_result.authenticity_score > 0:
            score_emoji = (
                "✅"
                if filter_result.authenticity_score >= 0.7
                else "⚠️"
                if filter_result.authenticity_score >= 0.5
                else "❌"
            )
            message_lines.append(
                f"{score_emoji} <b>Authenticity:</b> "
                f"{filter_result.authenticity_score:.1%}"
            )

        # Link as button
        message_lines.append("")
        message_lines.append(f"🔗 <a href='{deal.url}'>View Deal</a>")

        return {
            "text": "\n".join(message_lines),
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": {
                "inline_keyboard": [[{"text": "🛒 View Deal", "url": deal.url}]]
            },
        }

    def _format_discord(
        self, deal: Deal, filter_result: FilterResult, urgency: UrgencyLevel
    ) -> Dict[str, Any]:
        """Format alert for Discord."""
        # Discord supports rich embeds
        color_map = {
            UrgencyLevel.URGENT: 0xFF0000,  # Red
            UrgencyLevel.HIGH: 0xFF8C00,  # Dark Orange
            UrgencyLevel.MEDIUM: 0xFFD700,  # Gold
            UrgencyLevel.LOW: 0x00FF00,  # Green
        }

        fields: List[Dict[str, Any]] = []
        embed = {
            "title": deal.title,
            "url": deal.url,
            "color": color_map.get(urgency, 0x00FF00),
            "timestamp": deal.timestamp.isoformat(),
            "fields": fields,
        }

        # Price field
        if deal.price is not None:
            price_value = f"${deal.price:.2f}"
            if deal.original_price and deal.discount_percentage:
                price_value += (
                    f"\n~~${deal.original_price:.2f}~~ "
                    f"({deal.discount_percentage:.0f}% off)"
                )

            fields.append({"name": "💰 Price", "value": price_value, "inline": True})

        # Category field
        fields.append(
            {
                "name": "📂 Category",
                "value": deal.category,
                "inline": True,
            }
        )

        # Feed source field
        if deal.feed_source:
            fields.append(
                {
                    "name": "📡 Feed",
                    "value": deal.feed_source,
                    "inline": True,
                }
            )

        # Authenticity field
        if filter_result.authenticity_score > 0:
            score_emoji = (
                "✅"
                if filter_result.authenticity_score >= 0.7
                else "⚠️"
                if filter_result.authenticity_score >= 0.5
                else "❌"
            )
            fields.append(
                {
                    "name": f"{score_emoji} Authenticity",
                    "value": f"{filter_result.authenticity_score:.1%}",
                    "inline": True,
                }
            )

        # Description
        if deal.description:
            description = deal.description.strip()
            if len(description) > 300:
                description = description[:300] + "..."
            embed["description"] = description

        return {"embeds": [embed]}

    def _format_slack(
        self, deal: Deal, filter_result: FilterResult, urgency: UrgencyLevel
    ) -> Dict[str, Any]:
        """Format alert for Slack."""
        # Slack supports block kit formatting
        color_map = {
            UrgencyLevel.URGENT: "danger",
            UrgencyLevel.HIGH: "warning",
            UrgencyLevel.MEDIUM: "good",
            UrgencyLevel.LOW: "#36a64f",
        }

        blocks: List[Dict[str, Any]] = []

        # Header block
        urgency_emoji = {
            UrgencyLevel.URGENT: "🚨",
            UrgencyLevel.HIGH: "⚡",
            UrgencyLevel.MEDIUM: "📢",
            UrgencyLevel.LOW: "💡",
        }

        emoji = urgency_emoji.get(urgency, "💡")
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {deal.title}",
                },
            }
        )

        # Fields section
        fields: List[Dict[str, str]] = []

        if deal.price is not None:
            price_text = f"${deal.price:.2f}"
            if deal.original_price and deal.discount_percentage:
                price_text += (
                    f"\n~${deal.original_price:.2f}~ "
                    f"({deal.discount_percentage:.0f}% off)"
                )

            fields.append({"type": "mrkdwn", "text": f"*💰 Price:*\n{price_text}"})

        fields.append({"type": "mrkdwn", "text": f"*📂 Category:*\n{deal.category}"})

        if deal.feed_source:
            fields.append({"type": "mrkdwn", "text": f"*📡 Feed:*\n{deal.feed_source}"})

        if filter_result.authenticity_score > 0:
            score_emoji = (
                "✅"
                if filter_result.authenticity_score >= 0.7
                else "⚠️"
                if filter_result.authenticity_score >= 0.5
                else "❌"
            )
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*{score_emoji} Authenticity:*\n"
                        f"{filter_result.authenticity_score:.1%}"
                    ),
                }
            )

        if fields:
            blocks.append({"type": "section", "fields": fields})

        # Description
        if deal.description:
            description = deal.description.strip()
            if len(description) > 200:
                description = description[:200] + "..."

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📝 Description:*\n{description}",
                    },
                }
            )

        # Action button
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🛒 View Deal"},
                        "url": deal.url,
                        "action_id": "view_deal",
                    }
                ],
            }
        )

        return {
            "blocks": blocks,
            "color": color_map.get(urgency, "#36a64f"),
        }

    def _format_whatsapp(
        self, deal: Deal, filter_result: FilterResult, urgency: UrgencyLevel
    ) -> Dict[str, Any]:
        """Format alert for WhatsApp."""
        # WhatsApp supports basic text formatting
        lines = []

        # Title with urgency
        urgency_emoji = {
            UrgencyLevel.URGENT: "🚨",
            UrgencyLevel.HIGH: "⚡",
            UrgencyLevel.MEDIUM: "📢",
            UrgencyLevel.LOW: "💡",
        }

        emoji = urgency_emoji.get(urgency, "💡")
        lines.append(f"{emoji} *{deal.title}*")
        lines.append("")

        # Price
        if deal.price is not None:
            price_text = f"💰 *Price:* ${deal.price:.2f}"
            if deal.original_price and deal.discount_percentage:
                price_text += (
                    f" _(was ${deal.original_price:.2f}, "
                    f"{deal.discount_percentage:.0f}% off)_"
                )
            lines.append(price_text)

        # Category
        lines.append(f"📂 *Category:* {deal.category}")

        # Feed source
        if deal.feed_source:
            lines.append(f"📡 *Feed:* {deal.feed_source}")

        # Authenticity
        if filter_result.authenticity_score > 0:
            score_emoji = (
                "✅"
                if filter_result.authenticity_score >= 0.7
                else "⚠️"
                if filter_result.authenticity_score >= 0.5
                else "❌"
            )
            lines.append(
                f"{score_emoji} *Authenticity:* "
                f"{filter_result.authenticity_score:.1%}"
            )

        # Description (short)
        if deal.description:
            description = deal.description.strip()
            if len(description) > 150:
                description = description[:150] + "..."
            lines.append("")
            lines.append(f"📝 {description}")

        # Link
        lines.append("")
        lines.append(f"🔗 {deal.url}")

        return {"text": "\n".join(lines)}
