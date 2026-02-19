import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.kafka.consumer_base import BaseAgentConsumer
from agents.review_manager.tools import find_reviewer, update_jira_status, update_notion_status, send_slack_dm, get_user_slack_id
from shared.logger import event_logger
import json

class ReviewManagerConsumer(BaseAgentConsumer):
    def __init__(self):
        # ... (init stays same) ...
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
            reviewer_info = "Not Assigned"
            try:
                # 1. Find Reviewer
                reviewer_info = find_reviewer.invoke({
                    "service_name": repo, 
                    "pr_author": author,
                    "pr_id": int(pr_id)
                })
                print(f"   👤 Suggested Reviewer: {reviewer_info}")
                
                # 2. Notify Reviewer via Slack (Mocking extracted ID)
                slack_id = "#all-kaos"
                if "Slack:" in reviewer_info:
                    slack_id = reviewer_info.split("Slack:")[1].split("|")[0].strip()
                
                send_slack_dm.invoke({
                    "channel": slack_id,
                    "text": f"👀 PR #{pr_id} in {repo} needs your review. Author: {author}\n🔗 Link: https://github.com/kaos-org/{repo}/pull/{pr_id}"
                })
                
                # Also notify #all-kaos for Demo visibility
                send_slack_dm.invoke({
                    "channel": "#all-kaos",
                    "text": f"📋 **PR Opened**: {author} opened PR #{pr_id} in {repo}. Reviewer: {reviewer_info.split('|')[0].replace('Reviewer:', '').strip()}"
                })
                
                # 3. Update Jira (if linked)
                related_bug_summary = message.get("title", "")
                update_notion_status.invoke({
                    "title": related_bug_summary if related_bug_summary else repo,
                    "new_status": "To be reviewed"
                })

                update_jira_status.invoke({
                    "summary": related_bug_summary if related_bug_summary else repo,
                    "comment": f"PR #{pr_id} opened by {author}. Reviewer assigned: {reviewer_info}",
                    "service_name": repo,
                    "status": "In Progress"
                })

            except Exception as e:
                print(f"   ⚠️ Reviewer Lookup/Notify Failed: {e}")

            # Log
            # Log
            event_logger.log_event(event_type="REVIEW_NEEDED", actor="Agent-ReviewManager", repo=repo, pr_id=str(pr_id), details={"status": "Scanning for Reviewers", "suggestion": reviewer_info, "pr_author": author})

        # Logic for REVIEW DECISIONS
        elif event_type == "REVIEW_SUBMITTED":
            decision = message.get("decision", "COMMENT")
            comment = message.get("comment", "")
            related_bug = message.get("related_bug_title", "")
            pr_author = message.get("pr_author") # New field
            actor = message.get("reviewer") or "Reviewer"
            
            print(f"   📝 Decision: {decision}")

            # Log the decision to DB (Critical for Chatbot history)
            event_logger.log_event(
                event_type="REVIEW_SUBMITTED",
                actor=actor, # Reviewer
                repo=repo,
                pr_id=str(pr_id),
                details={
                    "decision": decision, 
                    "comment": comment, 
                    "pr_author": pr_author,
                    "reviewer": actor
                }
            )
            
            # Find Author's Slack ID
            author_slack = get_user_slack_id.invoke({"name": pr_author}) 
            if not author_slack and reviewer_info and "Slack: " in reviewer_info:
                 # Backup: If find_reviewer returned it (unlikely for author, but safe check)
                 pass

            if decision == "CHANGES_REQUESTED":
                # Notify Author (DM)
                if author_slack:
                    send_slack_dm.invoke({
                        "channel": author_slack, 
                        "text": f"❌ PR #{pr_id} Rejected by {actor}. Please address comments: {comment}"
                    })
                    mention = f"<@{author_slack}>"
                else:
                    print(f"⚠️ Could not find Slack ID for author '{pr_author}'. DM not sent.")
                    mention = pr_author

                # Notify Team (Public)
                send_slack_dm.invoke({"channel": "#all-kaos", "text": f"❌ PR #{pr_id} Rejected. {mention} please fix: {comment}"})
                
                # Update Notion & Jira
                target_ticket = related_bug if related_bug else repo
                
                update_notion_status.invoke({"title": target_ticket, "new_status": "Needs attention"})
                update_jira_status.invoke({
                    "summary": target_ticket, 
                    "comment": f"PR Rejected: {comment} \nStatus -> Needs Attention",
                    "service_name": repo,
                    "status": "In Progress" # Ensure it stays In Progress or moves back if changed
                })

            elif decision == "APPROVED":
                # Notify Author (DM)
                if author_slack:
                    send_slack_dm.invoke({"channel": author_slack, "text": f"✅ Your PR #{pr_id} was Approved! Great work."})
                    
                    if author_slack.startswith("#"):
                         mention = author_slack
                    else:
                        mention = f"<@{author_slack}>"
                else:
                    mention = pr_author

                # Notify Team (Public)
                send_slack_dm.invoke({"channel": "#all-kaos", "text": f"✅ PR #{pr_id} Approved. {mention}, it's ready to merge."})
                
                # Update Notion & Jira
                target_ticket = related_bug if related_bug else repo

                # User requested: "The jira ticket will be moved to Done when the prod succeeds ,not when teh merge succeeds"
                # so REMOVE status='Done' here.
                # User requested: "Resolved will be after the prod succeeds"
                # so REMOVE new_status='Resolved' here.
                
                # We can update Notion to "To be deployed" or just leave it.
                # Let's leave it as is or set to "Approved" if that status existed, but user didn't ask for it.
                # User only specified "Deploying" for Merged.
                
                # update_notion_status.invoke({"title": target_ticket, "new_status": "Resolved"}) # REMOVED
                
                update_jira_status.invoke({
                    "summary": target_ticket, 
                    "comment": f"PR Approved by {actor}. Ready for Merge.",
                    "service_name": repo,
                    # "status": "Done" # REMOVED
                })

        # Logic for PR_MERGED
        elif event_type == "PR_MERGED":
             print("   🎉 PR Merged! Deploying...")
             event_logger.log_event(
                event_type="PR_MERGED_LOG",
                actor="Agent-ReviewManager",
                repo=repo,
                pr_id=str(pr_id),
                details={"action": "deploying"}
             )
             
             # User requested: "In notion , the status will be Deploying when pr merged"
             related_bug = message.get("title", "")
             target_ticket = related_bug if related_bug else repo

             update_notion_status.invoke({"title": target_ticket, "new_status": "Deploying"})
             
             update_jira_status.invoke({
                "summary": target_ticket,
                "comment": f"PR Merged. Deploying to Production...",
                "service_name": repo,
                "status": "In Progress" # Ensure it stays In Progress until Prod Success
             })

if __name__ == "__main__":
    print("🚀 Starting Agent 2 (Review Manager) Listener...")
    consumer = ReviewManagerConsumer()
    consumer.run()
