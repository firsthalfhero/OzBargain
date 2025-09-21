#!/usr/bin/env python3
"""
Test deal processing pipeline by creating a test deal
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ozb_deal_filter.models.deal import Deal, RawDeal
from ozb_deal_filter.models.evaluation import EvaluationResult
from ozb_deal_filter.components.filter_engine import FilterEngine
from ozb_deal_filter.components.alert_formatter import AlertFormatter
from ozb_deal_filter.components.message_dispatcher import MessageDispatcherFactory
from ozb_deal_filter.models.config import UserCriteria
from datetime import datetime

def create_test_deal():
    """Create a test deal that should pass all filters"""
    raw_deal = RawDeal(
        id="test_deal_123",
        title="Test Gaming Laptop Deal - 50% Off!",
        description="Amazing gaming laptop with RTX 4060, perfect for gaming and work. Originally $2000, now only $1000!",
        link="https://example.com/deal",
        published_date=datetime.now(),
        category="Computing",
        price=1000.0,
        discount_percentage=50.0
    )
    
    # Convert to Deal object
    deal = Deal(
        id=raw_deal.id,
        title=raw_deal.title,
        description=raw_deal.description,
        link=raw_deal.link,
        published_date=raw_deal.published_date,
        category=raw_deal.category,
        price=raw_deal.price,
        discount_percentage=raw_deal.discount_percentage
    )
    
    return deal

def test_filter_engine():
    """Test the filter engine with a test deal"""
    print("🔍 Testing Filter Engine...")
    
    # Create very permissive criteria
    user_criteria = UserCriteria(
        prompt_template_path="prompts/deal_evaluator.txt",
        max_price=5000.0,
        min_discount_percentage=5.0,
        categories=[],  # Empty = allow all
        keywords=[],   # Empty = allow all
        min_authenticity_score=0.1
    )
    
    filter_engine = FilterEngine(user_criteria)
    deal = create_test_deal()
    
    # Create a positive evaluation
    evaluation = EvaluationResult(
        is_relevant=True,
        confidence_score=0.9,
        reasoning="This is a great gaming laptop deal with excellent discount"
    )
    
    print(f"📦 Test Deal: {deal.title}")
    print(f"💰 Price: ${deal.price}")
    print(f"📊 Discount: {deal.discount_percentage}%")
    print(f"🏷️ Category: {deal.category}")
    
    # Apply filters
    filter_result = filter_engine.apply_filters(deal, evaluation)
    
    print(f"\n🎯 Filter Results:")
    print(f"✅ Passes Filters: {filter_result.passes_filters}")
    print(f"💰 Price Match: {filter_result.price_match}")
    print(f"🔒 Authenticity Score: {filter_result.authenticity_score}")
    print(f"⚡ Urgency Level: {filter_result.urgency_level}")
    
    return deal, filter_result

def test_message_sending():
    """Test sending a message via Telegram"""
    print("\n📱 Testing Message Sending...")
    
    deal, filter_result = test_filter_engine()
    
    if not filter_result.passes_filters:
        print("❌ Deal failed filters, cannot test message sending")
        return False
    
    # Create alert formatter
    alert_formatter = AlertFormatter()
    formatted_alert = alert_formatter.format_alert(deal, filter_result)
    
    print(f"📝 Formatted Alert:")
    print(f"Title: {formatted_alert.title}")
    print(f"Message: {formatted_alert.message[:100]}...")
    
    # Create message dispatcher
    config = {
        "bot_token": "8255201714:AAGYlyN-zrH89v8UqrMHwWLhoa3AA-nGkIY",
        "chat_id": "8020983439"
    }
    
    message_dispatcher = MessageDispatcherFactory.create_dispatcher("telegram", config)
    
    # Send the alert
    delivery_result = message_dispatcher.send_alert(formatted_alert)
    
    print(f"\n📨 Delivery Result:")
    print(f"✅ Success: {delivery_result.success}")
    print(f"📊 Status: {delivery_result.status}")
    if not delivery_result.success:
        print(f"❌ Error: {delivery_result.error_message}")
    
    return delivery_result.success

if __name__ == "__main__":
    print("🧪 Testing Deal Processing Pipeline...")
    success = test_message_sending()
    
    if success:
        print("\n🎉 All tests passed! Check your Telegram for the test message.")
    else:
        print("\n❌ Tests failed. Check the logs above for details.")