from langchain_core.tools import tool
from shared.logger import event_logger, logger
from shared.neo4j.client import Neo4jClient
from config.settings import settings
import json
import requests
from typing import Optional, Dict, Any

# ─────────────────────────────────────────────
# Tool 1: Get Bug Timeline
# ─────────────────────────────────────────────
@tool
def get_bug_timeline(service_name: str) -> str:
    """
    Get the full lifecycle history of bugs and events for a specific service.
    Use this when the user asks "What happened with X?" or "Show me the history of X".
    Args:
        service_name: The name of the service or repository (e.g. "PaymentService").
    """
    logger.info(f"🤖 Chatbot: Fetching timeline for {service_name}...")
    try:
        timeline = event_logger.get_bug_timeline(service_name)
        if not timeline:
            return f"No events found for service '{service_name}'."
        
        # Format the timeline for the LLM to digest
        formatted = f"Timeline for {service_name}:\n"
        
        # Narrative Logic
        seen_events = set()
        
        for event in timeline:
            timestamp = event.get('timestamp', '').replace('T', ' ').split('.')[0]
            event_type = event['event_type']
            actor = event.get('actor', 'Unknown')
            details = event.get('details', {})
            
            # Skip duplicates if any
            event_sig = f"{event_type}-{actor}-{timestamp}"
            if event_sig in seen_events:
                continue
            seen_events.add(event_sig)

            # --- Story Builder ---
            if event_type == "NOTION_TICKET_CREATED":
                formatted += f"- [{timestamp}] 🐛 A bug '{details.get('title', 'Unknown')}' was reported in Notion by {actor}.\n"
            
            elif event_type == "JIRA_TICKET_CREATED":
                assignee = details.get("assignee")
                if assignee:
                    formatted += f"- [{timestamp}] 🎫 Jira ticket created and assigned to **{assignee}**.\n"
                else:
                    formatted += f"- [{timestamp}] 🎫 Jira ticket created for tracking.\n"

            elif event_type == "PR_OPENED":
                # Real GitHub event usually has the author
                formatted += f"- [{timestamp}] 🔄 **{actor}** opened a Pull Request to fix the issue.\n"

            elif event_type == "REVIEW_NEEDED":
                 # If we have pr_author in details, use it
                 pr_author = details.get("pr_author")
                 if pr_author:
                     formatted += f"- [{timestamp}] 🔄 **{pr_author}** opened a Pull Request to fix the issue.\n"
                 else:
                     formatted += f"- [{timestamp}] 🔄 A Pull Request was opened to fix the issue.\n"

            elif event_type == "REVIEW_ASSIGNED":
                reviewer = details.get("reviewer", "someone")
                pr_author = details.get("pr_author")
                if pr_author:
                     formatted += f"- [{timestamp}] 👤 **{reviewer}** was assigned to review **{pr_author}'s** PR.\n"
                else:
                     formatted += f"- [{timestamp}] 👤 **{reviewer}** was assigned to review the PR.\n"

            elif event_type == "REVIEW_SUBMITTED":
                decision = details.get("decision", "COMMENTED")
                comment = details.get("comment", "")
                reviewer_actor = details.get("reviewer", actor)
                
                if decision == "CHANGES_REQUESTED":
                    formatted += f"- [{timestamp}] ❌ **{reviewer_actor}** requested changes: '{comment}'\n"
                elif decision == "APPROVED":
                    formatted += f"- [{timestamp}] ✅ **{reviewer_actor}** approved the PR.\n"
                else:
                    formatted += f"- [{timestamp}] 💬 **{reviewer_actor}** commented: '{comment}'\n"

            elif event_type == "PR_MERGED":
                formatted += f"- [{timestamp}] 🔀 The PR was merged into the main branch.\n"

            elif event_type == "DEPLOYMENT_REPORT":
                status = details.get("status", "UNKNOWN")
                if status == "FAILED":
                    formatted += f"- [{timestamp}] 💥 Deployment to production failed. OpsManager is investigating.\n"
                elif status == "SUCCEEDED":
                    formatted += f"- [{timestamp}] 🚀 Deployment to production succeeded! The fix is live.\n"
                else:
                     formatted += f"- [{timestamp}] 🚀 Deployment Status: {status}.\n"

            else:
                # Fallback for unknown events
                formatted += f"- [{timestamp}] ℹ️  {event_type} by {actor}\n"
            
        return formatted
    except Exception as e:
        return f"Error fetching timeline: {str(e)}"

# ─────────────────────────────────────────────
# Tool 2: Search Events (Keyword)
# ─────────────────────────────────────────────
@tool
def search_events(keyword: str) -> str:
    """
    Search for events containing a specific keyword or error message.
    Use this when the user asks general questions like "Have we seen any NPEs?" or "Search for 'timeout'".
    Args:
        keyword: The search term.
    """
    logger.info(f"🤖 Chatbot: Searching for '{keyword}'...")
    try:
        results = event_logger.search_events(keyword)
        if not results:
            return f"No events found matching '{keyword}'."
        
        formatted = f"Search results for '{keyword}':\n"
        for event in results:
            timestamp = event['timestamp']
            service = event['service']
            details = event['details']
            
            summary = f"- [{timestamp}] {service}: "
            if "title" in details:
                summary += details['title']
            elif "message" in details:
                summary += details['message']
            elif "comment" in details:
                summary += details['comment']
            else:
                summary += str(details)[:50]
            
            formatted += summary + "\n"
            
        return formatted
    except Exception as e:
        return f"Error searching events: {str(e)}"

# ─────────────────────────────────────────────
# Tool 3: Find Team Info (Neo4j)
# ─────────────────────────────────────────────
@tool
def find_team_info(service_name: str) -> str:
    """
    Find out who owns a service, who works on it, and who manages it.
    Use this for questions like "Who owns PaymentService?" or "Who can I talk to about X?".
    Args:
        service_name: The name of the service.
    """
    logger.info(f"🤖 Chatbot: Looking up team info for {service_name}...")
    try:
        neo4j = Neo4jClient()
        normalized_name = service_name.replace("-", "").replace("_", "").lower()
        
        # 1. Owner
        owner_query = """
        MATCH (p:Person)-[:OWNS]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $name
        RETURN p.name as name, p.role as role, p.status as status, p.slack_id as slack_id
        """
        owners = neo4j.query(owner_query, {"name": normalized_name})
        
        # 2. Contributors
        contrib_query = """
        MATCH (p:Person)-[:WORKED_ON]->(s:Service)
        WHERE toLower(replace(replace(s.name, '-', ''), '_', '')) = $name
        RETURN p.name as name
        """
        contributors = neo4j.query(contrib_query, {"name": normalized_name})
        
        neo4j.close()
        
        response = f"Team Info for {service_name}:\n\n"
        
        if owners:
            o = owners[0]
            role_text = f"({o['role']})" if o['role'] else ""
            slack_text = f"(Slack: {o['slack_id']})" if o['slack_id'] else ""
            response += f"👑 **Owner**\n• {o['name']} {role_text}\n• Status: {o['status']}\n• Contact: {o['slack_id'] if o['slack_id'] else 'N/A'}\n\n"
        else:
            response += "👑 **Owner**\n• Unknown\n\n"
            
        if contributors:
            names = ", ".join([c['name'] for c in contributors])
            response += f"🛠️ **Contributors**\n• {names}\n"
        else:
            response += "🛠️ **Contributors**\n• None found\n"
            
        return response

    except Exception as e:
        return f"Error querying Neo4j: {str(e)}"

# ─────────────────────────────────────────────
# Tool 4: Get Jira Status
# ─────────────────────────────────────────────
@tool
def get_jira_status(service_name: str) -> str:
    """
    Get the current active Jira ticket status for a service.
    Use this when asked "What is the status of the ticket for X?".
    Args:
        service_name: The name of the service.
    """
    logger.info(f"🤖 Chatbot: Checking Jira status for {service_name}...")
    try:
        # Use our existing logger to find the linked ticket
        issue_key = event_logger.get_active_jira_ticket(service=service_name)
        if not issue_key:
            return f"No active Jira ticket found for {service_name}."
            
        # Fetch real-time status from Jira
        from jira import JIRA
        jira = JIRA(
            server=settings.JIRA_URL,
            basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
        )
        issue = jira.issue(issue_key)
        
        return f"Jira Ticket {issue_key}:\n- Status: {issue.fields.status.name}\n- Summary: {issue.fields.summary}\n- Assignee: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}\n- Link: {settings.JIRA_URL}/browse/{issue_key}"

    except Exception as e:
        return f"Error checking Jira: {str(e)}"

# ─────────────────────────────────────────────
# Tool 5: Get Bug Solution Details (HOW it was solved)
# ─────────────────────────────────────────────
@tool
def get_bug_solution_details(service_name: str) -> str:
    """
    Get the technical details of HOW a bug was solved.
    Fetches the PR description, changed files, and Jira resolution comments.
    Use this when asked "How was this fixed?" or "What was the solution?".
    Args:
        service_name: The name of the service or repository.
    """
    logger.info(f"🤖 Chatbot: Fetching solution details for {service_name}...")
    
    response_parts = []
    
    # 1. Get Context from Event Logger
    # We need to find the PR ID associated with the latest fix for this service
    try:
        # Assuming the latest "PR Merged" or "PR Closed" event is the solution
        timeline = event_logger.get_bug_timeline(service_name)
        if not timeline:
            return f"No event history found for {service_name}. Cannot determine solution."
            
        # Find the latest PR event
        # Timeline is sorted by timestamp asc, so reverse it
        latest_pr_event = None
        for event in reversed(timeline):
            if event['event_type'] in ["PR_MERGED", "PR_CLOSED", "REVIEW_SUBMITTED"]: 
                # Ideally we want the PR ID. The event logger stores it in 'pr_id' column but get_bug_timeline might hide it in details
                # Let's check if we can get it. The `get_bug_timeline` returns a list of Dicts.
                # Inspecting `get_bug_timeline` implementation: it returns 'details' which is a dict.
                # However, the `PREvent` model has `pr_id` column. `get_bug_timeline` DOES NOT currently return `pr_id` explicitly in the top level dict, 
                # but it likely puts it in `details` or we might need to query it differently.
                # Let's look at `get_bug_timeline` in `shared/logger.py`:
                # It returns `timestamp`, `event_type`, `actor`, `details`. 
                # It DOES NOT return `pr_id` directly.
                # BUT `get_logs_for_pr` uses `pr_id`.
                # We might need to rely on `details` containing the PR ID or name.
                pass

        # Since `get_bug_timeline` output is limited, let's use a direct query to `event_logger` if possible, 
        # OR we can improve `get_bug_timeline` later. 
        # For now, let's try to extract PR ID from the `details` if it's there, or assume we can't find it without a direct query.
        # Wait, `get_active_jira_ticket` exists. Maybe we can find the PR from the Jira ticket?
        
        # Let's try to find the PR ID by listing recent events for the repo using a new helper or existing pattern.
        # Actually, `get_bug_timeline` uses `PREvent` table. 
        # Let's write a targeted query here or just look at the `details` text?
        # A better approach: The `get_bug_timeline` *does* return what we need if we look closely at `shared/logger.py`.
        # It filters by `repo`.
        # Just use the latest event that *looks* like a PR interaction.
        
        # NOTE: Since I cannot easily modify `shared/logger.py` right now without breaking unrelated things, 
        # I will fetch the timeline and look for PR numbers in the `details` (often "PR #123").
        
        pr_id = None
        repo_name = service_name
        
        for event in reversed(timeline):
             # Try to find "PR #123" in details
             details_str = str(event.get('details', {}))
             # Simple heuristic extraction
             import re
             match = re.search(r"PR\s?#?(\d+)", details_str, re.IGNORECASE)
             if match:
                 pr_id = match.group(1)
                 break
        
        if not pr_id:
            response_parts.append(f"⚠️ Could not identify a specific PR number from the timeline for {service_name}.")
        else:
            response_parts.append(f"🔍 Identified PR #{pr_id} as the likely solution.")
            
            # 2. Fetch GitHub Details
            if settings.GITHUB_TOKEN and settings.GITHUB_OWNER:
                try:
                    gh_headers = {
                        "Authorization": f"token {settings.GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                    gh_url = f"https://api.github.com/repos/{settings.GITHUB_OWNER}/{repo_name}/pulls/{pr_id}"
                    
                    r = requests.get(gh_url, headers=gh_headers)
                    if r.status_code == 200:
                        pr_data = r.json()
                        response_parts.append(f"\n📂 **PR Details ({pr_data.get('state', 'Unknown')})**")
                        response_parts.append(f"Title: {pr_data.get('title')}")
                        body = pr_data.get('body', 'No description provided.')
                        response_parts.append(f"Description:\n{body[:500]}..." if len(body) > 500 else f"Description:\n{body}")
                        
                        # Get Files and Diffs
                        r_files = requests.get(f"{gh_url}/files", headers=gh_headers)
                        if r_files.status_code == 200:
                            files = r_files.json()
                            file_list = [f.get('filename') for f in files[:5]] # Limit to 5
                            response_parts.append(f"\nChanged Files: {', '.join(file_list)}")
                            
                            # Show diff for the first file
                            if files:
                                first_file = files[0]
                                if 'patch' in first_file:
                                    response_parts.append(f"\n**Diff for {first_file['filename']}:**")
                                    response_parts.append("```diff")
                                    # Limit diff size
                                    patch = first_file['patch']
                                    response_parts.append(patch[:1000] + ("\n..." if len(patch) > 1000 else ""))
                                    response_parts.append("```")
                            
                            if len(files) > 5:
                                response_parts.append(f"(and {len(files)-5} more files)")
                    else:
                        response_parts.append(f"❌ Failed to fetch PR details from GitHub (Status: {r.status_code})")
                except Exception as gh_e:
                    response_parts.append(f"❌ Error fetching from GitHub: {str(gh_e)}")
            else:
                response_parts.append("⚠️ GitHub integration not configured (missing GITHUB_TOKEN or GITHUB_OWNER).")

    except Exception as e:
        response_parts.append(f"Error processing PR timeline: {str(e)}")

    # 3. Fetch Jira Resolution
    try:
        issue_key = event_logger.get_active_jira_ticket(service=service_name)
        if issue_key and settings.JIRA_URL and settings.JIRA_API_TOKEN:
            from jira import JIRA
            jira = JIRA(
                server=settings.JIRA_URL,
                basic_auth=(settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)
            )
            issue = jira.issue(issue_key)
            
            response_parts.append(f"\n📋 **Jira Ticket ({issue_key})**")
            response_parts.append(f"Status: {issue.fields.status.name}")
            
            # Fetch last 3 comments
            comments = issue.fields.comment.comments
            if comments:
                response_parts.append("\nRecent Comments:")
                for c in comments[-3:]:
                    response_parts.append(f"- {c.author.displayName}: {c.body[:200]}")
            else:
                response_parts.append("No comments found.")
        elif issue_key:
             response_parts.append(f"\nLinked Jira Ticket: {issue_key} (Jira integration not fully configured)")
             
             
    except Exception as je:
        response_parts.append(f"Error fetching Jira details: {str(je)}")

    # ────────────────────────────────────────────────────────────────
    # SIMULATION MODE (Fallback if no external data found)
    # ────────────────────────────────────────────────────────────────
    if not settings.GITHUB_TOKEN or not settings.JIRA_API_TOKEN or "No event history" in response_parts[0]:
        response_parts.append("\n⚠️ **Simulation Mode Active** (Real data unavailable)")
        response_parts.append(f"Here is a simulated solution for {service_name}:")
        
        # Mock PR
        response_parts.append(f"\nmagnifying_glass_tilted_left Identified PR #102 as the solution.")
        response_parts.append(f"\n📂 **PR Details (MERGED)**")
        response_parts.append(f"Title: Fix NullPointerException in {service_name} validation logic")
        response_parts.append("Description:\nThis PR adds a null check to the input payload before processing. \nIt also adds a unit test to cover this edge case.")
        
        # Mock Files
        response_parts.append(f"\nChanged Files: {service_name.lower()}/processor.py, tests/test_processor.py")
        
        # Mock Diff (Simulating context of file diff)
        response_parts.append("\n**Code Change Causing Fix:**")
        response_parts.append("```python")
        response_parts.append("@@ -45,6 +45,9 @@ class PaymentProcessor:")
        response_parts.append("     def validate(self, payload):")
        response_parts.append("+        if payload is None:")
        response_parts.append("+            logger.error('Received null payload')")
        response_parts.append("+            return False")
        response_parts.append("         return self.schema.validate(payload)")
        response_parts.append("         return self.schema.validate(payload)")
        response_parts.append("```")
        response_parts.append(f"\n[View Full File on GitHub](https://github.com/VedantGadge/{service_name}/blob/main/{service_name.lower()}/processor.py)")
        
        # Mock Jira
        response_parts.append(f"\n📋 **Jira Ticket (KAOS-102)**")
        response_parts.append("Status: Done")
        response_parts.append("\nRecent Comments:")
        response_parts.append("- Dev: Fixed the issue and added tests. Ready for review.")
        response_parts.append("- Reviewer: Looks good. Approved.")

    return "\n".join(response_parts)

tools = [get_bug_timeline, search_events, find_team_info, get_jira_status, get_bug_solution_details]
