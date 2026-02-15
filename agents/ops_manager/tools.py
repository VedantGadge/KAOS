from langchain_core.tools import tool
from shared.neo4j.client import Neo4jClient
from shared.logger import event_logger
from config.settings import settings
import boto3
import json

# ─────────────────────────────────────────────
# Tool 1: Trigger AWS Pipeline (Simulated)
# ─────────────────────────────────────────────
@tool
def trigger_aws_pipeline(pipeline_name: str) -> str:
    """
    Trigger an AWS CodePipeline execution (simulated).
    In production, this would use boto3.client('codepipeline').
    """
    print(f"🚀 Triggering AWS Pipeline: {pipeline_name}...")
    # Simulated Success
    return f"Pipeline {pipeline_name} triggered successfully. Execution ID: exe-{settings.AWS_REGION}-999"

# ─────────────────────────────────────────────
# Tool 2: Update Jira Ticket Status
# ─────────────────────────────────────────────
@tool
def update_jira_status(summary: str, comment: str, status: str = "") -> str:
    """
    Update a Jira ticket by adding a comment and optionally transitioning its status.
    Searches for the ticket by summary.
    Args:
        summary: Title/summary of the Jira ticket to find (e.g., "PaymentService").
        comment: Comment to add to the ticket.
        status: Optional new status to transition to (e.g., "Done").
    """
    print(f"🎫 Updating Jira ticket: {summary}")
    try:
        from jira import JIRA
        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )

        jql = f'summary ~ "{summary}" ORDER BY created DESC'
        issues = jira.search_issues(jql, maxResults=1)

        if not issues:
            return f"No Jira ticket found matching: {summary}"

        issue = issues[0]
        jira.add_comment(issue, comment)
        
        if status:
            transitions = jira.transitions(issue)
            for t in transitions:
                if t['name'].lower() == status.lower():
                    jira.transition_issue(issue, t['id'])
                    return f"Jira {issue.key} updated with comment and transitioned to {status}."
        
        return f"Jira {issue.key} updated with comment."

    except Exception as e:
        return f"Error updating Jira ticket: {str(e)}"

# ─────────────────────────────────────────────
# Tool 3: Update Notion Status
# ─────────────────────────────────────────────
@tool
def update_notion_status(title: str, new_status: str) -> str:
    """
    Update the status of an existing bug entry in Notion.
    Args:
        title: Title of the bug/repo to find.
        new_status: Options: "Open", "Needs attention", "Resolved".
    """
    print(f"📋 Updating Notion status for '{title}' -> {new_status}")
    try:
        from notion_client import Client as NotionClient
        notion = NotionClient(auth=settings.NOTION_API_KEY)
        database_id = settings.NOTION_DATABASE_ID

        search_results = notion.search(
            query=title,
            filter={"value": "page", "property": "object"}
        ).get("results", [])

        for page in search_results:
            if page.get("parent", {}).get("database_id", "").replace("-", "") == database_id.replace("-", ""):
                notion.pages.update(
                    page_id=page["id"],
                    properties={"Status": {"status": {"name": new_status}}}
                )
                return f"Notion status updated to '{new_status}'."
        return f"No matching Notion page found for '{title}'."
    except Exception as e:
        return f"Error updating Notion: {str(e)}"

# ─────────────────────────────────────────────
# Tool 4: Send Slack DM
# ─────────────────────────────────────────────
@tool
def send_slack_dm(channel: str, text: str) -> str:
    """
    Send a direct message to a user on Slack.
    Args:
        channel: Slack channel name or User ID (e.g., @dave, U12345).
        text: Message content.
    """
    print(f"📨 Sending Slack DM to {channel}...")
    try:
        from slack_sdk import WebClient
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        
        target_id = channel
        if channel.startswith('U'):
            open_resp = client.conversations_open(users=channel)
            target_id = open_resp['channel']['id']
        
        client.chat_postMessage(channel=target_id, text=text)
        return f"DM sent to {target_id}"
    except Exception as e:
        return f"Error sending Slack DM: {str(e)}"

# ─────────────────────────────────────────────
# Tool 5: Analyze Deployment Failure (Bedrock)
# ─────────────────────────────────────────────
@tool
def analyze_deployment_failure(pipeline_name: str, logs_url: str = "") -> str:
    """
    Analyze deployment failure logs using AWS Bedrock to identify the root cause.
    """
    print(f"🧠 Analyzing failure for {pipeline_name}...")
    
    # Simulated logs based on typical failures
    simulated_logs = "Error: Config variable 'DATABASE_URL' is missing during 'Build' stage. Python exit code 1."
    
    try:
        bedrock = boto3.client(
            'bedrock-runtime',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        prompt = f"Analyze these deployment logs and provide a concise, friendly root cause and fix for a developer:\n\n{simulated_logs}"
        
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 512,
                "temperature": 0.5,
            }
        })
        
        response = bedrock.invoke_model(
            modelId="amazon.titan-text-express-v1",
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response.get("body").read())
        analysis = response_body.get("results", [{}])[0].get("outputText", "Could not analyze logs.")
        
        return f"Deployment Analysis for {pipeline_name}:\n{analysis}"

    except Exception as e:
        # Fallback if Bedrock fails
        return f"Failed to analyze logs via Bedrock. Manual check required at {logs_url}. Error: {str(e)}"

# ─────────────────────────────────────────────
# Tool 6: Slack Broadcast
# ─────────────────────────────────────────────
@tool
def send_slack_broadcast(message: str) -> str:
    """
    Send an announcement to the #all-kaos channel.
    """
    print(f"📢 Broadcasting to #all-kaos: {message}")
    try:
        from slack_sdk import WebClient
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        client.chat_postMessage(channel="#all-kaos", text=message)
        return "Broadcast sent to #all-kaos."
    except Exception as e:
        return f"Failed to send Slack broadcast: {str(e)}"

# ─────────────────────────────────────────────
# Tool 7: Log Deployment Report (For Future Retrieval)
# ─────────────────────────────────────────────
@tool
def log_deployment_report(repo: str, status: str, summary: str) -> str:
    """
    Compile and log the entire deployment story to the event history database.
    This creates an AI-searchable record for future troubleshooting.
    """
    print(f"📝 Logging deployment report for {repo}...")
    try:
        event_logger.log_event(
            event_type="DEPLOYMENT_REPORT",
            actor="OpsManager",
            repo=repo,
            details={
                "status": status,
                "summary": summary,
                "timestamp": settings.current_time_iso()
            }
        )
        return "Deployment story logged successfully."
    except Exception as e:
        return f"Failed to log deployment report: {str(e)}"

# ─────────────────────────────────────────────
# Tool 8: Emit Quality Report (Closed-Loop)
# ─────────────────────────────────────────────
@tool
def emit_quality_report(service_name: str, error_message: str, stack_trace: str = "", author: str = "") -> str:
    """
    Report a deployment failure back to the Triager (Agent 1) to restart the dev cycle.
    This creates a new bug report in the system.quality.reports Kafka topic.
    """
    print(f"🔄 Closing the loop: Reporting failure for {service_name} back to Triage (Author: {author or 'Unknown'})...")
    try:
        from shared.kafka.client import KafkaClient
        import uuid
        import time

        client = KafkaClient()
        producer = client.create_producer()
        
        event = {
            "event_id": str(uuid.uuid4()),
            "service_name": service_name,
            "severity": "CRITICAL",
            "error_message": f"Deployment Failure: {error_message}",
            "stack_trace": stack_trace,
            "suggested_assignee": author,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        producer.produce(
            topic="system.quality.reports",
            key=event["event_id"],
            value=json.dumps(event)
        )
        producer.flush()
        
        return f"Successfully emitted quality report for {service_name}. Agent 1 will now re-triage this issue."

    except Exception as e:
        return f"Failed to emit quality report: {str(e)}"

tools = [trigger_aws_pipeline, update_jira_status, update_notion_status, send_slack_dm, analyze_deployment_failure, send_slack_broadcast, log_deployment_report, emit_quality_report]
