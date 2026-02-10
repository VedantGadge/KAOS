from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient

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
        # (Assuming (:Person)-[:WORKED_ON]->(:Service))
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

        # 3. Escalate to Manager (of the Owner)
        # We need the owner's name/ID to find their manager. 
        # If no owner exists, we might need a fallback, but let's assume we have an owner record even if inactive.
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

@tool
def send_slack_message(channel: str, text: str) -> str:
    """
    Send a notification to Slack.
    Args:
        channel: Channel ID or Name (e.g., #bugs).
        text: Message content.
    """
    # Placeholder implementation
    print(f"TODO: Send Slack message to {channel}: {text}")
    return "Sent"

# Export tools list for LangChain
tools = [find_service_owner, create_jira_ticket, send_slack_message]
