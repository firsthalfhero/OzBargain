#!/usr/bin/env python3
"""
Get your chat ID after starting the bot
"""

import requests

BOT_TOKEN = "8255201714:AAGYlyN-zrH89v8UqrMHwWLhoa3AA-nGkIY"

def get_updates():
    """Get recent messages to find your chat ID"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok") and result.get("result"):
                print("📨 Recent messages:")
                for update in result["result"]:
                    if "message" in update:
                        msg = update["message"]
                        chat = msg["chat"]
                        user = msg["from"]
                        
                        print(f"\n💬 Message ID: {update['update_id']}")
                        print(f"👤 From: {user.get('first_name', '')} {user.get('last_name', '')}")
                        print(f"🆔 User ID: {user['id']}")
                        print(f"💬 Chat ID: {chat['id']}")
                        print(f"📝 Text: {msg.get('text', 'N/A')}")
                        print(f"📅 Date: {msg.get('date')}")
                        
                        if chat['id'] == user['id']:
                            print(f"✅ This is your personal chat ID: {chat['id']}")
                
                if not result["result"]:
                    print("❌ No messages found. Please:")
                    print("1. Go to @OzBargain_Firsthalfhero_bot")
                    print("2. Click START")
                    print("3. Send any message")
                    print("4. Run this script again")
            else:
                print("❌ No updates found")
        else:
            print(f"❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🔍 Getting your chat ID...")
    get_updates()