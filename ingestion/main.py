from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from shared.kafka.client import KafkaClient
from shared.models.events import ReportEvent, DevUpdateEvent
import uuid
from datetime import datetime
import json

app = FastAPI(title="KAOS Ingestion Service")
kafka = KafkaClient()
producer = kafka.create_producer()

def delivery_report(err, msg):
    if err:
        print(f"❌ Message delivery failed: {err}")
    else:
        print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")

@app.get("/")
def health_check():
    return {"status": "ok", "service": "KAOS Ingestion"}

@app.post("/webhooks/jira")
async def jira_webhook(request: Request):
    """
    Receives Jira Webhooks -> Pushes to 'system.quality.reports'
    """
    try:
        payload = await request.json()
        # simplified mapping for demo
        issue = payload.get("issue", {})
        fields = issue.get("fields", {})
        
        event = ReportEvent(
            event_id=str(uuid.uuid4()),
            service_name=fields.get("project", {}).get("key", "Unknown"),
            severity=fields.get("priority", {}).get("name", "Medium"),
            error_message=fields.get("summary", "No Summary"),
            stack_trace=fields.get("description", ""),
            timestamp=datetime.now()
        )
        
        # Produce to Kafka
        producer.produce(
            "system.quality.reports", 
            event.model_dump_json().encode('utf-8'), 
            callback=delivery_report
        )
        producer.poll(0)
        return {"status": "received", "event_id": event.event_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks/github")
async def github_webhook(request: Request):
    """
    Receives GitHub Webhooks -> Pushes to 'dev.pr.updates'
    """
    try:
        payload = await request.json()
        # Check if it's a PR event
        if "pull_request" not in payload:
            return {"status": "ignored", "reason": "not a PR event"}

        pr = payload["pull_request"]
        
        event = DevUpdateEvent(
            event=payload.get("action", "unknown"),
            repo=payload.get("repository", {}).get("name", "unknown"),
            pr_id=pr.get("number"),
            author=pr.get("user", {}).get("login"),
            commit_sha=pr.get("head", {}).get("sha"),
            timestamp=str(datetime.now())
        )

        producer.produce(
            "dev.pr.updates", 
            event.model_dump_json().encode('utf-8'), 
            callback=delivery_report
        )
        producer.poll(0)
        return {"status": "received", "pr_id": event.pr_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
