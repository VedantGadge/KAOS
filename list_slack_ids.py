"""
Retrieve Slack User and Channel IDs
"""
from slack_sdk import WebClient
from config.settings import settings

client = WebClient(token=settings.SLACK_BOT_TOKEN)

try:
    print("=== Users ===")
    users = client.users_list()
    for user in users['members']:
        if not user['is_bot']:
            print(f"Name: {user['name']}, ID: {user['id']}, Real Name: {user.get('real_name')}")

    print("\n=== Channels ===")
    channels = client.conversations_list()
    for channel in channels['channels']:
        print(f"Name: #{channel['name']}, ID: {channel['id']}")

except Exception as e:
    print(f"Error: {e}")
