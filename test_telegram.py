#!/usr/bin/env python3
"""
Quick test script to verify Telegram bot integration.
"""

import requests
import json

# Your bot details
BOT_TOKEN = "8255201714:AAGYlyN-zrH89v8UqrMHwWLhoa3AA-nGkIY"
CHAT_ID = "8020983439"

def send_test_message():
    """Send a test message to verify Telegram integration."""
    
    # Telegram Bot API URL
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Test message
    message = """🎉 *OzBargain Deal Filter Test*

✅ Telegram integration is working!

This is a test message from your OzBargain Deal Filter system.

*Next steps:*
• Configure your deal criteria
• Start the monitoring system
• Receive real deal alerts here

_Bot: @OzBargain_Firsthalfhero_bot_"""

    # Message payload
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        print("🚀 Sending test message to Telegram...")
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("✅ SUCCESS: Test message sent successfully!")
                print(f"📱 Message ID: {result['result']['message_id']}")
                print(f"👤 Sent to: {result['result']['chat']['first_name']}")
                return True
            else:
                print(f"❌ ERROR: Telegram API error: {result.get('description')}")
                return False
        else:
            print(f"❌ ERROR: HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")
        return False

def test_bot_info():
    """Test bot information retrieval."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        print("🔍 Testing bot information...")
        print(f"🔗 URL: {url}")
        print(f"🔑 Token length: {len(BOT_TOKEN)} characters")
        print(f"🔑 Token format: {'✅ Valid' if ':' in BOT_TOKEN and len(BOT_TOKEN) > 40 else '❌ Invalid'}")
        
        response = requests.get(url, timeout=10)
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result["result"]
                print(f"✅ Bot Info Retrieved:")
                print(f"   • Name: {bot_info.get('first_name')}")
                print(f"   • Username: @{bot_info.get('username')}")
                print(f"   • ID: {bot_info.get('id')}")
                print(f"   • Can Join Groups: {bot_info.get('can_join_groups')}")
                return True
            else:
                print(f"❌ ERROR: {result.get('description')}")
                return False
        else:
            try:
                error_detail = response.json()
                print(f"❌ ERROR: HTTP {response.status_code}")
                print(f"📄 Response: {error_detail}")
            except:
                print(f"❌ ERROR: HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("🤖 OzBargain Deal Filter - Telegram Integration Test")
    print("=" * 50)
    
    # Test bot info
    bot_ok = test_bot_info()
    print()
    
    # Send test message
    if bot_ok:
        message_ok = send_test_message()
        print()
        
        if message_ok:
            print("🎉 ALL TESTS PASSED!")
            print("Your Telegram integration is ready to use.")
            print()
            print("📋 Configuration for config.yaml:")
            print("messaging_platform:")
            print("  type: 'telegram'")
            print("  telegram:")
            print(f"    bot_token: '{BOT_TOKEN}'")
            print(f"    chat_id: '{CHAT_ID}'")
        else:
            print("❌ Message sending failed. Check the error above.")
    else:
        print("❌ Bot info test failed. Check your bot token.")