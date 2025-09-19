"""
Authenticity assessment component for the OzBargain Deal Filter system.

This module provides functionality to assess deal authenticity using
OzBargain community data such as votes and comments.
"""

from typing import Optional
import logging

from ..models.deal import Deal

logger = logging.getLogger(__name__)


class AuthenticityAssessor:
    """
    Assesses deal authenticity using OzBargain community data.

    Uses votes and comments to calculate a basic authenticity score
    that helps identify potentially questionable deals.
    """

    def __init__(self, min_votes_threshold: int = 5, min_comments_threshold: int = 2):
        """
        Initialize the authenticity assessor.

        Args:
            min_votes_threshold: Minimum votes needed for reliable assessment
            min_comments_threshold: Minimum comments needed for reliable assessment
        """
        self.min_votes_threshold = min_votes_threshold
        self.min_comments_threshold = min_comments_threshold

    def assess_authenticity(self, deal: Deal) -> float:
        """
        Assess the authenticity of a deal based on community data.

        Args:
            deal: The deal to assess

        Returns:
            float: Authenticity score between 0.0 and 1.0
                  - 1.0: Highly authentic (strong positive community engagement)
                  - 0.5: Neutral/unknown (insufficient data or mixed signals)
                  - 0.0: Potentially questionable (negative community signals)
        """
        logger.debug(f"Assessing authenticity for deal: {deal.id}")

        # If no community data available, return neutral score
        if deal.votes is None and deal.comments is None:
            logger.debug(
                f"No community data for deal {deal.id}, returning neutral score"
            )
            return 0.5

        # Calculate authenticity score based on available data
        score = self._calculate_authenticity_score(deal)

        logger.debug(f"Authenticity score for deal {deal.id}: {score}")
        return score

    def _calculate_authenticity_score(self, deal: Deal) -> float:
        """
        Calculate authenticity score using community engagement metrics.

        Args:
            deal: The deal to calculate score for

        Returns:
            float: Calculated authenticity score
        """
        # Initialize base score
        base_score = 0.5

        # Vote-based scoring
        vote_score = self._calculate_vote_score(deal.votes)

        # Comment-based scoring
        comment_score = self._calculate_comment_score(deal.comments)

        # Combine scores with weights
        # Votes are weighted more heavily as they're more direct indicators
        vote_weight = 0.7
        comment_weight = 0.3

        if vote_score is not None and comment_score is not None:
            # Both metrics available
            combined_score = (vote_score * vote_weight) + (
                comment_score * comment_weight
            )
        elif vote_score is not None:
            # Only votes available
            combined_score = vote_score
        elif comment_score is not None:
            # Only comments available
            combined_score = comment_score
        else:
            # No data available
            combined_score = base_score

        # Ensure score is within bounds
        return max(0.0, min(1.0, combined_score))

    def _calculate_vote_score(self, votes: Optional[int]) -> Optional[float]:
        """
        Calculate authenticity score based on vote count.

        Args:
            votes: Number of votes the deal received

        Returns:
            Optional[float]: Vote-based score or None if no vote data
        """
        if votes is None:
            return None

        # Negative votes indicate potential issues
        if votes < 0:
            # Heavily penalize negative votes
            return max(
                0.0, 0.5 + (votes * 0.1)
            )  # Each negative vote reduces score by 0.1

        # Positive votes indicate authenticity
        if votes >= self.min_votes_threshold:
            # Strong positive signal for deals with sufficient votes
            # Use logarithmic scaling to prevent extremely high scores
            import math

            normalized_votes = min(votes, 50)  # Cap at 50 for scoring purposes
            return min(1.0, 0.6 + (math.log(normalized_votes + 1) * 0.1))
        elif votes > 0:
            # Some positive votes but below threshold
            return 0.6 + (votes * 0.05)  # Modest boost for each positive vote
        else:
            # Zero votes - neutral
            return 0.5

    def _calculate_comment_score(self, comments: Optional[int]) -> Optional[float]:
        """
        Calculate authenticity score based on comment count.

        Args:
            comments: Number of comments the deal received

        Returns:
            Optional[float]: Comment-based score or None if no comment data
        """
        if comments is None:
            return None

        # Comments generally indicate engagement and scrutiny
        if comments >= self.min_comments_threshold:
            # Good engagement suggests the deal has been reviewed by community
            import math

            normalized_comments = min(comments, 20)  # Cap at 20 for scoring purposes
            return min(1.0, 0.55 + (math.log(normalized_comments + 1) * 0.08))
        elif comments > 0:
            # Some comments but below threshold
            return 0.52 + (comments * 0.02)  # Small boost for each comment
        else:
            # No comments - slightly below neutral as it might indicate lack of scrutiny
            return 0.48

    def is_questionable(
        self, authenticity_score: float, threshold: float = 0.4
    ) -> bool:
        """
        Determine if a deal should be flagged as questionable based on authenticity score.

        Args:
            authenticity_score: The calculated authenticity score
            threshold: Threshold below which deals are considered questionable

        Returns:
            bool: True if deal should be flagged as questionable
        """
        return authenticity_score < threshold

    def get_authenticity_description(self, score: float) -> str:
        """
        Get a human-readable description of the authenticity score.

        Args:
            score: Authenticity score between 0.0 and 1.0

        Returns:
            str: Description of the authenticity level
        """
        if score >= 0.8:
            return "Highly trusted"
        elif score >= 0.6:
            return "Well-regarded"
        elif score >= 0.4:
            return "Mixed signals"
        elif score >= 0.2:
            return "Questionable"
        else:
            return "Potentially problematic"
