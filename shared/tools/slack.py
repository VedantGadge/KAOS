from langchain_core.tools import tool
from config.settings import settings
from shared.logger import logger
from shared.neo4j.client import Neo4jClient
from shared.utils.retries import retry_with_backoff

@tool
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def send_slack_message(
    channel: str,
    bug_title: str,
    assignee: str,
    service_name: str,
    severity: str,
    notion_url: str,
    custom_message: str = ""
) -> str:
    """
    Send a bug assignment DM to the assignee and announce the bug in #all-kaos.
    """
    logger.info(f"📨 Preparing Slack message for {channel}...")
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        target_id = channel
        
        if channel.startswith('U'):
            try:
                open_resp = client.conversations_open(users=channel)
                target_id = open_resp['channel']['id']
                logger.info(f"📡 Opened DM channel: {target_id}")
            except SlackApiError as e:
                logger.warning(f"⚠️ Could not open DM with {channel}: {e.response['error']}")
        
        if custom_message:
            dm_text = custom_message
        else:
            dm_text = (
                f"You have been assigned a {severity} bug in {service_name}. "
                f"The bug has already been logged in Notion. "
                f"Here is the link: {notion_url}"
            )
        
        try:
            client.chat_postMessage(channel=target_id, text=dm_text)
            logger.info(f"✅ Slack message sent successfully to {target_id}!")
        except SlackApiError as e:
            logger.warning(f"⚠️ Could not send DM to {target_id}: {e.response['error']}")
        announcement = (
            f"🚨 *Bug Report Alert*\n"
            f"───────────────────\n"
            f"*Bug:* {bug_title}\n"
            f"*Service:* {service_name}\n"
            f"*Severity:* {severity}\n"
            f"*Assigned To:* {assignee}\n"
            f"───────────────────\n"
            f"The team is on it. 🔧"
        )
        try:
            client.chat_postMessage(channel="C0AEPCBT9A5", text=announcement)
            logger.info(f"📢 Announcement posted in #all-kaos")
        except SlackApiError as e:
            logger.warning(f"⚠️ Could not post to #all-kaos: {e.response['error']}")
        
        return f"Message sent to {target_id}"
        
    except Exception as e:
        error_msg = f"Error sending Slack message: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

@tool
def send_slack_dm(channel: str, text: str) -> str:
    """
    Send a direct message to a user on Slack.
    Will resolve names (e.g. "Dave") to Slack IDs via Neo4j if needed.
    """
    logger.info(f"📨 Sending Slack DM to {channel}...")
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        target_id = channel

        if not channel.startswith("U") and not channel.startswith("#") and not channel.startswith("@"):
            logger.info(f"🔍 Looking up Slack ID for name: {channel}")
            try:
                neo4j = Neo4jClient()
                query = "MATCH (p:Person) WHERE toLower(p.name) = toLower($name) RETURN p.slack_id as slack_id"
                res = neo4j.query(query, {"name": channel})
                neo4j.close()
                if res and res[0].get("slack_id"):
                    target_id = res[0]["slack_id"]
                    logger.info(f"✅ Resolved '{channel}' to Slack ID: {target_id}")
                else:
                    logger.warning(f"⚠️ Could not resolve name '{channel}'. Defaulting to #all-kaos.")
                    target_id = "C0AEPCBT9A5" 
            except Exception as e:
                logger.warning(f"⚠️ Neo4j Lookup failed: {e}")
                target_id = "C0AEPCBT9A5"

        if target_id.startswith('U'):
            try:
                open_resp = client.conversations_open(users=target_id)
                target_id = open_resp['channel']['id']
                logger.info(f"📡 Opened DM channel: {target_id}")
            except SlackApiError as e:
                logger.warning(f"⚠️ Could not open DM with {channel}: {e.response['error']}")

        client.chat_postMessage(channel=target_id, text=text)
        logger.info(f"✅ Slack DM sent to {target_id}!")
        return f"Message sent to {target_id}"

    except Exception as e:
        error_msg = f"Error sending Slack DM: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

@tool
def send_slack_broadcast(message: str) -> str:
    """
    Send an announcement to the #all-kaos channel.
    """
    logger.info(f"📢 Broadcasting to #all-kaos: {message}")
    try:
        from slack_sdk import WebClient
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        client.chat_postMessage(channel="C0AEPCBT9A5", text=message)
        return "Broadcast sent to #all-kaos."
    except Exception as e:
        return f"Failed to send Slack broadcast: {str(e)}"
