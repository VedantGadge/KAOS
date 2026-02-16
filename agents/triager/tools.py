from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient
from notion_client import Client as NotionClient
from config.settings import settings
from datetime import datetime
from shared.logger import event_logger, logger
from shared.utils.retries import retry_with_backoff
import httpx

# ─────────────────────────────────────────────
# Tool 1: Neo4j — Find Active Service Owner
# ─────────────────────────────────────────────
@tool
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def find_service_owner(service_name: str) -> str:
    """
    Find the best ACTIVE person to handle a service issue.
    Priority:
    1. Direct Owner (if Active)
    2. Any Team Member who WORKED_ON this service (if Active)
    3. Manager (Escalation)
    """
    logger.info(f"🔍 Finding best ACTIVE contact for {service_name}...")
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
            logger.warning(f"⚠️ Owner {owner['name']} is {owner['status']}. Checking Team Members...")

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
@retry_with_backoff(retries=3, backoff_in_seconds=2)
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
    logger.info(f"📋 Adding to Notion Dashboard: {title} -> Assigned to {assignee}")
    try:
        notion = NotionClient(auth=settings.NOTION_API_KEY)
        database_id = settings.NOTION_DATABASE_ID

        # --- DEDUPLICATION CHECK ---
        # 1. Standardize Database ID (ensure hyphens, strip whitespace)
        db_id = database_id.strip()
        if len(db_id) == 32 and "-" not in db_id:
            db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"

        # 2. Check if an "Open" bug with the same title already exists
        # Note: notion.databases.query() is missing/broken in this client version, using httpx directly.
        query_filter = {
            "and": [
                {
                    "property": "Tasks",
                    "title": {
                        "equals": title
                    }
                },
                {
                    "property": "Status",
                    "status": {
                        "equals": "Open"
                    }
                }
            ]
        }
        
        try:
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            headers = {
                "Authorization": f"Bearer {settings.NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            with httpx.Client() as client:
                resp = client.post(url, headers=headers, json={"filter": query_filter})
                resp.raise_for_status()
                response = resp.json()

            search_results = response.get("results", [])
            
            if search_results:
                page_url = search_results[0].get("url")
                logger.info(f"⏭️  Duplicate found in Notion. Skipping creation. URL: {page_url}")
                return f"Duplicate bug already exists in Notion: {page_url}"
                
        except Exception as e:
            logger.warning(f"⚠️ Deduplication check failed: {e}. Proceeding with creation.")
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
                    "date": {"start": datetime.utcnow().isoformat() + "Z"}
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
        logger.info(f"✅ Notion Page Created: {page_url}")
        event_logger.log_event(
            event_type="NOTION_TICKET_CREATED",
            actor="Agent",
            repo=service_name,
            details={
                "title": title, 
                "description": description, 
                "service": service_name, 
                "url": page_url, 
                "severity": severity
            }
        )
        
        # Persist to local DB for tracking
        page_id = new_page.get("id")
        event_logger.log_notion_ticket(service=service_name, page_id=page_id, title=title, status="Open")
        
        return f"Notion page created: {page_url}"

    except Exception as e:
        return f"Error adding to Notion: {str(e)}"

# ─────────────────────────────────────────────
# Tool 3: Jira — Create Ticket
# ─────────────────────────────────────────────
@tool
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def create_jira_ticket(summary: str, description: str, service_name: str, assignee: str = "", severity: str = "MEDIUM", project_key: str = "KAN") -> str:
    """
    Create a new Jira Bug issue.
    Args:
        summary: Title of the issue (e.g., "NullPointerException in PaymentService").
        description: Detailed description of the bug.
        service_name: The affected service (e.g., "PaymentService"). 
        assignee: Name of the person to assign this ticket to.
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW) — mapped to Jira priority.
        project_key: Jira Project Key (default: KAN).
    """
    logger.info(f"🎫 Creating Jira ticket: {summary} (assignee: {assignee})")
    try:
        from jira import JIRA

        # Map severity to Jira priority names
        priority_map = {
            "CRITICAL": "Highest",
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
        }
        priority_name = priority_map.get(severity.upper(), "Medium")

        # Include assignee in description as fallback
        full_description = description
        if assignee:
            full_description = f"Assigned To: {assignee}\n\n{description}"

        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )

        issue = jira.create_issue(
            project=project_key,
            summary=summary,
            description=full_description,
            issuetype={"name": "Task"},
            priority={"name": priority_name}
        )

        # Try to assign the ticket to the user by searching Jira users
        if assignee:
            try:
                users = jira.search_users(query=assignee)
                if users:
                    jira.assign_issue(issue, users[0].accountId)
                    logger.info(f"👤 Assigned to Jira user: {users[0].displayName}")
                else:
                    logger.warning(f"⚠️ No Jira user found for '{assignee}' — mentioned in description instead.")
            except Exception as assign_err:
                logger.warning(f"⚠️ Could not assign: {assign_err}")

        # --- FIX: Ensure status is 'To Do' (not Done) ---
        try:
            current_status = issue.fields.status.name
            logger.info(f"ℹ️ Current Jira Status: {current_status}")
            
            # Simple logic: Attempt to transition to 'To Do' if not already there
            if current_status not in ["To Do", "Open"]:
                transitions = jira.transitions(issue)
                # Find a transition that leads to 'To Do' or 'Open'
                target_transition = next((t for t in transitions if t['name'].lower() in ['to do', 'open', 'backlog']), None)
                
                if target_transition:
                    jira.transition_issue(issue, target_transition['id'])
                    logger.info(f"✅ Forced transition to '{target_transition['name']}'")
                else:
                    logger.warning(f"⚠️ Could not find transition to 'To Do'. Available: {[t['name'] for t in transitions]}")
        except Exception as status_err:
            logger.warning(f"⚠️ Status check/transition failed: {status_err}")
        # ------------------------------------------------

        issue_url = f"{settings.JIRA_URL}/browse/{issue.key}"
        logger.info(f"✅ Jira ticket created: {issue.key} — {issue_url}")
        
        event_logger.log_event(
            event_type="JIRA_TICKET_CREATED",
            actor="Agent",
            repo="KAOS", 
            details={
                "key": issue.key, 
                "summary": summary, 
                "description": description, 
                "url": issue_url
            }
        )
        
        # Persist to local DB for tracking
        event_logger.log_jira_ticket(service=service_name, issue_key=issue.key, summary=summary, status="To Do")
        
        return f"Jira ticket created: {issue.key} | URL: {issue_url}"

    except Exception as e:
        error_msg = f"Error creating Jira ticket: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

# ─────────────────────────────────────────────
# Tool 4: Slack — Send Notification
# ─────────────────────────────────────────────
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
    Args:
        channel: Channel ID or Name (e.g., #bugs, C1234567890, or U1234567890 for DM).
        bug_title: Title of the bug being reported.
        assignee: Name of the person the bug is assigned to.
        service_name: The affected service name.
        severity: Severity level of the bug (CRITICAL, HIGH, MEDIUM, LOW).
        notion_url: The Notion page URL for this bug.
        custom_message: Optional custom message to send as the DM body.
    """
    logger.info(f"📨 Preparing Slack message for {channel}...")
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
                logger.info(f"📡 Opened DM channel: {target_id}")
            except SlackApiError as e:
                logger.warning(f"⚠️ Could not open DM with {channel}: {e.response['error']}")
        
        # ── Build the DM message ──
        if custom_message:
            dm_text = custom_message
        else:
            dm_text = (
                f"You have been assigned a {severity} bug in {service_name}. "
                f"The bug has already been logged in Notion. "
                f"Here is the link: {notion_url}"
            )
        
        # Send the DM to the assignee
        response = client.chat_postMessage(
            channel=target_id,
            text=dm_text
        )
        logger.info(f"✅ Slack message sent successfully to {target_id}!")
        
        # ── Announce in #all-kaos ──
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
            client.chat_postMessage(
                channel="#all-kaos",
                text=announcement
            )
            logger.info(f"📢 Announcement posted in #all-kaos")
        except SlackApiError as e:
            logger.warning(f"⚠️ Could not post to #all-kaos: {e.response['error']}")
        
        return f"Message sent to {target_id}"
        
    except SlackApiError as e:
        error_msg = f"Slack API Error: {e.response['error']}"
        logger.error(f"❌ {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error sending Slack message: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

# ─────────────────────────────────────────────
# Export all tools for LangChain AgentExecutor
# ─────────────────────────────────────────────
tools = [find_service_owner, add_to_notion_dashboard, create_jira_ticket, send_slack_message]
