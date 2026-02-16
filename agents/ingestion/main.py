import sys
import os
import json
import logging
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from contextlib import asynccontextmanager
from typing import Dict, Any
from pydantic import BaseModel

# Add the parent directory to sys.path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.client import KafkaClient
from agents.ingestion.models import SentryWebhook, QualityReport, PRUpdate, PRDecision, DeploymentStatus
from config.settings import settings
import time

# Setup Logging
from shared.logger import setup_logger
logger = setup_logger("ingestion-agent")

# Global Kafka Producer
producer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global producer
    logger.info("🚀 Starting Ingestion Agent...")
    client = KafkaClient()
    producer = client.create_producer()
    yield
    # Shutdown
    logger.info("🛑 Shutting down Ingestion Agent...")
    if producer:
        producer.flush()

app = FastAPI(title="KAOS Ingestion Service", lifespan=lifespan)

def publish_to_kafka(topic: str, key: str, value: BaseModel):
    """Helper to publish Pydantic models to Kafka"""
    if not producer:
        logger.error("Kafka producer is not initialized!")
        return

    try:
        producer.produce(
            topic=topic,
            key=str(key),
            value=json.dumps(value.model_dump())
        )
        producer.poll(0) # Trigger callbacks
        logger.info(f"✅ Published to {topic}:Key={key}")
    except Exception as e:
        logger.error(f"❌ Failed to publish to {topic}: {e}")

@app.get("/")
def health_check():
    return {"status": "running", "service": "kaos-ingestion"}

@app.post("/webhooks/sentry")
async def handle_sentry_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Receives Sentry webhooks and publishes to 'system.quality.reports'.
    """
    logger.info(f"📨 Received Sentry Webhook: {payload.get('project_name', 'Unknown')}")
    
    try:
        # Map Sentry Payload to Internal Schema
        # Note: Real Sentry payloads are complex, this is a simplified mapping
        event_id = payload.get("id", "unknown-id")
        project = payload.get("project_name", "unknown-service")
        message = payload.get("message", "No error message")
        level = payload.get("level", "error").upper()
        
        # Normalize Severity
        severity_map = {"ERROR": "HIGH", "FATAL": "CRITICAL", "WARNING": "MEDIUM", "INFO": "LOW"}
        severity = severity_map.get(level, "MEDIUM")

        kafka_event = QualityReport(
            event_id=event_id,
            service_name=project,
            error_message=message,
            severity=severity,
            raw_payload=payload
        )

        # Publish in background to avoid blocking the webhook response
        background_tasks.add_task(
            publish_to_kafka, 
            topic=settings.TOPIC_QUALITY_REPORTS, 
            key=event_id, 
            value=kafka_event
        )

        return {"status": "queued", "event_id": event_id}

    except Exception as e:
        logger.error(f"Failed to process Sentry webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhooks/github")
async def handle_github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives GitHub webhooks and publishes to 'dev.pr.*' topics.
    """
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "ping")
    
    logger.info(f"📨 Received GitHub Webhook: {event_type}")

    if event_type == "pull_request":
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("name", "unknown-repo")
        
        if action in ["opened", "reopened", "synchronize"]:
            # Map to PRUpdate
            kafka_event = PRUpdate(
                event="PR_OPENED" if action == "opened" else "PR_UPDATED",
                repo=repo,
                pr_id=pr.get("number"),
                author=pr.get("user", {}).get("login", "unknown"),
                title=pr.get("title", ""),
            )
            
            background_tasks.add_task(
                publish_to_kafka,
                topic=settings.TOPIC_PR_UPDATES,
                key=f"pr-{pr.get('number')}",
                value=kafka_event
            )
            return {"status": "queued", "type": "PR Update"}

    elif event_type == "pull_request_review":
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("name", "unknown-repo")
        state = review.get("state").upper() # APPROVED, CHANGES_REQUESTED
        
        # Map to PRDecision
        kafka_event = PRDecision(
            event="REVIEW_SUBMITTED",
            repo=repo,
            pr_id=pr.get("number"),
            actor=review.get("user", {}).get("login"),
            pr_author=pr.get("user", {}).get("login"),
            decision=state,
            comment=review.get("body", "")
        )
        
        background_tasks.add_task(
            publish_to_kafka,
            topic=settings.TOPIC_PR_DECISIONS,
            key=f"review-{review.get('id')}",
            value=kafka_event
        )
        return {"status": "queued", "type": "PR Review"}

    return {"status": "ignored", "reason": "unsupported_event"}

@app.post("/webhooks/deployment")
async def handle_deployment_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Receives Deployment status (e.g. from Jenna/GitHub Actions) and publishes to 'ops.deploy.status'.
    """
    logger.info(f"📨 Received Deployment Webhook: {payload.get('service', 'Unknown')} -> {payload.get('status')}")
    
    try:
        # Map Payload to Internal Schema
        status_map = {"success": "SUCCEEDED", "failure": "FAILED"}
        status = status_map.get(payload.get("status", "").lower(), "FAILED")
        
        from shared.models.events import OpsStatusEvent
        
        # We use the API model for validation, but publish the Shared Event Model
        kafka_event = OpsStatusEvent(
            execution_id=payload.get("version", "unknown"),
            pipeline=payload.get("service", "Unknown"),
            status=status,
            failure_stage="Deploy",
            logs_url=payload.get("logs", ""),
            author=payload.get("author", "CI/CD"), # Allow passing author
            timestamp=str(time.time())
        )

        background_tasks.add_task(
            publish_to_kafka,
            topic=settings.TOPIC_DEPLOY_STATUS,
            key=f"deploy-{payload.get('service')}-{int(time.time())}",
            value=kafka_event
        )

        return {"status": "queued", "event": status}

    except Exception as e:
        logger.error(f"Failed to process Deployment webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
