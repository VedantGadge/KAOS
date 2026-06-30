"""
Triager Agent — LangGraph State Machine (Zero LLM)

A fully deterministic StateGraph that replaces the procedural if/elif
consumer logic. Every node is pure Python calling existing tools via .invoke().

Flow:
  START → extract_details → resolve_assignee → check_recurring
    ├─ recurring  → handle_recurring → END
    └─ new        → create_ticket → add_to_notion → send_slack → log_event → END
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from shared.tools import (
    find_service_owner,
    create_jira_ticket,
    add_to_notion_dashboard,
    send_slack_message,
    update_jira_status,
    update_notion_status
)
from shared.logger import event_logger, logger


# ─────────────────────────────────────────────
# State Schema
# ─────────────────────────────────────────────

class TriagerState(TypedDict):
    # Input (from Kafka message)
    message: dict

    # Extracted fields
    service: str
    error: str
    severity: str
    suggested_assignee: Optional[str]

    # Resolved by graph nodes
    owner_info: str
    assignee_name: str
    slack_id: str
    is_recurring: bool
    active_issue_key: Optional[str]

    # Outputs from tool calls
    ticket_result: str
    notion_url: str
    slack_result: str


# ─────────────────────────────────────────────
# Node Functions (all deterministic, zero LLM)
# ─────────────────────────────────────────────

def extract_details(state: TriagerState) -> dict:
    """Pull fields from the raw Kafka message dict."""
    message = state["message"]

    service = message.get("service_name", "Unknown")
    error = message.get("error_message", "No traceback provided")
    severity = message.get("severity", "MEDIUM")
    suggested_assignee = message.get("suggested_assignee")

    logger.info(f"🕵️ Triager analysing event: {message.get('event_id')}")

    return {
        "service": service,
        "error": error,
        "severity": severity,
        "suggested_assignee": suggested_assignee,
    }


def resolve_assignee(state: TriagerState) -> dict:
    """
    Determine who to assign the bug to.
    If a suggested_assignee is provided (closed-loop case from Ops Manager),
    use it directly. Otherwise, query Neo4j via find_service_owner.
    """
    suggested = state.get("suggested_assignee")
    service = state["service"]

    if suggested:
        logger.info(f"🔄 Closed-Loop: Using suggested assignee: {suggested}")
        owner_info = f"Owner: {suggested} (Suggested) | Slack: @{suggested}"
    else:
        logger.info(f"   🔍 Finding owner for {service}...")
        try:
            owner_info = find_service_owner.invoke({"service_name": service})
            logger.info(f"   👤 Owner Found: {owner_info}")
        except Exception as e:
            owner_info = "Unknown Team"
            logger.warning(f"   ⚠️ Neo4j Lookup Failed: {e}")

    # Extract assignee name from the owner_info string
    assignee_name = "Unknown"
    try:
        if "Owner:" in owner_info:
            assignee_name = owner_info.split("Owner:")[1].split("(")[0].strip()
        elif "Contributor:" in owner_info:
            assignee_name = owner_info.split("Contributor:")[1].split("(")[0].strip()
        elif "Manager:" in owner_info:
            assignee_name = owner_info.split("Manager:")[1].split("(")[0].strip()
    except Exception as e:
        logger.warning(f"   ⚠️ Assignee Extraction Failed: {e}")

    logger.info(f"   🕵️ Extracted Assignee: '{assignee_name}' from '{owner_info}'")

    # Extract Slack ID
    slack_id = "#all-kaos"
    if owner_info and "Slack:" in owner_info:
        slack_id = owner_info.split("Slack:")[1].split("|")[0].strip()

    return {
        "owner_info": owner_info,
        "assignee_name": assignee_name,
        "slack_id": slack_id,
    }


def check_recurring(state: TriagerState) -> dict:
    """
    Query the local SQLite store to see if an active Jira ticket
    already exists for this service. Sets the is_recurring flag.
    """
    service = state["service"]
    active_issue_key = event_logger.get_active_jira_ticket(service=service)

    if active_issue_key:
        logger.info(
            f"♻️  Recurring Issue: Found active ticket {active_issue_key}. "
            "Updating instead of creating new."
        )

    return {
        "is_recurring": bool(active_issue_key),
        "active_issue_key": active_issue_key,
    }


def handle_recurring(state: TriagerState) -> dict:
    """
    Update the existing Jira ticket and Notion entry for a recurring issue
    instead of creating duplicates.
    """
    service = state["service"]
    error = state["error"]

    # Update Jira
    try:
        update_res = update_jira_status.invoke({
            "summary": service,
            "comment": f"⚠️ Recurring Incident/Deployment Failure: {error}",
            "status": "In Progress",
        })
        logger.info(f"   ✅ Updated Existing Jira: {update_res}")
    except Exception as e:
        logger.error(f"   ❌ Failed to update Jira: {e}")

    # Update Notion
    try:
        notion_res = update_notion_status.invoke({
            "title": service,
            "new_status": "Needs attention",
        })
        logger.info(f"   ✅ Updated Existing Notion: {notion_res}")
    except Exception as e:
        logger.error(f"   ❌ Failed to update Notion: {e}")

    return {}


def create_ticket(state: TriagerState) -> dict:
    """Create a new Jira ticket for a fresh bug report."""
    service = state["service"]
    error = state["error"]
    severity = state["severity"]
    assignee_name = state["assignee_name"]
    owner_info = state["owner_info"]

    logger.info("   🎫 Creating Jira Ticket...")
    try:
        ticket_result = create_jira_ticket.invoke({
            "summary": f"[{service}] {error[:50]}...",
            "description": (
                f"Automated Report:\nService: {service}\n"
                f"Severity: {severity}\nError: {error}\nOwner: {owner_info}"
            ),
            "severity": severity,
            "service_name": service,
            "assignee": assignee_name,
        })
        logger.info(f"   ✅ Ticket: {ticket_result}")
    except Exception as e:
        ticket_result = f"Failed to create ticket: {e}"
        logger.error(f"   ❌ Jira Create Failed: {e}")

    return {"ticket_result": ticket_result}


def add_to_notion(state: TriagerState) -> dict:
    """Add the bug to the Notion dashboard."""
    service = state["service"]
    error = state["error"]
    severity = state["severity"]
    assignee_name = state["assignee_name"]
    owner_info = state["owner_info"]

    logger.info("   📋 Adding to Notion...")
    try:
        notion_result = add_to_notion_dashboard.invoke({
            "title": f"[{service}] {error[:50]}...",
            "assignee": assignee_name,
            "service_name": service,
            "severity": severity,
            "description": f"Error: {error}\nOwner Info: {owner_info}",
        })
        notion_url = (
            str(notion_result).split(": ")[-1]
            if ": " in str(notion_result)
            else "http://notion.so/unknown"
        )
        logger.info(f"   ✅ Notion: {notion_result}")
    except Exception as e:
        notion_url = "http://notion.so/failed"
        logger.error(f"   ❌ Notion Add Failed: {e}")

    return {"notion_url": notion_url}


def send_slack(state: TriagerState) -> dict:
    """Send Slack notification to the assignee and announce in #all-kaos."""
    service = state["service"]
    error = state["error"]
    severity = state["severity"]
    assignee_name = state["assignee_name"]
    slack_id = state["slack_id"]
    notion_url = state.get("notion_url", "http://notion.so/unknown")

    logger.info("   📨 Sending Slack Message...")
    try:
        slack_result = send_slack_message.invoke({
            "channel": slack_id,
            "bug_title": f"[{service}] {error[:50]}...",
            "assignee": assignee_name,
            "service_name": service,
            "severity": severity,
            "notion_url": notion_url,
        })
        logger.info(f"   ✅ Slack: {slack_result}")
    except Exception as e:
        slack_result = f"Slack Send Failed: {e}"
        logger.error(f"   ❌ Slack Send Failed: {e}")

    return {"slack_result": slack_result}


def log_event(state: TriagerState) -> dict:
    """Record a TICKET_CREATED event to the event store with embeddings."""
    event_logger.log_event(
        event_type="TICKET_CREATED",
        actor="Agent-Triager",
        repo=state["service"],
        details={
            "ticket": state.get("ticket_result", ""),
            "notion_url": state.get("notion_url", ""),
            "error": state["error"],
            "owner": state.get("owner_info", ""),
            "severity": state["severity"],
        },
    )
    return {}


# ─────────────────────────────────────────────
# Conditional Edge
# ─────────────────────────────────────────────

def route_after_recurring_check(state: TriagerState) -> str:
    """Route to the recurring-update path or the new-ticket path."""
    if state.get("is_recurring"):
        return "handle_recurring"
    return "create_ticket"


# ─────────────────────────────────────────────
# Graph Builder
# ─────────────────────────────────────────────

def build_triager_graph():
    """
    Assemble the Triager StateGraph, wire all nodes and edges,
    compile, and return the runnable graph.
    """
    graph = StateGraph(TriagerState)

    # Register nodes
    graph.add_node("extract_details", extract_details)
    graph.add_node("resolve_assignee", resolve_assignee)
    graph.add_node("check_recurring", check_recurring)
    graph.add_node("handle_recurring", handle_recurring)
    graph.add_node("create_ticket", create_ticket)
    graph.add_node("add_to_notion", add_to_notion)
    graph.add_node("send_slack", send_slack)
    graph.add_node("log_event", log_event)

    # Entry point
    graph.set_entry_point("extract_details")

    # Linear edges
    graph.add_edge("extract_details", "resolve_assignee")
    graph.add_edge("resolve_assignee", "check_recurring")

    # Conditional branch: recurring vs new
    graph.add_conditional_edges(
        "check_recurring",
        route_after_recurring_check,
        {
            "handle_recurring": "handle_recurring",
            "create_ticket": "create_ticket",
        },
    )

    # Recurring path → END
    graph.add_edge("handle_recurring", END)

    # New ticket path → sequential pipeline
    graph.add_edge("create_ticket", "add_to_notion")
    graph.add_edge("add_to_notion", "send_slack")
    graph.add_edge("send_slack", "log_event")
    graph.add_edge("log_event", END)

    return graph.compile()
