from langchain_core.tools import tool
from shared.logger import event_logger, logger
from shared.neo4j.client import Neo4jClient
from config.settings import settings
import json

# ─────────────────────────────────────────────
# Tool 1: Get Bug Timeline
# ─────────────────────────────────────────────
@tool
def get_bug_timeline(service_name: str) -> str:
    """
    Get the full lifecycle history of bugs and events for a specific service.
    Use this when the user asks "What happened with X?" or "Show me the history of X".
    Args:
        service_name: The name of the service or repository (e.g. "PaymentService").
    """
    logger.info(f"🤖 Chatbot: Fetching timeline for {service_name}...")
    try:
        timeline = event_logger.get_bug_timeline(service_name)
        if not timeline:
            return f"No events found for service '{service_name}'."
        
        # Format the timeline for the LLM to digest
        formatted = f"Timeline for {service_name}:\n"
        for event in timeline:
            timestamp = event['timestamp']
            event_type = event['event_type']
            actor = event['actor']
            details = event['details']
            
            # Create a summary sentence per event
            summary = f"- [{timestamp}] {event_type} by {actor}"
            if "title" in details:
                summary += f": {details['title']}"
            if "status" in details:
                summary += f" (Status: {details['status']})"
            if "decision" in details:
                summary += f" (Decision: {details['decision']})"
            
            formatted += summary + "\n"
            
        return formatted
    except Exception as e:
        return f"Error fetching timeline: {str(e)}"

# ─────────────────────────────────────────────
# Tool 2: Search Events (Keyword)
# ─────────────────────────────────────────────
@tool
def search_events(keyword: str) -> str:
    """
    Search for events containing a specific keyword or error message.
    Use this when the user asks general questions like "Have we seen any NPEs?" or "Search for 'timeout'".
    Args:
        keyword: The search term.
    """
    logger.info(f"🤖 Chatbot: Searching for '{keyword}'...")
    try:
        results = event_logger.search_events(keyword)
        if not results:
            return f"No events found matching '{keyword}'."
        
        formatted = f"Search results for '{keyword}':\n"
        for event in results:
            timestamp = event['timestamp']
            service = event['service']
            details = event['details']
            
            summary = f"- [{timestamp}] {service}: "
            if "title" in details:
                summary += details['title']
            elif "message" in details:
                summary += details['message']
            elif "comment" in details:
                summary += details['comment']
            else:
                summary += str(details)[:50]
            
            formatted += summary + "\n"
            
        return formatted
    except Exception as e:
        return f"Error searching events: {str(e)}"

# ─────────────────────────────────────────────
# Tool 3: Find Team Info (Neo4j)
# ─────────────────────────────────────────────
@tool
def find_team_info(service_name: str) -> str:
    """
    Find out who owns a service, who works on it, and who manages it.
    Use this for questions like "Who owns PaymentService?" or "Who can I talk to about X?".
    Args:
        service_name: The name of the service.
    """
    logger.info(f"🤖 Chatbot: Looking up team info for {service_name}...")
    try:
        neo4j = Neo4jClient()
        normalized_name = service_name.replace("-", "").replace("_", "").lower()
        
        # 1. Owner
        owner_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $name
        RETURN p.name as name, p.role as role, p.status as status, p.slack_id as slack_id
        """
        owners = neo4j.query(owner_query, {"name": normalized_name})
        
        # 2. Contributors
        contrib_query = """
        MATCH (p:Person)-[:WORKED_ON]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $name
        RETURN p.name as name
        """
        contributors = neo4j.query(contrib_query, {"name": normalized_name})
        
        neo4j.close()
        
        response = f"Team Info for {service_name}:\n"
        
        if owners:
            o = owners[0]
            response += f"👑 Owner: {o['name']} ({o['role']}) - Status: {o['status']} (Slack: {o['slack_id']})\n"
        else:
            response += "👑 Owner: Unknown\n"
            
        if contributors:
            names = ", ".join([c['name'] for c in contributors])
            response += f"🛠️ Contributors: {names}\n"
        else:
            response += "🛠️ Contributors: None found\n"
            
        return response

    except Exception as e:
        return f"Error querying Neo4j: {str(e)}"

# ─────────────────────────────────────────────
# Tool 4: Get Jira Status
# ─────────────────────────────────────────────
@tool
def get_jira_status(service_name: str) -> str:
    """
    Get the current active Jira ticket status for a service.
    Use this when asked "What is the status of the ticket for X?".
    Args:
        service_name: The name of the service.
    """
    logger.info(f"🤖 Chatbot: Checking Jira status for {service_name}...")
    try:
        # Use our existing logger to find the linked ticket
        issue_key = event_logger.get_active_jira_ticket(service=service_name)
        if not issue_key:
            return f"No active Jira ticket found for {service_name}."
            
        # Fetch real-time status from Jira
        from jira import JIRA
        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )
        issue = jira.issue(issue_key)
        
        return f"Jira Ticket {issue_key}:\n- Status: {issue.fields.status.name}\n- Summary: {issue.fields.summary}\n- Assignee: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}\n- Link: {settings.JIRA_URL}/browse/{issue_key}"

    except Exception as e:
        return f"Error checking Jira: {str(e)}"

tools = [get_bug_timeline, search_events, find_team_info, get_jira_status]
