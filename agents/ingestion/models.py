from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
import time

# --- INCOMING WEBHOOK SCHEMAS ---

class SentryWebhook(BaseModel):
    """
    Simplified schema for a Sentry webhook payload.
    In reality, Sentry sends a very complex JSON, but we'll focus on key fields.
    """
    id: str
    project_name: str = Field(..., alias="project_name")
    level: str = "error"
    message: str
    culprit: Optional[str] = None
    url: Optional[str] = None

class GitHubWebhook(BaseModel):
    """
    Simplified schema for a generic GitHub webhook.
    We will inspect headers/payload to determine the specific event type.
    """
    action: str
    repository: Dict[str, Any]
    pull_request: Optional[Dict[str, Any]] = None
    sender: Dict[str, Any]
    review: Optional[Dict[str, Any]] = None

# --- INTERNAL KAFKA SCHEMAS ---

class QualityReport(BaseModel):
    """
    Schema for 'system.quality.reports' topic (Triager Agent).
    """
    event_id: str
    service_name: str
    error_message: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    timestamp: float = Field(default_factory=time.time)
    source: str = "ingestion-service"
    raw_payload: Optional[Dict[str, Any]] = None

class PRUpdate(BaseModel):
    """
    Schema for 'dev.pr.updates' topic (Review Manager).
    """
    event: Literal["PR_OPENED", "PR_UPDATED", "PR_CLOSED", "PR_MERGED"]
    repo: str
    pr_id: int
    author: str
    title: str
    timestamp: float = Field(default_factory=time.time)

class PRDecision(BaseModel):
    """
    Schema for 'dev.pr.decisions' topic (Review Manager).
    """
    event: Literal["REVIEW_SUBMITTED"]
    repo: str
    pr_id: int
    actor: str
    pr_author: str
    decision: Literal["APPROVED", "CHANGES_REQUESTED", "COMMENTED"]
    comment: str
    timestamp: float = Field(default_factory=time.time)

class DeploymentStatus(BaseModel):
    """
    Schema for 'ops.deploy.status' topic (Ops Manager).
    """
    event: Literal["DEPLOY_SUCCESS", "DEPLOY_FAILURE"]
    service: str
    version: str
    timestamp: float = Field(default_factory=time.time)
    logs: Optional[str] = None
