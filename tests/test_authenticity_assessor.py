"""
Unit tests for the AuthenticityAssessor component.
"""

from datetime import datetime
from ozb_deal_filter.components.authenticity_assessor import (
    AuthenticityAssessor,
)
from ozb_deal_filter.models.deal import Deal


class TestAuthenticityAssessor:
    """Test cases for AuthenticityAssessor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.assessor = AuthenticityAssessor()

        # Base deal for testing
        self.base_deal = Deal(
            id="test-deal-1",
            title="Test Deal",
            description="A test deal for authenticity assessment",
            price=100.0,
            original_price=150.0,
            discount_percentage=33.3,
            category="Electronics",
            url="https://example.com/deal",
            timestamp=datetime.now(),
            votes=None,
            comments=None,
            urgency_indicators=[],
        )

    def test_init_default_thresholds(self):
        """Test initialization with default thresholds."""
        assessor = AuthenticityAssessor()
        assert assessor.min_votes_threshold == 5
        assert assessor.min_comments_threshold == 2

    def test_init_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        assessor = AuthenticityAssessor(
            min_votes_threshold=10, min_comments_threshold=5
        )
        assert assessor.min_votes_threshold == 10
        assert assessor.min_comments_threshold == 5

    def test_assess_authenticity_no_community_data(self):
        """Test authenticity assessment with no community data."""
        deal = self.base_deal
        deal.votes = None
        deal.comments = None

        score = self.assessor.assess_authenticity(deal)
        assert score == 0.5  # Neutral score for no data

    def test_assess_authenticity_only_votes(self):
        """Test authenticity assessment with only vote data."""
        deal = self.base_deal
        deal.votes = 10
        deal.comments = None

        score = self.assessor.assess_authenticity(deal)
        assert 0.6 <= score <= 1.0  # Should be positive score

    def test_assess_authenticity_only_comments(self):
        """Test authenticity assessment with only comment data."""
        deal = self.base_deal
        deal.votes = None
        deal.comments = 5

        score = self.assessor.assess_authenticity(deal)
        assert 0.5 <= score <= 1.0  # Should be positive score

    def test_assess_authenticity_both_metrics(self):
        """Test authenticity assessment with both votes and comments."""
        deal = self.base_deal
        deal.votes = 15
        deal.comments = 8

        score = self.assessor.assess_authenticity(deal)
        assert 0.6 <= score <= 1.0  # Should be positive score

    def test_calculate_vote_score_negative_votes(self):
        """Test vote score calculation with negative votes."""
        # Test various negative vote scenarios
        assert abs(self.assessor._calculate_vote_score(-1) - 0.4) < 0.001  # 0.5 - 0.1
        assert abs(self.assessor._calculate_vote_score(-3) - 0.2) < 0.001  # 0.5 - 0.3
        assert self.assessor._calculate_vote_score(-5) == 0.0  # Capped at 0.0

    def test_calculate_vote_score_zero_votes(self):
        """Test vote score calculation with zero votes."""
        score = self.assessor._calculate_vote_score(0)
        assert score == 0.5  # Neutral

    def test_calculate_vote_score_positive_votes_below_threshold(self):
        """Test vote score calculation with positive votes below threshold."""
        # Default threshold is 5
        score = self.assessor._calculate_vote_score(3)
        assert score == 0.75  # 0.6 + (3 * 0.05)

    def test_calculate_vote_score_positive_votes_above_threshold(self):
        """Test vote score calculation with positive votes above threshold."""
        score = self.assessor._calculate_vote_score(10)
        assert score > 0.6  # Should be above base positive score
        assert score <= 1.0  # Should not exceed maximum

    def test_calculate_vote_score_very_high_votes(self):
        """Test vote score calculation with very high vote counts."""
        score = self.assessor._calculate_vote_score(100)
        assert score <= 1.0  # Should be capped at 1.0

    def test_calculate_vote_score_none(self):
        """Test vote score calculation with None votes."""
        score = self.assessor._calculate_vote_score(None)
        assert score is None

    def test_calculate_comment_score_zero_comments(self):
        """Test comment score calculation with zero comments."""
        score = self.assessor._calculate_comment_score(0)
        assert score == 0.48  # Slightly below neutral

    def test_calculate_comment_score_below_threshold(self):
        """Test comment score calculation with comments below threshold."""
        # Default threshold is 2
        score = self.assessor._calculate_comment_score(1)
        assert score == 0.54  # 0.52 + (1 * 0.02)

    def test_calculate_comment_score_above_threshold(self):
        """Test comment score calculation with comments above threshold."""
        score = self.assessor._calculate_comment_score(5)
        assert score > 0.55  # Should be above base positive score
        assert score <= 1.0  # Should not exceed maximum

    def test_calculate_comment_score_very_high_comments(self):
        """Test comment score calculation with very high comment counts."""
        score = self.assessor._calculate_comment_score(50)
        assert score <= 1.0  # Should be capped at 1.0

    def test_calculate_comment_score_none(self):
        """Test comment score calculation with None comments."""
        score = self.assessor._calculate_comment_score(None)
        assert score is None

    def test_combined_scoring_weights(self):
        """Test that vote and comment scores are combined with proper weights."""
        deal = self.base_deal
        deal.votes = 10  # Should give high vote score
        deal.comments = 1  # Should give lower comment score

        score = self.assessor.assess_authenticity(deal)

        # Verify the score reflects vote weighting (0.7) more than comment weighting (0.3)
        vote_only_deal = Deal(**deal.__dict__)
        vote_only_deal.comments = None
        vote_only_score = self.assessor.assess_authenticity(vote_only_deal)

        # Combined score should be closer to vote-only score due to higher weight
        assert abs(score - vote_only_score) < 0.2

    def test_is_questionable_default_threshold(self):
        """Test questionable deal detection with default threshold."""
        assert self.assessor.is_questionable(0.3) is True  # Below 0.4
        assert self.assessor.is_questionable(0.4) is False  # At threshold
        assert self.assessor.is_questionable(0.5) is False  # Above threshold

    def test_is_questionable_custom_threshold(self):
        """Test questionable deal detection with custom threshold."""
        assert self.assessor.is_questionable(0.6, threshold=0.7) is True
        assert self.assessor.is_questionable(0.8, threshold=0.7) is False

    def test_get_authenticity_description(self):
        """Test authenticity score descriptions."""
        assert self.assessor.get_authenticity_description(0.9) == "Highly trusted"
        assert self.assessor.get_authenticity_description(0.7) == "Well-regarded"
        assert self.assessor.get_authenticity_description(0.5) == "Mixed signals"
        assert self.assessor.get_authenticity_description(0.3) == "Questionable"
        assert (
            self.assessor.get_authenticity_description(0.1) == "Potentially problematic"
        )

    def test_score_bounds(self):
        """Test that authenticity scores are always within valid bounds."""
        test_cases = [
            (None, None),  # No data
            (-10, None),  # Very negative votes
            (100, None),  # Very positive votes
            (None, 0),  # No comments
            (None, 50),  # Many comments
            (20, 10),  # Both high
            (-5, 1),  # Mixed signals
        ]

        for votes, comments in test_cases:
            deal = self.base_deal
            deal.votes = votes
            deal.comments = comments

            score = self.assessor.assess_authenticity(deal)
            assert (
                0.0 <= score <= 1.0
            ), f"Score {score} out of bounds for votes={votes}, comments={comments}"

    def test_realistic_scenarios(self):
        """Test authenticity assessment with realistic OzBargain scenarios."""

        # Popular deal with good engagement
        popular_deal = self.base_deal
        popular_deal.votes = 25
        popular_deal.comments = 12
        score = self.assessor.assess_authenticity(popular_deal)
        assert score >= 0.7  # Should be well-regarded

        # Controversial deal with negative votes
        controversial_deal = self.base_deal
        controversial_deal.votes = -3
        controversial_deal.comments = 8
        score = self.assessor.assess_authenticity(controversial_deal)
        assert score < 0.5  # Should be below neutral

        # New deal with minimal engagement
        new_deal = self.base_deal
        new_deal.votes = 2
        new_deal.comments = 1
        score = self.assessor.assess_authenticity(new_deal)
        assert 0.4 <= score <= 0.7  # Should be moderate

        # Suspicious deal with no engagement
        suspicious_deal = self.base_deal
        suspicious_deal.votes = 0
        suspicious_deal.comments = 0
        score = self.assessor.assess_authenticity(suspicious_deal)
        assert score <= 0.5  # Should be neutral or below

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""

        # Deal with exactly threshold values
        threshold_deal = self.base_deal
        threshold_deal.votes = self.assessor.min_votes_threshold
        threshold_deal.comments = self.assessor.min_comments_threshold
        score = self.assessor.assess_authenticity(threshold_deal)
        assert 0.5 <= score <= 1.0

        # Deal with one vote below threshold
        below_threshold_deal = self.base_deal
        below_threshold_deal.votes = self.assessor.min_votes_threshold - 1
        below_threshold_deal.comments = self.assessor.min_comments_threshold - 1
        score = self.assessor.assess_authenticity(below_threshold_deal)
        assert 0.4 <= score <= 0.8
