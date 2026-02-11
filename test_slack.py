"""
Test Slack integration
"""
from slack_sdk import WebClient
from config.settings import settings

print("Testing Slack API connection...")
print(f"Bot Token: {settings.SLACK_BOT_TOKEN[:20]}...\n")

try:
    client = WebClient(token=settings.SLACK_BOT_TOKEN)
    
    # Test authentication
    auth_response = client.auth_test()
    print(f"✅ Authentication successful!")
    print(f"   Bot Name: {auth_response['user']}")
    print(f"   Team: {auth_response['team']}")
    print(f"   User ID: {auth_response['user_id']}\n")
    
    # Send a test message to #all-kaos
    print("Sending test message to #all-kaos...")
    response = client.chat_postMessage(
        channel="#all-kaos",
        text="🤖 Test message from KAOS Agent! Slack integration is working! 🎉"
    )
    
    print(f"✅ Message sent successfully!")
    print(f"   Channel: {response['channel']}")
    print(f"   Timestamp: {response['ts']}")
    
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
