import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.review_manager.tools import find_reviewer, update_jira_status, update_notion_status, send_slack_dm
from shared.logger import event_logger
import json

class ReviewManagerConsumer(BaseAgentConsumer):
    def __init__(self):
        # Production Group ID
        prod_group = "review-manager-prod-group"
        print(f"🔧 Production Mode: Using stable group {prod_group} (v2 - Listening to Decisions)")
        
        super().__init__(
            group_id=prod_group,
            topics=["dev.pr.updates", "dev.pr.decisions"]
        )

    def process_message(self, message: dict):
        """
        Handle 'dev.pr.updates' events (GitHub Webhooks).
        """
        event_type = message.get("event")
        repo = message.get("repo")
        pr_id = message.get("pr_id")
        author = message.get("author")
        
        print(f"👀 ReviewManager received: {event_type} for PR #{pr_id} ({repo})")

        # Logic for PR_OPENED (Review Needed)
        if event_type in ["PR_OPENED", "PR_SYNCHRONIZE", "PR_REOPENED"]:
            print(f"   ⚖️  Needs Reviewer...")
            try:
                # 1. Find Reviewer
                reviewer_info = find_reviewer.invoke({"service_name": repo, "pr_author": author})
                print(f"   👤 Suggested Reviewer: {reviewer_info}")
                
                # 2. Notify Reviewer via Slack (Mocking extracted ID)
                slack_id = "#all-kaos"
                if "Slack:" in reviewer_info:
                    slack_id = reviewer_info.split("Slack:")[1].split("|")[0].strip()
                
                send_slack_dm.invoke({
                    "channel": slack_id,
                    "text": f"👀 PR #{pr_id} in {repo} needs your review. Author: {author}"
                })
                
                # 3. Update Jira (if linked)
                # We assume the PR title/body contains the bug summary or ID.
                # For this test, we accept a "related_bug_summary" field in the event or guess it.
                related_bug_summary = message.get("title", "")
                if related_bug_summary:
                    update_jira_status.invoke({
                        "summary": related_bug_summary,
                        "comment": f"PR #{pr_id} opened by {author}. Reviewer assigned: {reviewer_info}"
                    })

            except Exception as e:
                print(f"   ⚠️ Reviewer Lookup/Notify Failed: {e}")

            # Log
            event_logger.log_event(event_type="REVIEW_NEEDED", actor="Agent-ReviewManager", repo=repo, pr_id=str(pr_id), details={"status": "Scanning for Reviewers", "suggestion": reviewer_info})

        # Logic for REVIEW DECISIONS
        elif event_type == "REVIEW_SUBMITTED":
            decision = message.get("decision", "COMMENT")
            comment = message.get("comment", "")
            related_bug = message.get("related_bug_title", "")
            pr_author = message.get("pr_author") # New field
            
            print(f"   📝 Decision: {decision}")
            
            # Find Author's Slack ID
            author_slack = ""
            if pr_author:
                try:
                    from shared.neo4j.client import Neo4jClient
                    neo4j = Neo4jClient()
                    res = neo4j.query("MATCH (p:Person {name: $name}) RETURN p.slack_id as slack_id", {"name": pr_author})
                    neo4j.close()
                    if res:
                        author_slack = res[0]['slack_id']
                except Exception as e:
                    print(f"   ⚠️ Could not find Slack ID for author {pr_author}: {e}")

            if decision == "CHANGES_REQUESTED":
                # Notify Author (DM)
                if author_slack:
                    send_slack_dm.invoke({"channel": author_slack, "text": f"❌ Your PR #{pr_id} was Rejected. Please fix: {comment}"})

                # Notify Team (Public)
                send_slack_dm.invoke({"channel": "#all-kaos", "text": f"❌ PR #{pr_id} Rejected. @{author_slack or pr_author} please fix: {comment}"})
                
                # Update Notion & Jira
                if related_bug:
                    update_notion_status.invoke({"title": related_bug, "new_status": "Needs attention"})
                    update_jira_status.invoke({"summary": related_bug, "comment": f"PR Rejected: {comment} \nStatus -> Needs Attention"})

            elif decision == "APPROVED":
                # Notify Author (DM)
                if author_slack:
                    send_slack_dm.invoke({"channel": author_slack, "text": f"✅ Your PR #{pr_id} was Approved! Great work."})

                # Notify Team (Public)
                send_slack_dm.invoke({"channel": "#all-kaos", "text": f"✅ PR #{pr_id} Approved! Ready to merge."})
                
                # Update Notion & Jira
                if related_bug:
                    update_notion_status.invoke({"title": related_bug, "new_status": "To be deployed"})
                    update_jira_status.invoke({"summary": related_bug, "comment": "PR Approved. Ready for deployment.", "status": "Done"})

        # Logic for PR_MERGED
        elif event_type == "PR_MERGED":
             print("   🎉 PR Merged! Celebrating...")
             event_logger.log_event(
                event_type="PR_MERGED_LOG",
                actor="Agent-ReviewManager",
                repo=repo,
                pr_id=str(pr_id),
                details={"action": "celebrate"}
             )

if __name__ == "__main__":
    print("🚀 Starting Agent 2 (Review Manager) Listener...")
    consumer = ReviewManagerConsumer()
    consumer.run()
