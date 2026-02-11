from shared.kafka.client import KafkaClient
from shared.neo4j.client import Neo4jClient
from shared.models.events import ReportEvent
import json
import time

TOPIC_NAME = "system.quality.reports"
GROUP_ID = "agent-1-triager-group"

from agents.base import BaseAgent
from agents.triager.tools import tools as triager_tools
import json

# Define the System Prompt
SYSTEM_PROMPT = """
You are the Triager Agent (Agent 1).
Your goal is to analyze incoming bug reports and route them correctly.

IMPORTANT RULES:
- Call each tool EXACTLY ONCE per bug report. Do NOT call the same tool more than once.
- Once a tool returns a result, move on to the next step. Do NOT re-call it.
- If `add_to_notion_dashboard` returns "Duplicate bug already exists", STOP immediately. Do NOT call `create_jira_ticket` or `send_slack_message`. Just respond with a summary saying the bug is already tracked.

Steps:
1. Analyze the error message and stack trace.
2. Call `find_service_owner` ONCE to find the active owner (it handles escalation automatically).
3. Call `add_to_notion_dashboard` ONCE to log it in the Notion Dashboard with the assignee, service, and severity.
   - If the result says "Duplicate bug already exists", STOP here and respond with a summary.
4. Call `create_jira_ticket` ONCE to create a Jira ticket.
5. Call `send_slack_message` ONCE to notify the assignee. Pass `channel`, `bug_title`, `assignee`, `service_name`, `severity`, and the `notion_url` (from the Notion tool result). The tool will automatically generate the DM text and post an announcement in #all-kaos. Do NOT send a separate message to #all-kaos yourself.

After completing all steps, respond with a brief summary. Do NOT repeat any tool calls.
"""


from agents.triager.tools import tools as triager_tools

def process_message(msg_value):
    """
    Process the incoming message using the BaseAgent (LangChain).
    """
    try:
        # Validate against Pydantic model
        event_data = json.loads(msg_value)
        event = ReportEvent(**event_data)
        print(f"✅ [Agent 1] Received Report: {event.error_message} | Service: {event.service_name}")
        
        # Instantiate Agent (LangChain)
        agent = BaseAgent(
            name="Triager",
            tools=triager_tools,
            instructions=SYSTEM_PROMPT
        )
        
        # Run Agent
        task = f"""
        New Bug Report Received:
        Event ID: {event.event_id}
        Service: {event.service_name}
        Severity: {event.severity}
        Error: {event.error_message}
        Trace: {event.stack_trace}
        
        Please handle this.
        """
        
        agent.run(task)
        
    except Exception as e:
        print(f"❌ [Agent 1] Failed to process message: {e}")

def main():
    print("Agent 1: Triager Starting...")
    print(f"🔌 Connecting to Kafka Topic: {TOPIC_NAME}...")
    
    kafka = KafkaClient()
    consumer = kafka.create_consumer(group_id=GROUP_ID)
    consumer.subscribe([TOPIC_NAME])

    print("🎧 Listening for bugs...")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            process_message(msg.value().decode('utf-8'))
            
    except KeyboardInterrupt:
        print("🛑 Agent 1 stopping...")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
