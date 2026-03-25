import requests
import sys

def test_telegram_bot(token, chat_id):
    print(f"Testing Telegram Bot with Token: {token[:5]}... and Chat ID: {chat_id}")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': '✅ *TEST MESSAGE:* Your Telegram Notification System is working properly!',
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response_data = response.json()
        
        if response.status_code == 200:
            print("\n🎉 SUCCESS! The bot successfully sent the message.")
        else:
            print("\n❌ FAILED to send message.")
            print(f"Error Description: {response_data.get('description')}")
            print("\nCommon Errors:")
            print("- 'Bad Request: chat not found' -> The Chat ID is incorrect, or the user hasn't clicked 'Start' on the bot yet.")
            print("- 'Unauthorized' -> Your Bot Token is incorrect.")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED: Network error -> {e}")

if __name__ == "__main__":
    print("--- Telegram Bot Configuration Tester ---")
    token = input("Enter your Telegram Bot Token: ").strip()
    chat_id = input("Enter the Employee's numeric Chat ID: ").strip()
    
    if token and chat_id:
        test_telegram_bot(token, chat_id)
    else:
        print("Both Token and Chat ID are required!")
