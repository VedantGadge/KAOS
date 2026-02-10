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

1. Analyze the error message and stack trace.
2. **Find the Active Owner** using `find_service_owner` (it will handle escalation if needed).
3. Create a Jira ticket assigned to that person.
4. Notify them on Slack.
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
