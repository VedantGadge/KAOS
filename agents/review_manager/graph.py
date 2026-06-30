from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from shared.tools import (
    find_reviewer,
    get_user_slack_id,
    send_slack_dm,
    update_jira_status,
    update_notion_status
)
from shared.logger import event_logger, logger

class ReviewState(TypedDict):
    event_type: str
    repo: str
    pr_id: str
    author: str
    decision: Optional[str]
    comment: Optional[str]
    reviewer: Optional[str]
    related_bug: Optional[str]
    
    # Internal variables populated during graph execution
    reviewer_info: Optional[str]
    author_slack_id: Optional[str]

def extract_pr_details(state: ReviewState) -> dict:
    """Pull fields from the raw Kafka message."""
    message = state.get("message", {})
    
    return {
        "event_type": message.get("event"),
        "repo": message.get("repo"),
        "pr_id": str(message.get("pr_id")),
        "author": message.get("author") or message.get("pr_author"),
        "decision": message.get("decision", "COMMENT"),
        "comment": message.get("comment", ""),
        "reviewer": message.get("reviewer", "Reviewer"),
        "related_bug": message.get("related_bug_title", "")
    }

def route_event(state: ReviewState) -> str:
    """Route to the correct flow based on the event type."""
    evt = state.get("event_type")
    if evt in ["PR_OPENED", "PR_SYNCHRONIZE", "PR_REOPENED"]:
        return "review_needed"
    elif evt == "REVIEW_SUBMITTED":
        return "decision_submitted"
    elif evt == "PR_MERGED":
        return "pr_merged"
    return "end"

# ==========================================
# FLOW A: REVIEW NEEDED (PR OPENED)
# ==========================================
def assign_reviewer(state: ReviewState) -> dict:
    """Find a reviewer using Neo4j and log the assignment."""
    repo = state["repo"]
    author = state["author"]
    pr_id = state["pr_id"]
    
    logger.info(f"   ⚖️  Needs Reviewer for PR #{pr_id} in {repo}...")
    try:
        reviewer_info = find_reviewer.invoke({
            "service_name": repo, 
            "pr_author": author,
            "pr_id": int(pr_id)
        })
        logger.info(f"   👤 Suggested Reviewer: {reviewer_info}")
    except Exception as e:
        logger.warning(f"   ⚠️ Reviewer Lookup Failed: {e}")
        reviewer_info = "Not Assigned"
        
    event_logger.log_event(
        event_type="REVIEW_NEEDED", 
        actor="Agent-ReviewManager", 
        repo=repo, 
        pr_id=pr_id, 
        details={"status": "Scanning for Reviewers", "suggestion": reviewer_info, "pr_author": author}
    )
    
    return {"reviewer_info": reviewer_info}

def notify_review_needed(state: ReviewState) -> dict:
    """Send Slack DMs to the assigned reviewer and #all-kaos."""
    repo = state["repo"]
    author = state["author"]
    pr_id = state["pr_id"]
    reviewer_info = state.get("reviewer_info", "")
    
    slack_id = "#all-kaos"
    if "Slack:" in reviewer_info:
        slack_id = reviewer_info.split("Slack:")[1].split("|")[0].strip()
    
    try:
        send_slack_dm.invoke({
            "channel": slack_id,
            "text": f"👀 PR #{pr_id} in {repo} needs your review. Author: {author}\n🔗 Link: https://github.com/kaos-org/{repo}/pull/{pr_id}"
        })
        
        send_slack_dm.invoke({
            "channel": "#all-kaos",
            "text": f"📋 **PR Opened**: {author} opened PR #{pr_id} in {repo}. Reviewer: {reviewer_info.split('|')[0].replace('Reviewer:', '').strip()}"
        })
    except Exception as e:
        logger.warning(f"⚠️ Failed to send Slack notification for PR Open: {e}")
        
    return {}

def update_tickets_review(state: ReviewState) -> dict:
    """Update Jira and Notion to reflect the 'To be reviewed' status."""
    repo = state["repo"]
    author = state["author"]
    pr_id = state["pr_id"]
    reviewer_info = state.get("reviewer_info", "")
    related_bug = state.get("related_bug", "")
    
    target_ticket = related_bug if related_bug else repo
    
    try:
        update_notion_status.invoke({
            "title": target_ticket,
            "new_status": "To be reviewed"
        })

        update_jira_status.invoke({
            "summary": target_ticket,
            "comment": f"PR #{pr_id} opened by {author}. Reviewer assigned: {reviewer_info}",
            "service_name": repo,
            "status": "In Progress"
        })
    except Exception as e:
         logger.warning(f"⚠️ Failed to update tickets for PR Open: {e}")
         
    return {}

# ==========================================
# FLOW B: DECISION SUBMITTED
# ==========================================
def process_decision(state: ReviewState) -> dict:
    """Log the review decision and find the PR author's Slack ID."""
    repo = state["repo"]
    pr_id = state["pr_id"]
    author = state["author"]
    decision = state["decision"]
    comment = state["comment"]
    reviewer = state["reviewer"]
    
    logger.info(f"   📝 Decision: {decision} on PR #{pr_id} by {reviewer}")
    
    event_logger.log_event(
        event_type="REVIEW_SUBMITTED",
        actor=reviewer,
        repo=repo,
        pr_id=pr_id,
        details={
            "decision": decision, 
            "comment": comment, 
            "pr_author": author,
            "reviewer": reviewer
        }
    )
    
    author_slack = ""
    try:
        author_slack = get_user_slack_id.invoke({"name": author})
    except Exception as e:
        logger.warning(f"⚠️ Failed to lookup author slack ID: {e}")
        
    return {"author_slack_id": author_slack}

def route_decision(state: ReviewState) -> str:
    """Route based on whether the PR was approved or rejected."""
    decision = state.get("decision", "")
    if decision == "CHANGES_REQUESTED":
        return "changes_requested"
    elif decision == "APPROVED":
        return "approved"
    return "end"

def handle_rejection(state: ReviewState) -> dict:
    """Notify about rejection and update tickets."""
    repo = state["repo"]
    pr_id = state["pr_id"]
    author = state["author"]
    reviewer = state["reviewer"]
    comment = state["comment"]
    author_slack = state.get("author_slack_id")
    related_bug = state.get("related_bug", "")
    
    target_ticket = related_bug if related_bug else repo
    
    try:
        if author_slack:
            send_slack_dm.invoke({
                "channel": author_slack, 
                "text": f"❌ PR #{pr_id} Rejected by {reviewer}. Please address comments: {comment}"
            })
            mention = f"<@{author_slack}>"
        else:
            mention = author
            
        send_slack_dm.invoke({"channel": "#all-kaos", "text": f"❌ PR #{pr_id} Rejected. {mention} please fix: {comment}"})
        
        update_notion_status.invoke({"title": target_ticket, "new_status": "Needs attention"})
        update_jira_status.invoke({
            "summary": target_ticket, 
            "comment": f"PR Rejected: {comment} \nStatus -> Needs Attention",
            "service_name": repo,
            "status": "In Progress"
        })
    except Exception as e:
         logger.warning(f"⚠️ Failed to process rejection: {e}")
         
    return {}

def handle_approval(state: ReviewState) -> dict:
    """Notify about approval and add a comment to Jira."""
    repo = state["repo"]
    pr_id = state["pr_id"]
    author = state["author"]
    reviewer = state["reviewer"]
    author_slack = state.get("author_slack_id")
    related_bug = state.get("related_bug", "")
    
    target_ticket = related_bug if related_bug else repo
    
    try:
        if author_slack:
            send_slack_dm.invoke({"channel": author_slack, "text": f"✅ Your PR #{pr_id} was Approved! Great work."})
            if author_slack.startswith("#"):
                 mention = author_slack
            else:
                mention = f"<@{author_slack}>"
        else:
            mention = author

        send_slack_dm.invoke({"channel": "#all-kaos", "text": f"✅ PR #{pr_id} Approved. {mention}, it's ready to merge."})
        
        update_jira_status.invoke({
            "summary": target_ticket, 
            "comment": f"PR Approved by {reviewer}. Ready for Merge.",
            "service_name": repo
        })
    except Exception as e:
         logger.warning(f"⚠️ Failed to process approval: {e}")
         
    return {}

# ==========================================
# FLOW C: PR MERGED
# ==========================================
def handle_merge(state: ReviewState) -> dict:
    """Log the merge and update Notion/Jira for deployment."""
    repo = state["repo"]
    pr_id = state["pr_id"]
    related_bug = state.get("related_bug", "")
    target_ticket = related_bug if related_bug else repo
    
    logger.info("   🎉 PR Merged! Deploying...")
    
    try:
        event_logger.log_event(
            event_type="PR_MERGED_LOG",
            actor="Agent-ReviewManager",
            repo=repo,
            pr_id=pr_id,
            details={"action": "deploying"}
        )
        
        update_notion_status.invoke({"title": target_ticket, "new_status": "Deploying"})
        
        update_jira_status.invoke({
            "summary": target_ticket,
            "comment": f"PR Merged. Deploying to Production...",
            "service_name": repo,
            "status": "In Progress"
        })
    except Exception as e:
         logger.warning(f"⚠️ Failed to process merge: {e}")
         
    return {}

def build_review_graph() -> StateGraph:
    """Build and compile the Review Manager deterministic State Machine."""
    builder = StateGraph(ReviewState)

    # Add Nodes
    builder.add_node("extract_pr_details", extract_pr_details)
    
    # Review Needed Flow
    builder.add_node("assign_reviewer", assign_reviewer)
    builder.add_node("notify_review_needed", notify_review_needed)
    builder.add_node("update_tickets_review", update_tickets_review)
    
    # Decision Flow
    builder.add_node("process_decision", process_decision)
    builder.add_node("handle_rejection", handle_rejection)
    builder.add_node("handle_approval", handle_approval)
    
    # Merge Flow
    builder.add_node("handle_merge", handle_merge)

    # Set Entry
    builder.set_entry_point("extract_pr_details")

    # Edges - Main Routing
    builder.add_conditional_edges(
        "extract_pr_details",
        route_event,
        {
            "review_needed": "assign_reviewer",
            "decision_submitted": "process_decision",
            "pr_merged": "handle_merge",
            "end": END
        }
    )

    # Edges - Review Needed Flow
    builder.add_edge("assign_reviewer", "notify_review_needed")
    builder.add_edge("notify_review_needed", "update_tickets_review")
    builder.add_edge("update_tickets_review", END)

    # Edges - Decision Flow
    builder.add_conditional_edges(
        "process_decision",
        route_decision,
        {
            "changes_requested": "handle_rejection",
            "approved": "handle_approval",
            "end": END
        }
    )
    builder.add_edge("handle_rejection", END)
    builder.add_edge("handle_approval", END)

    # Edges - Merge Flow
    builder.add_edge("handle_merge", END)

    return builder.compile()
