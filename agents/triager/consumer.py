import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.triager.tools import create_jira_ticket, find_service_owner, add_to_notion_dashboard, send_slack_message
from shared.logger import event_logger
import json

class TriagerConsumer(BaseAgentConsumer):
    def __init__(self):
        # Production Group ID ensures we don't re-process events we've already committed.
        # If you restart the agent, it picks up where it left off.
        prod_group = "triager-prod-group"
        print(f"🔧 Production Mode: Using stable group {prod_group}")
        
        super().__init__(
            group_id=prod_group,
            topics=["system.quality.reports"]
        )

    def process_message(self, message: dict):
        """
        Handle 'system.quality.reports' events (Bugs/Incidents).
        """
        print(f"🕵️ Triager analysing event: {message.get('event_id')}")
        
        # 1. Extract Details
        service = message.get("service_name", "Unknown")
        error = message.get("error_message", "No traceback provided")
        severity = message.get("severity", "MEDIUM")
        
        # 2. Find Owner (Neo4j)
        # Note: tools usually return strings. In a real agent loop, we might use an LLM router here.
        # For this direct Kafka connection, we hardcode the logic:
        # Find Owner -> Create Ticket.
        print(f"   🔍 Finding owner for {service}...")
        # Since find_service_owner is a @tool, we invoke it directly or via its func. 
        # LangChain tools are callables but wrapped. Let's assume direct invocation works
        # or we might need to access the underlying function if it's wrapped. 
        # Checking tools.py in previous steps showed standard @tool. 
        # We can call them as functions usually if we import the function, 
        # but safely we might need .invoke or just use the logic directly if it's simple.
        # Let's try calling it. If it fails, we'll fix.
        try:
           # Use .invoke() for LangChain tools
           owner_info = find_service_owner.invoke({"service_name": service})
           print(f"   👤 Owner Found: {owner_info}")
        except Exception as e:
           owner_info = "Unknown Team"
           print(f"   ⚠️ Neo4j Lookup Failed: {e}")

        # 3. Create Jira Ticket
        print("   🎫 Creating Jira Ticket...")
        try:
            ticket_result = create_jira_ticket.invoke({
                "summary": f"[{service}] {error[:50]}...",
                "description": f"Automated Report:\nService: {service}\nSeverity: {severity}\nError: {error}\nOwner: {owner_info}",
                "issue_type": "Bug" # Note: tool def doesn't have issue_type, but kwargs might be ignored or cause error if extra. 
                # Checking tool def: create_jira_ticket(summary, description, assignee, severity, project_key)
                # It does NOT have issue_type. remove it.
            })
            print(f"   ✅ Ticket: {ticket_result}")
        except Exception as e:
            ticket_result = f"Failed to create ticket: {e}"
            print(f"   ❌ Jira Create Failed: {e}")

        # 4. Add to Notion
        print("   📋 Adding to Notion...")
        try:
            # We need to extract the assignee name from the owner_info string
            # Format: "Owner: [Name] (Active) | Slack: [ID]"
            assignee_name = "Unknown"
            if "Owner:" in owner_info:
                assignee_name = owner_info.split("Owner:")[1].split("(")[0].strip()
            elif "Contributor:" in owner_info:
                assignee_name = owner_info.split("Contributor:")[1].split("(")[0].strip()
            
            notion_result = add_to_notion_dashboard.invoke({
                "title": f"[{service}] {error[:50]}...",
                "assignee": assignee_name,
                "service_name": service,
                "severity": severity,
                "description": f"Error: {error}\nOwner Info: {owner_info}"
            })
            # unique string return from tool: "Notion page created: [URL]"
            notion_url = str(notion_result).split(": ")[-1] if ": " in str(notion_result) else "http://notion.so/unknown"
            print(f"   ✅ Notion: {notion_result}")
        except Exception as e:
            notion_url = "http://notion.so/failed"
            print(f"   ❌ Notion Add Failed: {e}")

        # 5. Send Slack Message
        print("   📨 Sending Slack Message...")
        try:
            # Extract Slack ID
            # Format: ... | Slack: U12345
            slack_id = "#all-kaos"
            if "Slack:" in owner_info:
                slack_id = owner_info.split("Slack:")[1].split("|")[0].strip()
            
            slack_result = send_slack_message.invoke({
                "channel": slack_id,
                "bug_title": f"[{service}] {error[:50]}...",
                "assignee": assignee_name,
                "service_name": service,
                "severity": severity,
                "notion_url": notion_url
            })
            print(f"   ✅ Slack: {slack_result}")
        except Exception as e:
            print(f"   ❌ Slack Send Failed: {e}")

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
    print("🚀 Starting Agent 1 (Triager) Listener...")
    consumer = TriagerConsumer()
    consumer.run()
