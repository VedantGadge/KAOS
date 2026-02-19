import sys
import os
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

def clear_channel(channel_name):
    client = WebClient(token=settings.SLACK_BOT_TOKEN)
    
    try:
        # 1. Resolve Channel Name to ID
        print(f"🔍 Looking for channel: {channel_name}...")
        channel_id = None
        
        # Check public channels only (to avoid missing scope error for groups:read)
        cursor = None
        while not channel_id:
            try:
                response = client.conversations_list(cursor=cursor, types="public_channel")
            except SlackApiError as e:
                print(f"❌ Error listing channels: {e.response['error']}")
                return

            for channel in response['channels']:
                if channel['name'] == channel_name.replace("#", ""):
                    channel_id = channel['id']
                    break
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor or channel_id:
                break
        
        if not channel_id:
            print(f"❌ Could not find channel '{channel_name}'")
            return

        print(f"✅ Found Channel ID: {channel_id}")
        
        # 2. Fetch and Delete Messages
        print("🗑️  Fetching messages to delete...")
        has_more = True
        cursor = None
        deleted_count = 0
        
        while has_more:
            # Fetch history
            try:
                history = client.conversations_history(channel=channel_id, cursor=cursor, limit=50)
            except SlackApiError as e:
                if e.response['error'] == 'missing_scope':
                    print(f"❌ Missing Scope: Your Bot Token needs 'channels:history' scope to read messages.")
                    print(f"   Please add it in the Slack Developer Portal -> OAuth & Permissions.")
                    return
                raise e

            messages = history['messages']
            
            if not messages:
                print("👍 Channel is empty.")
                break
                
            print(f"   Found {len(messages)} messages. Deleting...")
            
            for msg in messages:
                try:
                    # Specific to bot token: can usually only delete its own messages 
                    # OR requires admin permissions to delete others.
                    # We will try to delete everything.
                    client.chat_delete(channel=channel_id, ts=msg['ts'])
                    print(f"   - Deleted message {msg['ts']}")
                    deleted_count += 1
                    time.sleep(1.2) # Slack Rate limit Tier 3 is ~50 per minute. Be extra safe.
                except SlackApiError as e:
                    if e.response['error'] == "cant_delete_message":
                        print(f"   ⚠️  Skipped (Can't delete user message): {msg['ts']}")
                    elif e.response['error'] == "missing_scope":
                        print(f"❌ Missing Scope: Your Bot Token needs 'chat:write' scope to delete messages.")
                        return
                    else:
                        print(f"   ❌ Error deleting {msg['ts']}: {e.response['error']}")
            
            cursor = history.get('response_metadata', {}).get('next_cursor')
            has_more = bool(cursor)
            
        print(f"✨ Done! Deleted {deleted_count} messages from {channel_name}.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/clear_slack_channel.py <channel_name>")
        print("Example: python scripts/clear_slack_channel.py dave")
        sys.exit(1)
        
    target_channel = sys.argv[1]
    clear_channel(target_channel)
