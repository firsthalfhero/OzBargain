"""Filter engine for applying price, discount, and authenticity filters to deals."""

import logging
from typing import Optional

from ..models.deal import Deal
from ..models.evaluation import EvaluationResult
from ..models.filter import FilterResult, UrgencyLevel
from ..models.config import UserCriteria
from .authenticity_assessor import AuthenticityAssessor

logger = logging.getLogger(__name__)


class PriceFilter:
    """Handles price-based filtering logic."""

    def __init__(self, max_price: Optional[float] = None):
        """Initialize price filter with maximum price threshold."""
        self.max_price = max_price

    def check_price_threshold(self, deal: Deal) -> bool:
        """Check if deal price meets the threshold criteria."""
        if self.max_price is None:
            return True  # No price limit set

        if deal.price is None:
            return True  # No price information available, let it pass

        return deal.price <= self.max_price

    def check_discount_percentage(
        self, deal: Deal, min_discount: Optional[float] = None
    ) -> bool:
        """Check if deal meets minimum discount percentage requirement."""
        if min_discount is None:
            return True  # No discount requirement set

        if deal.discount_percentage is None:
            return True  # No discount information available, let it pass

        return deal.discount_percentage >= min_discount


class FilterEngine:
    """Main filter engine that applies all filtering criteria."""

    def __init__(self, user_criteria: UserCriteria):
        """Initialize filter engine with user criteria."""
        self.user_criteria = user_criteria
        self.price_filter = PriceFilter(user_criteria.max_price)
        self.authenticity_assessor = AuthenticityAssessor()
        logger.info(
            f"FilterEngine initialized with max_price={user_criteria.max_price}, "
            f"min_discount={user_criteria.min_discount_percentage}"
        )

    def apply_filters(self, deal: Deal, evaluation: EvaluationResult) -> FilterResult:
        """Apply all filters to a deal and return the result."""
        logger.debug(f"Applying filters to deal: {deal.id}")

        # Check price threshold
        price_match = self.price_filter.check_price_threshold(deal)
        logger.debug(f"Price match for deal {deal.id}: {price_match}")

        # Check discount percentage
        discount_match = self.price_filter.check_discount_percentage(
            deal, self.user_criteria.min_discount_percentage
        )
        logger.debug(f"Discount match for deal {deal.id}: {discount_match}")

        # Calculate authenticity score
        authenticity_score = self.authenticity_assessor.assess_authenticity(deal)
        authenticity_match = (
            authenticity_score >= self.user_criteria.min_authenticity_score
        )
        logger.debug(
            f"Authenticity match for deal {deal.id}: {authenticity_match} "
            f"(score: {authenticity_score})"
        )

        # Check category match
        category_match = self._check_category_match(deal)
        logger.debug(f"Category match for deal {deal.id}: {category_match}")

        # Check keyword match
        keyword_match = self._check_keyword_match(deal)
        logger.debug(f"Keyword match for deal {deal.id}: {keyword_match}")

        # Overall pass/fail
        passes_filters = (
            price_match
            and discount_match
            and authenticity_match
            and category_match
            and keyword_match
            and evaluation.is_relevant
        )

        # Calculate urgency level
        urgency_level = self._calculate_urgency_level(
            deal, evaluation, authenticity_score
        )

        filter_result = FilterResult(
            passes_filters=passes_filters,
            price_match=price_match,
            authenticity_score=authenticity_score,
            urgency_level=urgency_level,
        )

        logger.info(
            f"Filter result for deal {deal.id}: passes={passes_filters}, "
            f"urgency={urgency_level.value}"
        )

        return filter_result

    def _check_category_match(self, deal: Deal) -> bool:
        """Check if deal category matches user criteria."""
        if not self.user_criteria.categories:
            return True  # No category filter set

        # Case-insensitive category matching
        deal_category = deal.category.lower()
        user_categories = [cat.lower() for cat in self.user_criteria.categories]

        return deal_category in user_categories

    def _check_keyword_match(self, deal: Deal) -> bool:
        """Check if deal contains any of the user's keywords."""
        if not self.user_criteria.keywords:
            return True  # No keyword filter set

        # Search in title and description (case-insensitive)
        search_text = f"{deal.title} {deal.description}".lower()
        user_keywords = [keyword.lower() for keyword in self.user_criteria.keywords]

        return any(keyword in search_text for keyword in user_keywords)

    def _calculate_urgency_level(
        self, deal: Deal, evaluation: EvaluationResult, authenticity_score: float
    ) -> UrgencyLevel:
        """Calculate urgency level based on deal characteristics."""
        urgency_score = 0

        # High discount increases urgency
        if deal.discount_percentage and deal.discount_percentage >= 50:
            urgency_score += 2
        elif deal.discount_percentage and deal.discount_percentage >= 30:
            urgency_score += 1

        # Low price increases urgency
        if deal.price and deal.price <= 50:
            urgency_score += 2
        elif deal.price and deal.price <= 100:
            urgency_score += 1

        # High authenticity score increases urgency
        if authenticity_score >= 0.8:
            urgency_score += 1

        # High confidence from LLM increases urgency
        if evaluation.confidence_score >= 0.8:
            urgency_score += 1

        # Check for urgency indicators in the deal
        urgency_keywords = [
            "limited time",
            "expires",
            "while stocks last",
            "flash sale",
            "today only",
        ]
        deal_text = f"{deal.title} {deal.description}".lower()

        for keyword in urgency_keywords:
            if keyword in deal_text:
                urgency_score += 1
                break

        # Map score to urgency level
        if urgency_score >= 5:
            return UrgencyLevel.URGENT
        elif urgency_score >= 3:
            return UrgencyLevel.HIGH
        elif urgency_score >= 1:
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW
