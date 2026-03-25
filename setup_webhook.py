import requests

def setup_webhook(token, site_url):
    site_url = site_url.rstrip('/')
    webhook_url = f"{site_url}/tickets/telegram-webhook/{token}/"
    
    print(f"Setting Webhook URL to: {webhook_url}")
    
    api_url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            print("\n🎉 SUCCESS! Telegram Webhook is now active.")
            print("Your bot is now listening for interactions and button clicks.")
        else:
            print(f"\n❌ FAILED: {data.get('description')}")
    except Exception as e:
        print(f"\n❌ Error connecting to Telegram API: {e}")

if __name__ == "__main__":
    print("--- Telegram Webhook Setup ---")
    token = input("Enter your Telegram Bot Token: ").strip()
    site_url = input("Enter your production SITE_URL (e.g., https://taskfiber.onrender.com): ").strip()
    
    if token and site_url:
        setup_webhook(token, site_url)
    else:
        print("Both Token and SITE_URL are required!")
