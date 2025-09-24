#!/usr/bin/env python3
"""
Token verification helper
"""
import requests

# Please paste your bot token here exactly as shown in BotFather:
BOT_TOKEN = input("Please paste your bot token from BotFather: ").strip()

print("\n🔍 Token Analysis:")
print(f"Length: {len(BOT_TOKEN)}")
print(f"Contains colon: {':' in BOT_TOKEN}")
print(
    f"First part (bot ID): {BOT_TOKEN.split(':')[0] if ':' in BOT_TOKEN else 'No colon found'}"
)
print(
    f"Second part length: {len(BOT_TOKEN.split(':')[1]) if ':' in BOT_TOKEN else 'No colon found'}"
)

# Test the token

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
try:
    response = requests.get(url, timeout=10)
    print(f"\n📡 API Response: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            bot_info = result["result"]
            print("✅ SUCCESS! Bot details:")
            print(f"   • Name: {bot_info.get('first_name')}")
            print(f"   • Username: @{bot_info.get('username')}")
            print(f"   • ID: {bot_info.get('id')}")
        else:
            print(f"❌ API Error: {result}")
    else:
        print(f"❌ HTTP Error: {response.text}")

except Exception as e:
    print(f"❌ Network Error: {e}")
