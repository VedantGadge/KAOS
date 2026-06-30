from langchain_core.tools import tool
from config.settings import settings
from shared.logger import event_logger, logger
from shared.utils.retries import retry_with_backoff

@tool
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def create_jira_ticket(summary: str, description: str, service_name: str, assignee: str = "", severity: str = "MEDIUM", project_key: str = "KAN") -> str:
    """
    Create a new Jira Bug issue.
    Args:
        summary: Title of the issue.
        description: Detailed description of the bug.
        service_name: The affected service. 
        assignee: Name of the person to assign this ticket to.
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW).
        project_key: Jira Project Key (default: KAN).
    """
    logger.info(f"🎫 Creating Jira ticket: {summary} (assignee: {assignee})")
    try:
        from jira import JIRA

        priority_map = {
            "CRITICAL": "Highest",
            "HIGH": "High",
            "MEDIUM": "Medium",
            "LOW": "Low",
        }
        priority_name = priority_map.get(severity.upper(), "Medium")

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
            issuetype={"name": "Bug"},
            priority={"name": priority_name}
        )

        if assignee:
            try:
                users = jira.search_users(query=assignee)
                if users:
                    jira.assign_issue(issue, users[0].accountId)
                    logger.info(f"👤 Assigned to Jira user: {users[0].displayName}")
                else:
                    logger.warning(f"⚠️ No Jira user found for '{assignee}'")
            except Exception as assign_err:
                logger.warning(f"⚠️ Could not assign: {assign_err}")

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
        
        event_logger.log_jira_ticket(service=service_name, issue_key=issue.key, summary=summary, status="To Do")
        
        return f"Jira ticket created: {issue.key} | URL: {issue_url}"

    except Exception as e:
        error_msg = f"Error creating Jira ticket: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

@tool
def update_jira_status(summary: str, comment: str, status: str = "", service_name: str = "") -> str:
    """
    Update a Jira ticket by adding a comment and optionally transitioning its status.
    Searches for the ticket by summary.
    """
    logger.info(f"🎫 Updating Jira ticket: {summary}")
    try:
        from jira import JIRA

        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )

        issue = None

        issue_key = None
        if service_name:
            issue_key = event_logger.get_active_jira_ticket(service=service_name)
        
        if not issue_key:
             issue_key = event_logger.get_active_jira_ticket(service=summary)

        if issue_key:
            try:
                issue = jira.issue(issue_key)
                logger.info(f"💾 Found persisted Jira Issue: {issue.key}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load persisted issue {issue_key}: {e}. Falling back to search.")

        if not issue:
            clean_summary = summary.replace("Fix:", "").replace("Feat:", "").strip()
            logger.info(f"🔍 Falling back to search for '{clean_summary}'...")
            jql = f'summary ~ "{clean_summary}" ORDER BY created DESC'
            issues = jira.search_issues(jql, maxResults=1)
            if issues:
                issue = issues[0]

        if not issue:
            logger.warning(f"⚠️ No Jira ticket found matching: {summary}")
            return f"No Jira ticket found matching: {summary}"
        
        jira.add_comment(issue, comment)
        logger.info(f"💬 Comment added to {issue.key}")

        if status:
            current_status = issue.fields.status.name
            if current_status.lower() == status.lower():
                 logger.info(f"✅ Jira {issue.key} is already '{current_status}'. Skipping transition.")
            else:
                try:
                    transitions = jira.transitions(issue)
                    target = next((t for t in transitions if t['name'].lower() == status.lower()), None)
                    if not target:
                        target = next((t for t in transitions if status.lower() in t['name'].lower()), None)
                    if not target and status.lower() in ["done", "resolved", "closed", "complete"]:
                         completion_keywords = ["done", "resolve", "close", "complete", "finish"]
                         target = next((t for t in transitions if any(k in t['name'].lower() for k in completion_keywords)), None)

                    if target:
                        jira.transition_issue(issue, target['id'])
                        logger.info(f"✅ Jira {issue.key} transitioned to '{status}'")
                        if issue_key and issue_key == issue.key:
                            event_logger.update_jira_ticket_status(issue.key, status)
                    else:
                        logger.warning(f"⚠️ Transition '{status}' not found. Current: '{current_status}'. Available: {[t['name'] for t in transitions]}")
                except Exception as te:
                    logger.warning(f"⚠️ Could not transition: {te}")

        issue_url = f"{settings.JIRA_URL}/browse/{issue.key}"
        return f"Jira ticket {issue.key} updated with comment. URL: {issue_url}"

    except Exception as e:
        error_msg = f"Error updating Jira ticket: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

@tool
def get_jira_status(service_name: str) -> str:
    """
    Get the current active Jira ticket status for a service.
    """
    logger.info(f"🤖 Checking Jira status for {service_name}...")
    try:
        issue_key = event_logger.get_active_jira_ticket(service=service_name)
        if not issue_key:
            return f"No active Jira ticket found for {service_name}."
            
        from jira import JIRA
        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )
        issue = jira.issue(issue_key)
        
        return f"Jira Ticket {issue_key}:\n- Status: {issue.fields.status.name}\n- Summary: {issue.fields.summary}\n- Assignee: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}\n- Link: {settings.JIRA_URL}/browse/{issue_key}"

    except Exception as e:
        return f"Error checking Jira: {str(e)}"
