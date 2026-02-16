import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.triager.tools import create_jira_ticket, find_service_owner, add_to_notion_dashboard, send_slack_message
from agents.ops_manager.tools import update_jira_status, update_notion_status
from shared.logger import event_logger, logger
from config.settings import settings
import json

class TriagerConsumer(BaseAgentConsumer):
    def __init__(self):
        # Production Group ID ensures we don't re-process events we've already committed.
        # If you restart the agent, it picks up where it left off.
        prod_group = settings.GROUP_TRIAGER_PROD
        logger.info(f"🔧 Production Mode: Using stable group {prod_group}")
        
        super().__init__(
            group_id=prod_group,
            topics=[settings.TOPIC_QUALITY_REPORTS]
        )

    def process_message(self, message: dict):
        """
        Handle 'system.quality.reports' events (Bugs/Incidents).
        """
        logger.info(f"🕵️ Triager analysing event: {message.get('event_id')}")
        
        # 1. Extract Details
        service = message.get("service_name", "Unknown")
        error = message.get("error_message", "No traceback provided")
        severity = message.get("severity", "MEDIUM")
        
        # 2. Find Owner (Neo4j)
        suggested_assignee = message.get("suggested_assignee")
        if suggested_assignee:
            logger.info(f"🔄 Closed-Loop: Using suggested assignee: {suggested_assignee}")
            owner_info = f"Owner: {suggested_assignee} (Suggested) | Slack: @{suggested_assignee}"
        else:
            logger.info(f"   🔍 Finding owner for {service}...")
            try:
                # Use .invoke() for LangChain tools
                owner_info = find_service_owner.invoke({"service_name": service})
                logger.info(f"   👤 Owner Found: {owner_info}")
            except Exception as e:
                owner_info = "Unknown Team"
                logger.warning(f"   ⚠️ Neo4j Lookup Failed: {e}")

        # --- EXTRACT ASSIGNEE NAME ---
        assignee_name = "Unknown"
        try:
            if "Owner:" in owner_info:
                assignee_name = owner_info.split("Owner:")[1].split("(")[0].strip()
            elif "Contributor:" in owner_info:
                assignee_name = owner_info.split("Contributor:")[1].split("(")[0].strip()
            elif "Manager:" in owner_info:
                assignee_name = owner_info.split("Manager:")[1].split("(")[0].strip()
        except Exception as e:
            logger.warning(f"   ⚠️ Assignee Extraction Failed: {e}")
        
        logger.info(f"   🕵️ Extracted Assignee: '{assignee_name}' from '{owner_info}'")
        # -----------------------------

        # --- RECURRING ISSUE CHECK ---
        active_issue_key = event_logger.get_active_jira_ticket(service=service)
        if active_issue_key:
             logger.info(f"♻️  Recurring Issue: Found active ticket {active_issue_key}. Updating instead of creating new.")
             
             # Update Jira
             try:
                 update_res = update_jira_status.invoke({
                     "summary": service, 
                     "comment": f"⚠️ Recurring Incident/Deployment Failure: {error}", 
                     "status": "In Progress"
                 })
                 logger.info(f"   ✅ Updated Existing Jira: {update_res}")
             except Exception as e:
                 logger.error(f"   ❌ Failed to update Jira {active_issue_key}: {e}")
            
             # Update Notion
             try:
                 notion_res = update_notion_status.invoke({
                     "title": service,
                     "new_status": "Needs attention"
                 })
                 logger.info(f"   ✅ Updated Existing Notion: {notion_res}")
             except Exception as e:
                 logger.error(f"   ❌ Failed to update Notion: {e}")

             return # Skip creating new ticket
        # -----------------------------

        # 3. Create Jira Ticket
        logger.info("   🎫 Creating Jira Ticket...")
        try:
            ticket_result = create_jira_ticket.invoke({
                "summary": f"[{service}] {error[:50]}...",
                "description": f"Automated Report:\nService: {service}\nSeverity: {severity}\nError: {error}\nOwner: {owner_info}",
                "severity": severity,
                "service_name": service,
                "assignee": assignee_name
            })
            logger.info(f"   ✅ Ticket: {ticket_result}")
        except Exception as e:
            ticket_result = f"Failed to create ticket: {e}"
            logger.error(f"   ❌ Jira Create Failed: {e}")

        # 4. Add to Notion
        logger.info("   📋 Adding to Notion...")
        try:
            notion_result = add_to_notion_dashboard.invoke({
                "title": f"[{service}] {error[:50]}...",
                "assignee": assignee_name,
                "service_name": service,
                "severity": severity,
                "description": f"Error: {error}\nOwner Info: {owner_info}"
            })
            # unique string return from tool: "Notion page created: [URL]"
            notion_url = str(notion_result).split(": ")[-1] if ": " in str(notion_result) else "http://notion.so/unknown"
            logger.info(f"   ✅ Notion: {notion_result}")
        except Exception as e:
            notion_url = "http://notion.so/failed"
            logger.error(f"   ❌ Notion Add Failed: {e}")

        # 5. Send Slack Message
        logger.info("   📨 Sending Slack Message...")
        try:
            # Extract Slack ID
            # Format: ... | Slack: U12345
            slack_id = "#all-kaos"
            if owner_info and "Slack:" in owner_info:
                slack_id = owner_info.split("Slack:")[1].split("|")[0].strip()
            
            slack_result = send_slack_message.invoke({
                "channel": slack_id,
                "bug_title": f"[{service}] {error[:50]}...",
                "assignee": assignee_name,
                "service_name": service,
                "severity": severity,
                "notion_url": notion_url
            })
            logger.info(f"   ✅ Slack: {slack_result}")
        except Exception as e:
            logger.error(f"   ❌ Slack Send Failed: {e}")

        # 6. Log to EventLogger (with Embeddings!)
        event_logger.log_event(
            event_type="TICKET_CREATED",
            actor="Agent-Triager",
            repo=service, 
            details={
                "ticket": ticket_result,
                "notion_url": notion_url,
                "error": error,
                "owner": owner_info,
                "severity": severity
            }
        )

if __name__ == "__main__":
    logger.info("🚀 Starting Agent 1 (Triager) Listener...")
    consumer = TriagerConsumer()
    consumer.run()
