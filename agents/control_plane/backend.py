import os
import sys
import logging
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.control_plane.process_manager import manager
from shared.logger import setup_logger

logger = setup_logger("control-plane")

app = FastAPI(title="KAOS Control Plane")

# Agent Configurations
AGENTS = {
    "ingestion": ["python", "agents/ingestion/main.py"],
    "triager": ["python", "agents/triager/consumer.py"],
    "review_manager": ["python", "agents/review_manager/consumer.py"],
    "ops_manager": ["python", "agents/ops_manager/main.py"],
}

# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/status")
def get_status():
    """Get the running status of all agents."""
    return manager.get_status()

@app.post("/api/agents/{agent_name}/start")
def start_agent(agent_name: str):
    """Start a specific agent."""
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    command = AGENTS[agent_name]
    success = manager.start_process(agent_name, command)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to start {agent_name}")
    return {"status": "started", "agent": agent_name}

@app.post("/api/agents/{agent_name}/stop")
def stop_agent(agent_name: str):
    """Stop a specific agent."""
    if agent_name not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    success = manager.stop_process(agent_name)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to stop {agent_name}")
    return {"status": "stopped", "agent": agent_name}

# -----------------------------------------------------------------------------
# Simulation Endpoints
# -----------------------------------------------------------------------------

INGESTION_URL = "http://localhost:8000"

class SimulationRequest(BaseModel):
    service_name: str = "payment-service"
    error_message: str = "NullPointerException in ProcessTransaction"
    pr_author: str = "dev_user"

@app.post("/api/simulate/sentry_error")
async def simulate_sentry_error(req: SimulationRequest):
    """Simulate a Sentry error webhook."""
    payload = {
        "id": "evt_" + str(int(asyncio.get_event_loop().time())),
        "project_name": req.service_name,
        "level": "error",
        "message": req.error_message
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/sentry", json=payload)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

@app.post("/api/simulate/pr_open")
async def simulate_pr_open(req: SimulationRequest):
    """Simulate a GitHub PR Open webhook."""
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 101,
            "title": f"Fix: {req.error_message}",
            "user": {"login": req.pr_author},
            "head": {"ref": "fix/simulation-error"}
        },
        "repository": {"name": req.service_name}
    }
    headers = {"X-GitHub-Event": "pull_request"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/github", json=payload, headers=headers)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

class PRDecisionRequest(BaseModel):
    service_name: str = "payment-service"
    pr_id: int = 101
    decision: str  # APPROVED or CHANGES_REQUESTED
    comment: str

@app.post("/api/simulate/pr_decision")
async def simulate_pr_decision(req: PRDecisionRequest):
    """Simulate a GitHub PR Review webhook."""
    payload = {
        "action": "submitted",
        "pull_request": {
            "number": req.pr_id,
            "title": "Fix: Simulation Test Error",
            "user": {"login": "dev_user"} # Original PR author
        },
        "review": {
            "state": req.decision, # "approved" or "changes_requested"
            "body": req.comment,
            "user": {"login": "Dave"} # Reviewer
        },
        "repository": {"name": req.service_name}
    }
    headers = {"X-GitHub-Event": "pull_request_review"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/github", json=payload, headers=headers)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

class DeploymentRequest(BaseModel):
    service_name: str = "payment-service"
    status: str # success or failure
    reviewer: str = "Dave" # Added reviewer field

@app.post("/api/simulate/deployment")
async def simulate_deployment(req: DeploymentRequest):
    """Simulate a Deployment Status webhook."""
    payload = {
        "service": req.service_name,
        "version": "v1.0.5",
        "status": req.status,
        "logs": "Simulated deployment logs...\nError: Connection Refused" if req.status == "failure" else "Deployment successful.",
        "author": "dev_user",
        "reviewer": req.reviewer,
        "env": "production"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{INGESTION_URL}/webhooks/deployment", json=payload)
            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Failed to reach Ingestion Agent: {e}")

# -----------------------------------------------------------------------------
# Frontend Hosting
# -----------------------------------------------------------------------------

# Serve frontend files
frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path)

app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # process_manager needs to run in main thread, uvicorn works fine.
    # Listen on 8080 to avoid conflict with Ingestion Agent (8000)
    uvicorn.run(app, host="0.0.0.0", port=8080)
