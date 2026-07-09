import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()
token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=token)

try:
    # 1. Test auth to see who the bot is
    auth_test = client.auth_test()
    bot_id = auth_test["user_id"]
    bot_name = auth_test["user"]
    print(f"✅ Authenticated as: {bot_name} (ID: {bot_id})")

    # 2. Find the #all-kaos channel
    response = client.conversations_list(types="public_channel")
    channels = response["channels"]
    target_channel_id = None
    for channel in channels:
        if channel["name"] == "all-kaos":
            target_channel_id = channel["id"]
            break
            
    if not target_channel_id:
        print("❌ Could not find public channel #all-kaos. Is it private?")
    else:
        print(f"🔍 Found #all-kaos with ID: {target_channel_id}")
        # 3. Join the channel
        client.conversations_join(channel=target_channel_id)
        print("✅ Bot successfully joined the #all-kaos channel!")
        
        # 4. Send a test message
        client.chat_postMessage(channel=target_channel_id, text="👋 Hello! I have successfully connected to the channel.")
        print("✅ Test message sent!")

except SlackApiError as e:
    print(f"❌ Slack API Error: {e.response['error']}")
except Exception as e:
    print(f"❌ Error: {e}")
