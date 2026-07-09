import os
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()
token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=token)

try:
    # Use the ID we found earlier instead of the name string
    response = client.chat_postMessage(channel="C0AEPCBT9A5", text="🚨 *Test Alert* - If you see this, the bot has permissions!")
    print("✅ Message sent successfully using Channel ID!")
except Exception as e:
    print(f"❌ Error: {e}")
