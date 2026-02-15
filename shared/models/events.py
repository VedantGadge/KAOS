from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class ReportEvent(BaseModel):
    event_id: str
    service_name: str
    severity: str
    error_message: str
    stack_trace: Optional[str] = None
    suggested_assignee: Optional[str] = None
    timestamp: datetime

class DevUpdateEvent(BaseModel):
    event: str
    repo: str
    pr_id: int
    author: str
    commit_sha: str
    timestamp: Optional[str] = None

class DevDecisionEvent(BaseModel):
    event: str
    pr_id: int
    repo: str
    actor: str
    decision: str
    comment: Optional[str] = None
    timestamp: Optional[str] = None

class OpsStatusEvent(BaseModel):
    execution_id: str
    pipeline: str
    status: str
    failure_stage: Optional[str] = None
    logs_url: Optional[str] = None
    author: Optional[str] = None
    timestamp: Optional[str] = None
