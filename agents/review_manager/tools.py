from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient
from notion_client import Client as NotionClient
from config.settings import settings
from shared.logger import event_logger


# ─────────────────────────────────────────────
# Tool 1: Check PR Status (Simulated GitHub API)
# ─────────────────────────────────────────────
@tool
def check_pr_status(repo: str, pr_id: int) -> str:
    """
    Check the status of a Pull Request (simulated).
    In production, this would call the GitHub API.
    Args:
        repo: Repository name (e.g., "PaymentService").
        pr_id: Pull Request number.
    """
    print(f"🔍 Checking PR #{pr_id} status in {repo}...")
    # In simulation, we return CLEAN by default.
    # The actual status is driven by the Kafka event type:
    #   - PR_SYNCHRONIZE -> check for conflicts (simulated as CLEAN here)
    #   - MERGE_CONFLICT -> explicit conflict event
    # The agent's system prompt will handle routing based on the event.
    status = "CLEAN"
    event_logger.log_event(
        event_type="PR_STATUS_CHECK",
        actor="Agent",
        repo=repo,
        pr_id=str(pr_id),
        details={"status": status}
    )
    return f"PR #{pr_id} in {repo}: Status is {status}. No merge conflicts detected."


# ─────────────────────────────────────────────
# Tool 2: Find Reviewer via Neo4j
# ─────────────────────────────────────────────
@tool
def find_reviewer(service_name: str, pr_author: str, pr_id: int) -> str:
    """
    Find an eligible reviewer for a PR.
    Looks for a Senior, Active engineer who owns the service but is NOT the PR author.
    Args:
        service_name: The service/repo name (e.g., "PaymentService").
        pr_author: The name of the PR author (to exclude from reviewers).
        pr_id: The Pull Request number.
    """
    print(f"🔍 Finding reviewer for {service_name} (excluding {pr_author}) for PR #{pr_id}...")
    try:
        neo4j = Neo4jClient()

        # Normalize service name: 'payment-service' -> 'paymentservice' for matching
        normalized_name = service_name.replace("-", "").replace("_", "").lower()
        print(f"🔍 Normalized service name: '{service_name}' -> '{normalized_name}'")

        # Query: Find a Senior engineer who owns this service (case-insensitive name match)
        # CASE-INSENSITIVE EXCLUSION of pr_author
        reviewer_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $normalized_name
          AND p.role = 'Senior' AND toLower(p.status) = 'active'
          AND toLower(p.name) <> toLower($pr_author)
        RETURN p.name as name, p.slack_id as slack_id, p.role as role
        LIMIT 1
        """
        result = neo4j.query(reviewer_query, {
            "normalized_name": normalized_name,
            "pr_author": pr_author
        })

        if result:
            reviewer = result[0]
            neo4j.close()
            event_logger.log_event(
                event_type="REVIEW_ASSIGNED",
                actor="Agent",
                repo=service_name,
                pr_id=str(pr_id),
                details={"reviewer": reviewer['name'], "role": reviewer['role'], "reason": "Senior Owner", "pr_author": pr_author}
            )
            return f"Reviewer: {reviewer['name']} ({reviewer['role']}, Active) | Slack: {reviewer['slack_id']}"

        # Fallback: Any active person who worked on the service
        fallback_query = """
        MATCH (p:Person)-[:WORKED_ON|OWNS]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $normalized_name
          AND toLower(p.status) = 'active'
          AND toLower(p.name) <> toLower($pr_author)
        RETURN p.name as name, p.slack_id as slack_id, p.role as role
        LIMIT 1
        """
        fallback = neo4j.query(fallback_query, {
            "normalized_name": normalized_name,
            "pr_author": pr_author
        })

        if fallback:
            reviewer = fallback[0]
            neo4j.close()
            event_logger.log_event(
                event_type="REVIEW_ASSIGNED",
                actor="Agent",
                repo=service_name,
                pr_id=str(pr_id),
                details={"reviewer": reviewer['name'], "role": reviewer['role'], "reason": "Fallback Contributor", "pr_author": pr_author}
            )
            return f"Reviewer: {reviewer['name']} ({reviewer['role']}, Active) | Slack: {reviewer['slack_id']} | (Contributor)"

        neo4j.close()
        return f"No eligible reviewer found for {service_name} (excluding {pr_author}) for PR #{pr_id}."

    except Exception as e:
        return f"Error finding reviewer: {str(e)}"


# ─────────────────────────────────────────────
# Tool 3: Send Slack DM
# ─────────────────────────────────────────────
@tool
def send_slack_dm(channel: str, text: str) -> str:
    """
    Send a direct message to a user on Slack.
    Args:
        channel: Slack channel name or User ID (e.g., #charlie, U12345).
        text: Message content to send.
    """
    print(f"📨 Sending Slack DM to {channel}...")
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        target_id = channel

        # If it looks like a User ID (starts with U), open a DM
        if channel.startswith('U'):
            try:
                open_resp = client.conversations_open(users=channel)
                target_id = open_resp['channel']['id']
                print(f"📡 Opened DM channel: {target_id}")
            except SlackApiError as e:
                print(f"⚠️ Could not open DM with {channel}: {e.response['error']}")

        response = client.chat_postMessage(
            channel=target_id,
            text=text
        )

        print(f"✅ Slack DM sent to {target_id}!")
        return f"Message sent to {target_id}"

    except SlackApiError as e:
        error_msg = f"Slack API Error: {e.response['error']}"
        print(f"❌ {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Error sending Slack DM: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg


# ─────────────────────────────────────────────
# Tool 4: Update Notion Status
# ─────────────────────────────────────────────
@tool
def update_notion_status(title: str, new_status: str) -> str:
    """
    Update the status of an existing bug entry in Notion.
    Args:
        title: Title of the bug to find (e.g., "NullPointerException in PaymentService").
        new_status: New status to set. Options: "Open", "Needs attention", "In progress", "To be reviwed", "Resolved".
    """
    print(f"📋 Updating Notion status for '{title}' -> {new_status}")
    try:
        notion = NotionClient(auth=settings.NOTION_API_KEY)
        database_id = settings.NOTION_DATABASE_ID

        # 1. Try Persistent DB Lookup
        page_id = event_logger.get_active_notion_ticket(service=title)
        if page_id:
            print(f"💾 Found persisted Notion Page ID: {page_id}")
            try:
                notion.pages.update(
                    page_id=page_id,
                    properties={"Status": {"status": {"name": new_status}}}
                )
                event_logger.update_notion_ticket_status(page_id, new_status)
                return f"Notion status updated to '{new_status}' (via ID: {page_id})."
            except Exception as e:
                print(f"⚠️ Failed to update via ID {page_id}: {e}. Falling back to search.")

        # 2. Fallback: Search for the page by title
        print(f"🔍 Falling back to search for '{title}'...")
        search_results = notion.search(
            query=title,
            filter={"value": "page", "property": "object"}
        ).get("results", [])

        for page in search_results:
            if page.get("parent", {}).get("database_id", "").replace("-", "") == database_id.replace("-", ""):
                page_id = page["id"]
                # Update the status
                notion.pages.update(
                    page_id=page_id,
                    properties={"Status": {"status": {"name": new_status}}}
                )
                
                # We found it via search, let's persist it for next time!
                # But wait, we need 'service' name. 'title' acts as service name here.
                # event_logger.log_notion_ticket(service=title, page_id=page_id, title=title, status=new_status)
                
                page_url = page.get("url", "")
                print(f"✅ Notion status updated to '{new_status}': {page_url}")
                return f"Notion status updated to '{new_status}': {page_url}"

        print(f"⚠️ No matching Notion page found for '{title}'")
        return f"No matching Notion page found for '{title}'"

    except Exception as e:
        return f"Error updating Notion: {str(e)}"


# ─────────────────────────────────────────────
# Tool 5: Update Jira Ticket Status
# ─────────────────────────────────────────────
@tool
def update_jira_status(summary: str, comment: str, status: str = "", service_name: str = "") -> str:
    """
    Update a Jira ticket by adding a comment and optionally transitioning its status.
    Searches for the ticket by summary.
    Args:
        summary: Title/summary of the Jira ticket to find (e.g., "NullPointerException in PaymentService").
        comment: Comment to add to the ticket (e.g., "Merge conflict detected. Developer notified.").
        status: Optional new status to transition to (e.g., "In Progress", "Done"). Leave empty to skip transition.
        service_name: Optional service/repo name to help lookup the ticket (e.g., "PaymentService").
    """
    print(f"🎫 Updating Jira ticket: {summary}")
    try:
        from jira import JIRA

        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )

        issue = None

        # 1. Try Persistent DB Lookup (Prioritize service_name if provided)
        issue_key = None
        if service_name:
            issue_key = event_logger.get_active_jira_ticket(service=service_name)
        
        if not issue_key:
             # Try using summary as service name (fallback)
             issue_key = event_logger.get_active_jira_ticket(service=summary)

        if issue_key:
            try:
                issue = jira.issue(issue_key)
                print(f"💾 Found persisted Jira Issue: {issue.key}")
            except Exception as e:
                print(f"⚠️ Failed to load persisted issue {issue_key}: {e}. Falling back to search.")

        # 2. Fallback to Search
        if not issue:
            # Clean up summary for search (remove prefixes like "Fix:")
            clean_summary = summary.replace("Fix:", "").replace("Feat:", "").strip()
            # If the summary is very short, it might be risky, but let's try searching
            print(f"🔍 Falling back to search for '{clean_summary}'...")
            jql = f'summary ~ "{clean_summary}" ORDER BY created DESC'
            issues = jira.search_issues(jql, maxResults=1)
            if issues:
                issue = issues[0]

        if not issue:
            print(f"⚠️ No Jira ticket found matching: {summary}")
            return f"No Jira ticket found matching: {summary}"
        
        # Add comment
        jira.add_comment(issue, comment)
        print(f"💬 Comment added to {issue.key}")

        # Try to transition status if provided
        if status:
            current_status = issue.fields.status.name
            if current_status.lower() == status.lower():
                 print(f"✅ Jira {issue.key} is already '{current_status}'. Skipping transition.")
            else:
                try:
                    transitions = jira.transitions(issue)
                    for t in transitions:
                        if t['name'].lower() == status.lower():
                            jira.transition_issue(issue, t['id'])
                            print(f"✅ Jira {issue.key} transitioned to '{status}'")
                            
                            # Update local DB if we have it
                            if issue_key and issue_key == issue.key:
                                event_logger.update_jira_ticket_status(issue.key, status)
                            break
                    else:
                        print(f"⚠️ Transition '{status}' not found. Current: '{current_status}'. Available: {[t['name'] for t in transitions]}")
                except Exception as te:
                    print(f"⚠️ Could not transition: {te}")

        issue_url = f"{settings.JIRA_URL}/browse/{issue.key}"
        return f"Jira ticket {issue.key} updated with comment. URL: {issue_url}"

    except Exception as e:
        error_msg = f"Error updating Jira ticket: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg


# ─────────────────────────────────────────────
# Tool 6: Get User Slack ID
# ─────────────────────────────────────────────
@tool
def get_user_slack_id(name: str) -> str:
    """
    Get the Slack ID for a given user name.
    Useful for mentioning users in public channels.
    Args:
        name: Name of the person (e.g., "Dave", "dev_user").
    """
    print(f"🔍 Looking up Slack ID for '{name}'...")
    try:
        neo4j = Neo4jClient()
        query = "MATCH (p:Person) WHERE toLower(p.name) = toLower($name) RETURN p.slack_id as slack_id LIMIT 1"
        result = neo4j.query(query, {"name": name})
        neo4j.close()
        
        if result and result[0]['slack_id']:
            return result[0]['slack_id']
        elif name.lower() == "dev_user": 
             # Fallback for dev_user if not found (though seed should add it)
             return "#dave"
        return ""
    except Exception as e:
        print(f"⚠️ Error looking up Slack ID: {e}")
        return ""

# ─────────────────────────────────────────────
# Export all tools for LangChain AgentExecutor
# ─────────────────────────────────────────────
tools = [check_pr_status, find_reviewer, send_slack_dm, update_notion_status, update_jira_status, get_user_slack_id]
