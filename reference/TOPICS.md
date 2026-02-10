# Kafka Topic Taxonomy & Schemas

## 1. Input: `system.quality.reports`
**Source:** Sentry / Datadog / Manual Report
**Purpose:** Raw bug ingestion.
```json
{
  "event_id": "uuid-1234",
  "service_name": "PaymentService",
  "severity": "CRITICAL",
  "error_message": "NullPointerException in ProcessTransaction",
  "stack_trace": "...",
  "timestamp": "2026-02-10T10:00:00Z"
}
```

## 2. Dev Updates: `dev.pr.updates`
**Source:** GitHub Webhooks (Pull Request)
**Purpose:** Tracking code changes (Pushes, Opens).
```json
{
  "event": "PR_SYNCHRONIZE",
  "repo": "PaymentService",
  "pr_id": 102,
  "author": "bob",
  "commit_sha": "abc123",
  "timestamp": "..."
}
```

## 3. Dev Decisions: `dev.pr.decisions`
**Source:** GitHub Webhooks (Review Submission)
**Purpose:** Tracking human/AI decisions.
```json
{
  "event": "REVIEW_SUBMITTED",
  "pr_id": 102,
  "repo": "PaymentService",
  "actor": "alice", 
  "decision": "CHANGES_REQUESTED", 
  "comment": "Fix the typo on line 45.",
  "timestamp": "..."
}
```

## 4. Ops Status: `ops.deploy.status`
**Source:** AWS CodePipeline / EventBridge
**Purpose:** Tracking deployment lifecycle.
```json
{
  "execution_id": "exe-5678",
  "pipeline": "payment-service-prod",
  "status": "FAILED",
  "failure_stage": "Build",
  "logs_url": "s3://build-logs/...",
  "timestamp": "..."
}
```