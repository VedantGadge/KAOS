from langchain_core.tools import tool
from shared.logger import event_logger, logger
from config.settings import settings
import requests
import re

@tool
def get_bug_timeline(service_name: str) -> str:
    """
    Get the full lifecycle history of bugs and events for a specific service.
    """
    logger.info(f"🤖 Chatbot: Fetching timeline for {service_name}...")
    try:
        timeline = event_logger.get_bug_timeline(service_name)
        if not timeline:
            return f"No events found for service '{service_name}'."
        
        formatted = f"Timeline for {service_name}:\n"
        seen_events = set()
        
        for event in timeline:
            timestamp = event.get('timestamp', '').replace('T', ' ').split('.')[0]
            event_type = event['event_type']
            actor = event.get('actor', 'Unknown')
            details = event.get('details', {})
            
            event_sig = f"{event_type}-{actor}-{timestamp}"
            if event_sig in seen_events:
                continue
            seen_events.add(event_sig)

            if event_type == "NOTION_TICKET_CREATED":
                formatted += f"- [{timestamp}] 🐛 A bug '{details.get('title', 'Unknown')}' was reported in Notion by {actor}.\n"
            elif event_type == "JIRA_TICKET_CREATED":
                assignee = details.get("assignee")
                if assignee:
                    formatted += f"- [{timestamp}] 🎫 Jira ticket created and assigned to **{assignee}**.\n"
                else:
                    formatted += f"- [{timestamp}] 🎫 Jira ticket created for tracking.\n"
            elif event_type == "PR_OPENED":
                formatted += f"- [{timestamp}] 🔄 **{actor}** opened a Pull Request to fix the issue.\n"
            elif event_type == "REVIEW_NEEDED":
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
                formatted += f"- [{timestamp}] ℹ️  {event_type} by {actor}\n"
            
        return formatted
    except Exception as e:
        return f"Error fetching timeline: {str(e)}"

@tool
def search_events(keyword: str) -> str:
    """
    Search for events containing a specific keyword or error message.
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

@tool
def get_bug_solution_details(service_name: str) -> str:
    """
    Get the technical details of HOW a bug was solved.
    Fetches the PR description, changed files, and Jira resolution comments.
    """
    logger.info(f"🤖 Chatbot: Fetching solution details for {service_name}...")
    
    response_parts = []
    
    try:
        timeline = event_logger.get_bug_timeline(service_name)
        if not timeline:
            return f"No event history found for {service_name}. Cannot determine solution."
            
        pr_id = None
        repo_name = service_name
        
        for event in reversed(timeline):
             details_str = str(event.get('details', {}))
             match = re.search(r"PR\s?#?(\d+)", details_str, re.IGNORECASE)
             if match:
                 pr_id = match.group(1)
                 break
        
        if not pr_id:
            response_parts.append(f"⚠️ Could not identify a specific PR number from the timeline for {service_name}.")
        else:
            response_parts.append(f"🔍 Identified PR #{pr_id} as the likely solution.")
            
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
                        
                        r_files = requests.get(f"{gh_url}/files", headers=gh_headers)
                        if r_files.status_code == 200:
                            files = r_files.json()
                            file_list = [f.get('filename') for f in files[:5]]
                            response_parts.append(f"\nChanged Files: {', '.join(file_list)}")
                            
                            if files:
                                first_file = files[0]
                                if 'patch' in first_file:
                                    response_parts.append(f"\n**Diff for {first_file['filename']}:**")
                                    response_parts.append("```diff")
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

    if not settings.GITHUB_TOKEN or not settings.JIRA_API_TOKEN or "No event history" in response_parts[0]:
        response_parts.append("\n⚠️ **Simulation Mode Active** (Real data unavailable)")
        response_parts.append(f"Here is a simulated solution for {service_name}:")
        
        response_parts.append(f"\nmagnifying_glass_tilted_left Identified PR #102 as the solution.")
        response_parts.append(f"\n📂 **PR Details (MERGED)**")
        response_parts.append(f"Title: Fix NullPointerException in {service_name} validation logic")
        response_parts.append("Description:\nThis PR adds a null check to the input payload before processing. \nIt also adds a unit test to cover this edge case.")
        
        response_parts.append(f"\nChanged Files: {service_name.lower()}/processor.py, tests/test_processor.py")
        
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
        
        response_parts.append(f"\n📋 **Jira Ticket (KAOS-102)**")
        response_parts.append("Status: Done")
        response_parts.append("\nRecent Comments:")
        response_parts.append("- Dev: Fixed the issue and added tests. Ready for review.")
        response_parts.append("- Reviewer: Looks good. Approved.")

    return "\n".join(response_parts)
