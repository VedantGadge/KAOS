"""
Ops Manager Agent — LangGraph State Machine (Deterministic + Bedrock for Log Analysis)

A StateGraph that replaces the LLM-based BaseAgent orchestration.
The only AI call retained is `analyze_deployment_failure` (AWS Bedrock),
which is legitimately needed for log diagnosis. Everything else is pure Python.

Flow:
  START → extract_event → route_status
    ├─ SUCCEEDED → handle_success → log_success → END
    └─ FAILED   → analyze_failure → notify_failure → close_loop → END
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from shared.tools import (
    update_jira_status,
    update_notion_status,
    send_slack_dm,
    send_slack_broadcast,
    analyze_deployment_failure,
    log_deployment_report,
    emit_quality_report,
)
from shared.logger import event_logger, logger


# ── State ────────────────────────────────────────────────────────────────────

class OpsState(TypedDict):
    message: dict  # raw Kafka payload

    # Extracted fields
    execution_id: Optional[str]
    pipeline: Optional[str]
    status: Optional[str]
    author: Optional[str]
    reviewer: Optional[str]
    failure_stage: Optional[str]
    logs_url: Optional[str]

    # Populated during graph execution
    diagnosis: Optional[str]


# ── Nodes ────────────────────────────────────────────────────────────────────

def extract_event(state: OpsState) -> dict:
    """Parse the Kafka payload into typed state fields."""
    msg = state.get("message", {})

    execution_id = msg.get("execution_id", "unknown")
    pipeline = msg.get("pipeline", "unknown")
    status = msg.get("status", "UNKNOWN")

    logger.info(
        f"✅ [Ops Manager] Event: {status} | Pipeline: {pipeline} | ID: {execution_id}"
    )

    return {
        "execution_id": execution_id,
        "pipeline": pipeline,
        "status": status,
        "author": msg.get("author", "Unknown"),
        "reviewer": msg.get("reviewer", "Unknown"),
        "failure_stage": msg.get("failure_stage"),
        "logs_url": msg.get("logs_url"),
    }


def route_status(state: OpsState) -> str:
    """Conditional edge: branch on deployment status."""
    status = state.get("status", "").upper()
    if status == "SUCCEEDED":
        return "succeeded"
    elif status == "FAILED":
        return "failed"
    logger.warning(f"⚠️ Unrecognised deployment status: {status}")
    return "end"


# ── Success Flow ─────────────────────────────────────────────────────────────

def handle_success(state: OpsState) -> dict:
    """Update Jira → Done, Notion → Resolved, broadcast on Slack."""
    pipeline = state["pipeline"]
    execution_id = state["execution_id"]

    try:
        update_jira_status.invoke({
            "summary": pipeline,
            "comment": f"Deployment to production was successful. (Execution: {execution_id})",
            "service_name": pipeline,
            "status": "Done",
        })
    except Exception as e:
        logger.warning(f"⚠️ Jira update failed: {e}")

    try:
        update_notion_status.invoke({
            "title": pipeline,
            "new_status": "Resolved",
        })
    except Exception as e:
        logger.warning(f"⚠️ Notion update failed: {e}")

    try:
        send_slack_broadcast.invoke({
            "channel": "#all-kaos",
            "text": f"🚀 Deployment *SUCCEEDED* for `{pipeline}` (Execution: {execution_id}). Jira → Done, Notion → Resolved.",
        })
    except Exception as e:
        logger.warning(f"⚠️ Slack broadcast failed: {e}")

    return {}


def log_success(state: OpsState) -> dict:
    """Persist the success deployment report."""
    try:
        log_deployment_report.invoke({
            "repo": state["pipeline"],
            "status": "SUCCESS",
            "summary": f"Deployment {state['execution_id']} succeeded.",
        })
    except Exception as e:
        logger.warning(f"⚠️ Deployment report logging failed: {e}")

    return {}


# ── Failure Flow ─────────────────────────────────────────────────────────────

def analyze_failure(state: OpsState) -> dict:
    """Call AWS Bedrock to diagnose the failure logs."""
    pipeline = state["pipeline"]
    logs_url = state.get("logs_url") or "N/A"

    logger.info(f"🧠 Analysing deployment failure for {pipeline}...")

    try:
        diagnosis = analyze_deployment_failure.invoke({
            "pipeline_name": pipeline,
            "logs_url": logs_url,
        })
    except Exception as e:
        diagnosis = f"Bedrock analysis unavailable: {e}. Manual review required at {logs_url}."
        logger.warning(f"⚠️ Bedrock analysis failed: {e}")

    return {"diagnosis": diagnosis}


def notify_failure(state: OpsState) -> dict:
    """Update tickets and DM the author/reviewer with the AI diagnosis."""
    pipeline = state["pipeline"]
    execution_id = state["execution_id"]
    author = state.get("author", "Unknown")
    reviewer = state.get("reviewer", "Unknown")
    diagnosis = state.get("diagnosis", "No diagnosis available.")
    failure_stage = state.get("failure_stage", "N/A")

    # Jira
    try:
        update_jira_status.invoke({
            "summary": pipeline,
            "comment": (
                f"Production deployment FAILED at stage: {failure_stage}.\n"
                f"AI Diagnosis: {diagnosis}"
            ),
            "service_name": pipeline,
            "status": "In Progress",
        })
    except Exception as e:
        logger.warning(f"⚠️ Jira update failed: {e}")

    # Notion
    try:
        update_notion_status.invoke({
            "title": pipeline,
            "new_status": "Needs attention",
        })
    except Exception as e:
        logger.warning(f"⚠️ Notion update failed: {e}")

    # Slack DMs
    try:
        if author and author != "Unknown":
            send_slack_dm.invoke({
                "channel": f"@{author}",
                "text": (
                    f"❌ Your approved PR has failed in production (`{pipeline}`, execution {execution_id}).\n"
                    f"🧠 AI Diagnosis: {diagnosis}\n"
                    f"Please look into it."
                ),
            })

        if reviewer and reviewer != "Unknown":
            send_slack_dm.invoke({
                "channel": f"@{reviewer}",
                "text": (
                    f"⚠️ A PR you reviewed has failed in production (`{pipeline}`, execution {execution_id}).\n"
                    f"🧠 AI Diagnosis: {diagnosis}"
                ),
            })

        # Always broadcast to team channel
        send_slack_broadcast.invoke({
            "channel": "#all-kaos",
            "text": (
                f"🔴 Deployment *FAILED* for `{pipeline}` (Execution: {execution_id}).\n"
                f"Stage: {failure_stage} | Author: {author} | Reviewer: {reviewer}\n"
                f"🧠 Diagnosis: {diagnosis}"
            ),
        })
    except Exception as e:
        logger.warning(f"⚠️ Slack notification failed: {e}")

    return {}


def close_loop(state: OpsState) -> dict:
    """Re-trigger Agent 1 (Triager) and log the failure report."""
    pipeline = state["pipeline"]
    author = state.get("author", "Unknown")
    diagnosis = state.get("diagnosis", "No diagnosis available.")

    # Emit quality report → Kafka → Agent 1
    try:
        emit_quality_report.invoke({
            "service_name": pipeline,
            "error_message": diagnosis,
            "stack_trace": f"Failure stage: {state.get('failure_stage', 'N/A')}",
            "author": author,
        })
        logger.info("🔄 Quality report emitted — Agent 1 will re-triage.")
    except Exception as e:
        logger.warning(f"⚠️ Failed to emit quality report: {e}")

    # Log deployment report
    try:
        log_deployment_report.invoke({
            "repo": pipeline,
            "status": "FAILED",
            "summary": f"Execution {state['execution_id']} failed. Diagnosis: {diagnosis}",
        })
    except Exception as e:
        logger.warning(f"⚠️ Deployment report logging failed: {e}")

    return {}


# ── Graph Builder ────────────────────────────────────────────────────────────

def build_ops_graph():
    """Build and compile the Ops Manager deterministic State Machine."""
    builder = StateGraph(OpsState)

    # Nodes
    builder.add_node("extract_event", extract_event)
    builder.add_node("handle_success", handle_success)
    builder.add_node("log_success", log_success)
    builder.add_node("analyze_failure", analyze_failure)
    builder.add_node("notify_failure", notify_failure)
    builder.add_node("close_loop", close_loop)

    # Entry
    builder.set_entry_point("extract_event")

    # Conditional routing
    builder.add_conditional_edges(
        "extract_event",
        route_status,
        {
            "succeeded": "handle_success",
            "failed": "analyze_failure",
            "end": END,
        },
    )

    # Success path
    builder.add_edge("handle_success", "log_success")
    builder.add_edge("log_success", END)

    # Failure path
    builder.add_edge("analyze_failure", "notify_failure")
    builder.add_edge("notify_failure", "close_loop")
    builder.add_edge("close_loop", END)

    return builder.compile()
