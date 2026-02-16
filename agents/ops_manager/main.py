import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.client import KafkaClient
from shared.models.events import OpsStatusEvent
from agents.base import BaseAgent
from agents.ops_manager.tools import tools as ops_tools
import json

# Kafka Topics
OPS_TOPIC = "ops.deploy.status"
GROUP_ID = "agent-3-ops-manager-group"

# System Prompt
SYSTEM_PROMPT = """
You are the Ops Manager Agent (Agent 3).
Your goal is to manage the post-deployment phase of the KAOS system.

HANDLING SCENARIOS:

1. **Deployment SUCCESS (status: 'SUCCEEDED')**:
   - **Step 1**: Call `update_jira_status` to add a comment ("Deployment to production was successful.") and transition the status to "Done".
   - **Step 2**: Call `update_notion_status` to set the status to "Resolved".
   - **Step 3**: Call `send_slack_broadcast` to notify the team in #all-kaos.
   - **Step 4**: Call `log_deployment_report` to record the success.

2. **Deployment FAILURE (status: 'FAILED')**:
   - **Step 1**: Call `analyze_deployment_failure` (with Logs URL) to get the AI diagnosis.
   - **Step 2**: Call `update_jira_status` to add a comment ("Production deployment failed. Investigating..."). 
   - **Step 3**: Call `update_notion_status` to set the status to "Needs attention".
   - **Step 4**: **Personalized Notification**: Call `send_slack_dm` to:
     a) The original **Author** with: "Your approved PR has failed in prod. AI diagnosis: <DIAGNOSIS>. Please look into it."
     b) The **Reviewer** (if known) with: "A PR you reviewed has failed in prod. AI diagnosis: <DIAGNOSIS>."
     (Replace <DIAGNOSIS> with the result from analyze_deployment_failure).
   - **Step 5**: **Close the Loop**: Call `emit_quality_report` with the service, diagnosis, and Author to re-trigger Agent 1.
   - **Step 6**: Call `log_deployment_report` to record the failure.

IMPORTANT: Always use the 'Author' and 'Reviewer' provided in the event for DMs. If 'Author' is 'Unknown', fallback to #all-kaos for the notification but still emit the report.
"""

def process_ops_event(msg_value: str):
    """Process a deployment status event."""
    try:
        event_data = json.loads(msg_value)
        event = OpsStatusEvent(**event_data)
        print(f"✅ [Agent 3] Ops Event: {event.status} | Pipeline: {event.pipeline} | ID: {event.execution_id}")

        agent = BaseAgent(
            name="OpsManager",
            tools=ops_tools,
            instructions=SYSTEM_PROMPT
        )

        task = f"""
        Deployment Status Event Received:
        Execution ID: {event.execution_id}
        Service/Pipeline: {event.pipeline}
        Status: {event.status}
        Author: {event.author or 'Unknown'}
        Reviewer: {event.reviewer or 'Unknown'}
        Failure Stage: {event.failure_stage or 'N/A'}
        Logs URL: {event.logs_url or 'N/A'}

        Please handle this deployment outcome.
        """

        agent.run(task)

    except Exception as e:
        print(f"❌ [Agent 3] Failed to process ops event: {e}")

def main():
    print("Agent 3: Ops Manager Starting...")
    print(f"🔌 Connecting to Kafka Topic: {OPS_TOPIC}...")

    kafka = KafkaClient()
    consumer = kafka.create_consumer(group_id=GROUP_ID)
    consumer.subscribe([OPS_TOPIC])

    print("🎧 Listening for deployment status events...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            value = msg.value().decode('utf-8')
            process_ops_event(value)

    except KeyboardInterrupt:
        print("🛑 Agent 3 stopping...")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
