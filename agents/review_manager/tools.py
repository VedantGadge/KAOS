from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient
from notion_client import Client as NotionClient
from config.settings import settings


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
    return f"PR #{pr_id} in {repo}: Status is CLEAN. No merge conflicts detected."


# ─────────────────────────────────────────────
# Tool 2: Find Reviewer via Neo4j
# ─────────────────────────────────────────────
@tool
def find_reviewer(service_name: str, pr_author: str) -> str:
    """
    Find an eligible reviewer for a PR.
    Looks for a Senior, Active engineer who owns the service but is NOT the PR author.
    Args:
        service_name: The service/repo name (e.g., "PaymentService").
        pr_author: The name of the PR author (to exclude from reviewers).
    """
    print(f"🔍 Finding reviewer for {service_name} (excluding {pr_author})...")
    try:
        neo4j = Neo4jClient()

        # Query from SCHEMA.md: Find a Senior engineer who owns this service
        reviewer_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service {name: $service_name})
        WHERE p.role = 'Senior' AND p.status = 'Active' AND p.name <> $pr_author
        RETURN p.name as name, p.slack_id as slack_id, p.role as role
        LIMIT 1
        """
        result = neo4j.query(reviewer_query, {
            "service_name": service_name,
            "pr_author": pr_author
        })

        if result:
            reviewer = result[0]
            neo4j.close()
            return f"Reviewer: {reviewer['name']} ({reviewer['role']}, Active) | Slack: {reviewer['slack_id']}"

        # Fallback: Any active person who worked on the service
        fallback_query = """
        MATCH (p:Person)-[:WORKED_ON|OWNS]->(s:Service {name: $service_name})
        WHERE p.status = 'Active' AND p.name <> $pr_author
        RETURN p.name as name, p.slack_id as slack_id, p.role as role
        LIMIT 1
        """
        fallback = neo4j.query(fallback_query, {
            "service_name": service_name,
            "pr_author": pr_author
        })

        if fallback:
            reviewer = fallback[0]
            neo4j.close()
            return f"Reviewer (fallback): {reviewer['name']} ({reviewer['role']}, Active) | Slack: {reviewer['slack_id']}"

        neo4j.close()
        return f"No eligible reviewer found for {service_name} (excluding {pr_author})."

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

        # Search for the page by title
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
                    properties={
                        "Status": {
                            "status": {"name": new_status}
                        }
                    }
                )
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
def update_jira_status(summary: str, comment: str, status: str = "") -> str:
    """
    Update a Jira ticket by adding a comment and optionally transitioning its status.
    Searches for the ticket by summary.
    Args:
        summary: Title/summary of the Jira ticket to find (e.g., "NullPointerException in PaymentService").
        comment: Comment to add to the ticket (e.g., "Merge conflict detected. Developer notified.").
        status: Optional new status to transition to (e.g., "In Progress", "Done"). Leave empty to skip transition.
    """
    print(f"🎫 Updating Jira ticket: {summary}")
    try:
        from jira import JIRA

        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )

        # Search for the ticket by summary
        jql = f'summary ~ "{summary}" ORDER BY created DESC'
        issues = jira.search_issues(jql, maxResults=1)

        if not issues:
            print(f"⚠️ No Jira ticket found matching: {summary}")
            return f"No Jira ticket found matching: {summary}"

        issue = issues[0]
        
        # Add comment
        jira.add_comment(issue, comment)
        print(f"💬 Comment added to {issue.key}")

        # Try to transition status if provided
        if status:
            try:
                transitions = jira.transitions(issue)
                for t in transitions:
                    if t['name'].lower() == status.lower():
                        jira.transition_issue(issue, t['id'])
                        print(f"✅ Jira {issue.key} transitioned to '{status}'")
                        break
                else:
                    print(f"⚠️ Transition '{status}' not found. Available: {[t['name'] for t in transitions]}")
            except Exception as te:
                print(f"⚠️ Could not transition: {te}")

        issue_url = f"{settings.JIRA_URL}/browse/{issue.key}"
        return f"Jira ticket {issue.key} updated with comment. URL: {issue_url}"

    except Exception as e:
        error_msg = f"Error updating Jira ticket: {str(e)}"
        print(f"❌ {error_msg}")
        return error_msg


# ─────────────────────────────────────────────
# Export all tools for LangChain AgentExecutor
# ─────────────────────────────────────────────
tools = [check_pr_status, find_reviewer, send_slack_dm, update_notion_status, update_jira_status]
