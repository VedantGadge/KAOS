from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient
from shared.logger import event_logger, logger
from shared.utils.retries import retry_with_backoff

@tool
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def find_service_owner(service_name: str) -> str:
    """
    Find the best ACTIVE person to handle a service issue.
    """
    logger.info(f"🔍 Finding best ACTIVE contact for {service_name}...")
    try:
        neo4j = Neo4jClient()
        normalized_name = service_name.replace("-", "").replace("_", "").lower()
        
        owner_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $normalized_name
          AND toLower(p.status) = 'active'
        RETURN p.name as name, p.status as status, p.slack_id as slack_id
        LIMIT 1
        """
        owner_res = neo4j.query(owner_query, {"normalized_name": normalized_name})
        
        if owner_res:
            owner = owner_res[0]
            neo4j.close()
            return f"Owner: {owner['name']} (Active) | Slack: {owner['slack_id']}"
            
        logger.warning(f"⚠️ No ACTIVE Owner found for {service_name}. Checking Team Members...")

        team_query = """
        MATCH (p:Person)-[:WORKED_ON]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $normalized_name
          AND toLower(p.status) = 'active'
        RETURN p.name as name, p.slack_id as slack_id
        LIMIT 1
        """
        team_res = neo4j.query(team_query, {"normalized_name": normalized_name})
        
        if team_res:
            member = team_res[0]
            neo4j.close()
            return f"Assigned to Contributor: {member['name']} (Active) | Slack: {member['slack_id']} | Reason: Owner unavailable, but {member['name']} worked on this service."

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
def find_reviewer(service_name: str, pr_author: str, pr_id: int) -> str:
    """
    Find an eligible reviewer for a PR.
    Looks for a Senior, Active engineer who owns the service but is NOT the PR author.
    """
    logger.info(f"🔍 Finding reviewer for {service_name} (excluding {pr_author}) for PR #{pr_id}...")
    try:
        neo4j = Neo4jClient()
        normalized_name = service_name.replace("-", "").replace("_", "").lower()

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

@tool
def get_user_slack_id(name: str) -> str:
    """
    Get the Slack ID for a given user name.
    """
    logger.info(f"🔍 Looking up Slack ID for '{name}'...")
    try:
        neo4j = Neo4jClient()
        query = "MATCH (p:Person) WHERE toLower(p.name) = toLower($name) RETURN p.slack_id as slack_id LIMIT 1"
        result = neo4j.query(query, {"name": name})
        neo4j.close()
        
        if result and result[0]['slack_id']:
            return result[0]['slack_id']
        elif name.lower() == "dev_user": 
             return "#dave"
        return ""
    except Exception as e:
        logger.warning(f"⚠️ Error looking up Slack ID: {e}")
        return ""

@tool
def find_team_info(service_name: str) -> str:
    """
    Find out who owns a service, who works on it, and who manages it.
    """
    logger.info(f"🤖 Looking up team info for {service_name}...")
    try:
        neo4j = Neo4jClient()
        normalized_name = service_name.replace("-", "").replace("_", "").lower()
        
        owner_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $name
        RETURN p.name as name, p.role as role, p.status as status, p.slack_id as slack_id
        """
        owners = neo4j.query(owner_query, {"name": normalized_name})
        
        contrib_query = """
        MATCH (p:Person)-[:WORKED_ON]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $name
        RETURN p.name as name
        """
        contributors = neo4j.query(contrib_query, {"name": normalized_name})
        
        neo4j.close()
        
        response = f"Team Info for {service_name}:\n\n"
        
        if owners:
            o = owners[0]
            role_text = f"({o['role']})" if o['role'] else ""
            response += f"👑 **Owner**\n• {o['name']} {role_text}\n• Status: {o['status']}\n• Contact: {o['slack_id'] if o['slack_id'] else 'N/A'}\n\n"
        else:
            response += "👑 **Owner**\n• Unknown\n\n"
            
        if contributors:
            names = ", ".join([c['name'] for c in contributors])
            response += f"🛠️ **Contributors**\n• {names}\n"
        else:
            response += "🛠️ **Contributors**\n• None found\n"
            
        return response

    except Exception as e:
        return f"Error querying Neo4j: {str(e)}"
