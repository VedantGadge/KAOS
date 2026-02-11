from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient
from notion_client import Client as NotionClient
from config.settings import settings
from datetime import datetime

# ─────────────────────────────────────────────
# Tool 1: Neo4j — Find Active Service Owner
# ─────────────────────────────────────────────
@tool
def find_service_owner(service_name: str) -> str:
    """
    Find the best ACTIVE person to handle a service issue.
    Priority:
    1. Direct Owner (if Active)
    2. Any Team Member who WORKED_ON this service (if Active)
    3. Manager (Escalation)
    """
    print(f"🔍 Finding best ACTIVE contact for {service_name}...")
    try:
        neo4j = Neo4jClient()
        
        # 1. Check Direct Owner
        owner_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service {name: $service_name})
        RETURN p.name as name, p.status as status, p.slack_id as slack_id
        """
        owner_res = neo4j.query(owner_query, {"service_name": service_name})
        
        if owner_res:
            owner = owner_res[0]
            if owner.get('status') == 'Active':
                neo4j.close()
                return f"Owner: {owner['name']} (Active) | Slack: {owner['slack_id']}"
            print(f"⚠️ Owner {owner['name']} is {owner['status']}. Checking Team Members...")

        # 2. Check Team Members who WORKED_ON the service
        team_query = """
        MATCH (p:Person)-[:WORKED_ON]->(s:Service {name: $service_name})
        WHERE p.status = 'Active'
        RETURN p.name as name, p.slack_id as slack_id
        LIMIT 1
        """
        team_res = neo4j.query(team_query, {"service_name": service_name})
        
        if team_res:
            member = team_res[0]
            neo4j.close()
            return f"Assigned to Contributor: {member['name']} (Active) | Slack: {member['slack_id']} | Reason: Owner unavailable, but {member['name']} worked on this service."

        # 3. Escalate to Manager
        if owner_res:
             manager_query = """
             MATCH (p:Person {name: $name})-[:REPORTS_TO]->(m:Person)
             RETURN m.name as name, m.status as status, m.slack_id as slack_id
             """
             manager_res = neo4j.query(manager_query, {"name": owner['name']})
             if manager_res:
                 manager = manager_res[0]
                 neo4j.close()
                 return f"Escalated to Manager: {manager['name']} ({manager.get('status', 'Unknown')}) | Slack: {manager['slack_id']} | Reason: Owner and Team unavailable."

        neo4j.close()
        return f"No active owner, contributor, or manager found for {service_name}."

    except Exception as e:
        return f"Error querying Neo4j: {str(e)}"

# ─────────────────────────────────────────────
# Tool 2: Notion — Add Bug to Dashboard
# ─────────────────────────────────────────────
@tool
def add_to_notion_dashboard(
    title: str,
    assignee: str,
    service_name: str,
    severity: str,
    description: str
) -> str:
    """
    Add a bug/issue entry to the Notion Dashboard.
    This creates a new page in the KAOS Bug Tracker database.
    Args:
        title: Title of the bug (e.g., "NullPointerException in ProcessTransaction").
        assignee: Name of the person assigned to fix this.
        service_name: The affected service (e.g., "PaymentService").
        severity: Severity level (e.g., "CRITICAL", "HIGH", "MEDIUM", "LOW").
        description: Detailed description of the bug.
    """
    print(f"📋 Adding to Notion Dashboard: {title} -> Assigned to {assignee}")
    try:
        notion = NotionClient(auth=settings.NOTION_API_KEY)
        database_id = settings.NOTION_DATABASE_ID

        # --- DEDUPLICATION CHECK ---
        # Check if an "Open" bug with the same title already exists
        # NOTE: Using search() because databases.query() is missing in this environment
        search_results = notion.search(query=title, filter={"value": "page", "property": "object"}).get("results", [])
        
        # Manually filter for the correct database and status
        for page in search_results:
            # Check database ID (some pages might be outside this DB)
            if page.get("parent", {}).get("database_id", "").replace("-", "") == database_id.replace("-", ""):
                props = page.get("properties", {})
                # Check Status is 'Open'
                status_obj = props.get("Status", {}).get("status", {})
                if status_obj.get("name") == "Open":
                    page_url = page.get("url")
                    print(f"⏭️  Duplicate found in Notion (via search). Skipping creation. URL: {page_url}")
                    return f"Duplicate bug already exists in Notion: {page_url}"
        # ---------------------------

        # Create a new page in the Notion database
        new_page = notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Tasks": { 
                    "title": [{"text": {"content": title}}]
                },
                "Text": {
                    "rich_text": [{"text": {"content": assignee}}]
                },
                "Text 1": {
                    "rich_text": [{"text": {"content": service_name}}]
                },
                "Severity": {
                    "select": {"name": severity}
                },
                "Status": {
                    "status": {"name": "Open"}  # Options: Open, In progress, To be reviwed, Resolved
                },
                "Date": {
                    "date": {"start": datetime.now().isoformat()}
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": description}}]
                    }
                }
            ]
        )

        page_url = new_page.get("url", "No URL")
        print(f"✅ Notion Page Created: {page_url}")
        return f"Notion page created: {page_url}"

    except Exception as e:
        return f"Error adding to Notion: {str(e)}"

# ─────────────────────────────────────────────
# Tool 3: Jira — Create Ticket
# ─────────────────────────────────────────────
@tool
def create_jira_ticket(summary: str, description: str, project_key: str = "KAOS") -> str:
    """
    Create a new Jira issue for a bug or task.
    Args:
        summary: Title of the issue.
        description: Detailed description of the bug.
        project_key: Jira Project Key (default: KAOS).
    """
    # Placeholder implementation
    print(f"TODO: Create Jira ticket: {summary}")
    return "JIRA-123"

# ─────────────────────────────────────────────
# Tool 4: Slack — Send Notification
# ─────────────────────────────────────────────
@tool
def send_slack_message(channel: str, text: str) -> str:
    """
    Send a notification to Slack.
    Args:
        channel: Channel ID or Name (e.g., #bugs, C1234567890, or U1234567890 for DM).
        text: Message content.
    """
    print(f"📨 Preparing Slack message for {channel}...")
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        
        target_id = channel
        
        # If it looks like a User ID (starts with U), try to open a DM
        if channel.startswith('U'):
            try:
                open_resp = client.conversations_open(users=channel)
                target_id = open_resp['channel']['id']
                print(f"📡 Opened DM channel: {target_id}")
            except SlackApiError as e:
                print(f"⚠️ Could not open DM with {channel}: {e.response['error']}")
        
        # NOTE: Slack SDK's chat_postMessage supports channel NAMES (e.g. #bugs) 
        # as well as IDs if the bot is a member.

        # Send message
        response = client.chat_postMessage(
            channel=target_id,
            text=text
        )
        
        print(f"✅ Slack message sent successfully to {target_id}!")
        return f"Message sent to {target_id}"
        
    except SlackApiError as e:
        error_msg = f"Slack API Error: {e.response['error']}"
        print(f"❌ {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error sending Slack message: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg

# ─────────────────────────────────────────────
# Export all tools for LangChain AgentExecutor
# ─────────────────────────────────────────────
tools = [find_service_owner, add_to_notion_dashboard, create_jira_ticket, send_slack_message]
