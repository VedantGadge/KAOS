import os
import sys
import logging
import asyncio
import httpx
import json
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.control_plane.process_manager import manager
from shared.logger import setup_logger
from config.settings import settings
from shared.kafka.client import KafkaClient

logger = setup_logger("control-plane")

app = FastAPI(title="KAOS Control Plane")

AGENTS = {
    "ingestion": ["python", "agents/ingestion/main.py"],
    "triager": ["python", "agents/triager/consumer.py"],
    "review_manager": ["python", "agents/review_manager/consumer.py"],
    "ops_manager": ["python", "agents/ops_manager/main.py"],
    "chatbot": ["python", "agents/chatbot/main.py"],
}

# -----------------------------------------------------------------------------
# Event Polling for UI Graph
# -----------------------------------------------------------------------------
ui_events = []
MAX_EVENTS = 50

def consume_events_for_ui():
    client = KafkaClient()
    consumer = client.create_consumer("ui-dashboard-group")
    topics = [
        settings.TOPIC_QUALITY_REPORTS,
        settings.TOPIC_PR_UPDATES,
        settings.TOPIC_PR_DECISIONS,
        settings.TOPIC_DEPLOY_STATUS
    ]
    try:
        consumer.subscribe(topics)
        while True:
            msg = consumer.poll(1.0)
            if msg is None: continue
            if msg.error():
                logger.error(f"Kafka error in UI consumer: {msg.error()}")
                continue
            
            try:
                topic = msg.topic()
                val = json.loads(msg.value().decode('utf-8'))
                event_type = "unknown"
                
                # Determine event step for UI
                if topic == settings.TOPIC_QUALITY_REPORTS:
                    event_type = "QUALITY_REPORT" # Ingestion step
                elif topic == settings.TOPIC_PR_UPDATES:
                    event_type = val.get("event", "PR_UPDATE") # Triager / Review step
                elif topic == settings.TOPIC_PR_DECISIONS:
                    event_type = "PR_DECISION" # Review step
                elif topic == settings.TOPIC_DEPLOY_STATUS:
                    event_type = "DEPLOY_STATUS" # Ops step
                
                ui_events.append({
                    "topic": topic,
                    "type": event_type,
                    "payload": val,
                    "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
                })
                
                if len(ui_events) > MAX_EVENTS:
                    ui_events.pop(0)
                    
            except Exception as e:
                logger.error(f"Error parsing msg: {e}")
    finally:
        consumer.close()

# Start background consumer
threading.Thread(target=consume_events_for_ui, daemon=True).start()

@app.get("/api/events")
def get_events():
    return {"events": ui_events}

# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    return manager.get_status()

@app.post("/api/agents/{agent_name}/start")
def start_agent(agent_name: str):
    if agent_name not in AGENTS: raise HTTPException(status_code=404, detail="Agent not found")
    success = manager.start_process(agent_name, AGENTS[agent_name])
    if not success: raise HTTPException(status_code=500, detail=f"Failed to start {agent_name}")
    return {"status": "started", "agent": agent_name}

@app.post("/api/agents/{agent_name}/stop")
def stop_agent(agent_name: str):
    if agent_name not in AGENTS: raise HTTPException(status_code=404, detail="Agent not found")
    success = manager.stop_process(agent_name)
    if not success: raise HTTPException(status_code=500, detail=f"Failed to stop {agent_name}")
    return {"status": "stopped", "agent": agent_name}

INGESTION_URL = "http://localhost:8000"

class SimulationRequest(BaseModel):
    service_name: str = "payment-service"
    error_message: str = "NullPointerException in ProcessTransaction"
    pr_author: str = "dev_user"

@app.post("/api/simulate/sentry_error")
async def simulate_sentry_error(req: SimulationRequest):
    payload = {
        "id": "evt_" + str(int(asyncio.get_event_loop().time())),
        "project_name": req.service_name,
        "level": "error",
        "message": req.error_message
    }
    # Also log a synthetic UI event so we can animate the trigger immediately
    ui_events.append({"topic": "synthetic", "type": "SENTRY_TRIGGER", "payload": payload})
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/sentry", json=payload)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

@app.post("/api/simulate/pr_open")
async def simulate_pr_open(req: SimulationRequest):
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 102,
            "title": f"Fix: {req.error_message}",
            "body": "This PR fixes the NullPointerException in the validation logic.",
            "user": {"login": req.pr_author},
            "head": {"ref": "fix/simulation-error"}
        },
        "repository": {"name": req.service_name}
    }
    ui_events.append({"topic": "synthetic", "type": "GITHUB_TRIGGER", "payload": payload})
    headers = {"X-GitHub-Event": "pull_request"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/github", json=payload, headers=headers)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

class PRDecisionRequest(BaseModel):
    service_name: str = "payment-service"
    pr_id: int = 102
    decision: str
    comment: str

@app.post("/api/simulate/pr_decision")
async def simulate_pr_decision(req: PRDecisionRequest):
    payload = {
        "action": "submitted",
        "pull_request": {
            "number": req.pr_id,
            "title": "Fix: Simulation Test Error",
            "user": {"login": "dev_user"}
        },
        "review": {
            "state": req.decision,
            "body": req.comment,
            "user": {"login": "Dave"}
        },
        "repository": {"name": req.service_name}
    }
    ui_events.append({"topic": "synthetic", "type": "GITHUB_TRIGGER", "payload": payload})
    headers = {"X-GitHub-Event": "pull_request_review"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/github", json=payload, headers=headers)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

class DeploymentRequest(BaseModel):
    service_name: str = "payment-service"
    status: str
    reviewer: str = "Dave"

@app.post("/api/simulate/deployment")
async def simulate_deployment(req: DeploymentRequest):
    payload = {
        "service": req.service_name,
        "version": "v1.0.5",
        "status": req.status,
        "logs": "CRITICAL: NullPointerException..." if req.status == "failure" else "Deployment successful.",
        "author": "dev_user",
        "reviewer": req.reviewer,
        "env": "production"
    }
    ui_events.append({"topic": "synthetic", "type": "JENKINS_TRIGGER", "payload": payload})
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/deployment", json=payload)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "react-frontend", "dist")
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)

@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_path, "index.html"))

app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
