"""Unit tests for the FilterEngine and PriceFilter components."""

from datetime import datetime

from ozb_deal_filter.components.filter_engine import FilterEngine, PriceFilter
from ozb_deal_filter.models.config import UserCriteria
from ozb_deal_filter.models.deal import Deal
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.models.filter import UrgencyLevel


class TestPriceFilter:
    """Test cases for PriceFilter class."""

    def test_price_filter_no_limit(self):
        """Test price filter with no maximum price set."""
        price_filter = PriceFilter(max_price=None)

        deal = Deal(
            id="test1",
            title="Test Deal",
            description="Test description",
            price=999.99,
            original_price=1200.00,
            discount_percentage=16.67,
            category="Electronics",
            url="https://example.com/deal1",
            timestamp=datetime.now(),
            votes=10,
            comments=5,
            urgency_indicators=[],
        )

        assert price_filter.check_price_threshold(deal) is True

    def test_price_filter_under_limit(self):
        """Test price filter with deal under the limit."""
        price_filter = PriceFilter(max_price=100.0)

        deal = Deal(
            id="test2",
            title="Cheap Deal",
            description="Great value",
            price=50.0,
            original_price=80.0,
            discount_percentage=37.5,
            category="Books",
            url="https://example.com/deal2",
            timestamp=datetime.now(),
            votes=15,
            comments=3,
            urgency_indicators=[],
        )

        assert price_filter.check_price_threshold(deal) is True

    def test_price_filter_over_limit(self):
        """Test price filter with deal over the limit."""
        price_filter = PriceFilter(max_price=100.0)

        deal = Deal(
            id="test3",
            title="Expensive Deal",
            description="High-end product",
            price=150.0,
            original_price=200.0,
            discount_percentage=25.0,
            category="Electronics",
            url="https://example.com/deal3",
            timestamp=datetime.now(),
            votes=5,
            comments=2,
            urgency_indicators=[],
        )

        assert price_filter.check_price_threshold(deal) is False

    def test_price_filter_no_price_info(self):
        """Test price filter with deal having no price information."""
        price_filter = PriceFilter(max_price=100.0)

        deal = Deal(
            id="test4",
            title="Free Deal",
            description="No cost item",
            price=None,
            original_price=None,
            discount_percentage=None,
            category="Freebies",
            url="https://example.com/deal4",
            timestamp=datetime.now(),
            votes=20,
            comments=8,
            urgency_indicators=[],
        )

        assert price_filter.check_price_threshold(deal) is True

    def test_discount_filter_no_requirement(self):
        """Test discount filter with no minimum requirement."""
        price_filter = PriceFilter()

        deal = Deal(
            id="test5",
            title="Small Discount Deal",
            description="Minor savings",
            price=95.0,
            original_price=100.0,
            discount_percentage=5.0,
            category="Clothing",
            url="https://example.com/deal5",
            timestamp=datetime.now(),
            votes=3,
            comments=1,
            urgency_indicators=[],
        )

        assert price_filter.check_discount_percentage(deal, min_discount=None) is True

    def test_discount_filter_meets_requirement(self):
        """Test discount filter with deal meeting minimum requirement."""
        price_filter = PriceFilter()

        deal = Deal(
            id="test6",
            title="Good Discount Deal",
            description="Significant savings",
            price=60.0,
            original_price=100.0,
            discount_percentage=40.0,
            category="Home",
            url="https://example.com/deal6",
            timestamp=datetime.now(),
            votes=25,
            comments=12,
            urgency_indicators=[],
        )

        assert price_filter.check_discount_percentage(deal, min_discount=30.0) is True

    def test_discount_filter_below_requirement(self):
        """Test discount filter with deal below minimum requirement."""
        price_filter = PriceFilter()

        deal = Deal(
            id="test7",
            title="Low Discount Deal",
            description="Small savings",
            price=85.0,
            original_price=100.0,
            discount_percentage=15.0,
            category="Sports",
            url="https://example.com/deal7",
            timestamp=datetime.now(),
            votes=8,
            comments=4,
            urgency_indicators=[],
        )

        assert price_filter.check_discount_percentage(deal, min_discount=30.0) is False


class TestFilterEngine:
    """Test cases for FilterEngine class."""

    def create_user_criteria(self, **kwargs):
        """Helper to create UserCriteria with defaults."""
        defaults = {
            "prompt_template_path": "prompts/test.txt",
            "max_price": 100.0,
            "min_discount_percentage": 20.0,
            "categories": ["Electronics", "Books"],
            "keywords": ["laptop", "book"],
            "min_authenticity_score": 0.7,
        }
        defaults.update(kwargs)
        return UserCriteria(**defaults)

    def create_deal(self, **kwargs):
        """Helper to create Deal with defaults."""
        defaults = {
            "id": "test_deal",
            "title": "Test Deal",
            "description": "Test description",
            "price": 50.0,
            "original_price": 80.0,
            "discount_percentage": 37.5,
            "category": "Electronics",
            "url": "https://example.com/deal",
            "timestamp": datetime.now(),
            "votes": 10,
            "comments": 5,
            "urgency_indicators": [],
        }
        defaults.update(kwargs)
        return Deal(**defaults)

    def create_evaluation_result(self, **kwargs):
        """Helper to create EvaluationResult with defaults."""
        defaults = {
            "is_relevant": True,
            "confidence_score": 0.8,
            "reasoning": "Test reasoning",
        }
        defaults.update(kwargs)
        return EvaluationResult(**defaults)

    def test_filter_engine_initialization(self):
        """Test FilterEngine initialization."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        assert filter_engine.user_criteria == user_criteria
        assert filter_engine.price_filter.max_price == 100.0

    def test_apply_filters_all_pass(self):
        """Test applying filters when all criteria pass."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Great laptop deal",
            price=80.0,
            original_price=100.0,
            discount_percentage=20.0,
            category="Electronics",
        )

        evaluation = self.create_evaluation_result(is_relevant=True)

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is True
        assert result.price_match is True
        assert isinstance(result.authenticity_score, float)
        assert 0.0 <= result.authenticity_score <= 1.0
        assert isinstance(result.urgency_level, UrgencyLevel)

    def test_apply_filters_price_fail(self):
        """Test applying filters when price exceeds limit."""
        user_criteria = self.create_user_criteria(max_price=50.0)
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            price=80.0, original_price=100.0, discount_percentage=20.0
        )

        evaluation = self.create_evaluation_result()

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False
        assert result.price_match is False

    def test_apply_filters_discount_fail(self):
        """Test applying filters when discount is too low."""
        user_criteria = self.create_user_criteria(min_discount_percentage=50.0)
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            price=50.0, original_price=80.0, discount_percentage=37.5
        )

        evaluation = self.create_evaluation_result()

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False

    def test_apply_filters_authenticity_fail(self):
        """Test applying filters when authenticity score is too low."""
        user_criteria = self.create_user_criteria(min_authenticity_score=0.9)
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal()

        # Create a deal with low community engagement to get low authenticity score
        deal = self.create_deal(
            votes=-5, comments=0
        )  # Negative votes should give low score

        evaluation = self.create_evaluation_result()

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False
        assert result.authenticity_score < 0.9  # Should be below the high threshold

    def test_apply_filters_category_fail(self):
        """Test applying filters when category doesn't match."""
        user_criteria = self.create_user_criteria(categories=["Books", "Clothing"])
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(category="Sports")

        evaluation = self.create_evaluation_result()

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False

    def test_apply_filters_keyword_fail(self):
        """Test applying filters when keywords don't match."""
        user_criteria = self.create_user_criteria(keywords=["smartphone", "tablet"])
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Great book deal", description="Amazing novel at low price"
        )

        evaluation = self.create_evaluation_result()

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False

    def test_apply_filters_llm_not_relevant(self):
        """Test applying filters when LLM says deal is not relevant."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal()

        evaluation = self.create_evaluation_result(is_relevant=False)

        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False

    def test_category_match_case_insensitive(self):
        """Test category matching is case insensitive."""
        user_criteria = self.create_user_criteria(categories=["electronics", "books"])
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(category="ELECTRONICS")

        assert filter_engine._check_category_match(deal) is True

    def test_keyword_match_case_insensitive(self):
        """Test keyword matching is case insensitive."""
        user_criteria = self.create_user_criteria(keywords=["LAPTOP", "BOOK"])
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="great laptop deal", description="high-end gaming laptop"
        )

        assert filter_engine._check_keyword_match(deal) is True

    def test_urgency_calculation_high_discount(self):
        """Test urgency calculation with high discount."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            price=30.0, original_price=100.0, discount_percentage=70.0
        )

        # Create deal with high community engagement for high authenticity score
        deal = self.create_deal(
            price=30.0,
            original_price=100.0,
            discount_percentage=70.0,
            votes=25,  # High positive votes
            comments=10,  # Good engagement
        )

        evaluation = self.create_evaluation_result(confidence_score=0.9)

        # Calculate authenticity score for the deal
        authenticity_score = filter_engine.authenticity_assessor.assess_authenticity(
            deal
        )
        urgency = filter_engine._calculate_urgency_level(
            deal, evaluation, authenticity_score
        )

        # Should be HIGH or URGENT due to high discount, low price, high scores
        assert urgency in [UrgencyLevel.HIGH, UrgencyLevel.URGENT]

    def test_urgency_calculation_low_scores(self):
        """Test urgency calculation with low scores."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            price=200.0, original_price=220.0, discount_percentage=9.0
        )

        # Create deal with poor community engagement for low authenticity score
        deal = self.create_deal(
            price=200.0,
            original_price=220.0,
            discount_percentage=9.0,
            votes=0,  # No votes
            comments=0,  # No comments
        )

        evaluation = self.create_evaluation_result(confidence_score=0.5)

        # Calculate authenticity score for the deal
        authenticity_score = filter_engine.authenticity_assessor.assess_authenticity(
            deal
        )
        urgency = filter_engine._calculate_urgency_level(
            deal, evaluation, authenticity_score
        )

        # Should be LOW due to low discount, high price, low scores
        assert urgency == UrgencyLevel.LOW

    def test_urgency_calculation_with_keywords(self):
        """Test urgency calculation with urgency keywords."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Flash sale - limited time offer!",
            description="This deal expires today only",
        )

        evaluation = self.create_evaluation_result()

        # Calculate authenticity score for the deal
        authenticity_score = filter_engine.authenticity_assessor.assess_authenticity(
            deal
        )
        urgency = filter_engine._calculate_urgency_level(
            deal, evaluation, authenticity_score
        )

        # Should have increased urgency due to keywords
        assert urgency in [UrgencyLevel.MEDIUM, UrgencyLevel.HIGH, UrgencyLevel.URGENT]

    def test_empty_categories_and_keywords(self):
        """Test filter behavior with empty categories and keywords lists."""
        user_criteria = self.create_user_criteria(categories=[], keywords=[])
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(category="RandomCategory")

        # Should pass category and keyword checks when lists are empty
        assert filter_engine._check_category_match(deal) is True
        assert filter_engine._check_keyword_match(deal) is True

    def test_expired_deal_in_title(self):
        """Test that deals with 'expired' in title are filtered out."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Great laptop deal [EXPIRED]",
            description="Amazing discount on gaming laptop",
        )

        evaluation = self.create_evaluation_result()
        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False
        assert result.price_match is False  # Should be False for expired deals
        assert result.authenticity_score == 0.0  # Should be 0 for expired deals

    def test_expired_deal_in_description(self):
        """Test that deals with expiration indicators in description are filtered out."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Great laptop deal",
            description="This offer has expired and is no longer available",
        )

        evaluation = self.create_evaluation_result()
        result = filter_engine.apply_filters(deal, evaluation)

        assert result.passes_filters is False

    def test_expired_deal_various_patterns(self):
        """Test various expiration patterns are detected."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        expiration_texts = [
            "Deal has ended",
            "Offer expired",
            "SOLD OUT",
            "No longer available",
            "Promotion ended",
            "(expired)",
            "Deal closed",
            "Inactive deal",
        ]

        for expiration_text in expiration_texts:
            deal = self.create_deal(
                title=f"Great deal - {expiration_text}", description="Test description"
            )

            evaluation = self.create_evaluation_result()
            result = filter_engine.apply_filters(deal, evaluation)

            assert (
                result.passes_filters is False
            ), f"Failed to detect expiration in: {expiration_text}"

    def test_non_expired_deal_passes(self):
        """Test that non-expired deals pass the expiration check."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Great laptop deal - Limited time offer",
            description="Amazing discount on gaming laptop while stocks last",
        )

        # Should pass expiration check (other filters may still fail)
        assert filter_engine._check_deal_expired(deal) is False

    def test_expiration_check_case_insensitive(self):
        """Test that expiration checking is case insensitive."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        deal = self.create_deal(
            title="Great deal - EXPIRED", description="Test description"
        )

        assert filter_engine._check_deal_expired(deal) is True

        deal2 = self.create_deal(title="Great deal", description="This deal has ENDED")

        assert filter_engine._check_deal_expired(deal2) is True

    def test_expiration_check_direct_method(self):
        """Test the _check_deal_expired method directly."""
        user_criteria = self.create_user_criteria()
        filter_engine = FilterEngine(user_criteria)

        # Test expired deal
        expired_deal = self.create_deal(
            title="Laptop deal [expired]", description="Great laptop"
        )
        assert filter_engine._check_deal_expired(expired_deal) is True

        # Test active deal
        active_deal = self.create_deal(
            title="Laptop deal - great price", description="Amazing laptop discount"
        )
        assert filter_engine._check_deal_expired(active_deal) is False
