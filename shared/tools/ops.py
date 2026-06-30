from langchain_core.tools import tool
from config.settings import settings
from shared.logger import event_logger, logger
import boto3
import json

@tool
def trigger_aws_pipeline(pipeline_name: str) -> str:
    """
    Trigger an AWS CodePipeline execution (simulated).
    """
    logger.info(f"🚀 Triggering AWS Pipeline: {pipeline_name}...")
    return f"Pipeline {pipeline_name} triggered successfully. Execution ID: exe-{settings.AWS_REGION}-999"

@tool
def analyze_deployment_failure(pipeline_name: str, logs_url: str = "") -> str:
    """
    Analyze deployment failure logs using AWS Bedrock to identify the root cause.
    """
    logger.info(f"🧠 Analyzing failure for {pipeline_name}...")
    
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
        return f"Failed to analyze logs via Bedrock. Manual check required at {logs_url}. Error: {str(e)}"

@tool
def log_deployment_report(repo: str, status: str, summary: str) -> str:
    """
    Compile and log the entire deployment story to the event history database.
    """
    logger.info(f"📝 Logging deployment report for {repo}...")
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

@tool
def emit_quality_report(service_name: str, error_message: str, stack_trace: str = "", author: str = "") -> str:
    """
    Report a deployment failure back to the Triager (Agent 1) to restart the dev cycle.
    """
    logger.info(f"🔄 Closing the loop: Reporting failure for {service_name} back to Triage (Author: {author or 'Unknown'})...")
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
