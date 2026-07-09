import os
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()
token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=token)

try:
    response = client.conversations_list(types="public_channel")
    channels = response["channels"]
    print("CHANNEL IDs FOUND:")
    for channel in channels:
        if channel["name"].startswith("dev-") or channel["name"] == "all-kaos":
            print(f"{channel['name']}: {channel['id']}")
except Exception as e:
    print(f"❌ Error: {e}")
